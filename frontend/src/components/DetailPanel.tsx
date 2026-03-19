/**
 * Reusable slide-over detail panel for viewing/editing items.
 *
 * Fields with type 'select', 'date', 'badge' are inline-editable on click.
 * 'expandable' fields show a truncated preview that expands on click.
 */
import { useEffect, useRef, useState } from 'react';
import { X, Save, Edit3, Calendar, User, Tag, Flag, ExternalLink, ChevronDown, ChevronRight, Clock, Plus, Check } from 'lucide-react';

/** Capitalize first letter and replace underscores with spaces */
function displayValue(v: string): string {
  const s = v.replace(/_/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export interface DetailField {
  key: string;
  label: string;
  value: string | string[] | number | boolean | undefined;
  type?: 'text' | 'select' | 'date' | 'tags' | 'textarea' | 'readonly' | 'link' | 'badge' | 'expandable';
  options?: string[];
  color?: string;
  /** Tooltip or helper text shown below the label */
  hint?: string;
  /** For 'expandable' type: formatted content lines */
  lines?: string[];
  /** For 'expandable' type: action button on each line (e.g. "Convert to task") */
  lineAction?: { label: string; icon?: 'plus'; onAction: (line: string) => void };
  /** For 'expandable' type: remove button on each line */
  lineRemove?: { label: string; onRemove: (lineIndex: number) => void };
}

interface DetailPanelProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  badge?: { label: string; color: string };
  fields: DetailField[];
  onSave?: (updates: Record<string, any>) => void;
  onFieldChange?: (key: string, value: any) => void;
  actions?: { label: string; onClick: () => void; variant?: 'primary' | 'danger' | 'ghost' }[];
  children?: React.ReactNode;
}

export default function DetailPanel({ open, onClose, title, subtitle, badge, fields, onSave, onFieldChange, actions, children }: DetailPanelProps) {
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

  const handleInlineChange = (key: string, value: any) => {
    if (onFieldChange) {
      onFieldChange(key, value);
    } else {
      setEdits({ ...edits, [key]: value });
      onSave?.({ [key]: value });
    }
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
              <FieldRow key={f.key} field={f}
                editing={editing && f.type !== 'readonly' && f.type !== 'badge' && f.type !== 'expandable'}
                value={getFieldValue(f)}
                onChange={(v) => setEdits({ ...edits, [f.key]: v })}
                onInlineChange={(v) => handleInlineChange(f.key, v)}
              />
            ))}
          </div>
          {children}
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

/** Editable tag list — click X to remove, type to add new items */
function EditableTagList({ field, tags, onInlineChange }: {
  field: DetailField; tags: string[];
  onInlineChange: (value: any) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [newTag, setNewTag] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (adding && inputRef.current) inputRef.current.focus();
  }, [adding]);

  const addTag = () => {
    const val = newTag.trim();
    if (val && !tags.includes(val)) {
      onInlineChange([...tags, val]);
    }
    setNewTag('');
    setAdding(false);
  };

  const removeTag = (idx: number) => {
    onInlineChange(tags.filter((_, i) => i !== idx));
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{field.label}</span>
        {field.hint && <span title={field.hint} style={{ fontSize: 11, color: 'var(--text-muted)', cursor: 'help' }}>ⓘ</span>}
      </div>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
        {tags.length === 0 && !adding && (
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>—</span>
        )}
        {tags.map((t, i) => (
          <span key={`${t}-${i}`} style={{
            fontSize: 11, padding: '3px 6px 3px 8px', borderRadius: 8,
            backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-secondary)',
            display: 'inline-flex', alignItems: 'center', gap: 4,
          }}>
            {t}
            <button
              onClick={() => removeTag(i)}
              style={{
                border: 'none', background: 'none', cursor: 'pointer',
                color: 'var(--text-muted)', padding: 0, display: 'flex',
                alignItems: 'center', fontSize: 13, lineHeight: 1,
              }}
              title="Remove"
            >
              ×
            </button>
          </span>
        ))}
        {adding ? (
          <input
            ref={inputRef}
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') addTag();
              if (e.key === 'Escape') { setAdding(false); setNewTag(''); }
            }}
            onBlur={addTag}
            placeholder="Type and press Enter"
            style={{
              fontSize: 11, padding: '3px 8px', borderRadius: 8,
              border: '1px solid var(--accent)', backgroundColor: 'var(--bg-secondary)',
              color: 'var(--text-primary)', outline: 'none', width: 160,
            }}
          />
        ) : (
          <button
            onClick={() => setAdding(true)}
            style={{
              fontSize: 11, padding: '3px 8px', borderRadius: 8,
              border: '1px dashed var(--border)', background: 'none',
              color: 'var(--text-muted)', cursor: 'pointer',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-muted)'; }}
          >
            + Add
          </button>
        )}
      </div>
    </div>
  );
}

function FieldRow({ field, editing, value, onChange, onInlineChange }: {
  field: DetailField;
  editing: boolean;
  value: any;
  onChange: (v: any) => void;
  onInlineChange: (v: any) => void;
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [convertedLines, setConvertedLines] = useState<Set<number>>(new Set());
  const [removedLines, setRemovedLines] = useState<Set<number>>(new Set());
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!dropdownOpen) return;
    function close(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) setDropdownOpen(false);
    }
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [dropdownOpen]);

  const iconMap: Record<string, React.ReactNode> = {
    owner: <User size={14} style={{ color: 'var(--text-muted)' }} />,
    status: <Flag size={14} style={{ color: 'var(--text-muted)' }} />,
    date: <Calendar size={14} style={{ color: 'var(--text-muted)' }} />,
    follow_up_date: <Calendar size={14} style={{ color: 'var(--text-muted)' }} />,
    priority: <Tag size={14} style={{ color: 'var(--text-muted)' }} />,
    quarter: <Calendar size={14} style={{ color: 'var(--text-muted)' }} />,
    source_title: <Clock size={14} style={{ color: 'var(--text-muted)' }} />,
  };

  // Expandable field (for Context, Next Steps)
  if (field.type === 'expandable') {
    const text = String(value || '');
    const lines = field.lines || (text ? text.split(/\n|(?:\s*\[\s*\]\s*)/).filter(Boolean) : []);
    const hasContent = lines.length > 0 && lines.some(l => l.trim());
    return (
      <div>
        <div
          onClick={() => hasContent && setExpanded(!expanded)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4,
            cursor: hasContent ? 'pointer' : 'default', userSelect: 'none',
          }}
        >
          {hasContent && (expanded ?
            <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} /> :
            <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />
          )}
          {iconMap[field.key]}
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{field.label}</span>
          {hasContent && !expanded && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
              {lines.length} item{lines.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        {!hasContent && (
          <div style={{ fontSize: 13, color: 'var(--text-muted)', paddingLeft: 20 }}>—</div>
        )}
        {hasContent && expanded && (
          <div style={{
            paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4,
          }}>
            {lines.map((line, i) => {
              const trimmed = line.trim();
              if (!trimmed || removedLines.has(i)) return null;
              const numMatch = trimmed.match(/^(\d+)[.)]\s*(.*)/);
              const displayText = numMatch ? numMatch[2] : trimmed;
              const isConverted = convertedLines.has(i);
              return (
                <div key={i} style={{
                  fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5,
                  padding: '6px 10px',
                  backgroundColor: isConverted ? 'var(--accent-light)' : 'var(--bg-secondary)',
                  borderRadius: 'var(--radius)',
                  borderLeft: `2px solid ${isConverted ? 'var(--success)' : 'var(--border)'}`,
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ flex: 1 }}>
                    {numMatch && (
                      <span style={{ fontWeight: 600, color: 'var(--accent)', marginRight: 6 }}>{numMatch[1]}.</span>
                    )}
                    {displayText}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}>
                    {field.lineAction && (
                      isConverted ? (
                        <Check size={14} style={{ color: 'var(--success)' }} />
                      ) : (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            field.lineAction!.onAction(displayText);
                            setConvertedLines(prev => new Set(prev).add(i));
                          }}
                          title={field.lineAction.label}
                          style={lineActionBtnStyle}
                          onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent)'}
                          onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
                        >
                          <Plus size={14} />
                        </button>
                      )
                    )}
                    {field.lineRemove && !isConverted && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setRemovedLines(prev => new Set(prev).add(i));
                          field.lineRemove!.onRemove(i);
                        }}
                        title={field.lineRemove.label}
                        style={lineActionBtnStyle}
                        onMouseEnter={(e) => e.currentTarget.style.color = 'var(--danger)'}
                        onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {hasContent && !expanded && (
          <div style={{
            fontSize: 13, color: 'var(--text-secondary)', paddingLeft: 20,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {lines[0]?.trim().slice(0, 80)}{(lines[0]?.trim().length || 0) > 80 ? '...' : ''}
          </div>
        )}
      </div>
    );
  }

  // Inline-clickable badge (select, classification, source, etc.)
  if (field.type === 'badge') {
    const color = field.color || 'var(--accent)';
    const hasOptions = field.options && field.options.length > 0;
    return (
      <div style={{ position: 'relative' }} ref={dropdownRef}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 100 }}>{field.label}</span>
          <span
            onClick={() => hasOptions && setDropdownOpen(!dropdownOpen)}
            style={{
              fontSize: 12, fontWeight: 500, padding: '3px 10px', borderRadius: 12,
              backgroundColor: color + '20', color,
              cursor: hasOptions ? 'pointer' : 'default',
              transition: 'filter 0.1s',
            }}
            onMouseEnter={(e) => { if (hasOptions) e.currentTarget.style.filter = 'brightness(1.2)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.filter = 'none'; }}
          >
            {displayValue(String(value || '—'))}
            {hasOptions && <ChevronDown size={10} style={{ marginLeft: 4, verticalAlign: 'middle' }} />}
          </span>
          {field.hint && <span style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>{field.hint}</span>}
        </div>
        {dropdownOpen && hasOptions && (
          <div style={dropdownStyle}>
            {field.options!.map((o) => (
              <div
                key={o}
                onClick={() => { onInlineChange(o); setDropdownOpen(false); }}
                style={{
                  ...dropdownItemStyle,
                  fontWeight: String(value) === o ? 600 : 400,
                  backgroundColor: String(value) === o ? 'var(--bg-hover)' : 'transparent',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = String(value) === o ? 'var(--bg-hover)' : 'transparent'}
              >
                {displayValue(o)}
              </div>
            ))}
          </div>
        )}
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
    return <EditableTagList field={field} tags={tags} onInlineChange={onInlineChange} />;
  }

  // Inline-clickable select (Status, Owner, Priority, Quarter)
  if (field.type === 'select' && field.options && !editing) {
    return (
      <div style={{ position: 'relative' }} ref={dropdownRef}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          {iconMap[field.key]}
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{field.label}</span>
          {field.hint && <span title={field.hint} style={{ fontSize: 11, color: 'var(--text-muted)', cursor: 'help' }}>ⓘ</span>}
        </div>
        <div
          onClick={() => setDropdownOpen(!dropdownOpen)}
          style={{
            fontSize: 14, color: value ? 'var(--text-primary)' : 'var(--text-muted)',
            cursor: 'pointer', padding: '6px 10px',
            borderRadius: 'var(--radius)', border: '1px solid transparent',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            transition: 'border-color 0.1s, background-color 0.1s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)';
            e.currentTarget.style.backgroundColor = 'var(--bg-secondary)';
          }}
          onMouseLeave={(e) => {
            if (!dropdownOpen) {
              e.currentTarget.style.borderColor = 'transparent';
              e.currentTarget.style.backgroundColor = 'transparent';
            }
          }}
        >
          <span>{displayValue(String(value || '—'))}</span>
          <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
        </div>
        {dropdownOpen && (
          <div style={dropdownStyle}>
            {field.options.map((o) => (
              <div
                key={o || '__empty__'}
                onClick={() => { onInlineChange(o); setDropdownOpen(false); }}
                style={{
                  ...dropdownItemStyle,
                  fontWeight: String(value) === o ? 600 : 400,
                  backgroundColor: String(value) === o ? 'var(--bg-hover)' : 'transparent',
                  fontStyle: o === '' ? 'italic' : 'normal',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = String(value) === o ? 'var(--bg-hover)' : 'transparent'}
              >
                {o === '' ? 'Not set' : displayValue(o)}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Inline date picker
  if (field.type === 'date' && !editing) {
    return (
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          {iconMap[field.key]}
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{field.label}</span>
        </div>
        <input
          type="date"
          value={String(value || '')}
          onChange={(e) => onInlineChange(e.target.value)}
          style={{
            ...inputStyle,
            cursor: 'pointer',
            backgroundColor: 'transparent',
            border: '1px solid transparent',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)';
            e.currentTarget.style.backgroundColor = 'var(--bg-secondary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'transparent';
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
        />
      </div>
    );
  }

  // Standard field rendering
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
            {field.options.map((o) => <option key={o} value={o}>{displayValue(o)}</option>)}
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
          {displayValue(String(value || '—'))}
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

const dropdownStyle: React.CSSProperties = {
  position: 'absolute', top: '100%', left: 0, right: 0,
  backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius)', boxShadow: 'var(--shadow-lg)',
  zIndex: 50, marginTop: 4, maxHeight: 200, overflow: 'auto',
};

const dropdownItemStyle: React.CSSProperties = {
  padding: '8px 12px', fontSize: 13, color: 'var(--text-primary)',
  cursor: 'pointer', transition: 'background-color 0.1s',
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

const lineActionBtnStyle: React.CSSProperties = {
  border: 'none', background: 'none', cursor: 'pointer',
  color: 'var(--text-muted)', padding: 2, borderRadius: 4,
  display: 'flex', alignItems: 'center',
  transition: 'color 0.1s',
};

const dangerBtnStyle: React.CSSProperties = {
  padding: '8px 16px', border: 'none', borderRadius: 'var(--radius)',
  backgroundColor: 'var(--danger)', color: '#fff', fontSize: 13,
  fontWeight: 500, cursor: 'pointer',
};
