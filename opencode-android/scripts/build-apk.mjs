import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(PROJECT_ROOT, '..');
const ANDROID_APP = path.join(PROJECT_ROOT, 'android/app/src/main');
const BUILD_DIR = '/tmp/opencode-apk-build';
const TC = '/tmp/android-toolchain';

const JAVA = path.join(TC, 'py/jdk4py/java-runtime/bin/java');
const KEYTOOL = path.join(TC, 'py/jdk4py/java-runtime/bin/keytool');
const AAPT2 = path.join(TC, 'node_modules/aaptjs3/bin/x64/linux/aapt2');
const KOTLINC_JAR = path.join(TC, 'node_modules/kotlin-compiler/lib/kotlin-compiler.jar');
const KOTLIN_STDLIB = path.join(TC, 'node_modules/kotlin-compiler/lib/kotlin-stdlib.jar');
const ECJ_JAR = path.join(TC, 'ecj.jar');
const ANDROID_JAR = path.join(TC, 'android-34.jar');
const APKSIGNER_JAR = path.join(TC, 'node_modules/@postar/apktool-node/lib/apksigner.jar');
const D8_CLASSES = path.join(TC, 'd8-classes');
const D8_LIBS_DIR = path.join(TC, 'android-d8/libs');

function run(cmd, args, opts = {}) {
  console.log(`> ${path.basename(cmd)} ${args.slice(0, 5).join(' ')} ...`);
  return execFileSync(cmd, args, { stdio: 'inherit', ...opts });
}

function collectFiles(dir, ext) {
  const out = [];
  if (!fs.existsSync(dir)) return out;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) out.push(...collectFiles(p, ext));
    else if (!ext || p.endsWith(ext)) out.push(p);
  }
  return out;
}

console.log('=== [1/6] Preparing clean build workspace ===');
fs.rmSync(BUILD_DIR, { recursive: true, force: true });
fs.mkdirSync(path.join(BUILD_DIR, 'compiled-res'), { recursive: true });
fs.mkdirSync(path.join(BUILD_DIR, 'gen'), { recursive: true });
fs.mkdirSync(path.join(BUILD_DIR, 'classes'), { recursive: true });
fs.mkdirSync(path.join(BUILD_DIR, 'dex'), { recursive: true });

console.log('=== [2/6] Compiling & linking Android resources with AAPT2 ===');
const resFiles = collectFiles(path.join(ANDROID_APP, 'res'));
for (const rf of resFiles) {
  run(AAPT2, ['compile', rf, '-o', path.join(BUILD_DIR, 'compiled-res')]);
}

const flatFiles = collectFiles(path.join(BUILD_DIR, 'compiled-res'), '.flat');
const unalignedApk = path.join(BUILD_DIR, 'unsigned-unaligned.apk');

run(AAPT2, [
  'link',
  '-I', ANDROID_JAR,
  '--manifest', path.join(ANDROID_APP, 'AndroidManifest.xml'),
  '-A', path.join(ANDROID_APP, 'assets'),
  '--java', path.join(BUILD_DIR, 'gen'),
  '--min-sdk-version', '26',
  '--target-sdk-version', '34',
  '--version-code', '20205',
  '--version-name', '2.2.5',
  '-o', unalignedApk,
  ...flatFiles,
]);

console.log('=== [3/6] Compiling R.java & Kotlin Android sources ===');
const rJavaFiles = collectFiles(path.join(BUILD_DIR, 'gen'), '.java');
run(JAVA, [
  '-jar', ECJ_JAR,
  '-1.8',
  '-nowarn',
  '-cp', ANDROID_JAR,
  '-d', path.join(BUILD_DIR, 'classes'),
  ...rJavaFiles,
]);

const ktFiles = collectFiles(path.join(ANDROID_APP, 'java'), '.kt');
run(JAVA, [
  '-Xmx2g',
  '-cp', KOTLINC_JAR,
  'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler',
  '-jvm-target', '1.8',
  '-no-reflect',
  '-cp', `${ANDROID_JAR}:${KOTLIN_STDLIB}:${path.join(BUILD_DIR, 'classes')}`,
  '-d', path.join(BUILD_DIR, 'classes'),
  ...ktFiles,
]);

console.log('=== [4/6] Compiling JVM bytecode + Kotlin stdlib into Dalvik classes.dex (D8) ===');
const d8Libs = fs.readdirSync(D8_LIBS_DIR).filter((f) => f.endsWith('.jar')).map((f) => path.join(D8_LIBS_DIR, f));
const allClassFiles = collectFiles(path.join(BUILD_DIR, 'classes'), '.class');

// Strip META-INF module-info from kotlin-stdlib so older D8 ASM parses Java 8 classes cleanly
const cleanStdlibJar = path.join(BUILD_DIR, 'kotlin-stdlib-clean.jar');
execFileSync('python3', [
  '-c',
  `
import zipfile
with zipfile.ZipFile(${JSON.stringify(KOTLIN_STDLIB)}, 'r') as zin, zipfile.ZipFile(${JSON.stringify(cleanStdlibJar)}, 'w') as zout:
    for item in zin.infolist():
        if item.filename.endswith('module-info.class') or item.filename.startswith('META-INF/versions/'):
            continue
        zout.writestr(item, zin.read(item.filename))
`,
]);

run(JAVA, [
  '-Xmx2g',
  '-cp', [D8_CLASSES, ...d8Libs].join(':'),
  'com.android.tools.r8.D8',
  '--release',
  '--min-api', '26',
  '--lib', ANDROID_JAR,
  '--output', path.join(BUILD_DIR, 'dex'),
  cleanStdlibJar,
  ...allClassFiles,
]);

console.log('=== [5/6] Packaging classes.dex & 4-byte Zipaligning resources.arsc ===');
const alignedApk = path.join(BUILD_DIR, 'unsigned-aligned.apk');
execFileSync('python3', [
  '-c',
  `
import zipfile, struct, os

unaligned = ${JSON.stringify(unalignedApk)}
dex_dir = ${JSON.stringify(path.join(BUILD_DIR, 'dex'))}
aligned_out = ${JSON.stringify(alignedApk)}

# Collect all entries from aapt2 output + classes*.dex
entries = []
with zipfile.ZipFile(unaligned, 'r') as zin:
    for info in zin.infolist():
        data = zin.read(info.filename)
        # Android 11+ requires resources.arsc uncompressed & 4-byte aligned!
        store_raw = (info.filename == 'resources.arsc') or info.filename.endswith(('.png', '.webp', '.ogg', '.mp3', '.woff2'))
        entries.append((info.filename, data, store_raw))

for fn in sorted(os.listdir(dex_dir)):
    if fn.endswith('.dex'):
        with open(os.path.join(dex_dir, fn), 'rb') as fh:
            entries.append((fn, fh.read(), False))

with zipfile.ZipFile(aligned_out, 'w') as zout:
    for name, data, store_raw in entries:
        zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        zi.create_system = 3
        zi.external_attr = 0o644 << 16
        if store_raw:
            zi.compress_type = zipfile.ZIP_STORED
            # Local file header is 30 bytes + len(filename) + len(extra)
            cur_offset = zout.fp.tell()
            name_bytes = name.encode('utf-8')
            data_start = cur_offset + 30 + len(name_bytes)
            pad = (4 - (data_start % 4)) % 4
            zi.extra = b'\\x00' * pad
            zout.writestr(zi, data)
        else:
            zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

# Verify 4-byte alignment of resources.arsc
with zipfile.ZipFile(aligned_out, 'r') as zcheck:
    for info in zcheck.infolist():
        if info.compress_type == zipfile.ZIP_STORED:
            with open(aligned_out, 'rb') as rawf:
                rawf.seek(info.header_offset + 26)
                fn_len, ex_len = struct.unpack('<HH', rawf.read(4))
                data_off = info.header_offset + 30 + fn_len + ex_len
                assert data_off % 4 == 0, f"{info.filename} not 4-byte aligned ({data_off})"
print("4-byte zipalign verified for all uncompressed entries!")
`,
]);

console.log('=== [6/6] Signing APK (V1 + V2 + V3) & Verifying ===');
const keystore = path.join(BUILD_DIR, 'opencode-release.jks');
run(KEYTOOL, [
  '-genkeypair',
  '-v',
  '-keystore', keystore,
  '-storepass', 'opencodeandroid',
  '-keypass', 'opencodeandroid',
  '-alias', 'opencode',
  '-keyalg', 'RSA',
  '-keysize', '2048',
  '-validity', '10000',
  '-dname', 'CN=OpenCode Android, OU=Engineering, O=OpenCode Port, L=Stockholm, C=SE',
]);

const finalApkRepo = path.join(REPO_ROOT, 'OpenCode-Android-v2.2.5.apk');
const distDir = path.join(PROJECT_ROOT, 'dist');
fs.mkdirSync(distDir, { recursive: true });
const finalApkDist = path.join(distDir, 'OpenCode-Android-v2.2.5.apk');

run(JAVA, [
  '-jar', APKSIGNER_JAR,
  'sign',
  '--ks', keystore,
  '--ks-pass', 'pass:opencodeandroid',
  '--key-pass', 'pass:opencodeandroid',
  '--ks-key-alias', 'opencode',
  '--v1-signing-enabled', 'true',
  '--v2-signing-enabled', 'true',
  '--v3-signing-enabled', 'true',
  '--out', finalApkRepo,
  alignedApk,
]);

fs.copyFileSync(finalApkRepo, finalApkDist);

run(JAVA, ['-jar', APKSIGNER_JAR, 'verify', '--verbose', finalApkRepo]);
run(AAPT2, ['dump', 'badging', finalApkRepo]);

const sizeMb = (fs.statSync(finalApkRepo).size / (1024 * 1024)).toFixed(2);
console.log(`\nSUCCESS! Built & signed ${finalApkRepo} (${sizeMb} MB)`);
