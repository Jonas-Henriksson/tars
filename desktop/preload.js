const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('tarsAPI', {
  expand: () => ipcRenderer.send('expand'),
  collapse: () => ipcRenderer.send('collapse'),
  dragMove: (deltaX, deltaY) => ipcRenderer.send('drag-move', { deltaX, deltaY }),
  getBackendUrl: () => 'http://localhost:8080',
});
