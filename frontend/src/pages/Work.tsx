/**
 * Work page — Eisenhower matrix, Kanban board, task list, timeline.
 */
import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { getTheme } from '../themes';
import { api } from '../api/client';
import { Grid3x3, Columns3, List, GanttChart } from 'lucide-react';

type TabId = 'matrix' | 'board' | 'list' | 'timeline';

interface SmartTask {
  id: string;
  description: string;
  owner: string;
  status: string;
  priority?: { quadrant: number; label: string };
  follow_up_date?: string;
  topic?: string;
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

export default function Work() {
  const { themeId } = useStore();
  const theme = getTheme(themeId);
  const [tab, setTab] = useState<TabId>(theme.layout.defaultWorkTab);
  const [tasks, setTasks] = useState<SmartTask[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any>('/api/intel/tasks').then((data) => {
      setTasks(data.tasks || data.smart_tasks || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)' }}>Work</h1>
        <div style={{ display: 'flex', gap: 4, backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 3 }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 12px', border: 'none', borderRadius: 'var(--radius)',
                backgroundColor: tab === t.id ? 'var(--accent-light)' : 'transparent',
                color: tab === t.id ? 'var(--accent)' : 'var(--text-muted)',
                fontSize: 13, fontWeight: tab === t.id ? 500 : 400, cursor: 'pointer',
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
        <MatrixView tasks={tasks} />
      ) : tab === 'board' ? (
        <BoardView tasks={tasks} />
      ) : tab === 'list' ? (
        <ListView tasks={tasks} />
      ) : (
        <TimelineView tasks={tasks} />
      )}
    </div>
  );
}

function MatrixView({ tasks }: { tasks: SmartTask[] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      {[1, 2, 3, 4].map((q) => {
        const qTasks = tasks.filter((t) => (t.priority?.quadrant || 4) === q && t.status !== 'done');
        const label = QUADRANT_LABELS[q];
        return (
          <div
            key={q}
            style={{
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)',
              borderTop: `3px solid ${label.color}`,
              padding: 16,
              minHeight: 200,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: label.color }}>{label.name}</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', backgroundColor: 'var(--bg-secondary)', padding: '2px 8px', borderRadius: 10 }}>
                {qTasks.length}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {qTasks.slice(0, 10).map((t) => (
                <TaskCard key={t.id} task={t} compact />
              ))}
              {qTasks.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>No tasks</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BoardView({ tasks }: { tasks: SmartTask[] }) {
  const columns = [
    { id: 'open', label: 'Open', tasks: tasks.filter((t) => t.status === 'open') },
    { id: 'done', label: 'Done', tasks: tasks.filter((t) => t.status === 'done') },
  ];

  return (
    <div style={{ display: 'flex', gap: 16, overflowX: 'auto' }}>
      {columns.map((col) => (
        <div
          key={col.id}
          style={{
            flex: '0 0 320px',
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, padding: '0 4px' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{col.label}</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{col.tasks.length}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {col.tasks.slice(0, 20).map((t) => (
              <TaskCard key={t.id} task={t} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function ListView({ tasks }: { tasks: SmartTask[] }) {
  return (
    <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            {['Task', 'Owner', 'Priority', 'Follow-up', 'Status'].map((h) => (
              <th key={h} style={{ padding: '10px 16px', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textAlign: 'left' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tasks.slice(0, 50).map((t) => {
            const q = t.priority?.quadrant || 4;
            return (
              <tr key={t.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
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
                  <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, backgroundColor: t.status === 'done' ? 'var(--success)' + '20' : 'var(--accent-light)', color: t.status === 'done' ? 'var(--success)' : 'var(--accent)' }}>
                    {t.status}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TimelineView({ tasks }: { tasks: SmartTask[] }) {
  const tasksWithDates = tasks.filter((t) => t.follow_up_date).sort((a, b) => (a.follow_up_date || '').localeCompare(b.follow_up_date || ''));
  return (
    <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {tasksWithDates.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>No tasks with follow-up dates</div>
        ) : (
          tasksWithDates.slice(0, 30).map((t) => (
            <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', borderLeft: `3px solid ${QUADRANT_LABELS[t.priority?.quadrant || 4].color}`, backgroundColor: 'var(--bg-secondary)', borderRadius: '0 var(--radius) var(--radius) 0' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', minWidth: 80, fontFamily: 'var(--font-mono)' }}>{t.follow_up_date}</div>
              <div style={{ fontSize: 13, color: 'var(--text-primary)', flex: 1 }}>{t.description}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t.owner}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function TaskCard({ task, compact }: { task: SmartTask; compact?: boolean }) {
  const q = task.priority?.quadrant || 4;
  return (
    <div
      style={{
        padding: compact ? '8px 10px' : '10px 12px',
        backgroundColor: 'var(--bg-secondary)',
        borderRadius: 'var(--radius)',
        borderLeft: `3px solid ${QUADRANT_LABELS[q].color}`,
      }}
    >
      <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.4 }}>
        {task.description?.slice(0, compact ? 80 : 150)}
      </div>
      {!compact && task.owner && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{task.owner}</div>
      )}
    </div>
  );
}
