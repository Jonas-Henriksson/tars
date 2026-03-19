/**
 * Top bar — search, quick actions, notifications, chat toggle.
 */
import { useState, useEffect, useCallback } from 'react';
import { useStore } from '../store';
import {
  Search, Plus, Bell, MessageSquare, Sun, Moon,
} from 'lucide-react';
import CommandPalette from './CommandPalette';

export default function TopBar() {
  const { darkMode, setDarkMode, toggleChat, chatOpen } = useStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Global Cmd+K / Ctrl+K keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setPaletteOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const closePalette = useCallback(() => setPaletteOpen(false), []);

  return (
    <header
      style={{
        height: 'var(--topbar-height)',
        backgroundColor: 'var(--bg-primary)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: 12,
        flexShrink: 0,
      }}
    >
      {/* Search */}
      <div
        style={{
          flex: 1,
          maxWidth: 480,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '6px 12px',
        }}
      >
        <Search size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        <input
          type="text"
          placeholder="Search everything..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            flex: 1,
            border: 'none',
            outline: 'none',
            background: 'none',
            color: 'var(--text-primary)',
            fontSize: 14,
          }}
        />
        <kbd
          style={{
            fontSize: 11,
            padding: '2px 6px',
            borderRadius: 4,
            border: '1px solid var(--border)',
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          /
        </kbd>
      </div>

      <div style={{ flex: 1 }} />

      {/* Quick actions */}
      <button
        onClick={() => setPaletteOpen(true)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 12px',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          backgroundColor: 'var(--bg-primary)',
          color: 'var(--text-secondary)',
          fontSize: 13,
          cursor: 'pointer',
        }}
      >
        <Plus size={14} />
        Quick action
        <kbd style={{ fontSize: 10, padding: '1px 4px', borderRadius: 3, border: '1px solid var(--border)', color: 'var(--text-muted)', marginLeft: 2 }}>
          ⌘K
        </kbd>
      </button>

      {/* Dark mode toggle */}
      <button
        onClick={() => setDarkMode(!darkMode)}
        style={{
          padding: 8,
          border: 'none',
          borderRadius: 'var(--radius)',
          backgroundColor: 'transparent',
          color: 'var(--text-secondary)',
          cursor: 'pointer',
        }}
        title={darkMode ? 'Light mode' : 'Dark mode'}
      >
        {darkMode ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      {/* Notifications */}
      <button
        style={{
          position: 'relative',
          padding: 8,
          border: 'none',
          borderRadius: 'var(--radius)',
          backgroundColor: 'transparent',
          color: 'var(--text-secondary)',
          cursor: 'pointer',
        }}
      >
        <Bell size={18} />
        <span
          style={{
            position: 'absolute',
            top: 4,
            right: 4,
            width: 8,
            height: 8,
            borderRadius: '50%',
            backgroundColor: 'var(--danger)',
          }}
        />
      </button>

      {/* Chat toggle */}
      <button
        onClick={toggleChat}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 12px',
          border: 'none',
          borderRadius: 'var(--radius)',
          backgroundColor: chatOpen ? 'var(--accent)' : 'var(--accent-light)',
          color: chatOpen ? '#fff' : 'var(--accent)',
          fontSize: 13,
          fontWeight: 500,
          cursor: 'pointer',
          transition: 'all 0.15s',
        }}
      >
        <MessageSquare size={16} />
        TARS
      </button>

      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </header>
  );
}
