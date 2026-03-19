/**
 * Work page — Eisenhower matrix, Kanban board, task list, timeline.
 */
import { useEffect, useState, useCallback } from 'react';
import { useStore } from '../store';
import { getTheme } from '../themes';
import { api } from '../api/client';
import { Grid3x3, Columns3, List, GanttChart, ChevronDown, ChevronUp, Search } from 'lucide-react';
import DetailPanel from '../components/DetailPanel';
import type { DetailField } from '../components/DetailPanel';

type TabId = 'matrix' | 'board' | 'list' | 'timeline';

interface SmartTask {
  id: string;
  description: string;
  owner: string;
  status: string;
  priority?: { quadrant: number; label: string };
  quadrant?: number;
  quadrant_label?: string;
  follow_up_date?: string;
  topic?: string;
  topics?: string[];
  source_title?: string;
  source_url?: string;
  source_context?: string;
  age_days?: number;
  steps?: string;
  delegated?: boolean;
  story_id?: string;
  classification?: string;
  manual_override?: boolean;
  confidence?: number;
  source?: string;
}

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'matrix', label: 'Matrix', icon: <Grid3x3 size={16} /> },
  { id: 'board', label: 'Board', icon: <Columns3 size={16} /> },
  { id: 'list', label: 'List', icon: <List size={16} /> },
  { id: 'timeline', label: 'Timeline', icon: <GanttChart size={16} /> },
];

const QUADRANT_LABELS: Record<number, { name: string; color: string }> = {
  1: { name: 'Do First', color: '#ef4444' },
  2: { name: 'Schedule', color: '#3b82f6' },
  3: { name: 'Delegate', color: '#f59e0b' },
  4: { name: 'Defer', color: '#94a3b8' },
};

const BOARD_COLUMNS = [
  { id: 'backlog', label: 'Open', color: '#94a3b8' },
  { id: 'in_progress', label: 'In Progress', color: '#3b82f6' },
  { id: 'done', label: 'Done', color: '#22c55e' },
];

function getTaskQuadrant(t: SmartTask): number {
  return t.priority?.quadrant || t.quadrant || 4;
}

function getTaskPhase(t: SmartTask): string {
  const s = t.status?.toLowerCase();
  if (s === 'done' || s === 'completed') return 'done';
  if (s === 'in_progress' || s === 'in progress' || s === 'active') return 'in_progress';
  return 'backlog';
}

export default function Work() {
  const { themeId } = useStore();
  const theme = getTheme(themeId);
  const [tab, setTab] = useState<TabId>(theme.layout.defaultWorkTab);
  const [tasks, setTasks] = useState<SmartTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState<SmartTask | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    api.get<any>('/api/intel/tasks').then((data) => {
      setTasks(data.tasks || data.smart_tasks || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleTaskClick = useCallback((task: SmartTask) => {
    setSelectedTask(task);
  }, []);

  const handleTaskSave = useCallback((updates: Record<string, any>) => {
    if (!selectedTask) return;
    // Map display values back to data values
    const mapped: Record<string, any> = { ...updates };
    if ('priority' in mapped) {
      const qMap: Record<string, number> = { 'Do First': 1, 'Schedule': 2, 'Delegate': 3, 'Defer': 4 };
      mapped.quadrant = qMap[mapped.priority] || 4;
      delete mapped.priority;
    }
    // Update local state optimistically
    setTasks((prev) => prev.map((t) =>
      t.id === selectedTask.id ? { ...t, ...mapped } : t
    ));
    setSelectedTask((prev) => prev ? { ...prev, ...mapped } : null);
    // Try API update (fire and forget)
    api.patch<any>(`/api/intel/tasks/${selectedTask.id}`, mapped).catch(() => {});
  }, [selectedTask]);

  const handleFieldChange = useCallback((key: string, value: any) => {
    handleTaskSave({ [key]: value });
  }, [handleTaskSave]);

  const handleDragDrop = useCallback((taskId: string, newPhase: string) => {
    const statusMap: Record<string, string> = {
      backlog: 'open', in_progress: 'in_progress', done: 'done',
    };
    setTasks((prev) => prev.map((t) =>
      t.id === taskId ? { ...t, status: statusMap[newPhase] || newPhase } : t
    ));
    api.patch<any>(`/api/intel/tasks/${taskId}`, { status: statusMap[newPhase] || newPhase }).catch(() => {});
  }, []);

  // Build owner options sorted by frequency (most assigned first)
  const ownerFrequency = tasks.reduce<Record<string, number>>((acc, t) => {
    if (t.owner) acc[t.owner] = (acc[t.owner] || 0) + 1;
    return acc;
  }, {});
  const ownerOptions = Object.entries(ownerFrequency)
    .sort((a, b) => b[1] - a[1])
    .map(([name]) => name);

  // Format meeting source timestamp
  const formatMeetingSource = (src: string | undefined): string => {
    if (!src) return '—';
    // Try to extract ISO date from the string
    const isoMatch = src.match(/(\d{4}-\d{2}-\d{2}T[\d:.]+(?:[+-]\d{2}:\d{2})?)/);
    if (isoMatch) {
      const date = new Date(isoMatch[1]);
      const dateStr = date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
      const timeStr = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
      const meetingName = src.replace(isoMatch[0], '').replace(/\s*$/, '').replace(/\s+/g, ' ').trim();
      return meetingName ? `${meetingName} · ${dateStr} at ${timeStr}` : `${dateStr} at ${timeStr}`;
    }
    return src;
  };

  // Parse context into structured lines
  const parseContextLines = (ctx: string | undefined): string[] => {
    if (!ctx) return [];
    // Split on [ ] markers used by Notion or newlines
    return ctx.split(/\[\s*\]|\n/).map(s => s.trim()).filter(Boolean);
  };

  // Parse steps into structured lines
  const parseStepLines = (steps: string | undefined): string[] => {
    if (!steps) return [];
    return steps.split(/\n/).map(s => s.trim()).filter(Boolean);
  };

  const classificationColors: Record<string, string> = {
    strategic: '#3b82f6', operational: '#f59e0b', unclassified: '#94a3b8',
  };

  const taskFields: DetailField[] = selectedTask ? [
    { key: 'status', label: 'Status', value: selectedTask.status, type: 'select',
      options: ['open', 'in_progress', 'done'] },
    { key: 'owner', label: 'Owner', value: selectedTask.owner, type: 'select',
      options: ownerOptions },
    { key: 'priority', label: 'Priority', value: QUADRANT_LABELS[getTaskQuadrant(selectedTask)]?.name, type: 'select',
      options: ['Do First', 'Schedule', 'Delegate', 'Defer'], color: QUADRANT_LABELS[getTaskQuadrant(selectedTask)]?.color },
    { key: 'follow_up_date', label: 'Follow-up Date', value: selectedTask.follow_up_date, type: 'date' },
    { key: 'classification', label: 'Classification', value: selectedTask.classification || 'unclassified', type: 'badge',
      options: ['strategic', 'operational', 'unclassified'],
      color: classificationColors[selectedTask.classification || 'unclassified'],
      hint: 'How TARS categorizes this task' },
    { key: 'source', label: 'Source', value: selectedTask.source === 'auto' ? 'auto' : 'confirmed', type: 'badge',
      options: ['confirmed', 'auto'],
      color: selectedTask.source === 'auto' ? '#8b5cf6' : '#22c55e',
      hint: selectedTask.source === 'auto' ? 'AI-generated task' : 'From meeting notes' },
    { key: 'topics', label: 'Topics', value: selectedTask.topics || (selectedTask.topic ? [selectedTask.topic] : []), type: 'tags' },
    { key: 'source_title', label: 'Meeting Source', value: formatMeetingSource(selectedTask.source_title), type: 'readonly' },
    { key: 'source_url', label: 'Source Link', value: selectedTask.source_url, type: 'link' },
    { key: 'source_context', label: 'Context', value: selectedTask.source_context, type: 'expandable',
      lines: parseContextLines(selectedTask.source_context) },
    { key: 'steps', label: 'Next Steps', value: selectedTask.steps, type: 'expandable',
      lines: parseStepLines(selectedTask.steps),
      lineAction: {
        label: 'Create as task',
        icon: 'plus',
        onAction: (line: string) => {
          if (!selectedTask) return;
          api.post<any>(`/api/intel/tasks/${selectedTask.id}/create-from-step`, { step_description: line })
            .then((res) => {
              if (res.task) {
                setTasks((prev) => [...prev, res.task]);
              }
            })
            .catch(() => {});
        },
      },
      lineRemove: {
        label: 'Remove step',
        onRemove: (lineIndex: number) => {
          if (!selectedTask) return;
          const currentLines = parseStepLines(selectedTask.steps);
          const updated = currentLines.filter((_, idx) => idx !== lineIndex).join('\n');
          handleFieldChange('steps', updated);
          setSelectedTask((prev) => prev ? { ...prev, steps: updated } : null);
        },
      } },
    { key: 'age_days', label: 'Age (days)', value: selectedTask.age_days, type: 'readonly' },
    { key: 'delegated', label: 'Delegated', value: selectedTask.delegated ? 'Yes' : 'No', type: 'readonly' },
  ] : [];

  const filteredTasks = searchQuery
    ? tasks.filter((t) => t.description?.toLowerCase().includes(searchQuery.toLowerCase()))
    : tasks;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)' }}>Work</h1>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2 }}>
              {filteredTasks.length}{searchQuery ? ` of ${tasks.length}` : ''} tasks{(() => { const openCount = filteredTasks.filter(t => t.status !== 'done').length; return openCount < filteredTasks.length ? ` · ${openCount} open` : ''; })()}
            </p>
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', padding: '5px 10px', minWidth: 200,
          }}>
            <Search size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            <input
              type="text" placeholder="Filter tasks..." value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ flex: 1, border: 'none', outline: 'none', background: 'none', color: 'var(--text-primary)', fontSize: 13 }}
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery('')} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 11, padding: 0 }}>
                Clear
              </button>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4, backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 3 }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 14px', border: 'none', borderRadius: 'var(--radius)',
                backgroundColor: tab === t.id ? 'var(--accent-light)' : 'transparent',
                color: tab === t.id ? 'var(--accent)' : 'var(--text-muted)',
                fontSize: 13, fontWeight: tab === t.id ? 500 : 400, cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading tasks...</div>
      ) : tab === 'matrix' ? (
        <MatrixView tasks={filteredTasks} onTaskClick={handleTaskClick} />
      ) : tab === 'board' ? (
        <BoardView tasks={filteredTasks} onTaskClick={handleTaskClick} onDragDrop={handleDragDrop} />
      ) : tab === 'list' ? (
        <ListView tasks={filteredTasks} onTaskClick={handleTaskClick} />
      ) : (
        <TimelineView tasks={filteredTasks} onTaskClick={handleTaskClick} />
      )}

      <DetailPanel
        open={!!selectedTask}
        onClose={() => setSelectedTask(null)}
        title={selectedTask?.description || ''}
        subtitle={selectedTask?.owner ? `Assigned to ${selectedTask.owner}` : undefined}
        badge={selectedTask ? {
          label: QUADRANT_LABELS[getTaskQuadrant(selectedTask)]?.name || 'Unknown',
          color: QUADRANT_LABELS[getTaskQuadrant(selectedTask)]?.color || '#94a3b8',
        } : undefined}
        fields={taskFields}
        onSave={handleTaskSave}
        onFieldChange={handleFieldChange}
      />
    </div>
  );
}

/* ---------- Matrix View ---------- */

function MatrixView({ tasks, onTaskClick }: { tasks: SmartTask[]; onTaskClick: (t: SmartTask) => void }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      {[1, 2, 3, 4].map((q) => {
        const qTasks = tasks.filter((t) => getTaskQuadrant(t) === q && t.status !== 'done');
        const label = QUADRANT_LABELS[q];
        return (
          <div key={q} style={{
            backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)', borderTop: `3px solid ${label.color}`,
            padding: 16, minHeight: qTasks.length === 0 ? 120 : 200,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: label.color }}>{label.name}</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', backgroundColor: 'var(--bg-secondary)', padding: '2px 8px', borderRadius: 10 }}>
                {qTasks.length}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {qTasks.slice(0, 8).map((t) => (
                <TaskCard key={t.id} task={t} compact onClick={() => onTaskClick(t)} />
              ))}
              {qTasks.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: 12 }}>No tasks</div>
              )}
              {qTasks.length > 8 && (
                <div style={{
                  fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '6px 4px',
                  fontWeight: 500, backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius)',
                }}>
                  +{qTasks.length - 8} more of {qTasks.length} tasks
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ---------- Board View (Drag & Drop Kanban) ---------- */

function BoardView({ tasks, onTaskClick, onDragDrop }: {
  tasks: SmartTask[];
  onTaskClick: (t: SmartTask) => void;
  onDragDrop: (taskId: string, newPhase: string) => void;
}) {
  const [dragOverCol, setDragOverCol] = useState<string | null>(null);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [collapsedCols, setCollapsedCols] = useState<Set<string>>(new Set());

  const toggleCollapse = (colId: string) => {
    setCollapsedCols((prev) => {
      const next = new Set(prev);
      if (next.has(colId)) next.delete(colId);
      else next.add(colId);
      return next;
    });
  };

  const handleDragStart = (e: React.DragEvent, taskId: string) => {
    e.dataTransfer.setData('text/plain', taskId);
    e.dataTransfer.effectAllowed = 'move';
    setDraggedId(taskId);
  };

  const handleDragOver = (e: React.DragEvent, colId: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverCol(colId);
  };

  const handleDrop = (e: React.DragEvent, colId: string) => {
    e.preventDefault();
    const taskId = e.dataTransfer.getData('text/plain');
    if (taskId) onDragDrop(taskId, colId);
    setDragOverCol(null);
    setDraggedId(null);
  };

  const handleDragEnd = () => {
    setDragOverCol(null);
    setDraggedId(null);
  };

  return (
    <div style={{ display: 'flex', gap: 16, overflowX: 'auto', paddingBottom: 8 }}>
      {BOARD_COLUMNS.map((col) => {
        const colTasks = tasks.filter((t) => getTaskPhase(t) === col.id);
        const collapsed = collapsedCols.has(col.id);
        const isDragOver = dragOverCol === col.id;

        return (
          <div
            key={col.id}
            onDragOver={(e) => handleDragOver(e, col.id)}
            onDragLeave={() => setDragOverCol(null)}
            onDrop={(e) => handleDrop(e, col.id)}
            style={{
              flex: '0 0 280px',
              backgroundColor: isDragOver ? 'var(--accent-light)' : 'var(--bg-card)',
              border: `1px solid ${isDragOver ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 'var(--radius-lg)',
              padding: 12,
              transition: 'background-color 0.15s, border-color 0.15s',
              minHeight: 200,
            }}
          >
            {/* Column header */}
            <div
              onClick={() => toggleCollapse(col.id)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: collapsed ? 0 : 12, padding: '4px 4px', cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%', backgroundColor: col.color,
                }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{col.label}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{
                  fontSize: 12, color: 'var(--text-muted)', backgroundColor: 'var(--bg-secondary)',
                  padding: '1px 8px', borderRadius: 10, fontWeight: 500,
                }}>
                  {colTasks.length}
                </span>
                {collapsed ? <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} /> : <ChevronUp size={14} style={{ color: 'var(--text-muted)' }} />}
              </div>
            </div>

            {/* Column body */}
            {!collapsed && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minHeight: 60 }}>
                {colTasks.length === 0 ? (
                  <div style={{
                    fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', padding: 20,
                    border: '1px dashed var(--border-light)', borderRadius: 'var(--radius)',
                  }}>
                    Drop tasks here
                  </div>
                ) : (
                  colTasks.slice(0, 25).map((t) => (
                    <div
                      key={t.id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, t.id)}
                      onDragEnd={handleDragEnd}
                      style={{ opacity: draggedId === t.id ? 0.4 : 1, cursor: 'grab' }}
                    >
                      <TaskCard task={t} onClick={() => onTaskClick(t)} />
                    </div>
                  ))
                )}
                {colTasks.length > 25 && (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: 4 }}>
                    +{colTasks.length - 25} more
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ---------- List View ---------- */

function ListView({ tasks, onTaskClick }: { tasks: SmartTask[]; onTaskClick: (t: SmartTask) => void }) {
  const [sortBy, setSortBy] = useState<'priority' | 'owner' | 'date' | 'status'>('priority');
  const [sortAsc, setSortAsc] = useState(true);

  const sorted = [...tasks].sort((a, b) => {
    const dir = sortAsc ? 1 : -1;
    if (sortBy === 'priority') return (getTaskQuadrant(a) - getTaskQuadrant(b)) * dir;
    if (sortBy === 'owner') return (a.owner || '').localeCompare(b.owner || '') * dir;
    if (sortBy === 'date') return ((a.follow_up_date || '').localeCompare(b.follow_up_date || '')) * dir;
    return (a.status || '').localeCompare(b.status || '') * dir;
  });

  const handleSort = (col: 'priority' | 'owner' | 'date' | 'status') => {
    if (sortBy === col) setSortAsc(!sortAsc);
    else { setSortBy(col); setSortAsc(true); }
  };

  const SortHeader = ({ label, col }: { label: string; col: 'priority' | 'owner' | 'date' | 'status' }) => (
    <th
      onClick={() => handleSort(col)}
      style={{
        padding: '10px 16px', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)',
        textAlign: 'left', cursor: 'pointer', userSelect: 'none',
        backgroundColor: sortBy === col ? 'var(--bg-secondary)' : 'transparent',
      }}
    >
      {label} {sortBy === col && (sortAsc ? '↑' : '↓')}
    </th>
  );

  return (
    <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            <th style={{ padding: '10px 16px', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textAlign: 'left' }}>Task</th>
            <SortHeader label="Owner" col="owner" />
            <SortHeader label="Priority" col="priority" />
            <SortHeader label="Follow-up" col="date" />
            <SortHeader label="Status" col="status" />
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, 50).map((t) => {
            const q = getTaskQuadrant(t);
            return (
              <tr
                key={t.id}
                onClick={() => onTaskClick(t)}
                style={{
                  borderBottom: '1px solid var(--border-light)', cursor: 'pointer',
                  transition: 'background-color 0.1s',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <td style={{ padding: '10px 16px', fontSize: 13, color: 'var(--text-primary)', maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {t.description}
                </td>
                <td style={{ padding: '10px 16px', fontSize: 13, color: 'var(--text-secondary)' }}>{t.owner || '—'}</td>
                <td style={{ padding: '10px 16px' }}>
                  <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, backgroundColor: QUADRANT_LABELS[q].color + '20', color: QUADRANT_LABELS[q].color, fontWeight: 500 }}>
                    {QUADRANT_LABELS[q].name}
                  </span>
                </td>
                <td style={{ padding: '10px 16px', fontSize: 12, color: 'var(--text-muted)' }}>{t.follow_up_date || '—'}</td>
                <td style={{ padding: '10px 16px' }}>
                  <span style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 10,
                    backgroundColor: t.status === 'done' ? '#22c55e20' : t.status === 'in_progress' ? '#3b82f620' : '#94a3b820',
                    color: t.status === 'done' ? '#22c55e' : t.status === 'in_progress' ? '#3b82f6' : '#94a3b8',
                  }}>
                    {(t.status || 'open').replace(/_/g, ' ')}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {tasks.length > 50 && (
        <div style={{ padding: '12px 16px', fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', borderTop: '1px solid var(--border)' }}>
          Showing 50 of {tasks.length} tasks
        </div>
      )}
    </div>
  );
}

/* ---------- Timeline View ---------- */

function TimelineView({ tasks, onTaskClick }: { tasks: SmartTask[]; onTaskClick: (t: SmartTask) => void }) {
  const tasksWithDates = tasks.filter((t) => t.follow_up_date).sort((a, b) => (a.follow_up_date || '').localeCompare(b.follow_up_date || ''));

  // Group by date
  const groups: Record<string, SmartTask[]> = {};
  tasksWithDates.forEach((t) => {
    const date = t.follow_up_date!;
    if (!groups[date]) groups[date] = [];
    groups[date].push(t);
  });

  return (
    <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
      {tasksWithDates.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>No tasks with follow-up dates</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {Object.entries(groups).slice(0, 20).map(([date, dateTasks]) => {
            const isToday = date === new Date().toISOString().slice(0, 10);
            const isPast = date < new Date().toISOString().slice(0, 10);
            return (
              <div key={date}>
                <div style={{
                  fontSize: 12, fontWeight: 600, marginBottom: 8, padding: '4px 8px',
                  backgroundColor: isToday ? 'var(--accent-light)' : isPast ? 'var(--danger-light)' : 'var(--bg-secondary)',
                  color: isToday ? 'var(--accent)' : isPast ? 'var(--danger)' : 'var(--text-muted)',
                  borderRadius: 'var(--radius)', display: 'inline-block',
                }}>
                  {isToday ? 'Today' : new Date(date + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                  {isPast && !isToday && (() => {
                    const diffMs = new Date(new Date().toISOString().slice(0, 10) + 'T00:00:00').getTime() - new Date(date + 'T00:00:00').getTime();
                    const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
                    return ` (${diffDays} ${diffDays === 1 ? 'day' : 'days'} overdue)`;
                  })()}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {dateTasks.map((t) => (
                    <div
                      key={t.id}
                      onClick={() => onTaskClick(t)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
                        borderLeft: `3px solid ${QUADRANT_LABELS[getTaskQuadrant(t)].color}`,
                        backgroundColor: 'var(--bg-secondary)',
                        borderRadius: '0 var(--radius) var(--radius) 0',
                        cursor: 'pointer', transition: 'background-color 0.1s',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-secondary)'}
                    >
                      <div style={{ fontSize: 13, color: 'var(--text-primary)', flex: 1 }}>{t.description}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', flexShrink: 0 }}>{t.owner}</div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ---------- Task Card ---------- */

function TaskCard({ task, compact, onClick }: { task: SmartTask; compact?: boolean; onClick?: () => void }) {
  const q = getTaskQuadrant(task);
  const isAuto = task.source === 'auto';
  return (
    <div
      onClick={onClick}
      style={{
        padding: compact ? '8px 10px' : '10px 12px',
        backgroundColor: 'var(--bg-secondary)',
        borderRadius: 'var(--radius)',
        borderLeft: `3px ${isAuto ? 'dashed' : 'solid'} ${QUADRANT_LABELS[q].color}`,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'background-color 0.1s, box-shadow 0.1s',
      }}
      onMouseEnter={(e) => {
        if (onClick) {
          e.currentTarget.style.backgroundColor = 'var(--bg-hover)';
          e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = 'var(--bg-secondary)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div style={{ fontSize: 13, color: isAuto ? 'var(--text-muted)' : 'var(--text-primary)', lineHeight: 1.4 }}>
        {task.description?.slice(0, compact ? 80 : 150)}
      </div>
      {!compact && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
          {task.owner && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 3, fontWeight: 500 }}>
              {task.owner}
            </span>
          )}
          {task.follow_up_date && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{task.follow_up_date}</span>
          )}
          {isAuto && (
            <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, backgroundColor: 'rgba(139,92,246,0.1)', color: '#8b5cf6' }}>
              AI proposed
            </span>
          )}
          {task.classification === 'operational' && (
            <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, backgroundColor: 'rgba(245,158,11,0.1)', color: '#f59e0b' }}>
              Operational
            </span>
          )}
        </div>
      )}
    </div>
  );
}
