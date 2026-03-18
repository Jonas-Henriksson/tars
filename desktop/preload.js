const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('tarsAPI', {
  expand: () => ipcRenderer.send('expand'),
  collapse: () => ipcRenderer.send('collapse'),
  dragMove: (deltaX, deltaY) => ipcRenderer.send('drag-move', { deltaX, deltaY }),
  setIgnoreMouse: (ignore) => ipcRenderer.send('set-ignore-mouse', ignore),
  getBackendUrl: () => 'http://localhost:8080',
  onActivateVoice: (callback) => ipcRenderer.on('activate-voice', callback),
  onActivateVoiceBackground: (callback) => ipcRenderer.on('activate-voice-background', callback),
  setVoiceBubble: (active) => ipcRenderer.send('voice-bubble', active),
});
