/**
 * Command palette — Cmd+K style action launcher.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../store';
import {
  Search, CheckCircle2, Scale, Users, LayoutDashboard,
  Briefcase, Target, Settings, Sun, Moon, MessageSquare,
} from 'lucide-react';

interface PaletteAction {
  id: string;
  label: string;
  description?: string;
  icon: React.ReactNode;
  category: 'create' | 'navigate' | 'setting';
  action: () => void;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function CommandPalette({ open, onClose }: Props) {
  const navigate = useNavigate();
  const { darkMode, setDarkMode, toggleChat } = useStore();
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const actions: PaletteAction[] = [
    { id: 'create-task', label: 'Create Task', description: 'Add a new task to your work queue', icon: <CheckCircle2 size={16} />, category: 'create',
      action: () => { navigate('/work'); onClose(); } },
    { id: 'log-decision', label: 'Log Decision', description: 'Record a decision in the strategy log', icon: <Scale size={16} />, category: 'create',
      action: () => { navigate('/strategy?tab=decisions'); onClose(); } },
    { id: 'add-person', label: 'Add Person', description: 'Add a person to your network', icon: <Users size={16} />, category: 'create',
      action: () => { navigate('/people'); onClose(); } },
    { id: 'nav-home', label: 'Go to Command Center', icon: <LayoutDashboard size={16} />, category: 'navigate',
      action: () => { navigate('/'); onClose(); } },
    { id: 'nav-work', label: 'Go to Work', icon: <Briefcase size={16} />, category: 'navigate',
      action: () => { navigate('/work'); onClose(); } },
    { id: 'nav-strategy', label: 'Go to Strategy', icon: <Target size={16} />, category: 'navigate',
      action: () => { navigate('/strategy'); onClose(); } },
    { id: 'nav-people', label: 'Go to People', icon: <Users size={16} />, category: 'navigate',
      action: () => { navigate('/people'); onClose(); } },
    { id: 'nav-settings', label: 'Go to Settings', icon: <Settings size={16} />, category: 'navigate',
      action: () => { navigate('/settings'); onClose(); } },
    { id: 'toggle-dark', label: darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode', icon: darkMode ? <Sun size={16} /> : <Moon size={16} />, category: 'setting',
      action: () => { setDarkMode(!darkMode); onClose(); } },
    { id: 'open-chat', label: 'Open TARS Chat', icon: <MessageSquare size={16} />, category: 'setting',
      action: () => { toggleChat(); onClose(); } },
  ];

  const filtered = query
    ? actions.filter(a => a.label.toLowerCase().includes(query.toLowerCase()) || a.description?.toLowerCase().includes(query.toLowerCase()))
    : actions;

  // Reset state when opening
  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(i => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[activeIndex]) {
      e.preventDefault();
      filtered[activeIndex].action();
    } else if (e.key === 'Escape') {
      onClose();
    }
  }, [filtered, activeIndex, onClose]);

  // Reset active index when filter changes
  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (open) onClose();
        // Opening is handled by parent via state
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  const categoryLabels: Record<string, string> = { create: 'Create', navigate: 'Navigate', setting: 'Settings' };
  const groupedCategories = ['create', 'navigate', 'setting'].filter(cat => filtered.some(a => a.category === cat));

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)',
          zIndex: 9998, animation: 'fadeIn 0.15s ease',
        }}
      />

      {/* Palette */}
      <div
        style={{
          position: 'fixed', top: '20%', left: '50%', transform: 'translateX(-50%)',
          width: '100%', maxWidth: 520, zIndex: 9999,
          backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          overflow: 'hidden', animation: 'slideDown 0.15s ease',
        }}
        onKeyDown={handleKeyDown}
      >
        {/* Search input */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
          <Search size={18} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              flex: 1, border: 'none', outline: 'none', background: 'none',
              color: 'var(--text-primary)', fontSize: 15,
            }}
          />
          <kbd style={{
            fontSize: 10, padding: '2px 6px', borderRadius: 4,
            border: '1px solid var(--border)', color: 'var(--text-muted)',
          }}>ESC</kbd>
        </div>

        {/* Results */}
        <div style={{ maxHeight: 340, overflowY: 'auto', padding: '6px 0' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '20px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
              No matching commands
            </div>
          ) : (
            groupedCategories.map(cat => (
              <div key={cat}>
                <div style={{ padding: '6px 16px 4px', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {categoryLabels[cat]}
                </div>
                {filtered.filter(a => a.category === cat).map((action) => {
                  const globalIdx = filtered.indexOf(action);
                  const isActive = globalIdx === activeIndex;
                  return (
                    <div
                      key={action.id}
                      onClick={action.action}
                      onMouseEnter={() => setActiveIndex(globalIdx)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '8px 16px', cursor: 'pointer',
                        backgroundColor: isActive ? 'var(--accent-light)' : 'transparent',
                        color: isActive ? 'var(--accent)' : 'var(--text-primary)',
                        transition: 'background-color 0.08s',
                      }}
                    >
                      <span style={{ color: isActive ? 'var(--accent)' : 'var(--text-muted)', flexShrink: 0 }}>{action.icon}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{action.label}</div>
                        {action.description && (
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{action.description}</div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
