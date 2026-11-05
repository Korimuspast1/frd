package ai.opencode.android

import java.io.File

/**
 * Compact but genuine Python 3 subset interpreter used by the portable `python3` CLI shim.
 *
 * Supports indentation blocks, `def`/`return`, `if`/`elif`/`else`, `for`/`while` with
 * `break`/`continue`, f-strings, lists/dicts/tuples, slicing, string operators, `print`, `len`,
 * `range`, `sum`, `sorted`, `enumerate`, `zip`, `try/except/finally`, `raise`, classes, and the
 * `sys`, `os`, `json`, `math`, `time`, `random` modules.
 */
internal object Py {

    class PyExit(val code: Int) : RuntimeException("exit $code")

    class PyReturn(val value: Any?) : RuntimeException("return")

    class PyBreak : RuntimeException("break")

    class PyContinue : RuntimeException("continue")

    class PyError(message: String) : RuntimeException(message)

    class PyRaised(val value: Any?) : RuntimeException("raise")

    class PyRange(val items: List<Any?>)

    /** Deferred symbol reference (module attribute, builtin or user function name). */
    class PyAstRef(val name: String)

    class PyModule(val name: String)

    /** Quoted string literal produced by the tokenizer (never treated as a variable name). */
    class PyStr(val value: String)

    /** Bare identifier token produced by the tokenizer. */
    class PyName(val name: String)

    /** Prefixed string literal (f-string / raw string) produced by the tokenizer. */
    class PyFString(val content: String, val interpolate: Boolean)

    class PyFunction(
        val name: String,
        val params: List<String>,
        val body: List<Any>,
        val closure: MutableMap<String, Any?>,
    ) {
        fun call(args: List<Any?>, kargs: Map<String, Any?>, interp: Interpreter): Any? {
            val scope = HashMap<String, Any?>(closure)
            params.forEachIndexed { idx, raw ->
                val pname = raw.substringBefore('=').trim()
                val defaultExpr = if (raw.contains('=')) raw.substringAfter('=').trim() else ""
                val given = if (kargs.containsKey(pname)) kargs[pname] else args.getOrNull(idx)
                scope[pname] = if (given != null || kargs.containsKey(pname)) given
                else if (defaultExpr.isNotEmpty()) interp.eval(defaultExpr, scope)
                else null
            }
            try {
                interp.exec(body, scope)
            } catch (ret: PyReturn) {
                return ret.value
            }
            return null
        }
    }

    class PyClass(val name: String, val bases: List<String>, val methods: MutableMap<String, PyFunction>)

    class Instance(val klass: PyClass, val fields: MutableMap<String, Any?> = HashMap())

    fun runScript(script: String, args: List<String>): Int {
        val interp = Interpreter(args)
        return try {
            val program = Parser(script).parseProgram()
            interp.exec(program, interp.globals)
            0
        } catch (exit: PyExit) {
            exit.code
        } catch (err: Throwable) {
            System.err.println("Traceback (most recent call last):")
            System.err.println("  File \"<script>\", line 1, in <module>")
            System.err.println("${err.javaClass.simpleName}: ${err.message ?: ""}")
            1
        }
    }

    // ── Parser ──────────────────────────────────────────────────────────────────

    class Parser(script: String) {
        private class Line(val indent: Int, val text: String)

        private val lines = ArrayList<Line>()
        private var pos = 0

        init {
            for (raw in script.replace("\r\n", "\n").split("\n")) {
                if (raw.isBlank()) continue
                val trimmed = raw.trimStart()
                if (trimmed.startsWith("#")) continue
                lines.add(Line(raw.length - trimmed.length, stripComment(trimmed)))
            }
        }

        private fun stripComment(line: String): String {
            var inString = false
            var quote = ' '
            for (i in line.indices) {
                val ch = line[i]
                if (inString) {
                    if (ch == quote) inString = false
                    continue
                }
                when (ch) {
                    '"', '\'' -> {
                        inString = true
                        quote = ch
                    }

                    '#' -> if (i == 0 || line[i - 1] == ' ' || line[i - 1] == '\t') return line.substring(0, i).trimEnd()
                }
            }
            return line.trimEnd()
        }

        fun parseProgram(): List<Any> = parseBlock(-1)

        private fun parseBlock(parentIndent: Int): List<Any> {
            val block = ArrayList<Any>()
            while (pos < lines.size && lines[pos].indent > parentIndent) {
                val line = lines[pos]
                val text = line.text.trim()
                when {
                    text.isEmpty() -> pos++

                    text.startsWith("def ") -> {
                        pos++
                        val header = text.removePrefix("def ").trim()
                        val name = header.substringBefore('(').trim()
                        val close = header.lastIndexOf(')')
                        val paramsRaw = if (close > 0 && header.contains('(')) {
                            header.substring(header.indexOf('(') + 1, close)
                        } else ""
                        val params = pySplitTopLevel(paramsRaw, ',').filter { it.isNotEmpty() }
                        val body = parseBlock(line.indent)
                        block.add(PyFunction(name, params, body, HashMap()))
                    }

                    text.startsWith("class ") -> {
                        pos++
                        val header = text.removePrefix("class ").trim()
                        val name = header.substringBefore('(').substringBefore(':').trim()
                        val bases = header.substringAfter('(', "").substringBeforeLast(')', "")
                            .split(',').map { it.trim() }.filter { it.isNotEmpty() }
                        val body = parseBlock(line.indent)
                        val methods = LinkedHashMap<String, PyFunction>()
                        for (stmt in body) if (stmt is PyFunction) methods[stmt.name] = stmt
                        block.add(PyClass(name, bases, methods))
                    }

                    text.startsWith("try") && text.endsWith(":") -> {
                        pos++
                        val tryBody = parseBlock(line.indent)
                        var handlerVar: String? = null
                        var handlerBody: List<Any>? = null
                        var finallyBody: List<Any>? = null
                        while (pos < lines.size && (lines[pos].text.startsWith("except") ||
                                lines[pos].text.startsWith("finally") || lines[pos].text == "else:")
                        ) {
                            val header = lines[pos]
                            pos++
                            when {
                                header.text.startsWith("finally") -> finallyBody = parseBlock(header.indent)
                                header.text.startsWith("except") -> {
                                    val asMatch = Regex("\\bas\\s+([A-Za-z_][A-Za-z0-9_]*)").find(header.text)
                                    if (asMatch != null) handlerVar = asMatch.groupValues[1]
                                    handlerBody = parseBlock(header.indent)
                                }

                                else -> parseBlock(header.indent)
                            }
                        }
                        block.add(Triple("try", arrayListOf(tryBody, handlerVar, handlerBody, finallyBody), null))
                    }

                    text.startsWith("with ") && text.endsWith(":") -> {
                        pos++
                        val expr = text.removePrefix("with").removeSuffix(":").substringBefore(" as ").trim()
                        block.add(Triple("expr", arrayListOf(expr, parseBlock(line.indent)), null))
                    }

                    (text == "if" || text.startsWith("if ")) && text.endsWith(":") -> {
                        val branches = ArrayList<Pair<String?, List<Any>>>()
                        var cond: String? = text.removePrefix("if").removeSuffix(":").trim()
                        var done = false
                        while (!done) {
                            pos++
                            branches.add(cond to parseBlock(line.indent))
                            if (pos < lines.size && (lines[pos].text.startsWith("elif ") || lines[pos].text == "else:")) {
                                val branchLine = lines[pos]
                                if (branchLine.text.startsWith("elif ")) {
                                    cond = branchLine.text.removePrefix("elif").removeSuffix(":").trim()
                                    continue
                                }
                                pos++
                                branches.add(null to parseBlock(branchLine.indent))
                            }
                            done = true
                        }
                        block.add(Triple("if", arrayListOf<Any?>(branches), null))
                    }

                    text.startsWith("for ") && text.endsWith(":") -> {
                        pos++
                        val header = text.removePrefix("for ").removeSuffix(":").trim()
                        val target = header.substringBefore(" in ").trim()
                        val iterable = header.substringAfter(" in ").trim()
                        block.add(Triple("for", arrayListOf(target, iterable, parseBlock(line.indent)), null))
                    }

                    text.startsWith("while ") && text.endsWith(":") -> {
                        pos++
                        val cond = text.removePrefix("while").removeSuffix(":").trim()
                        block.add(Triple("while", arrayListOf(cond, parseBlock(line.indent)), null))
                    }

                    text == "pass" -> pos++

                    else -> {
                        pos++
                        block.add(text)
                    }
                }
            }
            return block
        }
    }

    // ── Interpreter ────────────────────────────────────────────────────────────

    class Interpreter(private val args: List<String>) {
        val globals = HashMap<String, Any?>()
        private var fileScope: MutableMap<String, Any?> = globals

        fun exec(block: List<Any>, scope: MutableMap<String, Any?>) {
            for (stmt in block) {
                when (stmt) {
                    is String -> execStatement(stmt, scope)
                    is PyFunction -> scope[stmt.name] = PyFunction(stmt.name, stmt.params, stmt.body, HashMap(scope))
                    is PyClass -> scope[stmt.name] = stmt
                    is Triple<*, *, *> -> execCompound(stmt, scope)
                }
            }
        }

        @Suppress("UNCHECKED_CAST")
        fun execCompound(stmt: Triple<*, *, *>, scope: MutableMap<String, Any?>) {
            when (stmt.first as String) {
                "for" -> {
                    val payload = stmt.second as List<Any?>
                    val target = payload[0] as String
                    val items = asList(eval(payload[1] as String, scope))
                    for (item in items) {
                        assignTarget(target, item, scope)
                        try {
                            exec(payload[2] as List<Any>, scope)
                        } catch (_: PyContinue) {
                            continue
                        } catch (_: PyBreak) {
                            break
                        }
                    }
                }

                "while" -> {
                    val payload = stmt.second as List<Any?>
                    var guard = 0
                    while (truthy(eval(payload[0] as String, scope))) {
                        if (++guard > 2_000_000) throw PyError("while loop exceeded 2,000,000 iterations")
                        try {
                            exec(payload[1] as List<Any>, scope)
                        } catch (_: PyContinue) {
                            continue
                        } catch (_: PyBreak) {
                            break
                        }
                    }
                }

                "if" -> {
                    val payload = stmt.second as List<Any?>
                    val branches = payload[0] as List<Pair<String?, List<Any>>>
                    for ((cond, body) in branches) {
                        if (cond == null || truthy(eval(cond, scope))) {
                            exec(body, scope)
                            return
                        }
                    }
                }

                "try" -> {
                    val payload = stmt.second as List<Any?>
                    val tryBody = payload[0] as List<Any>
                    val handlerVar = payload[1] as String?
                    val handlerBody = payload[2] as List<Any>?
                    val finallyBody = payload[3] as List<Any>?
                    try {
                        try {
                            exec(tryBody, scope)
                        } catch (e: PyRaised) {
                            val h = handlerBody ?: throw e
                            if (handlerVar != null) scope[handlerVar] = e.value
                            exec(h, scope)
                        } catch (e: PyError) {
                            val h = handlerBody ?: throw e
                            if (handlerVar != null) scope[handlerVar] = e.message
                            exec(h, scope)
                        } catch (e: ArithmeticException) {
                            val h = handlerBody ?: throw e
                            if (handlerVar != null) scope[handlerVar] = e.message ?: "arithmetic error"
                            exec(h, scope)
                        } catch (e: java.io.IOException) {
                            val h = handlerBody ?: throw e
                            if (handlerVar != null) scope[handlerVar] = e.message ?: "io error"
                            exec(h, scope)
                        }
                    } finally {
                        if (finallyBody != null) exec(finallyBody, scope)
                    }
                }

                "expr" -> {
                    val payload = stmt.second as List<Any?>
                    eval(payload[0] as String, scope)
                    exec(payload[1] as List<Any>, scope)
                }
            }
        }

        fun execStatement(statement: String, scope: MutableMap<String, Any?>) {
            val stmt = statement.trim()
            if (stmt.isEmpty()) return
            when {
                stmt == "break" -> throw PyBreak()
                stmt == "continue" -> throw PyContinue()
                stmt == "pass" -> return
                stmt.startsWith("return") -> {
                    val expr = stmt.removePrefix("return").trim()
                    throw PyReturn(if (expr.isEmpty()) null else eval(expr, scope))
                }

                stmt.startsWith("raise") -> {
                    val expr = stmt.removePrefix("raise").trim()
                    throw PyRaised(if (expr.isEmpty()) null else eval(expr, scope))
                }

                stmt.startsWith("global ") || stmt == "global" -> return
                stmt.startsWith("nonlocal ") -> return
                stmt.startsWith("assert ") -> {
                    val expr = stmt.removePrefix("assert ").trim().substringBefore(", ")
                    if (!truthy(eval(expr, scope))) throw PyError("AssertionError: $expr")
                    return
                }

                stmt.startsWith("del ") -> {
                    scope.remove(stmt.removePrefix("del ").trim().substringBefore('['))
                    return
                }

                stmt.startsWith("import ") -> {
                    for (name in stmt.removePrefix("import ").split(',')) {
                        val module = name.trim().substringBefore(" as ").trim()
                        val alias = if (name.contains(" as ")) name.substringAfter(" as ").trim() else module
                        scope[alias] = moduleFor(module)
                    }
                    return
                }

                stmt.startsWith("from ") -> {
                    val module = stmt.removePrefix("from ").substringBefore(" import").trim()
                    val imported = stmt.substringAfter(" import").trim()
                    for (name in imported.split(',')) {
                        val symbol = name.trim().substringBefore(" as ").trim()
                        val alias = if (name.contains(" as ")) name.substringAfter(" as ").trim() else symbol
                        scope[alias] = Py.PyAstRef("$module.$symbol")
                    }
                    return
                }
            }

            val augmented = Regex("^([A-Za-z_][A-Za-z0-9_.\\[\\]'\" ]*?)\\s*(\\+=|-=|\\*=|/=|%=)\\s*(.+)$").find(stmt)
            if (augmented != null) {
                val target = augmented.groupValues[1].trim()
                val op = augmented.groupValues[2].first().toString()
                val rhs = eval(augmented.groupValues[3], scope)
                assignTarget(target, binaryOp(op, lookup(target, scope), rhs), scope)
                return
            }

            val eq = pyFindAssignment(stmt)
            if (eq > 0) {
                val target = stmt.substring(0, eq).trim()
                val value = eval(stmt.substring(eq + 1).trim(), scope)
                assignTarget(target, value, scope)
                return
            }

            eval(stmt, scope)
        }

        fun assignTarget(target: String, value: Any?, scope: MutableMap<String, Any?>) {
            val t = target.trim()
            if (t.startsWith("self.")) {
                val self = scope["self"] ?: return
                if (self is Instance) self.fields[t.removePrefix("self.")] = value
                return
            }
            if (t.contains('.') && !t.startsWith("[")) {
                val objName = t.substringBefore('.')
                val field = t.substringAfter('.')
                val obj = scope[objName]
                if (obj is Instance) obj.fields[field] = value
                return
            }
            if (t.contains("[")) {
                val baseName = t.substringBefore('[')
                val indexExpr = t.substringAfter('[').substringBeforeLast(']')
                val container = scope[baseName]
                val key = eval(indexExpr, scope)
                when (container) {
                    is ArrayList<*> -> {
                        @Suppress("UNCHECKED_CAST")
                        val list = container as ArrayList<Any?>
                        val idx = num(key).toInt()
                        if (idx in list.indices) list[idx] = value
                    }

                    is LinkedHashMap<*, *> -> {
                        @Suppress("UNCHECKED_CAST")
                        val map = container as LinkedHashMap<String, Any?>
                        map[str(key)] = value
                    }
                }
                return
            }
            val names = pySplitTopLevel(t, ',')
            if (names.size > 1 && value is List<*>) {
                names.forEachIndexed { idx, name -> scope[name.trim()] = value.getOrNull(idx) }
                return
            }
            scope[t] = value
        }

        private fun lookup(target: String, scope: MutableMap<String, Any?>): Any? =
            if (target.contains('[')) eval(target, scope) else resolveName(target, scope)

        fun moduleFor(name: String): Any = when (name) {
            "sys" -> SysModule()
            "os" -> OsModule()
            "json" -> JsonModule()
            "math" -> MathModule()
            "time" -> TimeModule()
            "random" -> RandomModule()
            else -> PyModule(name)
        }

        fun resolveName(name: String, scope: MutableMap<String, Any?>): Any? {
            if (scope.containsKey(name)) return scope[name]
            if (globals.containsKey(name)) return globals[name]
            return when (name) {
                "True" -> true
                "False" -> false
                "None" -> null
                "__name__" -> "__main__"
                else -> Py.PyAstRef(name)
            }
        }

        // ── expressions ─────────────────────────────────────────────────────────

        fun eval(rawExpr: String, scope: MutableMap<String, Any?>): Any? {
            var expr = rawExpr.trim()
            if (expr.isEmpty()) return null
            expr = stripOuterParens(expr)
            val fstringMatch = Regex("^([fFrRbB])(\"\"\"|'''|\"|')([\\s\\S]*)\\2$").find(rawExpr.trim())
            if (fstringMatch != null) {
                return if (fstringMatch.groupValues[1].lowercase() == "f") {
                    interpolate(fstringMatch.groupValues[3], scope)
                } else {
                    unescape(fstringMatch.groupValues[3])
                }
            }
            return try {
                val tokens = tokenize(expr) ?: return simpleValue(expr, scope)
                ExprParser(tokens, this, scope).parse()
            } catch (e: PyRaised) {
                throw e
            } catch (e: PyError) {
                throw e
            } catch (_: Throwable) {
                simpleValue(expr, scope)
            }
        }

        private fun stripOuterParens(input: String): String {
            var s = input
            while (s.length > 1 && s.startsWith("(") && s.endsWith(")") && matchingClose(s, 0) == s.length - 1) {
                s = s.substring(1, s.length - 1).trim()
            }
            return s
        }

        private fun matchingClose(s: String, openIndex: Int): Int {
            var depth = 0
            var inString = false
            var quote = ' '
            for (i in openIndex until s.length) {
                val ch = s[i]
                if (inString) {
                    if (ch == quote) inString = false
                    continue
                }
                when (ch) {
                    '"', '\'' -> {
                        inString = true
                        quote = ch
                    }

                    '(', '[', '{' -> depth++
                    ')', ']', '}' -> {
                        depth--
                        if (depth == 0) return i
                    }
                }
            }
            return -1
        }

        private fun simpleValue(expr: String, scope: MutableMap<String, Any?>): Any? = when {
            scope.containsKey(expr) -> scope[expr]
            expr.startsWith("\"") && expr.endsWith("\"") && expr.length >= 2 -> unescape(expr.substring(1, expr.length - 1))
            expr.startsWith("'") && expr.endsWith("'") && expr.length >= 2 -> unescape(expr.substring(1, expr.length - 1))
            expr == "True" -> true
            expr == "False" -> false
            expr == "None" -> null
            expr.toDoubleOrNull() != null -> expr.toDouble()
            else -> Py.PyAstRef(expr)
        }

        private fun unescape(raw: String): String = raw
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\r", "\r")
            .replace("\\\"", "\"")
            .replace("\\'", "'")
            .replace("\\\\", "\\")

        fun interpolate(template: String, scope: MutableMap<String, Any?>): String {
            val sb = StringBuilder()
            var i = 0
            while (i < template.length) {
                val ch = template[i]
                if (ch == '{' && i + 1 < template.length && template[i + 1] == '{') {
                    sb.append('{')
                    i += 2
                    continue
                }
                if (ch == '}' && i + 1 < template.length && template[i + 1] == '}') {
                    sb.append('}')
                    i += 2
                    continue
                }
                if (ch == '{') {
                    var depth = 1
                    var j = i + 1
                    while (j < template.length && depth > 0) {
                        if (template[j] == '{') depth++
                        if (template[j] == '}') depth--
                        j++
                    }
                    val inner = template.substring(i + 1, (j - 1).coerceAtLeast(i + 1)).trim()
                    val valueExpr = inner.substringBefore(':')
                    val spec = if (inner.contains(':')) inner.substringAfter(':') else ""
                    sb.append(formatValue(eval(valueExpr, scope), spec))
                    i = j
                    continue
                }
                sb.append(ch)
                i++
            }
            return unescape(sb.toString())
        }

        private fun formatValue(value: Any?, spec: String): String {
            if (spec.isEmpty()) return str(value)
            val precision = Regex("\\.(\\d+)f`?").find(spec)?.groupValues?.get(1)?.toIntOrNull()
            return when {
                spec.endsWith("f") -> {
                    val d = num(value)
                    if (precision != null) String.format("%.${precision}f", d) else d.toString()
                }

                spec.endsWith("d") -> num(value).toLong().toString()
                spec.endsWith("s") -> str(value)
                else -> str(value)
            }
        }

        private fun tokenize(input: String): List<Any>? {
            val tokens = ArrayList<Any>()
            var i = 0
            while (i < input.length) {
                val ch = input[i]
                when {
                    ch.isWhitespace() -> i++
                    ch.isDigit() -> {
                        var j = i
                        while (j < input.length && (input[j].isDigit() || input[j] == '.')) j++
                        tokens.add(input.substring(i, j).toDoubleOrNull() ?: 0.0)
                        i = j
                    }

                    ch == '"' || ch == '\'' -> {
                        var j = i + 1
                        val sb = StringBuilder()
                        while (j < input.length && input[j] != ch) {
                            if (input[j] == '\\' && j + 1 < input.length) {
                                j++
                                sb.append(
                                    when (input[j]) {
                                        'n' -> '\n'
                                        't' -> '\t'
                                        'r' -> '\r'
                                        else -> input[j]
                                    }
                                )
                            } else {
                                sb.append(input[j])
                            }
                            j++
                        }
                        if (j >= input.length) return null
                        tokens.add(PyStr(sb.toString()))
                        i = j + 1
                    }

                    (ch == 'f' || ch == 'F' || ch == 'r' || ch == 'R') &&
                        i + 1 < input.length && (input[i + 1] == '"' || input[i + 1] == '\'') -> {
                        val quote = input[i + 1]
                        var j = i + 2
                        val sb = StringBuilder()
                        while (j < input.length && input[j] != quote) {
                            if (input[j] == '\\' && j + 1 < input.length && ch != 'r' && ch != 'R') {
                                j++
                                when (input[j]) {
                                    'n' -> sb.append('\n')
                                    't' -> sb.append('\t')
                                    'r' -> sb.append('\r')
                                    else -> sb.append(input[j])
                                }
                            } else {
                                sb.append(input[j])
                            }
                            j++
                        }
                        if (j >= input.length) return null
                        tokens.add(PyFString(sb.toString(), ch == 'f' || ch == 'F'))
                        i = j + 1
                    }

                    ch.isLetter() || ch == '_' -> {
                        var j = i
                        while (j < input.length && (input[j].isLetterOrDigit() || input[j] == '_' || input[j] == '.')) j++
                        tokens.add(PyName(input.substring(i, j)))
                        i = j
                    }

                    else -> {
                        val two = if (i + 1 < input.length) input.substring(i, i + 2) else ""
                        when (two) {
                            "//", "**", "==", "!=", "<=", ">=" -> {
                                tokens.add(two)
                                i += 2
                            }

                            else -> {
                                tokens.add(ch.toString())
                                i++
                            }
                        }
                    }
                }
            }
            return tokens
        }

        inner class ExprParser(
            private val tokens: List<Any>,
            private val interp: Interpreter,
            private val scope: MutableMap<String, Any?>,
        ) {
            private var pos = 0

            private fun peek(): Any? = tokens.getOrNull(pos)

            private fun next(): Any? = tokens.getOrNull(pos++)

            private fun opText(token: Any?): String? = when (token) {
                is String -> token
                is PyName -> token.name
                else -> null
            }

            private fun opIs(token: Any?, name: String): Boolean = opText(token) == name

            fun parse(): Any? = orExpr()

            private fun orExpr(): Any? {
                var left = andExpr()
                while (opIs(peek(), "or")) {
                    next()
                    val right = andExpr()
                    left = truthy(left) || truthy(right)
                }
                return left
            }

            private fun andExpr(): Any? {
                var left = notExpr()
                while (opIs(peek(), "and")) {
                    next()
                    val right = notExpr()
                    left = truthy(left) && truthy(right)
                }
                return left
            }

            private fun notExpr(): Any? {
                if (opIs(peek(), "not")) {
                    next()
                    return !truthy(notExpr())
                }
                return comparison()
            }

            private fun comparison(): Any? {
                var left = additive()
                while (true) {
                    val op = opText(peek()) ?: break
                    if (op != "==" && op != "!=" && op != "<" && op != ">" && op != "<=" && op != ">=" && op != "in") break
                    next()
                    val right = additive()
                    left = when (op) {
                        "==" -> equals(left, right)
                        "!=" -> !equals(left, right)
                        "<" -> num(left) < num(right)
                        ">" -> num(left) > num(right)
                        "<=" -> num(left) <= num(right)
                        ">=" -> num(left) >= num(right)
                        else -> asList(right).contains(left) || (right is String && str(left) in right)
                    }
                }
                return left
            }

            private fun additive(): Any? {
                var left = multiplicative()
                while (peek() == "+" || peek() == "-") {
                    val op = next() as String
                    left = binaryOp(op, left, multiplicative())
                }
                return left
            }

            private fun multiplicative(): Any? {
                var left = unary()
                while (peek() == "*" || peek() == "/" || peek() == "%" || peek() == "//") {
                    val op = next() as String
                    left = binaryOp(op, left, unary())
                }
                return left
            }

            private fun unary(): Any? {
                if (peek() == "-") {
                    next()
                    return -num(unary())
                }
                if (peek() == "+") {
                    next()
                    return unary()
                }
                return power()
            }

            private fun power(): Any? {
                var base = postfix()
                if (peek() == "**") {
                    next()
                    base = Math.pow(num(base), num(unary()))
                }
                return base
            }

            private fun postfix(): Any? {
                var value = primary()
                while (true) {
                    when (peek()) {
                        "(" -> {
                            next()
                            val positional = ArrayList<Any?>()
                            val keyword = LinkedHashMap<String, Any?>()
                            if (peek() != ")") {
                                while (true) {
                                    val save = pos
                                    val token = peek()
                                    if (token is PyName && pos + 1 < tokens.size && tokens[pos + 1] == "=") {
                                        next()
                                        next()
                                        keyword[token.name] = parse()
                                    } else {
                                        pos = save
                                        positional.add(parse())
                                    }
                                    if (peek() == ",") {
                                        next()
                                        continue
                                    }
                                    break
                                }
                            }
                            if (peek() == ")") next()
                            value = call(value, positional, keyword)
                        }

                        "[" -> {
                            next()
                            val from: Any? = if (peek() == ":") null else parse()
                            var to: Any? = null
                            var isSlice = false
                            if (peek() == ":") {
                                isSlice = true
                                next()
                                if (peek() != "]") to = parse()
                            }
                            if (peek() == "]") next()
                            value = if (isSlice) sliceValue(value, from, to) else indexValue(value, from)
                        }

                        "." -> {
                            next()
                            val member = when (val m = next()) {
                                is PyName -> m.name
                                is PyStr -> m.value
                                else -> break
                            }
                            if (peek() == "(") {
                                next()
                                val args = ArrayList<Any?>()
                                val kargs = LinkedHashMap<String, Any?>()
                                if (peek() != ")") {
                                    while (true) {
                                        args.add(parse())
                                        if (peek() == ",") {
                                            next()
                                            continue
                                        }
                                        break
                                    }
                                }
                                if (peek() == ")") next()
                                value = callMethod(value, member, args, kargs)
                            } else {
                                value = memberValue(value, member)
                            }
                        }

                        else -> return value
                    }
                }
                return value
            }

            private fun primary(): Any? {
                val token = next()
                return when (token) {
                    "(" -> {
                        val value = parse()
                        // tuple support: (a, b)
                        if (peek() == ",") {
                            val items = ArrayList<Any?>()
                            items.add(value)
                            while (peek() == ",") {
                                next()
                                if (peek() == ")") break
                                items.add(parse())
                            }
                            if (peek() == ")") next()
                            items
                        } else {
                            if (peek() == ")") next()
                            value
                        }
                    }

                    "[" -> {
                        val list = ArrayList<Any?>()
                        if (peek() != "]") {
                            while (true) {
                                list.add(parse())
                                if (peek() == ",") {
                                    next()
                                    if (peek() == "]") break
                                    continue
                                }
                                break
                            }
                        }
                        if (peek() == "]") next()
                        list
                    }

                    "{" -> {
                        val map = LinkedHashMap<String, Any?>()
                        if (peek() != "}") {
                            while (true) {
                                val key = parse()
                                if (peek() == ":") next()
                                map[str(key)] = parse()
                                if (peek() == ",") {
                                    next()
                                    if (peek() == "}") break
                                    continue
                                }
                                break
                            }
                        }
                        if (peek() == "}") next()
                        map
                    }

                    is PyFString -> if (token.interpolate) interpolate(token.content, scope) else token.content
                    is PyStr -> token.value
                    is PyName -> resolveName(token.name, scope)
                    is Double -> token

                    else -> token
                }
            }

            private fun call(target: Any?, args: List<Any?>, kargs: Map<String, Any?>): Any? = when (target) {
                is PyFunction -> target.call(args, kargs, interp)
                is PyClass -> {
                    val instance = Instance(target)
                    val init = target.methods["__init__"]
                    if (init != null) init.call(listOf<Any?>(instance) + args, kargs, interp)
                    instance
                }

                is Py.PyAstRef -> builtin(target.name, args, kargs)
                is Instance -> {
                    val method = target.klass.methods[target.klass.name]
                    method?.call(listOf<Any?>(target) + args, kargs, interp)
                }

                else -> target
            }

            private fun memberValue(target: Any?, member: String): Any? = when (target) {
                is Map<*, *> -> target[member]
                is Instance -> target.fields[member] ?: PyAstRef("$member()")
                is PyModule -> PyAstRef("${target.name}.$member")
                is SysModule -> when (member) {
                    "argv" -> args
                    "platform" -> "android"
                    "version" -> "3.11.9"
                    else -> PyAstRef("sys.$member")
                }

                is OsModule -> when (member) {
                    "sep" -> "/"
                    "linesep" -> "\n"
                    else -> PyAstRef("os.$member")
                }

                is MathModule -> when (member) {
                    "pi" -> Math.PI
                    "e" -> Math.E
                    "inf" -> Double.POSITIVE_INFINITY
                    else -> PyAstRef("math.$member")
                }

                else -> PyAstRef(member)
            }

            private fun callMethod(target: Any?, member: String, a: List<Any?>, k: Map<String, Any?>): Any? {
                if (target is Instance) {
                    val method = target.klass.methods[member]
                    if (method != null) return method.call(listOf<Any?>(target) + a, k, interp)
                    return target.fields[member]
                }
                if (target is SysModule || target is OsModule || target is MathModule ||
                    target is JsonModule || target is TimeModule || target is RandomModule
                ) {
                    val name = when (target) {
                        is SysModule -> "sys.$member"
                        is OsModule -> "os.$member"
                        is MathModule -> "math.$member"
                        is JsonModule -> "json.$member"
                        is TimeModule -> "time.$member"
                        else -> "random.$member"
                    }
                    return builtin(name, a, k)
                }
                val text = if (target is String) target else null
                return when (member) {
                    "upper" -> str(text ?: target).uppercase()
                    "lower" -> str(text ?: target).lowercase()
                    "title" -> str(text ?: target).split(" ").joinToString(" ") { s ->
                        s.replaceFirstChar { c -> c.uppercase() }
                    }

                    "capitalize" -> str(text ?: target).replaceFirstChar { it.uppercase() }
                    "strip" -> str(text ?: target).trim()
                    "lstrip" -> str(text ?: target).trimStart()
                    "rstrip" -> str(text ?: target).trimEnd()
                    "split" -> {
                        val sep = a.firstOrNull()?.let { str(it) }
                        if (sep.isNullOrEmpty()) str(text ?: target).trim().split(Regex("\\s+"))
                        else str(text ?: target).split(sep)
                    }

                    "rsplit" -> {
                        val sep = a.firstOrNull()?.let { str(it) } ?: " "
                        str(text ?: target).split(sep).reversed()
                    }

                    "join" -> asList(a.firstOrNull()).joinToString(str(target)) { str(it) }
                    "replace" -> str(text ?: target).replace(str(a.getOrNull(0)), str(a.getOrNull(1)))
                    "startswith" -> str(text ?: target).startsWith(str(a.firstOrNull()))
                    "endswith" -> str(text ?: target).endsWith(str(a.firstOrNull()))
                    "find", "index" -> str(text ?: target).indexOf(str(a.firstOrNull())).toDouble()
                    "count" -> {
                        val needle = str(a.firstOrNull())
                        if (text != null) {
                            text.split(needle).size - 1.0
                        } else {
                            asList(target).count { it == a.firstOrNull() }.toDouble()
                        }
                    }

                    "format" -> {
                        var result = str(text ?: target)
                        a.forEachIndexed { idx, value ->
                            result = result.replaceFirst("{${idx}}", str(value)).replaceFirst("{}", str(value))
                        }
                        result
                    }

                    "append" -> {
                        (target as? MutableList<Any?>)?.add(a.firstOrNull())
                        null
                    }

                    "extend" -> {
                        (target as? MutableList<Any?>)?.addAll(asList(a.firstOrNull()))
                        null
                    }

                    "insert" -> {
                        (target as? MutableList<Any?>)?.add(num(a.firstOrNull()).toInt().coerceIn(0, target.size), a.getOrNull(1))
                        null
                    }

                    "pop" -> {
                        val list = target as? MutableList<Any?>
                        val index = (a.firstOrNull() as? Double)?.toInt() ?: (list?.size ?: 1) - 1
                        if (list != null && index in list.indices) list.removeAt(index) else null
                    }

                    "remove" -> {
                        (target as? MutableList<Any?>)?.remove(a.firstOrNull())
                        null
                    }

                    "sort" -> {
                        val list = target as? MutableList<Any?>
                        if (list != null) {
                            val sorted = list.sortedBy { str(it) }
                            list.clear()
                            list.addAll(sorted)
                        }
                        null
                    }

                    "reverse" -> {
                        val list = target as? MutableList<Any?>
                        if (list != null) {
                            val reversed = list.reversed()
                            list.clear()
                            list.addAll(reversed)
                        }
                        null
                    }

                    "keys" -> (target as? Map<*, *>)?.keys?.toList() ?: emptyList<String>()
                    "values" -> (target as? Map<*, *>)?.values?.toList() ?: emptyList<Any?>()
                    "items" -> (target as? Map<*, *>)?.entries?.map { listOf(it.key, it.value) } ?: emptyList<Any?>()
                    "get" -> (target as? Map<*, *>)?.get(str(a.firstOrNull())) ?: a.getOrNull(1)
                    "copy" -> (target as? Map<*, *>)?.toMap() ?: target
                    "update" -> {
                        val source = a.firstOrNull()
                        @Suppress("UNCHECKED_CAST")
                        val map = target as? LinkedHashMap<String, Any?>
                        if (map != null && source is Map<*, *>) {
                            for ((key, value) in source) map[str(key)] = value
                        }
                        null
                    }

                    "setdefault" -> {
                        @Suppress("UNCHECKED_CAST")
                        val map = target as? MutableMap<String, Any?>
                        if (map != null) {
                            val key = str(a.firstOrNull())
                            if (map.containsKey(key)) map[key] else {
                                map[key] = a.getOrNull(1)
                                a.getOrNull(1)
                            }
                        } else null
                    }
                    "read" -> File(str(target)).readText()
                    "readlines" -> File(str(target)).readLines()
                    "readline" -> File(str(target)).readLines().firstOrNull() ?: ""
                    "write" -> {
                        val text = str(a.firstOrNull())
                        File(str(target)).appendText(text)
                        text.length.toDouble()
                    }

                    "close" -> null
                    "isupper" -> str(target).uppercase() == str(target)
                    "islower" -> str(target).lowercase() == str(target)
                    "isdigit" -> str(target).isNotEmpty() && str(target).all { it.isDigit() }
                    "isalpha" -> str(target).isNotEmpty() && str(target).all { it.isLetter() }
                    "isspace" -> str(target).isNotEmpty() && str(target).all { it.isWhitespace() }
                    "zfill" -> str(target).padStart(num(a.firstOrNull()).toInt(), '0')
                    "ljust" -> str(target).padEnd(num(a.firstOrNull()).toInt())
                    "rjust" -> str(target).padStart(num(a.firstOrNull()).toInt())
                    "center" -> str(target).padStart(num(a.firstOrNull()).toInt() / 2)
                    else -> throw PyError("AttributeError: object has no attribute '$member'")
                }
            }

            private fun indexValue(target: Any?, key: Any?): Any? = when (target) {
                is Map<*, *> -> target[str(key)]
                is String -> {
                    val idx = num(key).toInt()
                    val resolved = if (idx < 0) target.length + idx else idx
                    if (resolved in target.indices) target[resolved].toString() else throw PyError("IndexError: string index out of range")
                }

                is List<*> -> {
                    val idx = num(key).toInt()
                    val resolved = if (idx < 0) target.size + idx else idx
                    if (resolved in target.indices) target[resolved] else throw PyError("IndexError: list index out of range")
                }

                is PyRange -> indexValue(target.items, key)
                else -> null
            }

            private fun sliceValue(target: Any?, from: Any?, to: Any?): Any? {
                val list = asList(target)
                val startRaw = from?.let { num(it).toInt() }
                val endRaw = to?.let { num(it).toInt() }
                val start = when {
                    startRaw == null -> 0
                    startRaw < 0 -> (list.size + startRaw).coerceAtLeast(0)
                    else -> startRaw.coerceAtMost(list.size)
                }
                val end = when {
                    endRaw == null -> list.size
                    endRaw < 0 -> (list.size + endRaw).coerceAtLeast(0)
                    else -> endRaw.coerceAtMost(list.size)
                }
                if (start >= end) return if (target is String) "" else emptyList<Any?>()
                val sub = list.subList(start, end)
                return if (target is String) sub.joinToString("") { str(it) } else sub.toList()
            }

            private fun builtin(name: String, a: List<Any?>, k: Map<String, Any?>): Any? {
                val resolvedName = if (name.startsWith("sys.") || name.startsWith("os.") || name.startsWith("json.") ||
                    name.startsWith("math.") || name.startsWith("time.") || name.startsWith("random.")
                ) name else name
                return when (resolvedName) {
                    "print" -> {
                        val sep = k["sep"]?.let { str(it) } ?: " "
                        val end = k["end"]?.let { str(it) } ?: "\n"
                        System.out.print(a.joinToString(sep) { str(it) } + end)
                        System.out.flush()
                        null
                    }

                    "len" -> when (val v = a.firstOrNull()) {
                        is String -> v.length.toDouble()
                        is List<*> -> v.size.toDouble()
                        is Map<*, *> -> v.size.toDouble()
                        is PyRange -> v.items.size.toDouble()
                        else -> 0.0
                    }

                    "str" -> str(a.firstOrNull())
                    "repr" -> repr(a.firstOrNull())
                    "bool" -> truthy(a.firstOrNull())
                    "int" -> when (val v = a.firstOrNull()) {
                        is Double -> Math.floor(v)
                        is String -> v.trim().toDoubleOrNull()?.let { Math.floor(it) }
                            ?: throw PyError("ValueError: invalid literal for int(): '$v'")
                        is Boolean -> if (v) 1.0 else 0.0
                        else -> 0.0
                    }

                    "float" -> num(a.firstOrNull())
                    "abs" -> Math.abs(num(a.firstOrNull()))
                    "round" -> {
                        val digits = num(a.getOrNull(1)).toInt()
                        val factor = Math.pow(10.0, digits.toDouble())
                        Math.round(num(a.firstOrNull()) * factor) / factor
                    }

                    "range" -> {
                        val nums = a.map { num(it).toInt() }
                        val start: Int
                        val end: Int
                        val step: Int
                        when (nums.size) {
                            0 -> {
                                start = 0; end = 0; step = 1
                            }

                            1 -> {
                                start = 0; end = nums[0]; step = 1
                            }

                            2 -> {
                                start = nums[0]; end = nums[1]; step = 1
                            }

                            else -> {
                                start = nums[0]; end = nums[1]; step = if (nums[2] == 0) 1 else nums[2]
                            }
                        }
                        val items = ArrayList<Any?>()
                        var i = start
                        if (step > 0) {
                            while (i < end) {
                                items.add(i.toDouble()); i += step
                            }
                        } else {
                            while (i > end) {
                                items.add(i.toDouble()); i += step
                            }
                        }
                        PyRange(items)
                    }

                    "sum" -> a.firstOrNull()?.let { asList(it).sumOf { v -> num(v) } } ?: 0.0
                    "min" -> if (a.size > 1) a.minByOrNull { num(it) } else asList(a.firstOrNull()).minByOrNull { num(it) }
                    "max" -> if (a.size > 1) a.maxByOrNull { num(it) } else asList(a.firstOrNull()).maxByOrNull { num(it) }
                    "sorted" -> asList(a.firstOrNull()).sortedBy { str(it) }
                    "reversed" -> asList(a.firstOrNull()).reversed()
                    "list" -> ArrayList(asList(a.firstOrNull()))
                    "tuple" -> asList(a.firstOrNull())
                    "set" -> asList(a.firstOrNull()).distinct()
                    "dict" -> {
                        val map = LinkedHashMap<String, Any?>()
                        val src = a.firstOrNull()
                        if (src is Map<*, *>) for ((key, value) in src) map[str(key)] = value
                        map
                    }

                    "enumerate" -> asList(a.firstOrNull()).mapIndexed { idx, value -> listOf(idx.toDouble(), value) }
                    "zip" -> {
                        val lists = a.map { asList(it) }
                        val size = lists.minOfOrNull { it.size } ?: 0
                        (0 until size).map { idx -> lists.map { it[idx] } }
                    }

                    "any" -> asList(a.firstOrNull()).any { truthy(it) }
                    "all" -> asList(a.firstOrNull()).all { truthy(it) }
                    "isinstance" -> {
                        val value = a.firstOrNull()
                        when (str(a.getOrNull(1))) {
                            "str" -> value is String
                            "int" -> value is Double && value == Math.floor(value)
                            "float" -> value is Double
                            "bool" -> value is Boolean
                            "list" -> value is List<*>
                            "dict" -> value is Map<*, *>
                            else -> false
                        }
                    }

                    "type" -> PyAstRef(
                        when (a.firstOrNull()) {
                            is String -> "str"
                            is Double -> "float"
                            is Boolean -> "bool"
                            is List<*> -> "list"
                            is Map<*, *> -> "dict"
                            null -> "NoneType"
                            else -> "object"
                        }
                    )

                    "input" -> readLine() ?: ""
                    "open" -> str(a.firstOrNull())
                    "exit" -> throw PyExit(num(a.firstOrNull()).toInt())
                    "sys.exit" -> throw PyExit(num(a.firstOrNull()).toInt())
                    "sys.getrecursionlimit" -> 1000.0
                    "sys.path" -> emptyList<String>()
                    "os.getcwd" -> File(System.getProperty("user.dir") ?: "/").absolutePath
                    "os.chdir" -> {
                        null
                    }

                    "os.listdir" -> {
                        val dir = a.firstOrNull()?.let { str(it) } ?: (System.getProperty("user.dir") ?: "/")
                        File(dir).list()?.toList() ?: emptyList<String>()
                    }

                    "os.mkdir", "os.makedirs" -> {
                        a.firstOrNull()?.let { File(str(it)).mkdirs() }
                        null
                    }

                    "os.remove", "os.unlink", "os.rmdir" -> {
                        a.firstOrNull()?.let { File(str(it)).delete() }
                        null
                    }

                    "os.rename" -> {
                        File(str(a.firstOrNull())).renameTo(File(str(a.getOrNull(1))))
                        null
                    }

                    "os.path.join" -> a.joinToString("/") { str(it) }
                    "os.path.exists" -> File(str(a.firstOrNull())).exists()
                    "os.path.isdir" -> File(str(a.firstOrNull())).isDirectory
                    "os.path.isfile" -> File(str(a.firstOrNull())).isFile
                    "os.path.basename" -> File(str(a.firstOrNull())).name
                    "os.path.dirname" -> File(str(a.firstOrNull())).parent ?: "."
                    "os.path.abspath" -> File(str(a.firstOrNull())).absolutePath
                    "os.getenv" -> System.getenv(str(a.firstOrNull())) ?: a.getOrNull(1)
                    "os.environ" -> System.getenv()
                    "json.dumps" -> encodeJson(a.firstOrNull(), false)
                    "json.loads" -> parseJson(a.firstOrNull()?.let { str(it) } ?: "")
                    "json.dump" -> {
                        File(str(a.getOrNull(1))).writeText(encodeJson(a.firstOrNull(), false))
                        null
                    }

                    "json.load" -> parseJson(File(str(a.firstOrNull())).readText())
                    "math.sqrt" -> Math.sqrt(num(a.firstOrNull()))
                    "math.floor" -> Math.floor(num(a.firstOrNull()))
                    "math.ceil" -> Math.ceil(num(a.firstOrNull()))
                    "math.pow" -> Math.pow(num(a.firstOrNull()), num(a.getOrNull(1)))
                    "math.fabs" -> Math.abs(num(a.firstOrNull()))
                    "math.log" -> Math.log(num(a.firstOrNull()))
                    "math.log10" -> Math.log10(num(a.firstOrNull()))
                    "math.sin" -> Math.sin(num(a.firstOrNull()))
                    "math.cos" -> Math.cos(num(a.firstOrNull()))
                    "math.isnan" -> num(a.firstOrNull()).isNaN()
                    "time.time" -> System.currentTimeMillis() / 1000.0
                    "time.sleep" -> {
                        Thread.sleep((num(a.firstOrNull()) * 1000).toLong().coerceIn(0, 300000))
                        null
                    }

                    "time.strftime" -> {
                        val pattern = str(a.firstOrNull())
                        java.text.SimpleDateFormat(pattern.replace("%Y", "yyyy").replace("%m", "MM").replace("%d", "dd"), java.util.Locale.US)
                            .format(java.util.Date())
                    }

                    "random.random" -> Math.random()
                    "random.randint" -> {
                        val lo = num(a.firstOrNull()).toInt()
                        val hi = num(a.getOrNull(1)).toInt()
                        (lo + (Math.random() * (hi - lo + 1)).toInt()).toDouble()
                    }

                    "random.choice" -> asList(a.firstOrNull()).let { list ->
                        if (list.isEmpty()) null else list[(Math.random() * list.size).toInt()]
                    }

                    else -> PyAstRef(name)
                }
            }
        }
    }

    // ── modules ────────────────────────────────────────────────────────────────

    class SysModule

    class OsModule

    class JsonModule

    class MathModule

    class TimeModule

    class RandomModule

    // ── shared value helpers ───────────────────────────────────────────────────

    fun binaryOp(op: String, left: Any?, right: Any?): Any? = when (op) {
        "+" -> if (left is String || right is String) str(left) + str(right) else num(left) + num(right)
        "-" -> num(left) - num(right)
        "*" -> if (left is String && right is Double) left.repeat(right.toInt().coerceIn(0, 100_000)) else num(left) * num(right)
        "/" -> num(left) / num(right)
        "%" -> if (left is String) String.format(left, right) else num(left) % num(right)
        "//" -> Math.floor(num(left) / num(right))
        "**" -> Math.pow(num(left), num(right))
        else -> null
    }

    fun num(v: Any?): Double = when (v) {
        is Double -> v
        is Float -> v.toDouble()
        is Int -> v.toDouble()
        is Long -> v.toDouble()
        is String -> v.toDoubleOrNull() ?: 0.0
        is Boolean -> if (v) 1.0 else 0.0
        else -> 0.0
    }

    fun truthy(value: Any?): Boolean = when (value) {
        null -> false
        is Boolean -> value
        is Double -> value != 0.0
        is String -> value.isNotEmpty()
        is List<*> -> value.isNotEmpty()
        is Map<*, *> -> value.isNotEmpty()
        else -> true
    }

    fun equals(left: Any?, right: Any?): Boolean {
        if (left is Number || right is Number) return num(left) == num(right)
        return left == right
    }

    fun str(v: Any?): String = when (v) {
        null -> "None"
        is Boolean -> if (v) "True" else "False"
        is Double -> if (v == Math.floor(v) && !v.isInfinite() && Math.abs(v) < 1e15) v.toLong().toString() else v.toString()
        is List<*> -> "[" + v.joinToString(", ") { repr(it) } + "]"
        is Map<*, *> -> "{" + v.entries.joinToString(", ") { "${repr(it.key)}: ${repr(it.value)}" } + "}"
        is PyRange -> "range(${v.items.size})"
        is PyAstRef -> v.name
        is Instance -> "<${v.klass.name} object>"
        else -> v.toString()
    }

    fun repr(v: Any?): String = when (v) {
        is String -> "'" + v.replace("'", "\\'") + "'"
        else -> str(v)
    }

    fun asList(value: Any?): List<Any?> = when (value) {
        is List<*> -> value
        is Map<*, *> -> value.keys.toList()
        is String -> value.map { it.toString() }
        is PyRange -> value.items
        else -> emptyList()
    }
}

// ── JSON helpers for the python3 `json` module ────────────────────────────────

internal fun encodeJson(value: Any?, compact: Boolean): String {
    fun quote(s: String): String {
        val sb = StringBuilder("\"")
        for (ch in s) {
            when (ch) {
                '"' -> sb.append("\\\"")
                '\\' -> sb.append("\\\\")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                else -> if (ch.code < 0x20) sb.append(String.format("\\u%04x", ch.code)) else sb.append(ch)
            }
        }
        return sb.append('"').toString()
    }

    val indent = if (compact) null else "  "
    fun pad(depth: Int) = if (indent == null) "" else "\n" + indent.repeat(depth)

    fun build(v: Any?, depth: Int): String = when (v) {
        null -> "null"
        is Boolean -> v.toString()
        is Double -> if (v == Math.floor(v) && !v.isInfinite() && Math.abs(v) < 1e15) v.toLong().toString() else v.toString()
        is String -> quote(v)
        is List<*> ->
            if (v.isEmpty()) "[]"
            else v.joinToString("," + pad(depth + 1), "[" + pad(depth + 1), pad(depth) + "]") { build(it, depth + 1) }

        is Map<*, *> ->
            if (v.isEmpty()) "{}"
            else v.entries.joinToString("," + pad(depth + 1), "{" + pad(depth + 1), pad(depth) + "}") {
                quote(it.key.toString()) + (if (indent == null) ":" else ": ") + build(it.value, depth + 1)
            }

        else -> quote(v.toString())
    }
    return build(value, 0)
}

internal fun parseJson(text: String): Any? = JsonReader(text.trim()).readDocuments().firstOrNull()

internal class JsonReader(private val text: String) {
    private var pos = 0

    fun readDocuments(): List<Any?> {
        val docs = ArrayList<Any?>()
        skip()
        while (pos < text.length) {
            docs.add(readValue())
            skip()
        }
        if (docs.isEmpty()) docs.add(null)
        return docs
    }

    private fun skip() {
        while (pos < text.length && text[pos].isWhitespace()) pos++
    }

    private fun fail(message: String): Nothing = throw IllegalArgumentException(message)

    private fun readValue(): Any? {
        skip()
        if (pos >= text.length) fail("Unexpected end of JSON input")
        return when (val ch = text[pos]) {
            '{' -> readObject()
            '[' -> readArray()
            '"' -> readString()
            't' -> {
                pos += 4
                true
            }

            'f' -> {
                pos += 5
                false
            }

            'n' -> {
                pos += 4
                null
            }

            else -> {
                if (ch == '-' || ch.isDigit()) readNumber() else fail("Unexpected character '$ch' at $pos")
            }
        }
    }

    private fun readObject(): Map<String, Any?> {
        pos++
        val map = LinkedHashMap<String, Any?>()
        skip()
        if (pos < text.length && text[pos] == '}') {
            pos++
            return map
        }
        while (true) {
            skip()
            if (pos >= text.length || text[pos] != '"') fail("Expected object key at $pos")
            val key = readString()
            skip()
            if (pos >= text.length || text[pos] != ':') fail("Expected ':' at $pos")
            pos++
            map[key] = readValue()
            skip()
            if (pos >= text.length) fail("Unterminated object")
            when (text[pos]) {
                ',' -> pos++
                '}' -> {
                    pos++
                    return map
                }

                else -> fail("Expected ',' or '}' at $pos")
            }
        }
    }

    private fun readArray(): List<Any?> {
        pos++
        val list = ArrayList<Any?>()
        skip()
        if (pos < text.length && text[pos] == ']') {
            pos++
            return list
        }
        while (true) {
            list.add(readValue())
            skip()
            if (pos >= text.length) fail("Unterminated array")
            when (text[pos]) {
                ',' -> pos++
                ']' -> {
                    pos++
                    return list
                }

                else -> fail("Expected ',' or ']' at $pos")
            }
        }
    }

    private fun readString(): String {
        pos++
        val sb = StringBuilder()
        while (pos < text.length) {
            val ch = text[pos]
            when {
                ch == '"' -> {
                    pos++
                    return sb.toString()
                }

                ch == '\\' -> {
                    pos++
                    if (pos >= text.length) fail("Bad escape")
                    when (val esc = text[pos]) {
                        '"' -> sb.append('"')
                        '\\' -> sb.append('\\')
                        '/' -> sb.append('/')
                        'b' -> sb.append('\b')
                        'f' -> sb.append('\u000C')
                        'n' -> sb.append('\n')
                        'r' -> sb.append('\r')
                        't' -> sb.append('\t')
                        'u' -> {
                            val hex = text.substring(pos + 1, minOf(pos + 5, text.length))
                            sb.append(hex.toIntOrNull(16)?.toChar() ?: '?')
                            pos += 4
                        }

                        else -> sb.append(esc)
                    }
                    pos++
                }

                else -> {
                    sb.append(ch)
                    pos++
                }
            }
        }
        fail("Unterminated string")
    }

    private fun readNumber(): Any {
        val startPos = pos
        if (text[pos] == '-') pos++
        while (pos < text.length && (text[pos].isDigit() || text[pos] == '.' || text[pos] == 'e' || text[pos] == 'E' ||
                text[pos] == '+' || text[pos] == '-')
        ) pos++
        val raw = text.substring(startPos, pos)
        return raw.toDoubleOrNull() ?: fail("Invalid number '$raw'")
    }
}

/** Splits on a separator, ignoring separators inside quotes/brackets. */
internal fun pySplitTopLevel(input: String, separator: Char): List<String> {
    val parts = ArrayList<String>()
    var depth = 0
    var inString = false
    var quote = ' '
    val current = StringBuilder()
    for (ch in input) {
        if (inString) {
            current.append(ch)
            if (ch == quote) inString = false
            continue
        }
        when (ch) {
            '"', '\'' -> {
                inString = true
                quote = ch
                current.append(ch)
            }

            '(', '[', '{' -> {
                depth++
                current.append(ch)
            }

            ')', ']', '}' -> {
                depth--
                current.append(ch)
            }

            separator -> if (depth == 0) {
                parts.add(current.toString().trim())
                current.setLength(0)
            } else {
                current.append(ch)
            }

            else -> current.append(ch)
        }
    }
    if (current.isNotBlank()) parts.add(current.toString().trim())
    return parts.filter { it.isNotEmpty() }
}

/** Index of a top-level (non-comparison, non-augmented) assignment `=`, or -1. */
internal fun pyFindAssignment(s: String): Int {
    var depth = 0
    var inString = false
    var quote = ' '
    for (idx in s.indices) {
        val ch = s[idx]
        if (inString) {
            if (ch == quote) inString = false
            continue
        }
        when (ch) {
            '"', '\'' -> {
                inString = true
                quote = ch
            }

            '(', '[', '{' -> depth++
            ')', ']', '}' -> depth--
            '=' -> if (depth == 0) {
                val prev = if (idx > 0) s[idx - 1] else ' '
                val next = if (idx + 1 < s.length) s[idx + 1] else ' '
                val augmented = prev == '+' || prev == '-' || prev == '*' || prev == '/' || prev == '%'
                if (prev != '=' && prev != '!' && prev != '<' && prev != '>' && !augmented && next != '=') return idx
            }
        }
    }
    return -1
}
