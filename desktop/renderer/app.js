(function() {
    'use strict';

    const BACKEND = (window.tarsAPI && window.tarsAPI.getBackendUrl()) || 'http://localhost:8080';
    const CHAT_ID = 0; // Desktop session

    // ── State ───────────────────────────────────────────────────────

    let isExpanded = false;
    let isConnected = false;
    let isVoiceActive = false;
    let pc = null;   // RTCPeerConnection
    let dc = null;   // RTCDataChannel
    let audioEl = null;
    let micStream = null;

    // ── DOM refs ────────────────────────────────────────────────────

    const bubble = document.getElementById('bubble');
    const chat = document.getElementById('chat');
    const statusDot = document.getElementById('statusDot');
    const messages = document.getElementById('messages');
    const msgInput = document.getElementById('msgInput');
    const sendBtn = document.getElementById('sendBtn');
    const collapseBtn = document.getElementById('collapseBtn');
    const voiceBtn = document.getElementById('voiceBtn');
    const attachBtn = document.getElementById('attachBtn');
    const fileInput = document.getElementById('fileInput');
    const noteBtn = document.getElementById('noteBtn');
    const noteModal = document.getElementById('noteModal');
    const noteText = document.getElementById('noteText');
    const noteSaveBtn = document.getElementById('noteSaveBtn');
    const noteCancelBtn = document.getElementById('noteCancelBtn');
    const modelSelect = document.getElementById('modelSelect');
    const searchToggle = document.getElementById('searchToggle');

    // ── Bubble drag + click ──────────────────────────────────────────
    // Manual drag so clicks still work (webkit-app-region: drag blocks clicks)
    let dragState = null;
    bubble.addEventListener('mousedown', (e) => {
        dragState = { startX: e.screenX, startY: e.screenY, moved: false };
    });
    window.addEventListener('mousemove', (e) => {
        if (!dragState) return;
        const dx = e.screenX - dragState.startX;
        const dy = e.screenY - dragState.startY;
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragState.moved = true;
        if (dragState.moved && window.tarsAPI) {
            window.tarsAPI.dragMove(dx, dy);
            dragState.startX = e.screenX;
            dragState.startY = e.screenY;
        }
    });
    window.addEventListener('mouseup', () => {
        if (dragState && !dragState.moved) expand();
        dragState = null;
    });

    // ── Expand / Collapse ───────────────────────────────────────────


    function expand() {
        if (window.tarsAPI) window.tarsAPI.expand();
        bubble.classList.add('hidden');
        chat.classList.remove('hidden');
        // Trigger CSS transition
        requestAnimationFrame(() => chat.classList.add('visible'));
        isExpanded = true;
        msgInput.focus();
    }

    collapseBtn.addEventListener('click', () => {
        chat.classList.remove('visible');
        setTimeout(() => {
            chat.classList.add('hidden');
            bubble.classList.remove('hidden');
            if (window.tarsAPI) window.tarsAPI.collapse();
            isExpanded = false;
        }, 150);
    });

    // ── Chat ────────────────────────────────────────────────────────

    sendBtn.addEventListener('click', sendMessage);
    msgInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });

    async function sendMessage() {
        const text = msgInput.value.trim();
        if (!text) return;
        msgInput.value = '';

        appendMsg('user', text);
        const thinkingId = appendMsg('assistant', '<span class="thinking">Thinking...</span>', true);

        try {
            const body = {
                message: searchToggle.checked ? '[web search enabled] ' + text : text,
                chat_id: CHAT_ID,
                model: modelSelect.value,
            };

            const resp = await fetch(BACKEND + '/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            const data = await resp.json();
            removeMsg(thinkingId);

            if (data.error) {
                appendMsg('assistant', 'Error: ' + esc(data.error));
            } else {
                appendMsg('assistant', renderMarkdown(data.reply));
            }
        } catch (err) {
            removeMsg(thinkingId);
            appendMsg('assistant', 'Connection error: ' + esc(err.message));
        }
    }

    let msgCounter = 0;

    function appendMsg(role, html, isRaw) {
        const id = 'msg-' + (++msgCounter);
        const div = document.createElement('div');
        div.className = 'msg ' + role;
        div.id = id;
        if (isRaw) {
            div.innerHTML = html;
        } else {
            div.innerHTML = html;
        }
        // Timestamp
        const time = document.createElement('div');
        time.className = 'msg-time';
        time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        div.appendChild(time);

        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
        return id;
    }

    function removeMsg(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    // ── Simple Markdown Renderer ────────────────────────────────────

    function renderMarkdown(text) {
        if (!text) return '';
        let html = esc(text);

        // Code blocks (``` ... ```)
        html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Italic
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        // Bullet lists
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
        // Line breaks
        html = html.replace(/\n/g, '<br>');
        // Clean up <br> inside <pre>
        html = html.replace(/<pre><code>([\s\S]*?)<\/code><\/pre>/g, (match, code) => {
            return '<pre><code>' + code.replace(/<br>/g, '\n') + '</code></pre>';
        });

        return html;
    }

    function esc(s) {
        if (!s) return '';
        const el = document.createElement('span');
        el.textContent = s;
        return el.innerHTML;
    }

    // ── File Upload ─────────────────────────────────────────────────

    attachBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', async () => {
        for (const file of fileInput.files) {
            const formData = new FormData();
            formData.append('file', file);

            appendMsg('system', 'Uploading ' + esc(file.name) + '...');

            try {
                const resp = await fetch(BACKEND + '/api/upload', {
                    method: 'POST',
                    body: formData,
                });
                const data = await resp.json();
                if (data.ok) {
                    appendMsg('system', 'Uploaded: ' + esc(data.filename) + ' (' + formatSize(data.size) + ')');
                } else {
                    appendMsg('system', 'Upload failed: ' + esc(data.error || 'Unknown error'));
                }
            } catch (err) {
                appendMsg('system', 'Upload error: ' + esc(err.message));
            }
        }
        fileInput.value = '';
    });

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    }

    // ── Quick Notes ─────────────────────────────────────────────────

    noteBtn.addEventListener('click', () => {
        noteModal.classList.remove('hidden');
        noteText.value = '';
        noteText.focus();
    });

    noteCancelBtn.addEventListener('click', () => noteModal.classList.add('hidden'));

    noteSaveBtn.addEventListener('click', async () => {
        const text = noteText.value.trim();
        if (!text) return;
        noteModal.classList.add('hidden');

        try {
            await fetch(BACKEND + '/api/memory/note', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text }),
            });
            appendMsg('system', 'Note saved.');
        } catch (err) {
            appendMsg('system', 'Failed to save note: ' + esc(err.message));
        }
    });

    noteText.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) noteSaveBtn.click();
        if (e.key === 'Escape') noteCancelBtn.click();
    });

    // ── Voice (WebRTC to OpenAI Realtime API) ───────────────────────

    voiceBtn.addEventListener('click', toggleVoice);

    async function toggleVoice() {
        if (isVoiceActive) {
            hangupVoice();
        } else {
            await startVoice();
        }
    }

    async function startVoice() {
        voiceBtn.classList.add('active');
        isVoiceActive = true;
        bubble.classList.add('voice-active');
        // Voice session starting

        try {
            // Get token
            const tokenResp = await fetch(BACKEND + '/api/token');
            const tokenData = await tokenResp.json();
            if (tokenData.error) throw new Error(tokenData.error);

            // WebRTC setup
            pc = new RTCPeerConnection();

            audioEl = document.createElement('audio');
            audioEl.autoplay = true;
            pc.ontrack = (e) => { audioEl.srcObject = e.streams[0]; };

            micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            micStream.getTracks().forEach(track => pc.addTrack(track, micStream));

            // Data channel for events
            dc = pc.createDataChannel('oai-events');
            dc.onmessage = (e) => {
                const event = JSON.parse(e.data);
                handleRealtimeEvent(event);
            };

            // SDP exchange with OpenAI
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            const sdpResp = await fetch(
                'https://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview',
                {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + tokenData.token,
                        'Content-Type': 'application/sdp',
                    },
                    body: offer.sdp,
                }
            );

            if (!sdpResp.ok) throw new Error('OpenAI returned ' + sdpResp.status);

            const answer = { type: 'answer', sdp: await sdpResp.text() };
            await pc.setRemoteDescription(answer);

            appendMsg('system', 'Voice connected. Listening...');

            pc.onconnectionstatechange = () => {
                if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
                    hangupVoice();
                }
            };

        } catch (err) {
            appendMsg('system', 'Voice error: ' + esc(err.message));
            hangupVoice();
        }
    }

    function hangupVoice() {
        if (pc) { pc.close(); pc = null; }
        if (dc) { dc = null; }
        if (audioEl) { audioEl.srcObject = null; audioEl = null; }
        if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
        voiceBtn.classList.remove('active');
        bubble.classList.remove('voice-active');
        isVoiceActive = false;
    }

    // ── Realtime Event Handling (tool calls) ────────────────────────

    const pendingCalls = {};

    function handleRealtimeEvent(event) {
        switch (event.type) {
            case 'response.function_call_arguments.delta': {
                const callId = event.call_id;
                if (!pendingCalls[callId]) pendingCalls[callId] = { name: event.name || '', args: '' };
                if (event.name) pendingCalls[callId].name = event.name;
                pendingCalls[callId].args += event.delta || '';
                break;
            }
            case 'response.function_call_arguments.done':
                handleFunctionCall(event.call_id, event.name, event.arguments);
                break;
            case 'error':
                console.error('Realtime error:', event.error);
                break;
        }
    }

    async function handleFunctionCall(callId, name, argsStr) {
        try {
            const resp = await fetch(BACKEND + '/api/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, arguments: JSON.parse(argsStr || '{}') }),
            });

            const data = await resp.json();
            const output = data.error
                ? JSON.stringify({ error: data.error })
                : JSON.stringify(data.result);

            if (dc && dc.readyState === 'open') {
                dc.send(JSON.stringify({
                    type: 'conversation.item.create',
                    item: { type: 'function_call_output', call_id: callId, output },
                }));
                dc.send(JSON.stringify({ type: 'response.create' }));
            }
        } catch (err) {
            console.error('Tool call failed:', err);
        }
        delete pendingCalls[callId];
    }

    // ── Voice Activation (global shortcut: Ctrl+Shift+T) ───────────

    function activateVoice() {
        // Say "What's up?" acknowledgment
        if ('speechSynthesis' in window) {
            const utter = new SpeechSynthesisUtterance("What's up?");
            utter.rate = 1.1;
            utter.pitch = 0.9;
            utter.volume = 0.8;
            speechSynthesis.speak(utter);
        }

        // Expand chat if in bubble mode
        if (!isExpanded) expand();

        // Start voice session
        setTimeout(() => {
            if (!isVoiceActive) startVoice();
        }, 500);
    }

    // Listen for global shortcut from main process (expands + voice)
    if (window.tarsAPI && window.tarsAPI.onActivateVoice) {
        window.tarsAPI.onActivateVoice(() => activateVoice());
    }

    // Listen for wake word (voice only, stay in bubble mode)
    if (window.tarsAPI && window.tarsAPI.onActivateVoiceBackground) {
        window.tarsAPI.onActivateVoiceBackground(() => {
            // Say "What's up?" acknowledgment
            if ('speechSynthesis' in window) {
                const utter = new SpeechSynthesisUtterance("What's up?");
                utter.rate = 1.1;
                utter.pitch = 0.9;
                utter.volume = 0.8;
                speechSynthesis.speak(utter);
            }
            // Start voice without expanding — bubble pulses to show active
            setTimeout(() => {
                if (!isVoiceActive) startVoice();
            }, 500);
        });
    }

    // ── Backend Health Check ────────────────────────────────────────

    async function checkHealth() {
        try {
            const resp = await fetch(BACKEND + '/api/settings/status', { signal: AbortSignal.timeout(3000) });
            if (resp.ok) {
                isConnected = true;
                statusDot.classList.add('connected');
                statusDot.title = 'Connected to TARS';
            } else {
                throw new Error();
            }
        } catch {
            isConnected = false;
            statusDot.classList.remove('connected');
            statusDot.title = 'TARS backend not running';
        }
    }

    // ── Init ────────────────────────────────────────────────────────

    checkHealth();
    setInterval(checkHealth, 10000);

    // Welcome message
    appendMsg('assistant', renderMarkdown('**TARS ready.** Type a message, say **"Hey TARS"**, or press **Ctrl+Shift+T** for voice.'));

})();
