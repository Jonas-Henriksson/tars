/**
 * Reusable slide-over detail panel for viewing/editing items.
 */
import { useEffect, useRef, useState } from 'react';
import { X, Save, Edit3, Calendar, User, Tag, Flag, ExternalLink } from 'lucide-react';

export interface DetailField {
  key: string;
  label: string;
  value: string | string[] | number | boolean | undefined;
  type?: 'text' | 'select' | 'date' | 'tags' | 'textarea' | 'readonly' | 'link' | 'badge';
  options?: string[];
  color?: string;
}

interface DetailPanelProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  badge?: { label: string; color: string };
  fields: DetailField[];
  onSave?: (updates: Record<string, any>) => void;
  actions?: { label: string; onClick: () => void; variant?: 'primary' | 'danger' | 'ghost' }[];
}

export default function DetailPanel({ open, onClose, title, subtitle, badge, fields, onSave, actions }: DetailPanelProps) {
  const [editing, setEditing] = useState(false);
  const [edits, setEdits] = useState<Record<string, any>>({});
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setEditing(false);
      setEdits({});
    }
  }, [open, title]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    if (open) document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open) return null;

  const handleSave = () => {
    onSave?.(edits);
    setEditing(false);
    setEdits({});
  };

  const getFieldValue = (f: DetailField) => {
    return f.key in edits ? edits[f.key] : f.value;
  };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.4)',
          zIndex: 999, animation: 'fadeIn 0.15s ease',
        }}
      />
      {/* Panel */}
      <div
        ref={panelRef}
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0,
          width: 480, maxWidth: '90vw', backgroundColor: 'var(--bg-primary)',
          borderLeft: '1px solid var(--border)', zIndex: 1000,
          display: 'flex', flexDirection: 'column',
          boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
          animation: 'slideIn 0.2s ease',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '20px 24px 16px', borderBottom: '1px solid var(--border)',
          display: 'flex', flexDirection: 'column', gap: 8,
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.3 }}>{title}</h2>
              {subtitle && <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>{subtitle}</p>}
            </div>
            <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
              {onSave && !editing && (
                <button onClick={() => setEditing(true)} style={iconBtnStyle} title="Edit">
                  <Edit3 size={16} />
                </button>
              )}
              <button onClick={onClose} style={iconBtnStyle} title="Close">
                <X size={16} />
              </button>
            </div>
          </div>
          {badge && (
            <span style={{
              display: 'inline-flex', alignSelf: 'flex-start',
              fontSize: 12, fontWeight: 500, padding: '3px 10px', borderRadius: 12,
              backgroundColor: badge.color + '20', color: badge.color,
            }}>
              {badge.label}
            </span>
          )}
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {fields.map((f) => (
              <FieldRow key={f.key} field={f} editing={editing && f.type !== 'readonly' && f.type !== 'badge'}
                value={getFieldValue(f)}
                onChange={(v) => setEdits({ ...edits, [f.key]: v })}
              />
            ))}
          </div>
        </div>

        {/* Footer */}
        {(editing || actions) && (
          <div style={{
            padding: '16px 24px', borderTop: '1px solid var(--border)',
            display: 'flex', gap: 8, justifyContent: 'flex-end',
          }}>
            {editing ? (
              <>
                <button onClick={() => { setEditing(false); setEdits({}); }} style={ghostBtnStyle}>Cancel</button>
                <button onClick={handleSave} style={primaryBtnStyle}>
                  <Save size={14} /> Save Changes
                </button>
              </>
            ) : (
              actions?.map((a, i) => (
                <button key={i} onClick={a.onClick} style={
                  a.variant === 'primary' ? primaryBtnStyle :
                  a.variant === 'danger' ? dangerBtnStyle : ghostBtnStyle
                }>
                  {a.label}
                </button>
              ))
            )}
          </div>
        )}
      </div>

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </>
  );
}

function FieldRow({ field, editing, value, onChange }: {
  field: DetailField;
  editing: boolean;
  value: any;
  onChange: (v: any) => void;
}) {
  const iconMap: Record<string, React.ReactNode> = {
    owner: <User size={14} style={{ color: 'var(--text-muted)' }} />,
    status: <Flag size={14} style={{ color: 'var(--text-muted)' }} />,
    date: <Calendar size={14} style={{ color: 'var(--text-muted)' }} />,
    follow_up_date: <Calendar size={14} style={{ color: 'var(--text-muted)' }} />,
    priority: <Tag size={14} style={{ color: 'var(--text-muted)' }} />,
    quarter: <Calendar size={14} style={{ color: 'var(--text-muted)' }} />,
  };

  if (field.type === 'badge') {
    const color = field.color || 'var(--accent)';
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 100 }}>{field.label}</span>
        <span style={{
          fontSize: 12, fontWeight: 500, padding: '3px 10px', borderRadius: 12,
          backgroundColor: color + '20', color,
        }}>
          {String(value || '—').replace(/_/g, ' ')}
        </span>
      </div>
    );
  }

  if (field.type === 'link') {
    return (
      <div>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>{field.label}</span>
        {value ? (
          <a href={String(value)} target="_blank" rel="noreferrer"
            style={{ fontSize: 13, color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', gap: 4, textDecoration: 'none' }}>
            Open link <ExternalLink size={12} />
          </a>
        ) : <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>—</span>}
      </div>
    );
  }

  if (field.type === 'tags') {
    const tags = Array.isArray(value) ? value : [];
    return (
      <div>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>{field.label}</span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {tags.length === 0 ? (
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>—</span>
          ) : tags.map((t: string) => (
            <span key={t} style={{
              fontSize: 11, padding: '3px 8px', borderRadius: 8,
              backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-secondary)',
            }}>
              {t}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        {iconMap[field.key]}
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{field.label}</span>
      </div>
      {editing ? (
        field.type === 'select' && field.options ? (
          <select
            value={String(value || '')}
            onChange={(e) => onChange(e.target.value)}
            style={inputStyle}
          >
            {field.options.map((o) => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
          </select>
        ) : field.type === 'textarea' ? (
          <textarea
            value={String(value || '')}
            onChange={(e) => onChange(e.target.value)}
            rows={3}
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
          />
        ) : field.type === 'date' ? (
          <input
            type="date"
            value={String(value || '')}
            onChange={(e) => onChange(e.target.value)}
            style={inputStyle}
          />
        ) : (
          <input
            type="text"
            value={String(value || '')}
            onChange={(e) => onChange(e.target.value)}
            style={inputStyle}
          />
        )
      ) : (
        <div style={{ fontSize: 14, color: value ? 'var(--text-primary)' : 'var(--text-muted)', lineHeight: 1.5 }}>
          {String(value || '—').replace(/_/g, ' ')}
        </div>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', fontSize: 13,
  border: '1px solid var(--border)', borderRadius: 'var(--radius)',
  backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)',
  outline: 'none',
};

const iconBtnStyle: React.CSSProperties = {
  padding: 8, border: 'none', borderRadius: 'var(--radius)',
  backgroundColor: 'transparent', color: 'var(--text-muted)',
  cursor: 'pointer', display: 'flex', alignItems: 'center',
};

const primaryBtnStyle: React.CSSProperties = {
  padding: '8px 16px', border: 'none', borderRadius: 'var(--radius)',
  backgroundColor: 'var(--accent)', color: '#fff', fontSize: 13,
  fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
};

const ghostBtnStyle: React.CSSProperties = {
  padding: '8px 16px', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
  backgroundColor: 'transparent', color: 'var(--text-secondary)', fontSize: 13,
  cursor: 'pointer',
};

const dangerBtnStyle: React.CSSProperties = {
  padding: '8px 16px', border: 'none', borderRadius: 'var(--radius)',
  backgroundColor: 'var(--danger)', color: '#fff', fontSize: 13,
  fontWeight: 500, cursor: 'pointer',
};
