"use strict";
const electron = require("electron");
const path = require("path");
const fs = require("fs");
const child_process = require("child_process");
const http = require("http");
const net = require("net");
const is = {
  dev: !electron.app.isPackaged
};
const platform = {
  isWindows: process.platform === "win32",
  isMacOS: process.platform === "darwin",
  isLinux: process.platform === "linux"
};
const electronApp = {
  setAppUserModelId(id) {
    if (platform.isWindows)
      electron.app.setAppUserModelId(is.dev ? process.execPath : id);
  },
  setAutoLaunch(auto) {
    if (platform.isLinux)
      return false;
    const isOpenAtLogin = () => {
      return electron.app.getLoginItemSettings().openAtLogin;
    };
    if (isOpenAtLogin() !== auto) {
      electron.app.setLoginItemSettings({
        openAtLogin: auto,
        path: process.execPath
      });
      return isOpenAtLogin() === auto;
    } else {
      return true;
    }
  },
  skipProxy() {
    return electron.session.defaultSession.setProxy({ mode: "direct" });
  }
};
const optimizer = {
  watchWindowShortcuts(window, shortcutOptions) {
    if (!window)
      return;
    const { webContents } = window;
    const { escToCloseWindow = false, zoom = false } = shortcutOptions || {};
    webContents.on("before-input-event", (event, input) => {
      if (input.type === "keyDown") {
        if (!is.dev) {
          if (input.code === "KeyR" && (input.control || input.meta))
            event.preventDefault();
        } else {
          if (input.code === "F12") {
            if (webContents.isDevToolsOpened()) {
              webContents.closeDevTools();
            } else {
              webContents.openDevTools({ mode: "undocked" });
              console.log("Open dev tool...");
            }
          }
        }
        if (escToCloseWindow) {
          if (input.code === "Escape" && input.key !== "Process") {
            window.close();
            event.preventDefault();
          }
        }
        if (!zoom) {
          if (input.code === "Minus" && (input.control || input.meta))
            event.preventDefault();
          if (input.code === "Equal" && input.shift && (input.control || input.meta))
            event.preventDefault();
        }
      }
    });
  },
  registerFramelessWindowIpc() {
    electron.ipcMain.on("win:invoke", (event, action) => {
      const win = electron.BrowserWindow.fromWebContents(event.sender);
      if (win) {
        if (action === "show") {
          win.show();
        } else if (action === "showInactive") {
          win.showInactive();
        } else if (action === "min") {
          win.minimize();
        } else if (action === "max") {
          const isMaximized = win.isMaximized();
          if (isMaximized) {
            win.unmaximize();
          } else {
            win.maximize();
          }
        } else if (action === "close") {
          win.close();
        }
      }
    });
  }
};
const USER_DATA_DIR_NAME = ".sorce_trans";
const STORAGE_CONFIG_FILE = "storage-paths.json";
const CACHE_DIR_NAME = "cache";
const DB_FILE_NAMES = ["settings.db", "history.db", "ai_chat.db", "tasks.db"];
function loadStoragePaths() {
  const defaults = defaultStoragePaths();
  const config = readStorageConfig(defaults.configPath);
  const dataDir = normalizeDir(config.dataDir, defaults.dataDir);
  const cacheDir = normalizeDir(config.cacheDir, path.join(dataDir, CACHE_DIR_NAME));
  return { dataDir, cacheDir, configPath: defaults.configPath };
}
function saveStoragePaths(update) {
  const previous = loadStoragePaths();
  const dataDir = normalizeDir(update.dataDir, previous.dataDir);
  const cacheDir = normalizeDir(update.cacheDir, previous.cacheDir);
  const next = { dataDir, cacheDir, configPath: previous.configPath };
  if (dataDir !== previous.dataDir) {
    migrateDataFiles(previous.dataDir, dataDir);
  }
  if (cacheDir !== previous.cacheDir) {
    copyDirectoryContents(previous.cacheDir, cacheDir);
  }
  fs.mkdirSync(path.dirname(previous.configPath), { recursive: true });
  fs.writeFileSync(
    previous.configPath,
    `${JSON.stringify({ dataDir, cacheDir }, null, 2)}
`,
    "utf-8"
  );
  fs.mkdirSync(dataDir, { recursive: true });
  fs.mkdirSync(cacheDir, { recursive: true });
  return next;
}
function defaultStoragePaths() {
  const dataDir = path.join(electron.app.getPath("home"), USER_DATA_DIR_NAME);
  return {
    dataDir,
    cacheDir: path.join(dataDir, CACHE_DIR_NAME),
    configPath: path.join(dataDir, STORAGE_CONFIG_FILE)
  };
}
function normalizeDir(value, fallback) {
  if (typeof value !== "string" || !value.trim()) {
    return path.resolve(fallback);
  }
  return path.resolve(value.trim());
}
function readStorageConfig(configPath) {
  try {
    const raw = fs.readFileSync(configPath, "utf-8");
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}
function migrateDataFiles(sourceDataDir, targetDataDir) {
  for (const name of DB_FILE_NAMES) {
    for (const suffix of ["", "-wal", "-shm"]) {
      copyFileIfMissing(
        path.join(sourceDataDir, "work", `${name}${suffix}`),
        path.join(targetDataDir, "work", `${name}${suffix}`)
      );
    }
  }
}
function copyDirectoryContents(source, target) {
  if (!fs.existsSync(source) || path.resolve(source) === path.resolve(target)) {
    return;
  }
  for (const child of fs.readdirSync(source)) {
    copyPathIfMissing(path.join(source, child), path.join(target, child));
  }
}
function copyPathIfMissing(source, target) {
  if (fs.existsSync(target)) {
    return;
  }
  try {
    const stat = fs.statSync(source);
    if (stat.isDirectory()) {
      fs.mkdirSync(target, { recursive: true });
      copyDirectoryContents(source, target);
      return;
    }
    if (stat.isFile()) {
      copyFileIfMissing(source, target);
    }
  } catch {
    return;
  }
}
function copyFileIfMissing(source, target) {
  if (!fs.existsSync(source) || fs.existsSync(target)) {
    return;
  }
  try {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(source, target);
  } catch {
    return;
  }
}
const DEFAULT_PORT = 19200;
const HEALTH_CHECK_INTERVAL = 1e3;
const HEALTH_CHECK_TIMEOUT = 15e3;
const SHUTDOWN_TIMEOUT = 5e3;
class BackendProcess {
  process = null;
  port;
  baseURL;
  constructor(port = DEFAULT_PORT) {
    this.port = port;
    this.baseURL = `http://127.0.0.1:${port}`;
  }
  async start() {
    const isDev = !electron.app.isPackaged;
    this.port = await findAvailablePort(this.port);
    this.baseURL = `http://127.0.0.1:${this.port}`;
    const storagePaths = loadStoragePaths();
    const backendEnv = {
      ...process.env,
      SCORE_TRANS_DATA_DIR: storagePaths.dataDir,
      SCORE_TRANS_CACHE_DIR: storagePaths.cacheDir
    };
    if (isDev) {
      const projectRoot = resolveProjectRoot();
      const localPython = path.join(projectRoot, ".venv", "Scripts", "python.exe");
      const pythonExe = fs.existsSync(localPython) ? localPython : "python";
      const backendPath = path.join(projectRoot, "backend");
      const pythonPath = [backendPath, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
      this.process = child_process.spawn(pythonExe, [
        "-m",
        "uvicorn",
        "score_trans.api.app:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        String(this.port),
        "--reload"
      ], {
        stdio: "pipe",
        cwd: projectRoot,
        env: { ...backendEnv, PYTHONPATH: pythonPath },
        windowsHide: true
      });
    } else {
      const resourcesPath = process.resourcesPath;
      const exePath = path.join(resourcesPath, "backend", "backend.exe");
      const backendCwd = path.join(resourcesPath, "backend");
      this.process = child_process.spawn(exePath, [
        "--host",
        "127.0.0.1",
        "--port",
        String(this.port)
      ], { stdio: "pipe", windowsHide: true, cwd: backendCwd, env: backendEnv });
    }
    this.process.stdout?.on("data", (data) => {
      console.log(`[backend] ${data.toString().trim()}`);
    });
    this.process.stderr?.on("data", (data) => {
      console.error(`[backend] ${data.toString().trim()}`);
    });
    this.process.on("exit", (code) => {
      console.log(`[backend] Process exited with code=${code}`);
      this.process = null;
    });
    this.process.on("error", (err) => {
      console.error(`[backend] Process error: ${err.message}`);
    });
    await this.waitForHealthy();
  }
  async waitForHealthy(maxWait = HEALTH_CHECK_TIMEOUT) {
    const start = Date.now();
    while (Date.now() - start < maxWait) {
      try {
        await this.healthCheck();
        console.log(`[backend] Health check passed on port ${this.port}`);
        return;
      } catch {
        await new Promise((r) => setTimeout(r, HEALTH_CHECK_INTERVAL));
      }
    }
    throw new Error(`Backend startup timed out after ${maxWait}ms`);
  }
  healthCheck() {
    return new Promise((resolve, reject) => {
      const req = http.get(`${this.baseURL}/health`, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          resolve();
        } else {
          reject(new Error(`Health check returned ${res.statusCode}`));
        }
      });
      req.on("error", reject);
      req.setTimeout(2e3, () => {
        req.destroy();
        reject(new Error("Health check timeout"));
      });
    });
  }
  async stop() {
    if (!this.process) return;
    const pid = this.process.pid;
    if (!pid) {
      this.process = null;
      return;
    }
    if (process.platform === "win32") {
      this.killTree(pid);
    } else {
      this.process.kill("SIGTERM");
      await new Promise((resolve) => {
        const timeout = setTimeout(() => {
          try {
            this.process?.kill("SIGKILL");
          } catch {
          }
          resolve();
        }, SHUTDOWN_TIMEOUT);
        this.process?.on("exit", () => {
          clearTimeout(timeout);
          resolve();
        });
      });
    }
    this.process = null;
  }
  killTree(pid) {
    try {
      child_process.execSync(`taskkill /T /F /PID ${pid}`, { stdio: "ignore" });
    } catch {
    }
  }
  getBaseURL() {
    return this.baseURL;
  }
}
function resolveProjectRoot() {
  const candidates = [
    path.resolve(__dirname, "..", "..", ".."),
    path.resolve(__dirname, "..", ".."),
    process.cwd(),
    path.resolve(process.cwd(), "..")
  ];
  const found = candidates.find((candidate) => fs.existsSync(path.join(candidate, "backend", "score_trans")));
  return found ?? process.cwd();
}
async function findAvailablePort(startPort) {
  for (let port = startPort; port < startPort + 20; port += 1) {
    if (await isPortAvailable(port)) {
      return port;
    }
  }
  throw new Error(`No available backend port found from ${startPort}`);
}
function isPortAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, "127.0.0.1");
  });
}
let mainWindow = null;
let backend = null;
let quitting = false;
function createWindow(baseURL) {
  const iconPath = path.join(__dirname, "../../build/icon.ico");
  const iconPng = path.join(__dirname, "../../build/icon.png");
  mainWindow = new electron.BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    autoHideMenuBar: true,
    show: false,
    ...fs.existsSync(iconPath) ? { icon: iconPath } : fs.existsSync(iconPng) ? { icon: iconPng } : {},
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.js"),
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  mainWindow.on("ready-to-show", () => {
    mainWindow?.show();
  });
  mainWindow.removeMenu();
  mainWindow.webContents.setWindowOpenHandler((details) => {
    electron.shell.openExternal(details.url);
    return { action: "deny" };
  });
  if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    mainWindow.loadURL(process.env["ELECTRON_RENDERER_URL"]);
  } else {
    mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
  const emitWindowMaximizedState = () => {
    const value = mainWindow?.isMaximized() ?? false;
    mainWindow?.webContents.send("window:maximized-changed", value);
  };
  mainWindow.on("maximize", emitWindowMaximizedState);
  mainWindow.on("unmaximize", emitWindowMaximizedState);
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}
async function cleanupBackend() {
  if (!backend) return;
  const ref = backend;
  backend = null;
  try {
    await ref.stop();
    console.log("[main] Backend stopped");
  } catch (err) {
    console.error("[main] Error stopping backend:", err);
  }
}
electron.app.whenReady().then(async () => {
  electronApp.setAppUserModelId("com.scoretrans.app");
  electron.app.on("browser-window-created", (_, window) => {
    optimizer.watchWindowShortcuts(window);
  });
  backend = new BackendProcess();
  try {
    await backend.start();
  } catch (err) {
    console.error("[main] Failed to start backend:", err);
  }
  const backendURL = backend.getBaseURL();
  electron.ipcMain.on("get-backend-url", (event) => {
    event.returnValue = backendURL;
  });
  electron.ipcMain.handle("window:minimize", () => {
    mainWindow?.minimize();
  });
  electron.ipcMain.handle("window:toggle-maximize", () => {
    if (!mainWindow) {
      return false;
    }
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
      return false;
    }
    mainWindow.maximize();
    return true;
  });
  electron.ipcMain.handle("window:is-maximized", () => {
    return mainWindow?.isMaximized() ?? false;
  });
  electron.ipcMain.handle("window:close", () => {
    mainWindow?.close();
  });
  electron.ipcMain.handle("dialog:select-directory", async () => {
    if (!mainWindow) return null;
    const result = await electron.dialog.showOpenDialog(mainWindow, {
      properties: ["openDirectory"]
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    return result.filePaths[0];
  });
  electron.ipcMain.handle("storage:get", () => {
    return loadStoragePaths();
  });
  electron.ipcMain.handle("storage:set", (_event, paths) => {
    return saveStoragePaths(paths ?? {});
  });
  electron.ipcMain.handle("app:relaunch", () => {
    electron.app.relaunch();
    electron.app.quit();
  });
  createWindow();
  electron.app.on("activate", () => {
    if (electron.BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});
electron.app.on("before-quit", async (e) => {
  if (quitting) return;
  quitting = true;
  if (backend) {
    e.preventDefault();
    await cleanupBackend();
    electron.app.quit();
  }
});
electron.app.on("will-quit", async () => {
  await cleanupBackend();
  electron.ipcMain.removeHandler("window:minimize");
  electron.ipcMain.removeHandler("window:toggle-maximize");
  electron.ipcMain.removeHandler("window:is-maximized");
  electron.ipcMain.removeHandler("window:close");
  electron.ipcMain.removeHandler("dialog:select-directory");
  electron.ipcMain.removeHandler("storage:get");
  electron.ipcMain.removeHandler("storage:set");
  electron.ipcMain.removeHandler("app:relaunch");
});
electron.app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    electron.app.quit();
  }
});
