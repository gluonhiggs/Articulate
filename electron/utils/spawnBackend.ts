import * as child_process from "child_process";
import * as fs from "fs";
import * as path from "path";

export interface BackendOptions {
  port: number;
  dataDir: string;
  /** Path to config.env file containing KEY=VALUE settings. */
  configEnvPath: string;
}

/**
 * Spawn the Articulate backend process.
 *
 * In a packaged app (process.resourcesPath set by Electron):
 *   Runs the PyInstaller-bundled binary at resources/backend/articulate_backend(.exe).
 *
 * In development (no process.resourcesPath / not app.isPackaged):
 *   Falls back to `uv run uvicorn backend.main:app ...` from the project root.
 */
export function spawnBackend(opts: BackendOptions): child_process.ChildProcess {
  const { port, dataDir, configEnvPath } = opts;

  // Build the environment for the child process.
  const env: Record<string, string> = {
    ...process.env as Record<string, string>,
    ARTICULATE_PORT: String(port),
    ARTICULATE_HOST: "127.0.0.1",
    ARTICULATE_NO_INTERACTIVE: "1",
    ARTICULATE_DATA_DIR: dataDir,
    ARTICULATE_HF_HOME: path.join(dataDir, "hf_cache"),
    // Clear PYTHONPATH to avoid host-installed packages polluting the bundle.
    PYTHONPATH: "",
  };

  // Overlay settings from config.env if it exists.
  if (fs.existsSync(configEnvPath)) {
    const lines = fs.readFileSync(configEnvPath, "utf-8").split(/\r?\n/);
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx === -1) continue;
      const key = trimmed.slice(0, eqIdx).trim();
      const value = trimmed.slice(eqIdx + 1).trim();
      if (key) env[key] = value;
    }
  }

  // Ensure data directory exists.
  fs.mkdirSync(dataDir, { recursive: true });
  fs.mkdirSync(path.join(dataDir, "logs"), { recursive: true });

  const logPath = path.join(dataDir, "logs", "backend.log");
  const logStream = fs.createWriteStream(logPath, { flags: "a" });

  let proc: child_process.ChildProcess;

  if (isPackaged()) {
    // Packaged: run the PyInstaller binary.
    const binaryName = process.platform === "win32"
      ? "articulate_backend.exe"
      : "articulate_backend";
    const binaryPath = path.join(
      process.resourcesPath,
      "backend",
      binaryName
    );
    proc = child_process.spawn(binaryPath, [], { env, stdio: ["ignore", "pipe", "pipe"] });
  } else {
    // Development: use uv from the repo root.
    const repoRoot = path.resolve(__dirname, "..", "..");
    proc = child_process.spawn(
      "uv",
      [
        "run",
        "uvicorn",
        "backend.main:app",
        "--host", "127.0.0.1",
        "--port", String(port),
        "--workers", "1",
      ],
      { cwd: repoRoot, env, stdio: ["ignore", "pipe", "pipe"] }
    );
  }

  // Pipe stdout/stderr to the log file.
  proc.stdout?.pipe(logStream, { end: false });
  proc.stderr?.pipe(logStream, { end: false });

  proc.on("error", (err) => {
    logStream.write(`[electron] Backend process error: ${err.message}\n`);
  });

  return proc;
}

function isPackaged(): boolean {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { app } = require("electron");
    return app.isPackaged;
  } catch {
    return false;
  }
}
