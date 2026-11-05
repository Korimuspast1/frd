#!/usr/bin/env node
/**
 * Syncs OpenCode Android overrides + shared OpenCodeV2Engine into upstream `anomalyco/opencode`
 * (`/tmp/opencode-ref`) and compiles the literal `@opencode/app` desktop/mobile UI bundle.
 */

import fs from "node:fs"
import path from "node:path"
import { execFileSync } from "node:child_process"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = path.resolve(__dirname, "..")
const UPSTREAM_DIR = process.env.OPENCODE_UPSTREAM_DIR || "/tmp/opencode-ref"
const BUN = fs.existsSync("/tmp/bun-bin/node_modules/.bin/bun")
  ? "/tmp/bun-bin/node_modules/.bin/bun"
  : "bun"

if (!fs.existsSync(UPSTREAM_DIR)) {
  console.log(`[build-web] Cloning upstream anomalyco/opencode into ${UPSTREAM_DIR}...`)
  execFileSync("git", ["clone", "--depth", "1", "https://github.com/anomalyco/opencode.git", UPSTREAM_DIR], {
    stdio: "inherit",
  })
  execFileSync(BUN, ["install", "--ignore-scripts"], { cwd: UPSTREAM_DIR, stdio: "inherit" })
}

// Sync engine + upstream overrides
const androidSrcDir = path.join(UPSTREAM_DIR, "packages/app/src/android")
fs.mkdirSync(androidSrcDir, { recursive: true })
fs.copyFileSync(
  path.join(PROJECT_ROOT, "src/engine/opencode-v2-engine.ts"),
  path.join(androidSrcDir, "opencode-v2-engine.ts"),
)

fs.cpSync(path.join(PROJECT_ROOT, "upstream-overrides/app"), path.join(UPSTREAM_DIR, "packages/app"), {
  recursive: true,
})
fs.cpSync(path.join(PROJECT_ROOT, "upstream-overrides/gui-plugins"), path.join(UPSTREAM_DIR, "packages/gui-plugins"), {
  recursive: true,
})

// Bundle standalone Node ESM engine for server/dev-daemon.mjs
execFileSync(
  BUN,
  [
    "build",
    path.join(PROJECT_ROOT, "src/engine/opencode-v2-engine.ts"),
    "--target=node",
    "--format=esm",
    `--outfile=${path.join(PROJECT_ROOT, "server/opencode-v2-engine.mjs")}`,
  ],
  { stdio: "inherit" },
)

// Build upstream @opencode/app
fs.rmSync(path.join(UPSTREAM_DIR, "packages/app/dist"), { recursive: true, force: true })
execFileSync(BUN, ["--cwd", "packages/app", "build"], {
  cwd: UPSTREAM_DIR,
  stdio: "inherit",
  env: {
    ...process.env,
    PATH: `/tmp/bun-bin/node_modules/.bin:${process.env.PATH || ""}`,
  },
})

console.log(`[build-web] Upstream @opencode/app built at ${path.join(UPSTREAM_DIR, "packages/app/dist")}`)
