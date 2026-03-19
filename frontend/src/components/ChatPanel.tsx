/**
 * TARS Chat panel — collapsible right panel with streaming WebSocket chat.
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { useStore } from '../store';
import { createChatWebSocket } from '../api/client';
import { Send, X, Loader2, Wrench } from 'lucide-react';

export default function ChatPanel() {
  const {
    chatMessages, conversationId, isStreaming,
    addChatMessage, appendToLastMessage, setChatOpen,
    setConversationId, setIsStreaming,
  } = useStore();

  const [input, setInput] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => { scrollToBottom(); }, [chatMessages, scrollToBottom]);

  // WebSocket connection
  useEffect(() => {
    const ws = createChatWebSocket();

    ws.onopen = () => { wsRef.current = ws; };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'token':
          appendToLastMessage(data.content);
          break;
        case 'message_complete':
          setIsStreaming(false);
          if (data.conversation_id) setConversationId(data.conversation_id);
          break;
        case 'conversation_created':
          setConversationId(data.conversation_id);
          break;
        case 'tool_call':
          addChatMessage({
            role: 'system',
            content: `Using ${data.name}...`,
            toolCalls: [{ name: data.name, arguments: data.arguments }],
          });
          break;
        case 'tool_result':
          // Tool results are handled internally, just continue streaming
          break;
        case 'error':
          setIsStreaming(false);
          addChatMessage({ role: 'system', content: `Error: ${data.detail}` });
          break;
        case 'pong':
          break;
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      // Auto-reconnect after 3 seconds
      setTimeout(() => {
        if (!wsRef.current) {
          const newWs = createChatWebSocket();
          newWs.onopen = ws.onopen;
          newWs.onmessage = ws.onmessage;
          newWs.onclose = ws.onclose;
          newWs.onerror = ws.onerror;
        }
      }, 3000);
    };

    ws.onerror = () => { wsRef.current = null; };

    return () => { ws.close(); };
  }, []);

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current || isStreaming) return;

    const content = input.trim();
    setInput('');
    addChatMessage({ role: 'user', content });
    addChatMessage({ role: 'assistant', content: '' }); // Placeholder for streaming
    setIsStreaming(true);

    wsRef.current.send(JSON.stringify({
      type: 'message',
      content,
      conversation_id: conversationId,
    }));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div
      style={{
        width: 'var(--chat-width)',
        borderLeft: '1px solid var(--border)',
        backgroundColor: 'var(--bg-chat)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          height: 'var(--topbar-height)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>
          TARS Chat
        </div>
        <button
          onClick={() => setChatOpen(false)}
          style={{
            background: 'none', border: 'none',
            color: 'var(--text-muted)', cursor: 'pointer', padding: 4,
          }}
        >
          <X size={18} />
        </button>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflow: 'auto',
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        {chatMessages.length === 0 && (
          <div
            style={{
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: 13,
              padding: '40px 20px',
            }}
          >
            <div style={{ fontSize: 32, marginBottom: 12 }}>T</div>
            <p>Ask TARS anything about your work, tasks, calendar, or strategy.</p>
          </div>
        )}

        {chatMessages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                maxWidth: '85%',
                padding: '8px 12px',
                borderRadius: msg.role === 'user'
                  ? '12px 12px 2px 12px'
                  : '12px 12px 12px 2px',
                backgroundColor: msg.role === 'user'
                  ? 'var(--accent)'
                  : msg.role === 'system'
                    ? 'var(--bg-tertiary)'
                    : 'var(--bg-card)',
                color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
                fontSize: 13,
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                border: msg.role === 'assistant' ? '1px solid var(--border)' : 'none',
              }}
            >
              {msg.role === 'system' && msg.toolCalls && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)', fontSize: 12 }}>
                  <Wrench size={12} />
                  {msg.content}
                </div>
              )}
              {msg.role !== 'system' && (msg.content || (isStreaming && i === chatMessages.length - 1 && '...'))}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div
        style={{
          padding: '12px 16px',
          borderTop: '1px solid var(--border)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: 8,
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: '8px 12px',
          }}
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message TARS..."
            rows={1}
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              resize: 'none',
              background: 'none',
              color: 'var(--text-primary)',
              fontSize: 13,
              lineHeight: 1.5,
              maxHeight: 120,
              fontFamily: 'inherit',
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming}
            style={{
              padding: 6,
              border: 'none',
              borderRadius: 'var(--radius)',
              backgroundColor: input.trim() && !isStreaming ? 'var(--accent)' : 'var(--bg-tertiary)',
              color: input.trim() && !isStreaming ? '#fff' : 'var(--text-muted)',
              cursor: input.trim() && !isStreaming ? 'pointer' : 'default',
              flexShrink: 0,
            }}
          >
            {isStreaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}
