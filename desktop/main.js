const { app, BrowserWindow, Tray, Menu, ipcMain, screen, session, globalShortcut } = require('electron');
const path = require('path');
const http = require('http');
const fs = require('fs');
const wakeWord = require('./wake-word');

// Disable GPU acceleration to avoid chunked_data_pipe errors on Windows
app.disableHardwareAcceleration();

let mainWindow;
let tray;
let localServer;

const BUBBLE_SIZE = { width: 72, height: 72 };
const CHAT_SIZE = { width: 420, height: 640 };

// Serve renderer files via HTTP so webkitSpeechRecognition works (needs HTTP origin)
function startLocalServer() {
  return new Promise((resolve) => {
    const MIME = {
      '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
      '.png': 'image/png', '.svg': 'image/svg+xml', '.json': 'application/json',
    };
    localServer = http.createServer((req, res) => {
      let filePath = path.join(__dirname, 'renderer', req.url === '/' ? 'index.html' : req.url);
      const ext = path.extname(filePath);
      fs.readFile(filePath, (err, data) => {
        if (err) { res.writeHead(404); res.end('Not found'); return; }
        res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
        res.end(data);
      });
    });
    localServer.listen(0, '127.0.0.1', () => {
      resolve(localServer.address().port);
    });
  });
}

function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: BUBBLE_SIZE.width,
    height: BUBBLE_SIZE.height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadURL(`http://127.0.0.1:${port}/`);
  mainWindow.setVisibleOnAllWorkspaces(true);

  // Position bottom-right
  const display = screen.getPrimaryDisplay();
  const x = display.workArea.x + display.workArea.width - BUBBLE_SIZE.width - 24;
  const y = display.workArea.y + display.workArea.height - BUBBLE_SIZE.height - 24;
  mainWindow.setPosition(x, y);
}

// IPC: expand to chat mode
ipcMain.on('expand', () => {
  const [x, y] = mainWindow.getPosition();
  const newX = x - (CHAT_SIZE.width - BUBBLE_SIZE.width);
  const newY = y - (CHAT_SIZE.height - BUBBLE_SIZE.height);
  mainWindow.setBounds({
    x: Math.max(0, newX),
    y: Math.max(0, newY),
    width: CHAT_SIZE.width,
    height: CHAT_SIZE.height,
  });
});

// IPC: collapse back to bubble
ipcMain.on('collapse', () => {
  const bounds = mainWindow.getBounds();
  mainWindow.setBounds({
    x: bounds.x + (CHAT_SIZE.width - BUBBLE_SIZE.width),
    y: bounds.y + (CHAT_SIZE.height - BUBBLE_SIZE.height),
    width: BUBBLE_SIZE.width,
    height: BUBBLE_SIZE.height,
  });
});

// IPC: toggle mouse events (for transparent click-through on Windows)
ipcMain.on('set-ignore-mouse', (_event, ignore) => {
  mainWindow.setIgnoreMouseEvents(ignore, { forward: true });
});

// IPC: manual drag (for transparent window regions)
ipcMain.on('drag-move', (_event, { deltaX, deltaY }) => {
  const [x, y] = mainWindow.getPosition();
  mainWindow.setPosition(x + deltaX, y + deltaY);
});

app.whenReady().then(async () => {
  // Auto-grant microphone permission for wake word and voice
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    callback(true);
  });
  // Also handle permission checks (Chromium checks before requesting)
  session.defaultSession.setPermissionCheckHandler(() => true);

  const port = await startLocalServer();
  console.log(`TARS renderer serving on http://127.0.0.1:${port}`);
  createWindow(port);

  // Global shortcut: Ctrl+Shift+T to activate TARS voice
  globalShortcut.register('CommandOrControl+Shift+T', () => {
    mainWindow.show();
    mainWindow.webContents.send('activate-voice');
  });

  // "Hey TARS" wake word via Porcupine
  const accessKey = process.env.PICOVOICE_ACCESS_KEY || '';
  const ppnFile = path.join(__dirname, 'Hey-TARS_en_windows_v4_0_0.ppn');
  if (accessKey) {
    wakeWord.start({
      accessKey,
      keywordPath: fs.existsSync(ppnFile) ? ppnFile : undefined,
      builtinKeyword: fs.existsSync(ppnFile) ? undefined : 'COMPUTER',
      sensitivity: 0.5,
      onDetected: () => {
        mainWindow.show();
        mainWindow.webContents.send('activate-voice');
      },
    });
  } else {
    console.log('PICOVOICE_ACCESS_KEY not set — wake word disabled. Set it to enable "Hey TARS".');
  }

  // System tray
  const trayIcon = path.join(__dirname, 'renderer', 'icons', 'tars-tray.png');
  try {
    tray = new Tray(trayIcon);
    tray.setToolTip('TARS');
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: 'Show TARS', click: () => mainWindow.show() },
      { type: 'separator' },
      { label: 'Quit', click: () => app.quit() },
    ]));
    tray.on('click', () => mainWindow.show());
  } catch (e) {
    console.log('Tray icon not found, skipping:', e.message);
  }
});

app.on('window-all-closed', () => {
  wakeWord.stop();
  globalShortcut.unregisterAll();
  if (localServer) localServer.close();
  app.quit();
});
