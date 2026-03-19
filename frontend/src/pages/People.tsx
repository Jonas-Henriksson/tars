/**
 * People page — directory, relationship graph, meeting prep.
 */
import { useEffect, useState, useCallback, useRef } from 'react';
import { api } from '../api/client';
import { Users, Network, CalendarCheck, Search, Clock } from 'lucide-react';
import DetailPanel from '../components/DetailPanel';
import type { DetailField } from '../components/DetailPanel';

type TabId = 'directory' | 'graph' | 'meeting-prep';

const ORG_COLORS: Record<string, string> = {
  Operations: '#3b82f6',
  Technology: '#8b5cf6',
  Strategy: '#10b981',
  HR: '#f59e0b',
  Finance: '#ef4444',
  'Executive Office': '#6366f1',
  Procurement: '#14b8a6',
};

function orgColor(org: string | undefined): string {
  if (!org) return 'var(--accent)';
  return ORG_COLORS[org] ?? 'var(--accent)';
}

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
  const [sortMode, setSortMode] = useState<'mentions' | 'az'>('mentions');

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
  ).sort((a, b) => sortMode === 'az' ? a.name.localeCompare(b.name) : (b.mentions || 0) - (a.mentions || 0));

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
        <div style={{ marginLeft: 12, display: 'flex', gap: 2, fontSize: 12 }}>
          <button
            onClick={() => setSortMode('mentions')}
            style={{
              background: 'none', border: 'none', cursor: 'pointer', padding: '4px 8px',
              borderRadius: 'var(--radius)', fontSize: 12,
              color: sortMode === 'mentions' ? 'var(--accent)' : 'var(--text-muted)',
              fontWeight: sortMode === 'mentions' ? 600 : 400,
              backgroundColor: sortMode === 'mentions' ? 'var(--accent-light)' : 'transparent',
            }}
          >
            By mentions
          </button>
          <button
            onClick={() => setSortMode('az')}
            style={{
              background: 'none', border: 'none', cursor: 'pointer', padding: '4px 8px',
              borderRadius: 'var(--radius)', fontSize: 12,
              color: sortMode === 'az' ? 'var(--accent)' : 'var(--text-muted)',
              fontWeight: sortMode === 'az' ? 600 : 400,
              backgroundColor: sortMode === 'az' ? 'var(--accent-light)' : 'transparent',
            }}
          >
            A-Z
          </button>
        </div>
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
                e.currentTarget.style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--bg-card)';
                e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.transform = 'translateY(0)';
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

              {((p.mentions || 0) > 0 || (p.pages_count || p.pages?.length || 0) > 0 || (p.tasks_count || 0) > 0) && (
                <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--text-muted)' }}>
                  {(p.mentions || 0) > 0 && <span>{p.mentions} mentions</span>}
                  {(p.pages_count || p.pages?.length || 0) > 0 && <span>{p.pages_count || p.pages?.length} pages</span>}
                  {(p.tasks_count || 0) > 0 && <span>{p.tasks_count} tasks</span>}
                </div>
              )}

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

/* ---------- Graph (D3 Force-Directed) ---------- */

function GraphView() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [graphData, setGraphData] = useState<any>(null);
  const [people, setPeople] = useState<Record<string, Person>>({});
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; name: string; role: string; mentions: number; org: string } | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<any>('/api/intel/graph?min_edge_weight=1').catch(() => ({ nodes: [], edges: [] })),
      api.get<any>('/api/people').catch(() => ({ people: {} })),
    ]).then(([graph, peopleData]) => {
      setGraphData(graph);
      setPeople(peopleData.people || {});
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (!graphData || !svgRef.current) return;

    // Filter to person nodes only for the main visualization
    const personNodes = graphData.nodes
      ?.filter((n: any) => n.type === 'person')
      ?.map((n: any) => {
        const name = n.label || n.id.replace('person:', '');
        const p = people[name];
        return { ...n, name, org: p?.organization || '', role: p?.role || '', mentions: p?.mentions || n.weight || 1 };
      }) || [];

    if (personNodes.length === 0) return;

    // Build person-to-person edges (people connected via shared pages/topics)
    const personIds = new Set(personNodes.map((n: any) => n.id));
    const pageConnections: Record<string, Set<string>> = {};

    // Find indirect connections: person → page → person
    const edges = graphData.edges || [];
    const personToPages: Record<string, string[]> = {};
    edges.forEach((e: any) => {
      const src = e.source || e.src;
      const tgt = e.target || e.tgt;
      if (personIds.has(src) && !personIds.has(tgt)) {
        if (!personToPages[src]) personToPages[src] = [];
        personToPages[src].push(tgt);
      }
      if (personIds.has(tgt) && !personIds.has(src)) {
        if (!personToPages[tgt]) personToPages[tgt] = [];
        personToPages[tgt].push(src);
      }
    });

    // Build person↔person links from shared intermediaries
    const linkMap: Record<string, number> = {};
    Object.entries(personToPages).forEach(([personId, pages]) => {
      pages.forEach(pageId => {
        if (!pageConnections[pageId]) pageConnections[pageId] = new Set();
        pageConnections[pageId].add(personId);
      });
    });
    Object.values(pageConnections).forEach(connectedPersons => {
      const arr = Array.from(connectedPersons);
      for (let i = 0; i < arr.length; i++) {
        for (let j = i + 1; j < arr.length; j++) {
          const key = arr[i] < arr[j] ? `${arr[i]}|${arr[j]}` : `${arr[j]}|${arr[i]}`;
          linkMap[key] = (linkMap[key] || 0) + 1;
        }
      }
    });

    // Also add direct person↔person edges
    edges.forEach((e: any) => {
      const src = e.source || e.src;
      const tgt = e.target || e.tgt;
      if (personIds.has(src) && personIds.has(tgt)) {
        const key = src < tgt ? `${src}|${tgt}` : `${tgt}|${src}`;
        linkMap[key] = (linkMap[key] || 0) + (e.weight || 1);
      }
    });

    const links = Object.entries(linkMap).map(([key, weight]) => {
      const [source, target] = key.split('|');
      return { source, target, weight };
    });

    // D3 force simulation (inline to avoid import issues)
    const svg = svgRef.current;
    const width = svg.clientWidth || 800;
    const height = 500;
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

    // Clear previous
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const maxMentions = Math.max(...personNodes.map((n: any) => n.mentions), 1);
    const nodeRadius = (n: { mentions: number }) => 16 + (n.mentions / maxMentions) * 16;

    // Simple force simulation without D3 import (use requestAnimationFrame)
    const nodes = personNodes.map((n: any) => ({
      ...n,
      x: width / 2 + (Math.random() - 0.5) * 300,
      y: height / 2 + (Math.random() - 0.5) * 200,
      vx: 0, vy: 0,
      r: nodeRadius(n),
    }));

    const nodeMap: Record<string, any> = {};
    nodes.forEach((n: any) => { nodeMap[n.id] = n; });

    const simLinks = links.filter(l => nodeMap[l.source] && nodeMap[l.target]);

    // Create SVG elements
    const ns = 'http://www.w3.org/2000/svg';

    // Link lines
    const linkEls = simLinks.map(l => {
      const line = document.createElementNS(ns, 'line');
      line.setAttribute('stroke', 'var(--border)');
      line.setAttribute('stroke-opacity', '0.4');
      line.setAttribute('stroke-width', String(Math.min(3, Math.max(1, l.weight * 0.5))));
      svg.appendChild(line);
      return line;
    });

    // Node groups
    const nodeEls = nodes.map((n: any) => {
      const g = document.createElementNS(ns, 'g');
      g.style.cursor = 'grab';

      const circle = document.createElementNS(ns, 'circle');
      circle.setAttribute('r', String(n.r));
      circle.setAttribute('fill', orgColor(n.org));
      circle.setAttribute('stroke', '#fff');
      circle.setAttribute('stroke-width', '2');
      g.appendChild(circle);

      const text = document.createElementNS(ns, 'text');
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('dy', '0.35em');
      text.setAttribute('fill', '#fff');
      text.setAttribute('font-size', String(Math.max(10, n.r / 2)));
      text.setAttribute('font-weight', '600');
      text.setAttribute('pointer-events', 'none');
      text.textContent = n.name.charAt(0);
      g.appendChild(text);

      // Name label below
      if (n.r > 20) {
        const label = document.createElementNS(ns, 'text');
        label.setAttribute('text-anchor', 'middle');
        label.setAttribute('dy', String(n.r + 14));
        label.setAttribute('fill', 'var(--text-muted)');
        label.setAttribute('font-size', '10');
        label.setAttribute('pointer-events', 'none');
        label.textContent = n.name.split(' ')[0];
        g.appendChild(label);
      }

      // Hover events
      g.addEventListener('mouseenter', () => {
        circle.setAttribute('stroke', 'var(--accent)');
        circle.setAttribute('stroke-width', '3');
        const rect = svg.getBoundingClientRect();
        setTooltip({ x: n.x + rect.left, y: n.y + rect.top - n.r - 10, name: n.name, role: n.role, mentions: n.mentions, org: n.org });
      });
      g.addEventListener('mouseleave', () => {
        circle.setAttribute('stroke', '#fff');
        circle.setAttribute('stroke-width', '2');
        setTooltip(null);
      });

      // Drag
      let dragging = false;
      g.addEventListener('mousedown', (e) => {
        dragging = true;
        g.style.cursor = 'grabbing';
        e.preventDefault();
      });
      const onMove = (e: MouseEvent) => {
        if (!dragging) return;
        const rect = svg.getBoundingClientRect();
        n.x = e.clientX - rect.left;
        n.y = e.clientY - rect.top;
        n.vx = 0; n.vy = 0;
      };
      const onUp = () => { dragging = false; g.style.cursor = 'grab'; };
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);

      svg.appendChild(g);
      return { g, circle, node: n, cleanup: () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); } };
    });

    // Simple force simulation (no D3 needed — basic physics)
    let running = true;
    const alpha = { value: 1.0 };

    function tick() {
      if (!running) return;
      alpha.value *= 0.99;
      if (alpha.value < 0.001) { alpha.value = 0; }

      // Center force
      nodes.forEach((n: any) => {
        n.vx += (width / 2 - n.x) * 0.005 * alpha.value;
        n.vy += (height / 2 - n.y) * 0.005 * alpha.value;
      });

      // Repulsion (charge)
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x;
          const dy = nodes[j].y - nodes[i].y;
          const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
          const force = -200 * alpha.value / (dist * dist);
          const fx = force * dx / dist;
          const fy = force * dy / dist;
          nodes[i].vx -= fx; nodes[i].vy -= fy;
          nodes[j].vx += fx; nodes[j].vy += fy;
        }
      }

      // Link attraction
      simLinks.forEach((l) => {
        const s = nodeMap[l.source];
        const t = nodeMap[l.target];
        if (!s || !t) return;
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const desired = 100 + s.r + t.r;
        const force = (dist - desired) * 0.01 * alpha.value;
        const fx = force * dx / dist;
        const fy = force * dy / dist;
        s.vx += fx; s.vy += fy;
        t.vx -= fx; t.vy -= fy;
      });

      // Collision
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x;
          const dy = nodes[j].y - nodes[i].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const minDist = nodes[i].r + nodes[j].r + 4;
          if (dist < minDist && dist > 0) {
            const overlap = (minDist - dist) / 2;
            const nx = dx / dist;
            const ny = dy / dist;
            nodes[i].x -= nx * overlap;
            nodes[i].y -= ny * overlap;
            nodes[j].x += nx * overlap;
            nodes[j].y += ny * overlap;
          }
        }
      }

      // Apply velocity + boundary
      nodes.forEach((n: any) => {
        n.vx *= 0.8; n.vy *= 0.8;
        n.x += n.vx; n.y += n.vy;
        n.x = Math.max(n.r + 5, Math.min(width - n.r - 5, n.x));
        n.y = Math.max(n.r + 5, Math.min(height - n.r - 5, n.y));
      });

      // Update positions
      simLinks.forEach((l, idx) => {
        const s = nodeMap[l.source];
        const t = nodeMap[l.target];
        if (!s || !t) return;
        linkEls[idx]?.setAttribute('x1', String(s.x));
        linkEls[idx]?.setAttribute('y1', String(s.y));
        linkEls[idx]?.setAttribute('x2', String(t.x));
        linkEls[idx]?.setAttribute('y2', String(t.y));
      });

      nodeEls.forEach((ne: { g: SVGGElement; node: any; cleanup: () => void }) => {
        ne.g.setAttribute('transform', `translate(${ne.node.x},${ne.node.y})`);
      });

      if (alpha.value > 0) requestAnimationFrame(tick);
    }

    requestAnimationFrame(tick);

    return () => {
      running = false;
      nodeEls.forEach((ne: { cleanup: () => void }) => ne.cleanup());
    };
  }, [graphData, people]);

  if (loading) return <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading graph...</div>;

  return (
    <div style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 24, position: 'relative' }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
        Relationship Network
      </h3>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
        Circle size reflects mention frequency · Lines show shared pages and topics · Drag to rearrange
      </p>
      <svg ref={svgRef} style={{ width: '100%', height: 500, borderRadius: 'var(--radius)' }} />
      {tooltip && (
        <div style={{
          position: 'fixed', left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)',
          backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
          padding: '6px 10px', boxShadow: 'var(--shadow)', pointerEvents: 'none', zIndex: 100,
          fontSize: 12,
        }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{tooltip.name}</div>
          <div style={{ color: 'var(--text-muted)' }}>{tooltip.role} · {tooltip.org}</div>
          <div style={{ color: 'var(--text-muted)' }}>{tooltip.mentions} mentions</div>
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
        <CalendarCheck size={32} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
        <h3 style={{ fontSize: 16, color: 'var(--text-primary)', marginBottom: 8 }}>Meeting Prep</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          {prep?.reason || prep?.error || 'Connect Microsoft 365 in Settings to get meeting briefings.'}
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
