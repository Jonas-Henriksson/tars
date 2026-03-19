/**
 * People page — directory, relationship graph, meeting prep.
 */
import { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import { Users, Network, CalendarCheck, Search, Clock } from 'lucide-react';
import DetailPanel from '../components/DetailPanel';
import type { DetailField } from '../components/DetailPanel';

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
  notes?: string;
  mentions: number;
  pages_count?: number;
  tasks_count?: number;
  has_one_on_ones: boolean;
  topics: string[];
  pages?: { title: string; url: string; topics: string[]; last_edited: string }[];
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
                padding: '6px 14px', border: 'none', borderRadius: 'var(--radius)',
                backgroundColor: tab === t.id ? 'var(--accent-light)' : 'transparent',
                color: tab === t.id ? 'var(--accent)' : 'var(--text-muted)',
                fontSize: 13, fontWeight: tab === t.id ? 500 : 400, cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {t.icon}{t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'directory' ? <DirectoryView /> :
       tab === 'graph' ? <GraphView /> :
       <MeetingPrepView />}
    </div>
  );
}

/* ---------- Directory ---------- */

function DirectoryView() {
  const [people, setPeople] = useState<Record<string, Person>>({});
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Person | null>(null);

  useEffect(() => {
    api.get<any>('/api/people').then((data) => {
      setPeople(data.people || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleSave = useCallback((updates: Record<string, any>) => {
    if (!selected) return;
    const updated = { ...selected, ...updates };
    setPeople((prev) => ({ ...prev, [selected.name]: updated }));
    setSelected(updated);
    api.patch<any>(`/api/people/${encodeURIComponent(selected.name)}`, updates).catch(() => {});
  }, [selected]);

  const filtered = Object.values(people).filter((p) =>
    !search || p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.role?.toLowerCase().includes(search.toLowerCase()) ||
    p.organization?.toLowerCase().includes(search.toLowerCase()) ||
    p.email?.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) return <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading...</div>;

  const fields: DetailField[] = selected ? [
    { key: 'role', label: 'Role', value: selected.role, type: 'text' },
    { key: 'relationship', label: 'Relationship', value: selected.relationship, type: 'select', options: ['colleague', 'manager', 'report', 'stakeholder', 'client', 'vendor', 'other'] },
    { key: 'organization', label: 'Organization', value: selected.organization, type: 'text' },
    { key: 'email', label: 'Email', value: selected.email, type: 'text' },
    { key: 'notes', label: 'Notes', value: selected.notes || '', type: 'textarea' },
    { key: 'topics', label: 'Topics', value: selected.topics || [], type: 'tags' },
    { key: 'mentions', label: 'Mentions', value: selected.mentions, type: 'readonly' },
    { key: 'has_one_on_ones', label: 'Has 1:1s', value: selected.has_one_on_ones ? 'Yes' : 'No', type: 'readonly' },
    { key: 'pages_count', label: 'Related Pages', value: selected.pages_count || selected.pages?.length || 0, type: 'readonly' },
    { key: 'tasks_count', label: 'Open Tasks', value: selected.tasks_count || 0, type: 'readonly' },
  ] : [];

  return (
    <>
      {/* Search bar */}
      <div style={{
        marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8,
        backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius)', padding: '8px 12px', maxWidth: 400,
      }}>
        <Search size={16} style={{ color: 'var(--text-muted)' }} />
        <input
          type="text" placeholder="Search people..." value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1, border: 'none', outline: 'none', background: 'none', color: 'var(--text-primary)', fontSize: 13 }}
        />
        {search && (
          <button onClick={() => setSearch('')} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 12 }}>
            Clear
          </button>
        )}
      </div>

      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
        {filtered.length} people{search && ` matching "${search}"`}
      </p>

      {/* People grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
        {filtered.length === 0 ? (
          <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>
            {search ? 'No people match your search.' : 'No people found. Run a Notion scan to discover your network.'}
          </div>
        ) : (
          filtered.map((p) => (
            <div
              key={p.name}
              onClick={() => setSelected(p)}
              style={{
                backgroundColor: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                padding: 16,
                boxShadow: 'var(--shadow-sm)',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--bg-hover)';
                e.currentTarget.style.boxShadow = 'var(--shadow)';
                e.currentTarget.style.borderColor = 'var(--accent)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--bg-card)';
                e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                e.currentTarget.style.borderColor = 'var(--border)';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: '50%', background: 'var(--accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontSize: 15, fontWeight: 600, flexShrink: 0,
                }}>
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
                <span>{p.pages_count || p.pages?.length || 0} pages</span>
                <span>{p.tasks_count || 0} tasks</span>
              </div>

              {p.topics?.length > 0 && (
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 8 }}>
                  {p.topics.slice(0, 4).map((t) => (
                    <span key={t} style={{ fontSize: 10, padding: '2px 6px', borderRadius: 8, backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>
                      {t}
                    </span>
                  ))}
                  {p.topics.length > 4 && (
                    <span style={{ fontSize: 10, padding: '2px 6px', color: 'var(--text-muted)' }}>
                      +{p.topics.length - 4}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Detail panel */}
      <DetailPanel
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.name || ''}
        subtitle={[selected?.role, selected?.organization].filter(Boolean).join(' at ')}
        fields={fields}
        onSave={handleSave}
      />
    </>
  );
}

/* ---------- Graph ---------- */

function GraphView() {
  const [people, setPeople] = useState<Record<string, Person>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any>('/api/people').then((data) => {
      setPeople(data.people || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading...</div>;

  const entries = Object.values(people);
  const maxMentions = Math.max(...entries.map((p) => p.mentions || 1), 1);

  // Group by organization
  const orgs: Record<string, Person[]> = {};
  entries.forEach((p) => {
    const org = p.organization || 'Unknown';
    if (!orgs[org]) orgs[org] = [];
    orgs[org].push(p);
  });

  return (
    <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 24 }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 20 }}>
        Relationship Network
      </h3>
      {entries.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>
          No people data available yet.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {Object.entries(orgs).sort(([, a], [, b]) => b.length - a.length).map(([org, orgPeople]) => (
            <div key={org}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>{org}</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {orgPeople.sort((a, b) => (b.mentions || 0) - (a.mentions || 0)).map((p) => {
                  const size = 32 + Math.round(((p.mentions || 0) / maxMentions) * 24);
                  return (
                    <div key={p.name} title={`${p.name} — ${p.mentions || 0} mentions`}
                      style={{
                        width: size, height: size, borderRadius: '50%',
                        background: 'var(--accent)', display: 'flex', alignItems: 'center',
                        justifyContent: 'center', color: '#fff', fontSize: Math.max(10, size / 3.5),
                        fontWeight: 600, cursor: 'default', transition: 'transform 0.15s',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.15)'}
                      onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
                    >
                      {p.name.charAt(0)}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- Meeting Prep ---------- */

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

  if (!prep || !prep.available || prep.error) {
    return (
      <div style={{
        backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', padding: 40, textAlign: 'center',
      }}>
        <CalendarCheck size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
        <h3 style={{ fontSize: 16, color: 'var(--text-primary)', marginBottom: 8 }}>Meeting Prep</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          {prep?.reason || prep?.error || 'No upcoming meetings found. Connect your calendar to get meeting briefings.'}
        </p>
      </div>
    );
  }

  const event = prep.event || prep.meeting;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Meeting header */}
      <div style={{
        backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', padding: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <CalendarCheck size={18} style={{ color: 'var(--accent)' }} />
          <h3 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)' }}>
            {event?.subject || 'Next Meeting'}
          </h3>
        </div>
        <div style={{ display: 'flex', gap: 16, fontSize: 13, color: 'var(--text-muted)' }}>
          {prep.time_until && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Clock size={14} /> {prep.time_until}
            </span>
          )}
          {event?.attendees && <span>{event.attendees.length} attendees</span>}
        </div>
      </div>

      {/* Attendee profiles */}
      {prep.attendee_profiles?.length > 0 && (
        <div style={{
          backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: 20,
        }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>Attendees</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {prep.attendee_profiles.map((a: any, i: number) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
                backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius)',
              }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%', background: 'var(--accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontSize: 12, fontWeight: 600, flexShrink: 0,
                }}>
                  {(a.name || a.email || '?').charAt(0)}
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{a.name || a.email}</div>
                  {a.role && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.role}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Talking points */}
      {prep.talking_points?.length > 0 && (
        <div style={{
          backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: 20,
        }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>Talking Points</h4>
          <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {prep.talking_points.map((tp: string, i: number) => (
              <li key={i} style={{
                fontSize: 13, color: 'var(--text-secondary)', padding: '6px 10px',
                backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius)',
                borderLeft: '3px solid var(--accent)',
              }}>
                {tp}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Open items */}
      {prep.open_items?.length > 0 && (
        <div style={{
          backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: 20,
        }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>Open Items</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {prep.open_items.map((item: any, i: number) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '8px 10px', backgroundColor: 'var(--bg-secondary)',
                borderRadius: 'var(--radius)',
              }}>
                <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{item.description}</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>{item.owner}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
