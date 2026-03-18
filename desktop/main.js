const { app, BrowserWindow, Tray, Menu, ipcMain, screen, session } = require('electron');
const path = require('path');

// Disable GPU acceleration to avoid chunked_data_pipe errors on Windows
app.disableHardwareAcceleration();

let mainWindow;
let tray;

const BUBBLE_SIZE = { width: 72, height: 72 };
const CHAT_SIZE = { width: 420, height: 640 };

function createWindow() {
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

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
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
  // Expand upward and to the left from current position
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
  // Collapse to bottom-right corner of current position
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

app.whenReady().then(() => {
  // Auto-grant microphone permission for wake word and voice
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    if (permission === 'media' || permission === 'microphone') {
      callback(true);
    } else {
      callback(true);
    }
  });

  createWindow();

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
    // Tray icon may not exist yet during development
    console.log('Tray icon not found, skipping:', e.message);
  }
});

app.on('window-all-closed', () => app.quit());
