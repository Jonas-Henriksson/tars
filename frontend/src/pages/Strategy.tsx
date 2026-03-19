/**
 * Strategy page — Initiatives, Decisions, Portfolio, Weekly Review.
 */
import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { getTheme } from '../themes';
import { api } from '../api/client';
import { Target, Scale, Users, BarChart3 } from 'lucide-react';

type TabId = 'initiatives' | 'decisions' | 'portfolio' | 'review';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'initiatives', label: 'Initiatives', icon: <Target size={16} /> },
  { id: 'decisions', label: 'Decisions', icon: <Scale size={16} /> },
  { id: 'portfolio', label: 'Portfolio', icon: <Users size={16} /> },
  { id: 'review', label: 'Review', icon: <BarChart3 size={16} /> },
];

const STATUS_COLORS: Record<string, string> = {
  on_track: '#22c55e', at_risk: '#f59e0b', off_track: '#ef4444',
  completed: '#6b7280', paused: '#94a3b8',
  decided: '#3b82f6', pending: '#f59e0b', revisit: '#ef4444',
};

export default function Strategy() {
  const { themeId } = useStore();
  const theme = getTheme(themeId);
  const [tab, setTab] = useState<TabId>(theme.layout.defaultStrategyTab);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)' }}>Strategy</h1>
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
              {t.icon}{t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'initiatives' ? <InitiativesView /> :
       tab === 'decisions' ? <DecisionsView /> :
       tab === 'portfolio' ? <PortfolioView /> :
       <ReviewView />}
    </div>
  );
}

function InitiativesView() {
  const [initiatives, setInitiatives] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any>('/api/initiatives').then((data) => {
      setInitiatives(data.initiatives || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {initiatives.length === 0 ? (
        <EmptyState message="No initiatives yet. Use TARS chat to create one." />
      ) : (
        initiatives.map((init) => (
          <div key={init.id} style={cardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{init.title}</h3>
              <StatusBadge status={init.status} />
            </div>
            {init.description && <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>{init.description}</p>}
            <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
              {init.owner && <span>Owner: {init.owner}</span>}
              {init.quarter && <span>{init.quarter}</span>}
              {init.milestone_progress && <span>Milestones: {init.milestone_progress}</span>}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function DecisionsView() {
  const [decisions, setDecisions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any>('/api/decisions').then((data) => {
      setDecisions(data.decisions || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {decisions.length === 0 ? (
        <EmptyState message="No decisions logged yet." />
      ) : (
        decisions.map((d) => (
          <div key={d.id} style={cardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{d.title}</h3>
              <StatusBadge status={d.status} />
            </div>
            {d.rationale && <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>{d.rationale}</p>}
            <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
              <span>By: {d.decided_by || 'Unknown'}</span>
              {d.stakeholders?.length > 0 && <span>Stakeholders: {d.stakeholders.join(', ')}</span>}
              <span>{new Date(d.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function PortfolioView() {
  const [portfolio, setPortfolio] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any>('/api/portfolio').then((data) => {
      setPortfolio(data.portfolio || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;

  const members = Object.entries(portfolio);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
      {members.length === 0 ? (
        <EmptyState message="No portfolio data. Run a Notion scan first." />
      ) : (
        members.map(([name, data]: [string, any]) => (
          <div key={name} style={cardStyle}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>{name}</h3>
            <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
              <MiniStat label="Epics" value={data.epic_count || 0} />
              <MiniStat label="Stories" value={data.story_count || 0} />
              <MiniStat label="Tasks" value={data.task_count || 0} />
            </div>
            {data.workload_status && (
              <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, backgroundColor: data.workload_status === 'overloaded' ? 'var(--danger-light)' : 'var(--accent-light)', color: data.workload_status === 'overloaded' ? 'var(--danger)' : 'var(--accent)' }}>
                {data.workload_status}
              </span>
            )}
          </div>
        ))
      )}
    </div>
  );
}

function ReviewView() {
  const [review, setReview] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any>('/api/review/weekly').then((data) => {
      setReview(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;
  if (!review) return <EmptyState message="No review data available." />;

  const st = review.smart_tasks || {};
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <MiniStatCard label="Open Tasks" value={st.open || 0} />
        <MiniStatCard label="Completed" value={st.done || 0} />
        <MiniStatCard label="Overdue" value={st.overdue_count || 0} color="var(--danger)" />
        <MiniStatCard label="Tracked" value={review.tracked_tasks?.open || 0} />
      </div>

      {st.overdue?.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--danger)' }}>Overdue Items</h3>
          {st.overdue.slice(0, 10).map((t: any, i: number) => (
            <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border-light)', fontSize: 13 }}>
              <span style={{ color: 'var(--text-primary)' }}>{t.description}</span>
              <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>({t.days_overdue}d overdue)</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || '#94a3b8';
  return (
    <span style={{ fontSize: 11, padding: '2px 10px', borderRadius: 10, backgroundColor: color + '20', color, fontWeight: 500 }}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</div>
    </div>
  );
}

function MiniStatCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ ...cardStyle, padding: '14px 16px', textAlign: 'center' }}>
      <div style={{ fontSize: 24, fontWeight: 700, color: color || 'var(--text-primary)' }}>{value}</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
    </div>
  );
}

function LoadingState() {
  return <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)', fontSize: 13 }}>Loading...</div>;
}

function EmptyState({ message }: { message: string }) {
  return <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)', fontSize: 13 }}>{message}</div>;
}

const cardStyle: React.CSSProperties = {
  backgroundColor: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-lg)',
  padding: 16,
  boxShadow: 'var(--shadow-sm)',
};
