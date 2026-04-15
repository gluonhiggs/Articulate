import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  /** The port the backend is listening on. Set by the main process. */
  getPort: (): Promise<number> => ipcRenderer.invoke("get-port"),

  /** Open the backend log file in the default text editor. */
  openLogFile: (): void => ipcRenderer.send("open-log-file"),

  /** Save config.env content from the first-run setup form. */
  saveConfig: (content: string): void => ipcRenderer.send("save-config", content),

  /** Open a URL in the system default browser. */
  openExternal: (url: string): void => ipcRenderer.send("open-external", url),

  /** Current platform string (e.g. "win32", "darwin", "linux"). */
  platform: process.platform,
});
