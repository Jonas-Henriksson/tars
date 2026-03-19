/**
 * People page — directory, relationship graph, meeting prep.
 */
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Users, Network, CalendarCheck, Search } from 'lucide-react';

type TabId = 'directory' | 'graph' | 'meeting-prep';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'directory', label: 'Directory', icon: <Users size={16} /> },
  { id: 'graph', label: 'Graph', icon: <Network size={16} /> },
  { id: 'meeting-prep', label: 'Meeting Prep', icon: <CalendarCheck size={16} /> },
];

interface Person {
  name: string;
  role: string;
  relationship: string;
  organization: string;
  email: string;
  mentions: number;
  pages_count: number;
  tasks_count: number;
  has_one_on_ones: boolean;
  topics: string[];
}

export default function People() {
  const [tab, setTab] = useState<TabId>('directory');

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)' }}>People</h1>
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

      {tab === 'directory' ? <DirectoryView /> :
       tab === 'graph' ? <GraphPlaceholder /> :
       <MeetingPrepView />}
    </div>
  );
}

function DirectoryView() {
  const [people, setPeople] = useState<Record<string, Person>>({});
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any>('/api/people').then((data) => {
      setPeople(data.people || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const filtered = Object.values(people).filter((p) =>
    !search || p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.role?.toLowerCase().includes(search.toLowerCase()) ||
    p.organization?.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading...</div>;

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8, backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '8px 12px', maxWidth: 400 }}>
        <Search size={16} style={{ color: 'var(--text-muted)' }} />
        <input
          type="text" placeholder="Search people..." value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1, border: 'none', outline: 'none', background: 'none', color: 'var(--text-primary)', fontSize: 13 }}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
        {filtered.length === 0 ? (
          <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>
            No people found. Run a Notion scan to discover your network.
          </div>
        ) : (
          filtered.map((p) => (
            <div
              key={p.name}
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                padding: 16,
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 14, fontWeight: 600, flexShrink: 0 }}>
                  {p.name.charAt(0)}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{p.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{p.role || p.relationship || 'Unknown role'}</div>
                </div>
              </div>

              {p.organization && (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>{p.organization}</div>
              )}

              <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--text-muted)' }}>
                <span>{p.mentions || 0} mentions</span>
                <span>{p.pages_count || 0} pages</span>
                <span>{p.tasks_count || 0} tasks</span>
              </div>

              {p.topics?.length > 0 && (
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 8 }}>
                  {p.topics.slice(0, 4).map((t) => (
                    <span key={t} style={{ fontSize: 10, padding: '2px 6px', borderRadius: 8, backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function GraphPlaceholder() {
  return (
    <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 60, textAlign: 'center' }}>
      <Network size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
      <h3 style={{ fontSize: 16, color: 'var(--text-primary)', marginBottom: 8 }}>Relationship Graph</h3>
      <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Interactive network visualization coming soon</p>
    </div>
  );
}

function MeetingPrepView() {
  const [prep, setPrep] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any>('/api/meeting-prep').then((data) => {
      setPrep(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading meeting prep...</div>;

  if (!prep || prep.error) {
    return (
      <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 40, textAlign: 'center' }}>
        <CalendarCheck size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
        <h3 style={{ fontSize: 16, color: 'var(--text-primary)', marginBottom: 8 }}>Meeting Prep</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          {prep?.error || 'No upcoming meetings found. Connect your calendar to get meeting briefings.'}
        </p>
      </div>
    );
  }

  return (
    <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: 'var(--text-primary)' }}>
        {prep.meeting?.subject || 'Next Meeting'}
      </h3>
      <pre style={{ fontSize: 13, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
        {JSON.stringify(prep, null, 2)}
      </pre>
    </div>
  );
}
