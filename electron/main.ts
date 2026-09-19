import {
  app,
  BrowserWindow,
  ipcMain,
  shell,
} from "electron";
import * as child_process from "child_process";
import * as fs from "fs";
import * as http from "http";
import * as path from "path";
import { findFreePort } from "./utils/findFreePort";
import { spawnBackend } from "./utils/spawnBackend";

// --- State ---

let mainWindow: BrowserWindow | null = null;
let backendProcess: child_process.ChildProcess | null = null;
let backendPort: number = 8000;
let isQuitting = false;

// --- Paths ---

const dataDir = app.getPath("userData");
const configEnvPath = path.join(dataDir, "config.env");

// --- Window helpers ---

function isWebUrl(url: string): boolean {
  try {
    const { protocol } = new URL(url);
    return protocol === "http:" || protocol === "https:";
  } catch {
    return false;
  }
}

function createLoadingWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 480,
    height: 360,
    resizable: false,
    frame: false,
    backgroundColor: "#0b0f19",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });
  win.loadFile(path.join(__dirname, "..", "loading.html"));
  return win;
}

function createSetupWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 520,
    height: 560,
    resizable: false,
    backgroundColor: "#0b0f19",
    title: "Articulate - Setup",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });
  win.loadFile(path.join(__dirname, "..", "setup.html"));
  return win;
}

function createMainWindow(port: number): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: "#0b0f19",
    title: "Articulate",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  // Open external links in the system browser, not Electron. Only web links: pack files from other
  // people can carry file: or custom-protocol URLs that would launch local programs.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (isWebUrl(url)) shell.openExternal(url);
    return { action: "deny" };
  });

  win.on("closed", () => {
    mainWindow = null;
  });

  return win;
}

// --- Backend health check ---

// First launch downloads Kokoro models (~330 MB), so startup can take a long time.
const BACKEND_START_TIMEOUT_MS = 30 * 60 * 1_000;

function formatDuration(ms: number): string {
  const seconds = Math.round(ms / 1_000);
  if (seconds < 120) return `${seconds} second${seconds === 1 ? "" : "s"}`;
  return `${Math.round(seconds / 60)} minutes`;
}

function waitForBackend(port: number, timeoutMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const interval = 500;

    const check = () => {
      // A timed-out request is destroyed, which also emits "error"; the flag keeps
      // each request from scheduling more than one follow-up check.
      let settled = false;
      const next = () => {
        if (settled) return;
        settled = true;
        scheduleNextCheck();
      };
      const req = http.get(
        `http://127.0.0.1:${port}/api/v1/system/info`,
        (res) => {
          res.resume();
          if (res.statusCode === 200) {
            settled = true;
            resolve();
          } else {
            next();
          }
        }
      );
      req.on("error", next);
      req.setTimeout(1000, () => { req.destroy(); next(); });
    };

    const scheduleNextCheck = () => {
      if (Date.now() >= deadline) {
        reject(new Error(`The backend process did not respond within ${formatDuration(timeoutMs)}.`));
        return;
      }
      setTimeout(check, interval);
    };

    check();
  });
}

// --- Backend shutdown ---

function stopBackend(): Promise<void> {
  return new Promise((resolve) => {
    if (!backendProcess || backendProcess.killed) {
      resolve();
      return;
    }

    const forceKillTimer = setTimeout(() => {
      backendProcess?.kill("SIGKILL");
      resolve();
    }, 5000);

    backendProcess.once("exit", () => {
      clearTimeout(forceKillTimer);
      resolve();
    });

    backendProcess.kill("SIGTERM");
  });
}

// --- First-run setup ---

function isFirstRun(): boolean {
  return !fs.existsSync(configEnvPath);
}

function runSetup(): Promise<void> {
  return new Promise((resolve) => {
    const win = createSetupWindow();

    // Use ipcMain.once so we listen for the `send` from the preload (not invoke).
    ipcMain.once("save-config", (_event, configContent: string) => {
      writeConfigEnv(configContent);
      win.close();
      resolve();
    });
  });
}

function writeConfigEnv(content: string): void {
  fs.mkdirSync(dataDir, { recursive: true });
  if (content) {
    fs.writeFileSync(configEnvPath, content, "utf-8");
  } else {
    // User skipped: write a marker file so we don't prompt again.
    fs.writeFileSync(configEnvPath, "# Articulate config\n", "utf-8");
  }
}

// --- IPC handlers ---

ipcMain.handle("get-port", () => backendPort);

ipcMain.on("open-log-file", () => {
  const logPath = path.join(dataDir, "logs", "backend.log");
  if (fs.existsSync(logPath)) shell.openPath(logPath);
});

ipcMain.on("open-external", (_event, url: string) => {
  if (isWebUrl(url)) shell.openExternal(url);
});

// save-config is handled in runSetup() via ipcMain.once for the first-run flow.

// --- App lifecycle ---

app.whenReady().then(async () => {
  // First-run: collect API keys before starting the backend.
  if (isFirstRun()) {
    await runSetup();
  }

  backendPort = await findFreePort(8000);
  backendProcess = spawnBackend({
    port: backendPort,
    dataDir,
    configEnvPath,
  });

  const loadingWin = createLoadingWindow();

  try {
    // Race against process exit so a crash fails fast instead of waiting out the timeout.
    // A binary that cannot be launched (e.g. ENOENT) emits "error" but never "exit".
    await Promise.race([
      waitForBackend(backendPort, BACKEND_START_TIMEOUT_MS),
      new Promise<never>((_, reject) => {
        backendProcess!.once("exit", (code) => {
          reject(new Error(`Backend exited with code ${code ?? "unknown"} before becoming ready.`));
        });
        backendProcess!.once("error", (err) => {
          reject(new Error(`Backend could not be started: ${err.message}`));
        });
      }),
    ]);
  } catch (err) {
    const { dialog } = await import("electron");
    const logPath = path.join(dataDir, "logs", "backend.log");
    const reason = err instanceof Error ? err.message : String(err);
    await dialog.showMessageBox({
      type: "error",
      title: "Articulate - Backend failed to start",
      message: `${reason}\n\nCheck the log file for details:\n${logPath}`,
      buttons: ["Quit", "Open Log"],
    }).then(({ response }) => {
      if (response === 1) shell.openPath(logPath);
    });
    app.quit();
    return;
  }

  loadingWin.close();
  mainWindow = createMainWindow(backendPort);
  mainWindow.loadURL(`http://127.0.0.1:${backendPort}`);
  mainWindow.show();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createMainWindow(backendPort);
      mainWindow.loadURL(`http://127.0.0.1:${backendPort}`);
    }
  });
});

app.on("before-quit", () => {
  isQuitting = true;
});

app.on("will-quit", async (event) => {
  if (backendProcess && !backendProcess.killed) {
    event.preventDefault();
    await stopBackend();
    app.quit();
  }
});

// On macOS, keep the app in the dock even with no windows open.
app.on("window-all-closed", () => {
  if (process.platform !== "darwin" || isQuitting) {
    app.quit();
  }
});
