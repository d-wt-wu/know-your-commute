import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const python = process.env.COMMUTE_PYTHON ?? `${root}/.venv/bin/python`;
if (!existsSync(python)) {
  console.error("Set up the Python environment first: uv sync --locked");
  process.exit(1);
}
const child = spawn(
  python,
  [
    "scripts/run_local.py",
    "--env-file",
    ".env.local",
    "--require-readonly",
    ...process.argv.slice(2),
  ],
  {
    cwd: root,
    stdio: "inherit",
    env: process.env,
  },
);
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => child.kill(signal));
child.on("error", () => {
  console.error("The Python app could not start.");
  process.exit(1);
});
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
