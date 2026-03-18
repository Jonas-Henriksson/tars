/**
 * Porcupine Wake Word Detection for TARS
 * Runs in Electron main process, sends IPC events on detection.
 */
const path = require('path');
const fs = require('fs');

let porcupine = null;
let recorder = null;
let isListening = false;

/**
 * Start wake word detection.
 * @param {object} opts
 * @param {string} opts.accessKey - Picovoice access key
 * @param {string} [opts.keywordPath] - Path to custom .ppn file (e.g. "Hey TARS")
 * @param {string} [opts.builtinKeyword] - Built-in keyword name fallback
 * @param {number} [opts.sensitivity=0.5] - Detection sensitivity 0.0-1.0
 * @param {function} opts.onDetected - Callback when wake word is detected
 */
async function start(opts) {
  if (isListening) return;

  const { Porcupine, BuiltinKeyword } = require('@picovoice/porcupine-node');
  const { PvRecorder } = require('@picovoice/pvrecorder-node');

  const sensitivity = opts.sensitivity || 0.5;

  // Determine keyword source
  let keywords, keywordPaths;
  if (opts.keywordPath && fs.existsSync(opts.keywordPath)) {
    keywordPaths = [opts.keywordPath];
    keywords = undefined;
    console.log(`Wake word: using custom model ${path.basename(opts.keywordPath)}`);
  } else if (opts.builtinKeyword) {
    keywords = [BuiltinKeyword[opts.builtinKeyword]];
    keywordPaths = undefined;
    console.log(`Wake word: using built-in keyword "${opts.builtinKeyword}"`);
  } else {
    console.log('Wake word: no keyword configured, skipping');
    return;
  }

  try {
    // Create Porcupine instance
    if (keywordPaths) {
      porcupine = new Porcupine(opts.accessKey, keywordPaths, [sensitivity]);
    } else {
      porcupine = new Porcupine(opts.accessKey, keywords, [sensitivity]);
    }

    // Create audio recorder with Porcupine's expected frame length
    recorder = new PvRecorder(porcupine.frameLength);
    recorder.start();
    isListening = true;
    console.log('Wake word listener active (Porcupine)');

    // Audio processing loop
    processLoop(opts.onDetected);
  } catch (err) {
    console.error('Wake word init error:', err.message);
    stop();
  }
}

async function processLoop(onDetected) {
  while (isListening && recorder && porcupine) {
    try {
      const pcm = await recorder.read();
      const keywordIndex = porcupine.process(pcm);
      if (keywordIndex >= 0) {
        console.log('Wake word detected!');
        onDetected(keywordIndex);
      }
    } catch (err) {
      if (isListening) {
        console.error('Wake word processing error:', err.message);
        await new Promise(r => setTimeout(r, 1000));
      }
    }
  }
}

function stop() {
  isListening = false;
  if (recorder) {
    try { recorder.stop(); } catch (e) {}
    try { recorder.release(); } catch (e) {}
    recorder = null;
  }
  if (porcupine) {
    try { porcupine.release(); } catch (e) {}
    porcupine = null;
  }
  console.log('Wake word listener stopped');
}

function getIsListening() {
  return isListening;
}

module.exports = { start, stop, getIsListening };
