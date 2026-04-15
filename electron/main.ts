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

// ── State ─────────────────────────────────────────────────────────────────────

let mainWindow: BrowserWindow | null = null;
let backendProcess: child_process.ChildProcess | null = null;
let backendPort: number = 8000;
let isQuitting = false;

// ── Paths ─────────────────────────────────────────────────────────────────────

const dataDir = app.getPath("userData");
const configEnvPath = path.join(dataDir, "config.env");

// ── Window helpers ────────────────────────────────────────────────────────────

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
    title: "Articulate — Setup",
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

  // Open external links in the system browser, not Electron.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  win.on("closed", () => {
    mainWindow = null;
  });

  return win;
}

// ── Backend health check ──────────────────────────────────────────────────────

function waitForBackend(port: number, timeoutMs: number = 120_000): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const interval = 500;

    const check = () => {
      const req = http.get(
        `http://127.0.0.1:${port}/api/v1/system/info`,
        (res) => {
          if (res.statusCode === 200) {
            res.resume();
            resolve();
          } else {
            res.resume();
            scheduleNextCheck();
          }
        }
      );
      req.on("error", scheduleNextCheck);
      req.setTimeout(1000, () => { req.destroy(); scheduleNextCheck(); });
    };

    const scheduleNextCheck = () => {
      if (Date.now() >= deadline) {
        reject(new Error("Backend did not start within the timeout."));
        return;
      }
      setTimeout(check, interval);
    };

    check();
  });
}

// ── Backend shutdown ──────────────────────────────────────────────────────────

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

// ── First-run setup ───────────────────────────────────────────────────────────

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
    // User skipped — write a marker file so we don't prompt again.
    fs.writeFileSync(configEnvPath, "# Articulate config\n", "utf-8");
  }
}

// ── IPC handlers ─────────────────────────────────────────────────────────────

ipcMain.handle("get-port", () => backendPort);

ipcMain.on("open-log-file", () => {
  const logPath = path.join(dataDir, "logs", "backend.log");
  if (fs.existsSync(logPath)) shell.openPath(logPath);
});

ipcMain.on("open-external", (_event, url: string) => {
  shell.openExternal(url);
});

// save-config is handled in runSetup() via ipcMain.once for the first-run flow.

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  // First-run: collect API keys before starting the backend.
  if (isFirstRun()) {
    await runSetup();
  }

  // Find a free port and start the backend.
  backendPort = await findFreePort(8000);
  backendProcess = spawnBackend({
    port: backendPort,
    dataDir,
    configEnvPath,
  });

  // Show a loading screen while the backend warms up.
  const loadingWin = createLoadingWindow();

  try {
    // Wait up to 30 min — first launch downloads Kokoro models (~330 MB).
    // On a slow connection (1 Mbps) that can take 44 minutes; 30 min covers most cases.
    // The loading screen shows a "downloading AI models" hint after 10 seconds.
    await waitForBackend(backendPort, 30 * 60 * 1_000);
  } catch (err) {
    // Backend failed to start; show the log file path in a dialog.
    const { dialog } = await import("electron");
    const logPath = path.join(dataDir, "logs", "backend.log");
    await dialog.showMessageBox({
      type: "error",
      title: "Articulate — Backend failed to start",
      message: `The backend process did not respond within 2 minutes.\n\nCheck the log file for details:\n${logPath}`,
      buttons: ["Quit", "Open Log"],
    }).then(({ response }) => {
      if (response === 1) shell.openPath(logPath);
    });
    app.quit();
    return;
  }

  // Close loading screen, open the real app window.
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
