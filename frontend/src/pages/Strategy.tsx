/**
 * Strategy page — Initiatives, Decisions, Portfolio, Weekly Review.
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useStore } from '../store';
import { getTheme } from '../themes';
import { api } from '../api/client';
import { Target, Scale, Users, BarChart3, CheckCircle2, Circle, GitBranch, Check, X, Sparkles, ChevronRight, ChevronDown, Plus, Pencil, Trash2, Undo2 } from 'lucide-react';
import DetailPanel from '../components/DetailPanel';
import type { DetailField } from '../components/DetailPanel';

type TabId = 'hierarchy' | 'health' | 'decisions' | 'portfolio' | 'review';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'hierarchy', label: 'Hierarchy', icon: <GitBranch size={16} /> },
  { id: 'health', label: 'Health', icon: <Target size={16} /> },
  { id: 'decisions', label: 'Decisions', icon: <Scale size={16} /> },
  { id: 'portfolio', label: 'Portfolio', icon: <Users size={16} /> },
  { id: 'review', label: 'Review', icon: <BarChart3 size={16} /> },
];

const linkBtnStyle: React.CSSProperties = {
  border: 'none', background: 'none', cursor: 'pointer',
  fontSize: 12, color: 'var(--accent)', padding: 0,
  textDecoration: 'none',
};

// Generate quarter options: current year ± 1 year, Q1–Q4
const _currentYear = new Date().getFullYear();
const QUARTER_OPTIONS = [
  '', // allow clearing
  ...[_currentYear - 1, _currentYear, _currentYear + 1].flatMap(y =>
    ['Q1', 'Q2', 'Q3', 'Q4'].map(q => `${q} ${y}`)
  ),
];

const STATUS_COLORS: Record<string, string> = {
  on_track: '#22c55e', at_risk: '#f59e0b', off_track: '#ef4444',
  completed: '#6b7280', paused: '#94a3b8',
  decided: '#3b82f6', pending: '#f59e0b', revisit: '#ef4444', request: '#8b5cf6',
  in_progress: '#3b82f6', active: '#3b82f6',
};

export default function Strategy() {
  const { themeId } = useStore();
  const theme = getTheme(themeId);
  const [tab, setTab] = useState<TabId>(theme.layout.defaultStrategyTab);
  const [strategySummary, setStrategySummary] = useState<any>(null);

  useEffect(() => {
    api.get<any>('/api/strategic-summary').then(setStrategySummary).catch(() => {});
  }, []);

  const currentQ = `Q${Math.ceil((new Date().getMonth() + 1) / 3)} ${new Date().getFullYear()}`;
  const initCount = strategySummary?.initiatives?.total || 0;
  const epicCount = strategySummary?.epics?.total || strategySummary?.initiatives?.epics_count || 0;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)' }}>Strategy</h1>
          {strategySummary && (
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2 }}>
              {currentQ}{initCount ? ` · ${initCount} initiative${initCount !== 1 ? 's' : ''}` : ''}{epicCount ? ` · ${epicCount} epic${epicCount !== 1 ? 's' : ''}` : ''}
            </p>
          )}
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
              {t.icon}{t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'hierarchy' ? <HierarchyView /> :
       tab === 'health' ? <HealthDashboard /> :
       tab === 'decisions' ? <DecisionsView /> :
       tab === 'portfolio' ? <PortfolioView /> :
       <ReviewView />}
    </div>
  );
}

/* ---------- Hierarchy (full agile tree) ---------- */

function HierarchyView() {
  const [tree, setTree] = useState<any[]>([]);
  const [operational, setOperational] = useState<any[]>([]);
  const [unclassified, setUnclassified] = useState<any[]>([]);
  const [counts, setCounts] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [classifying, setClassifying] = useState(false);
  const [classifyStatus, setClassifyStatus] = useState('');
  const [classifyProgress, setClassifyProgress] = useState(0); // 0-100
  // Decision requests linked to hierarchy nodes
  const [hierDecisions, setHierDecisions] = useState<any[]>([]);
  const { user } = useStore();
  const [requestingDecision, setRequestingDecision] = useState(false);
  const [decisionForm, setDecisionForm] = useState({ title: '', requested_from: '' });
  const [selectedDecision, setSelectedDecision] = useState<any>(null);

  // Undo system
  const [undoAction, setUndoAction] = useState<{ label: string; undo: () => void } | null>(null);
  const undoTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const showUndo = useCallback((label: string, undoFn: () => void) => {
    if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
    setUndoAction({ label, undo: undoFn });
    undoTimerRef.current = setTimeout(() => setUndoAction(null), 8000);
  }, []);

  const handleUndo = useCallback(() => {
    if (undoAction) {
      undoAction.undo();
      setUndoAction(null);
      if (undoTimerRef.current) clearTimeout(undoTimerRef.current);
    }
  }, [undoAction]);

  const loadHierarchy = useCallback((silent = false) => {
    if (!silent) setLoading(true);
    api.get<any>('/api/hierarchy').then((data) => {
      setTree(data.tree || []);
      setOperational(data.operational_tasks || []);
      setUnclassified(data.unclassified_tasks || []);
      setCounts(data.counts || {});
      if (!silent) setLoading(false);
    }).catch(() => { if (!silent) setLoading(false); });
    api.get<any>('/api/decisions').then((d) => setHierDecisions(d.decisions || [])).catch(() => {});
  }, []);

  useEffect(() => { loadHierarchy(); }, [loadHierarchy]);

  // Lookup map: node ID → linked decisions
  // Direct decisions per node
  const decisionsByNode = useMemo(() => {
    const map: Record<string, any[]> = {};
    for (const d of hierDecisions) {
      if (d.linked_id) {
        if (!map[d.linked_id]) map[d.linked_id] = [];
        map[d.linked_id].push(d);
      }
    }
    return map;
  }, [hierDecisions]);

  // Bubble up: count pending decisions in all descendants for each node
  const descendantPendingCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    function walk(nodes: any[]): number {
      let total = 0;
      for (const n of nodes) {
        const own = (decisionsByNode[n.id] || []).filter((d: any) => d.status === 'request' || d.status === 'pending').length;
        const childCount = n.children ? walk(n.children) : 0;
        const subtreeCount = own + childCount;
        if (subtreeCount > 0) counts[n.id] = subtreeCount;
        total += subtreeCount;
      }
      return total;
    }
    walk(tree);
    return counts;
  }, [tree, decisionsByNode]);

  // Poll classification status — works even after navigating away and back
  const pollRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const handleStatusUpdate = useCallback((msg: any) => {
    if (msg.message) setClassifyStatus(msg.message);
    if (msg.phase === 'context') setClassifyProgress(5);
    else if (msg.phase === 'phase1') setClassifyProgress(15);
    else if (msg.phase === 'phase2' && msg.current && msg.total) {
      setClassifyProgress(20 + Math.round((msg.current / msg.total) * 65));
    }
    else if (msg.phase === 'grammar') setClassifyProgress(90);

    if (msg.status === 'complete') {
      setClassifyProgress(100);
      setClassifying(false);
      // If we have counts, show them; otherwise show the message from the classifier
      if (msg.themes_created !== undefined) {
        setClassifyStatus(`Done: ${msg.themes_created || 0} themes, ${msg.initiatives_created || 0} initiatives, ${msg.epics_created || 0} epics, ${msg.stories_created || 0} stories`);
      } else if (msg.message) {
        setClassifyStatus(msg.message);
      }
      loadHierarchy();
      stopPolling();
    } else if (msg.status === 'error') {
      setClassifying(false);
      setClassifyStatus(`Classification failed: ${msg.message || 'unknown error'}`);
      loadHierarchy();
      stopPolling();
    }
  }, [loadHierarchy, stopPolling]);

  const startPolling = useCallback(() => {
    stopPolling();
    pollRef.current = setInterval(() => {
      api.get<any>('/api/classify/status').then(handleStatusUpdate).catch(() => {});
    }, 1500);
  }, [handleStatusUpdate, stopPolling]);

  // On mount, check if a classification is already running
  useEffect(() => {
    api.get<any>('/api/classify/status').then((msg) => {
      if (msg.running) {
        setClassifying(true);
        handleStatusUpdate(msg);
        startPolling();
      } else if (msg.status === 'complete' || msg.status === 'error') {
        // Show last result (success or error) from a previous run
        handleStatusUpdate(msg);
      }
    }).catch(() => {});
    return stopPolling;
  }, [handleStatusUpdate, startPolling, stopPolling]);

  const runClassification = useCallback(() => {
    setClassifying(true);
    setClassifyStatus('Starting classification...');
    setClassifyProgress(0);

    api.post<any>('/api/classify').then(() => {
      startPolling();
    }).catch(() => {
      setClassifying(false);
      setClassifyStatus('Failed to start classification');
    });
  }, [startPolling]);

  // --- Click-to-edit hierarchy nodes ---
  const [selectedNode, setSelectedNode] = useState<any | null>(null);

  // Collect all owners from tree for frequency-sorted dropdown
  const collectOwners = useCallback((nodes: any[]): Record<string, number> => {
    const counts: Record<string, number> = {};
    for (const n of nodes) {
      if (n.owner) counts[n.owner] = (counts[n.owner] || 0) + 1;
      if (n.children) {
        const sub = collectOwners(n.children);
        for (const [k, v] of Object.entries(sub)) counts[k] = (counts[k] || 0) + v;
      }
    }
    return counts;
  }, []);
  const ownerCounts = collectOwners(tree);
  const ownerOptions = Object.entries(ownerCounts).sort((a, b) => b[1] - a[1]).map(([name]) => name);

  const getNodeFields = useCallback((node: any): DetailField[] => {
    const t = node.type;
    if (t === 'theme') return [
      { key: 'title', label: 'Title', value: node.title, type: 'text' },
      { key: 'description', label: 'Description', value: node.description, type: 'textarea' },
      { key: 'status', label: 'Status', value: node.status || 'active', type: 'select', options: ['active', 'completed', 'paused'] },
    ];
    if (t === 'initiative') return [
      { key: 'title', label: 'Title', value: node.title, type: 'text' },
      { key: 'description', label: 'Description', value: node.description, type: 'textarea' },
      { key: 'owner', label: 'Owner', value: node.owner, type: 'select', options: ownerOptions },
      { key: 'quarter', label: 'Quarter', value: node.quarter || '', type: 'select', options: QUARTER_OPTIONS, hint: 'Target delivery quarter — the fiscal quarter by which this should be completed' },
      { key: 'status', label: 'Status', value: node.status || 'on_track', type: 'select', options: ['on_track', 'at_risk', 'off_track', 'completed', 'paused'] },
      { key: 'priority', label: 'Priority', value: node.priority || 'high', type: 'select', options: ['high', 'medium', 'low'] },
    ];
    if (t === 'epic') return [
      { key: 'title', label: 'Title', value: node.title, type: 'text' },
      { key: 'description', label: 'Description', value: node.description, type: 'textarea' },
      { key: 'owner', label: 'Owner', value: node.owner, type: 'select', options: ownerOptions },
      { key: 'status', label: 'Status', value: node.status || 'backlog', type: 'select', options: ['backlog', 'in_progress', 'done', 'cancelled'] },
      { key: 'priority', label: 'Priority', value: node.priority || 'high', type: 'select', options: ['high', 'medium', 'low'] },
      { key: 'quarter', label: 'Quarter', value: node.quarter || '', type: 'select', options: QUARTER_OPTIONS, hint: 'Target delivery quarter — the fiscal quarter by which this epic should be completed' },
      { key: 'acceptance_criteria', label: 'Acceptance Criteria', value: node.acceptance_criteria || [], type: 'tags', hint: 'Definition of done — conditions that must be met for this epic to be considered complete' },
    ];
    if (t === 'story') return [
      { key: 'title', label: 'Title', value: node.title, type: 'text' },
      { key: 'description', label: 'Description', value: node.description, type: 'textarea' },
      { key: 'owner', label: 'Owner', value: node.owner, type: 'select', options: ownerOptions },
      { key: 'status', label: 'Status', value: node.status || 'backlog', type: 'select', options: ['backlog', 'ready', 'in_progress', 'in_review', 'done', 'blocked'] },
      { key: 'priority', label: 'Priority', value: node.priority || 'medium', type: 'select', options: ['high', 'medium', 'low'] },
      { key: 'size', label: 'Size', value: node.size || 'M', type: 'select', options: ['XS', 'S', 'M', 'L', 'XL'] },
      { key: 'acceptance_criteria', label: 'Acceptance Criteria', value: node.acceptance_criteria || [], type: 'tags', hint: 'Definition of done — specific conditions that must be met for this story to be accepted' },
    ];
    return [];
  }, [ownerOptions]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node);
  }, []);

  // Optimistic tree update helpers
  const updateNodeInTree = useCallback((nodes: any[], id: string, updater: (n: any) => any): any[] => {
    return nodes.map((n) => {
      if (n.id === id) return updater(n);
      if (n.children) return { ...n, children: updateNodeInTree(n.children, id, updater) };
      return n;
    });
  }, []);

  const removeNodeFromTree = useCallback((nodes: any[], id: string): any[] => {
    return nodes
      .filter((n) => n.id !== id)
      .map((n) => n.children ? { ...n, children: removeNodeFromTree(n.children, id) } : n);
  }, []);

  const nodeEndpointMap: Record<string, string> = {
    theme: '/api/themes', initiative: '/api/initiatives',
    epic: '/api/epics', story: '/api/stories',
  };

  const handleNodeFieldChange = useCallback((key: string, value: any) => {
    if (!selectedNode) return;
    const endpoint = nodeEndpointMap[selectedNode.type];
    if (!endpoint) return;
    setTree((prev) => updateNodeInTree(prev, selectedNode.id, (n) => ({ ...n, [key]: value })));
    setSelectedNode((prev: any) => prev ? { ...prev, [key]: value } : null);
    api.patch<any>(`${endpoint}/${selectedNode.id}`, { [key]: value }).catch(() => {});
  }, [selectedNode, updateNodeInTree]);

  const handleRequestDecision = useCallback(() => {
    if (!selectedNode || !decisionForm.title.trim()) return;
    const nodeLabel = TYPE_LABELS[selectedNode.type] || selectedNode.type;
    api.post<any>('/api/decisions', {
      title: decisionForm.title,
      status: 'request',
      source: 'request',
      requested_by: user?.name || 'Me',
      requested_from: decisionForm.requested_from,
      request_reason: `Needed for: ${selectedNode.title}`,
      linked_type: selectedNode.type,
      linked_id: selectedNode.id,
      linked_title: selectedNode.title,
      from_workstream: `${nodeLabel}: ${selectedNode.title}`,
    }).then((res) => {
      if (res.decision) setHierDecisions((prev) => [res.decision, ...prev]);
    }).catch(() => {});
    setDecisionForm({ title: '', requested_from: '' });
    setRequestingDecision(false);
  }, [selectedNode, decisionForm, user]);

  // Inline node update (e.g. status change from the tree row)
  const handleNodeUpdate = useCallback((node: any, key: string, value: any) => {
    const endpoint = nodeEndpointMap[node.type];
    if (!endpoint) return;
    setTree((prev) => updateNodeInTree(prev, node.id, (n) => ({ ...n, [key]: value })));
    if (selectedNode?.id === node.id) setSelectedNode((prev: any) => prev ? { ...prev, [key]: value } : null);
    api.patch<any>(`${endpoint}/${node.id}`, { [key]: value }).catch(() => {});
  }, [updateNodeInTree, selectedNode]);

  const handleApprove = useCallback((type: string, id: string) => {
    // Optimistic: mark as confirmed locally
    setTree((prev) => updateNodeInTree(prev, id, (n) => ({ ...n, source: 'confirmed' })));
    setOperational((prev) => prev.map((t) => t.id === id ? { ...t, source: 'confirmed' } : t));
    setUnclassified((prev) => prev.map((t) => t.id === id ? { ...t, source: 'confirmed' } : t));
    api.post(`/api/approve/${type}/${id}`, {}).catch((err) => {
      console.error('Approve failed:', err);
      // Don't reload — keep the optimistic update so the UI doesn't flicker
    });
  }, [updateNodeInTree]);

  const handleDismiss = useCallback((type: string, id: string) => {
    // Optimistic: remove from tree locally
    setTree((prev) => removeNodeFromTree(prev, id));
    setOperational((prev) => prev.filter((t) => t.id !== id));
    setUnclassified((prev) => prev.filter((t) => t.id !== id));
    api.post(`/api/dismiss/${type}/${id}`, {}).catch((err) => {
      console.error('Dismiss failed:', err);
    });
    showUndo('Item dismissed', () => loadHierarchy(true));
  }, [removeNodeFromTree, showUndo, loadHierarchy]);

  const handleNodeDelete = useCallback((node: any) => {
    setTree((prev) => removeNodeFromTree(prev, node.id));
    const endpoint = nodeEndpointMap[node.type];
    if (endpoint) {
      api.delete<any>(`${endpoint}/${node.id}`).catch(() => {});
    }
    showUndo(`${TYPE_LABELS[node.type] || node.type} "${node.title || ''}" deleted`, () => {
      loadHierarchy(true);
    });
  }, [removeNodeFromTree, showUndo, loadHierarchy]);

  // Task-level updates
  const handleTaskUpdate = useCallback((taskId: string, updates: Record<string, any>) => {
    api.patch<any>(`/api/intel/tasks/${taskId}`, updates).catch(() => {});
  }, []);

  const handleTaskRemove = useCallback((taskId: string) => {
    setTree((prev) => removeNodeFromTree(prev, taskId));
    setOperational((prev) => prev.filter((t) => t.id !== taskId));
    setUnclassified((prev) => prev.filter((t) => t.id !== taskId));
    api.delete<any>(`/api/intel/tasks/${taskId}`).catch(() => {});
  }, [removeNodeFromTree]);

  const handleTaskAdd = useCallback((parentNode: any, newTask: any) => {
    // Add the new task as a child of the parent story node
    setTree((prev) => updateNodeInTree(prev, parentNode.id, (n) => ({
      ...n, children: [...(n.children || []), newTask],
    })));
  }, [updateNodeInTree]);

  const handleChildAdd = useCallback((parentNode: any, child: any) => {
    setTree((prev) => updateNodeInTree(prev, parentNode.id, (n) => ({
      ...n, children: [...(n.children || []), child],
    })));
  }, [updateNodeInTree]);

  // Collapse/expand all: bump key to force re-mount with different default
  const [expandMode, setExpandMode] = useState<'default' | 'all' | 'none'>('default');
  const [treeKey, setTreeKey] = useState(0);

  const expandAll = useCallback(() => {
    setExpandMode('all');
    setTreeKey((k) => k + 1);
  }, []);

  const collapseAll = useCallback(() => {
    setExpandMode('none');
    setTreeKey((k) => k + 1);
  }, []);

  if (loading) return <LoadingState />;

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, fontSize: 12, color: 'var(--text-muted)', alignItems: 'center' }}>
          <span>{counts.themes || 0} themes</span>
          <span>{counts.initiatives || 0} initiatives</span>
          <span>{counts.epics || 0} epics</span>
          <span>{counts.stories || 0} stories</span>
          <span>{counts.tasks || 0} tasks</span>
          {(counts.linked > 0 || counts.dangling > 0) && (
            <span style={{ fontSize: 11, color: counts.linked > 0 ? '#22c55e' : '#ef4444' }}>
              ({counts.linked || 0} linked{counts.dangling > 0 ? `, ${counts.dangling} orphaned` : ''})
            </span>
          )}
          <span style={{ color: 'var(--border)' }}>|</span>
          <button onClick={expandAll} style={linkBtnStyle}>Expand all</button>
          <button onClick={collapseAll} style={linkBtnStyle}>Collapse all</button>
        </div>
        <button
          onClick={runClassification}
          disabled={classifying}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 16px', border: 'none', borderRadius: 'var(--radius)',
            backgroundColor: classifying ? 'var(--bg-hover)' : 'var(--accent)',
            color: classifying ? 'var(--text-muted)' : '#fff',
            fontSize: 13, fontWeight: 500, cursor: classifying ? 'default' : 'pointer',
          }}
        >
          <Sparkles size={14} />
          {classifying ? 'Classifying...' : 'Classify Tasks'}
        </button>
      </div>

      {classifyStatus && (
        <div style={{
          marginBottom: 12, borderRadius: 'var(--radius)', overflow: 'hidden',
          backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
        }}>
          {classifying && (
            <div style={{
              height: 4, backgroundColor: 'var(--bg-secondary)', borderRadius: 2,
              overflow: 'hidden',
            }}>
              <div style={{
                height: '100%', borderRadius: 2,
                backgroundColor: 'var(--accent)',
                width: `${classifyProgress}%`,
                transition: 'width 0.5s ease',
              }} />
            </div>
          )}
          <div style={{
            padding: '8px 12px', fontSize: 12,
            color: classifying ? 'var(--accent)' : 'var(--text-secondary)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span>{classifyStatus}</span>
            {classifying && <span style={{ color: 'var(--text-muted)' }}>{classifyProgress}%</span>}
          </div>
        </div>
      )}

      {/* Tree */}
      <div key={treeKey} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {tree.map((node) => (
          <HierarchyNode key={node.id} node={node} depth={0} expandMode={expandMode} ownerOptions={ownerOptions} onApprove={handleApprove} onDismiss={handleDismiss} onNodeClick={handleNodeClick} onNodeUpdate={handleNodeUpdate} onNodeDelete={handleNodeDelete} onTaskUpdate={handleTaskUpdate} onTaskRemove={handleTaskRemove} onTaskAdd={handleTaskAdd} onChildAdd={handleChildAdd} nodeDecisions={decisionsByNode} descendantPendingCounts={descendantPendingCounts} onDecisionClick={setSelectedDecision} />
        ))}
      </div>

      {/* Operational tasks */}
      {operational.length > 0 && (
        <CollapsibleTaskSection
          title="Operational tasks"
          count={operational.length}
          subtitle="Day-to-day work not tied to a strategic initiative"
          color="#f59e0b"
          tasks={operational}
          ownerOptions={ownerOptions}
          onApprove={handleApprove}
          onDismiss={handleDismiss}
          onUpdate={handleTaskUpdate}
          onRemove={handleTaskRemove}
        />
      )}

      {/* Unclassified */}
      {unclassified.length > 0 && (
        <CollapsibleTaskSection
          title="Unclassified tasks"
          count={unclassified.length}
          subtitle="Needs review — could be strategic or operational"
          color="var(--text-muted)"
          tasks={unclassified}
          ownerOptions={ownerOptions}
          onApprove={handleApprove}
          onDismiss={handleDismiss}
          onUpdate={handleTaskUpdate}
          onRemove={handleTaskRemove}
        />
      )}

      {/* Detail panel for editing hierarchy nodes */}
      <DetailPanel
        open={!!selectedNode && !selectedDecision}
        onClose={() => { setSelectedNode(null); setRequestingDecision(false); setDecisionForm({ title: '', requested_from: '' }); }}
        title={selectedNode?.title || selectedNode?.description || ''}
        subtitle={selectedNode ? `${TYPE_LABELS[selectedNode.type] || selectedNode.type}${selectedNode.owner ? ` · ${selectedNode.owner}` : ''}` : undefined}
        badge={selectedNode?.source === 'auto' ? { label: 'AI proposed', color: '#8b5cf6' } : undefined}
        fields={selectedNode ? getNodeFields(selectedNode) : []}
        onFieldChange={handleNodeFieldChange}
        onSave={(updates) => {
          if (!selectedNode) return;
          const endpoint = nodeEndpointMap[selectedNode.type];
          if (endpoint) {
            api.patch<any>(`${endpoint}/${selectedNode.id}`, updates).catch(() => {});
          }
          setTree((prev) => updateNodeInTree(prev, selectedNode.id, (n) => ({ ...n, ...updates })));
          setSelectedNode(null);
        }}
        actions={selectedNode?.source === 'auto' ? [
          { label: 'Approve', variant: 'primary' as const, onClick: () => {
            handleApprove(selectedNode.type + 's', selectedNode.id);
            setSelectedNode((prev: any) => prev ? { ...prev, source: 'confirmed' } : null);
          }},
          { label: 'Dismiss', variant: 'danger' as const, onClick: () => {
            handleDismiss(selectedNode.type + 's', selectedNode.id);
            setSelectedNode(null);
          }},
        ] : undefined}
      >
        {/* Inline decision request section — like Acceptance Criteria */}
        {selectedNode && (
          <DecisionRequestSection
            nodeDecisions={decisionsByNode[selectedNode.id] || []}
            adding={requestingDecision}
            form={decisionForm}
            onToggleAdding={(v) => { setRequestingDecision(v); if (!v) setDecisionForm({ title: '', requested_from: '' }); }}
            onFormChange={setDecisionForm}
            onSubmit={handleRequestDecision}
            onDecisionClick={setSelectedDecision}
          />
        )}
      </DetailPanel>

      {/* Detail panel for viewing a decision from hierarchy indicator */}
      <DetailPanel
        open={!!selectedDecision}
        onClose={() => setSelectedDecision(null)}
        title={selectedDecision?.title || ''}
        subtitle={selectedDecision?.request_reason || selectedDecision?.rationale}
        badge={selectedDecision ? { label: (selectedDecision.status || '').replace(/_/g, ' '), color: STATUS_COLORS[selectedDecision.status] || '#94a3b8' } : undefined}
        fields={selectedDecision ? [
          { key: 'status', label: 'Status', value: selectedDecision.status, type: 'select' as const, options: ['pending', 'decided', 'revisit', 'request'], color: STATUS_COLORS[selectedDecision.status] },
          { key: 'decided_by', label: 'Decided By', value: selectedDecision.decided_by, type: 'text' as const },
          { key: 'requested_by', label: 'Requested By', value: selectedDecision.requested_by || '', type: 'readonly' as const },
          { key: 'requested_from', label: 'Decision Needed From', value: selectedDecision.requested_from || '', type: 'text' as const },
          { key: 'request_reason', label: 'Reason', value: selectedDecision.request_reason || '', type: 'textarea' as const },
          { key: 'rationale', label: 'Rationale', value: selectedDecision.rationale || '', type: 'textarea' as const },
          { key: 'outcome_notes', label: 'Outcome Notes', value: selectedDecision.outcome_notes || '', type: 'textarea' as const },
          { key: 'created_at', label: 'Created', value: selectedDecision.created_at ? new Date(selectedDecision.created_at).toLocaleDateString() : '—', type: 'readonly' as const },
        ] : []}
        onSave={(updates) => {
          if (!selectedDecision) return;
          setHierDecisions((prev) => prev.map((d) => d.id === selectedDecision.id ? { ...d, ...updates } : d));
          setSelectedDecision((prev: any) => prev ? { ...prev, ...updates } : null);
          api.patch<any>(`/api/decisions/${selectedDecision.id}`, updates).catch(() => {});
        }}
      >
        <HierarchyBreadcrumb linkedId={selectedDecision?.linked_id} tree={tree} />
      </DetailPanel>

      {/* Undo toast */}
      {undoAction && (
        <div style={{
          position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '10px 16px', borderRadius: 8,
          backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          zIndex: 1000, fontSize: 13,
        }}>
          <span style={{ color: 'var(--text-secondary)' }}>{undoAction.label}</span>
          <button
            onClick={handleUndo}
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '4px 12px', border: 'none', borderRadius: 6,
              backgroundColor: 'var(--accent)', color: '#fff',
              fontSize: 12, fontWeight: 500, cursor: 'pointer',
            }}
          >
            <Undo2 size={12} /> Undo
          </button>
          <button
            onClick={() => setUndoAction(null)}
            style={{
              display: 'flex', alignItems: 'center', padding: 2,
              border: 'none', background: 'none', cursor: 'pointer',
              color: 'var(--text-muted)',
            }}
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

/* Hierarchy tree node — recursive */
const TYPE_COLORS: Record<string, string> = {
  theme: '#8b5cf6', initiative: '#3b82f6', epic: '#10b981', story: '#f59e0b',
};
const TYPE_LABELS: Record<string, string> = {
  theme: 'Theme', initiative: 'Initiative', epic: 'Epic', story: 'Story',
};

const NODE_STATUS_OPTIONS: Record<string, string[]> = {
  theme: ['active', 'completed', 'paused'],
  initiative: ['on_track', 'at_risk', 'off_track', 'completed', 'paused'],
  epic: ['backlog', 'in_progress', 'done', 'cancelled'],
  story: ['backlog', 'ready', 'in_progress', 'in_review', 'done', 'blocked'],
};

function HierarchyNode({ node, depth, expandMode = 'default', ownerOptions = [], onApprove, onDismiss, onNodeClick, onNodeUpdate, onNodeDelete, onTaskUpdate, onTaskRemove, onTaskAdd, onChildAdd, nodeDecisions, descendantPendingCounts, onDecisionClick }: {
  node: any; depth: number;
  expandMode?: 'default' | 'all' | 'none';
  ownerOptions?: string[];
  onApprove: (type: string, id: string) => void;
  onDismiss: (type: string, id: string) => void;
  onNodeClick?: (node: any) => void;
  onNodeUpdate?: (node: any, key: string, value: any) => void;
  onNodeDelete?: (node: any) => void;
  onTaskUpdate?: (id: string, updates: Record<string, any>) => void;
  onTaskRemove?: (id: string) => void;
  onTaskAdd?: (parentNode: any, newTask: any) => void;
  onChildAdd?: (parentNode: any, child: any) => void;
  nodeDecisions?: Record<string, any[]>;
  descendantPendingCounts?: Record<string, number>;
  onDecisionClick?: (decision: any) => void;
}) {
  const defaultExpanded = expandMode === 'all' ? true : expandMode === 'none' ? false : depth < 2;
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [statusOpen, setStatusOpen] = useState(false);
  const [ownerOpen, setOwnerOpen] = useState(false);
  const statusRef = React.useRef<HTMLDivElement>(null);
  const ownerRef = React.useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  React.useEffect(() => {
    if (!statusOpen && !ownerOpen) return;
    const handler = (e: MouseEvent) => {
      if (statusOpen && statusRef.current && !statusRef.current.contains(e.target as Node)) setStatusOpen(false);
      if (ownerOpen && ownerRef.current && !ownerRef.current.contains(e.target as Node)) setOwnerOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [statusOpen, ownerOpen]);
  const children = node.children || [];
  const isAuto = node.source === 'auto';
  const entityType = node.type + 's'; // themes, initiatives, epics, stories

  const [rowHovered, setRowHovered] = useState(false);

  return (
    <div>
      <div
        onClick={() => setExpanded(!expanded)}
        onMouseEnter={() => setRowHovered(true)}
        onMouseLeave={() => setRowHovered(false)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '3px 8px', paddingLeft: depth * 20 + 8,
          borderLeft: `3px ${isAuto ? 'dashed' : 'solid'} ${TYPE_COLORS[node.type] || '#666'}`,
          backgroundColor: rowHovered ? 'var(--bg-hover)' : 'transparent',
          marginBottom: 0,
          color: isAuto ? 'var(--text-muted)' : 'var(--text-primary)',
          cursor: 'pointer',
          transition: 'background-color 0.1s',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', padding: 2 }}>
          {children.length > 0 ? (
            expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : <span style={{ width: 14 }} />}
        </span>

        <span style={{
          fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px',
          color: TYPE_COLORS[node.type] || '#666', minWidth: 60, flexShrink: 0,
        }}>
          {TYPE_LABELS[node.type] || node.type}
        </span>

        <span style={{ fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap' }}>
          {node.title || node.description || '(untitled)'}
        </span>

        {/* Edit button — opens sidebar */}
        <button
          onClick={(e) => { e.stopPropagation(); onNodeClick?.(node); }}
          title="Edit details"
          style={{
            display: 'flex', alignItems: 'center', padding: 2,
            border: 'none', background: 'none', cursor: 'pointer',
            color: 'var(--text-muted)',
            opacity: rowHovered ? 0.7 : 0, transition: 'opacity 0.15s',
          }}
        >
          <Pencil size={12} />
        </button>

        {/* Delete button — on hover */}
        {!isAuto && (
          <button
            onClick={(e) => { e.stopPropagation(); onNodeDelete?.(node); }}
            title="Delete"
            style={{
              display: 'flex', alignItems: 'center', padding: 2,
              border: 'none', background: 'none', cursor: 'pointer',
              color: '#ef4444',
              opacity: rowHovered ? 0.5 : 0, transition: 'opacity 0.15s',
            }}
          >
            <Trash2 size={12} />
          </button>
        )}

        {/* Dotted leader line connecting title to right-side badges */}
        <span style={{
          flex: 1, minWidth: 20,
          borderBottom: '1px dotted var(--border)',
          marginBottom: 2, opacity: rowHovered ? 0.6 : 0.25,
          transition: 'opacity 0.15s',
        }} />

        {isAuto && (
          <>
            <span style={{
              fontSize: 10, padding: '1px 6px', borderRadius: 4,
              backgroundColor: 'var(--accent-light)', color: 'var(--accent)',
            }}>
              AI proposed
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); onApprove(entityType, node.id); }}
              title="Approve"
              style={{
                display: 'flex', alignItems: 'center', padding: 2,
                border: 'none', background: 'none', cursor: 'pointer',
                color: '#22c55e', transition: 'opacity 0.15s',
              }}
            >
              <Check size={16} />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDismiss(entityType, node.id); }}
              title="Dismiss"
              style={{
                display: 'flex', alignItems: 'center', padding: 2,
                border: 'none', background: 'none', cursor: 'pointer',
                color: '#ef4444', transition: 'opacity 0.15s',
              }}
            >
              <X size={14} />
            </button>
          </>
        )}

        {/* Owner inline dropdown */}
        <div ref={ownerRef} style={{ position: 'relative', flexShrink: 0, width: 90, textAlign: 'right' }}>
          {node.type !== 'theme' && (
            <span
              onClick={(e) => { e.stopPropagation(); setOwnerOpen(!ownerOpen); }}
              style={{
                fontSize: 11, padding: '1px 8px', borderRadius: 10, cursor: 'pointer',
                backgroundColor: 'var(--bg-tertiary)',
                color: node.owner ? 'var(--text-secondary)' : 'var(--text-muted)',
                transition: 'background-color 0.1s', display: 'inline-block',
                textAlign: 'center',
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)'}
            >
              {node.owner || '—'}
            </span>
            {ownerOpen && (
              <div style={{
                position: 'absolute', top: '100%', right: 0, zIndex: 100, marginTop: 4,
                backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 6, overflow: 'hidden', minWidth: 140, maxHeight: 200, overflowY: 'auto',
                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
              }}>
                {ownerOptions.map((o) => (
                  <div
                    key={o}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (o !== node.owner) onNodeUpdate?.(node, 'owner', o);
                      setOwnerOpen(false);
                    }}
                    style={{
                      padding: '5px 12px', fontSize: 12, cursor: 'pointer',
                      color: o === node.owner ? 'var(--text-primary)' : 'var(--text-secondary)',
                      fontWeight: o === node.owner ? 600 : 400,
                      transition: 'background-color 0.1s',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    {o}
                  </div>
                ))}
              </div>
            )}
          )}
        </div>

        {node.status && (
          <div ref={statusRef} style={{ position: 'relative', flexShrink: 0, width: 80, textAlign: 'right' }}>
            <span
              onClick={(e) => { e.stopPropagation(); setStatusOpen(!statusOpen); }}
              style={{
                fontSize: 11, padding: '1px 6px', borderRadius: 4, cursor: 'pointer',
                backgroundColor: (STATUS_COLORS[node.status] || '#666') + '20',
                color: STATUS_COLORS[node.status] || '#666',
                transition: 'opacity 0.15s',
              }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '0.8'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
            >
              {(node.status || '').replace(/_/g, ' ')}
            </span>
            {statusOpen && (
              <div style={{
                position: 'absolute', top: '100%', right: 0, zIndex: 100, marginTop: 4,
                backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 6, overflow: 'hidden', minWidth: 120,
                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
              }}>
                {(NODE_STATUS_OPTIONS[node.type] || []).map((s) => (
                  <div
                    key={s}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (s !== node.status) onNodeUpdate?.(node, 'status', s);
                      setStatusOpen(false);
                    }}
                    style={{
                      padding: '5px 12px', fontSize: 12, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 8,
                      color: s === node.status ? 'var(--text-primary)' : 'var(--text-secondary)',
                      fontWeight: s === node.status ? 600 : 400,
                      transition: 'background-color 0.1s',
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <span style={{
                      width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                      backgroundColor: STATUS_COLORS[s] || '#666',
                    }} />
                    {s.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Decision indicators — direct + bubble-up from descendants */}
        {(() => {
          const decs = nodeDecisions?.[node.id] || [];
          const pending = decs.filter((d: any) => d.status === 'request' || d.status === 'pending');
          const decided = decs.filter((d: any) => d.status === 'decided');
          const descendantCount = (descendantPendingCounts?.[node.id] || 0) - pending.length;
          if (!decs.length && descendantCount <= 0) return null;
          return (
            <>
              {pending.length > 0 && (
                <span
                  onClick={(e) => { e.stopPropagation(); onDecisionClick?.(pending[0]); }}
                  title={pending.map((d: any) => d.title).join(', ')}
                  style={{
                    fontSize: 10, padding: '1px 6px', borderRadius: 4, cursor: 'pointer',
                    backgroundColor: '#8b5cf620', color: '#8b5cf6', fontWeight: 500,
                    whiteSpace: 'nowrap', flexShrink: 0,
                  }}
                >
                  {pending.length} decision{pending.length > 1 ? 's' : ''} needed
                </span>
              )}
              {decided.length > 0 && pending.length === 0 && descendantCount <= 0 && (
                <span
                  onClick={(e) => { e.stopPropagation(); onDecisionClick?.(decided[0]); }}
                  title={decided.map((d: any) => d.title).join(', ')}
                  style={{
                    fontSize: 10, padding: '1px 6px', borderRadius: 4, cursor: 'pointer',
                    backgroundColor: '#3b82f620', color: '#3b82f6', fontWeight: 500,
                    whiteSpace: 'nowrap', flexShrink: 0,
                  }}
                >
                  {decided.length} decided
                </span>
              )}
              {/* Bubble-up: pending decisions in children not directly on this node */}
              {descendantCount > 0 && pending.length === 0 && (
                <span
                  onClick={(e) => { e.stopPropagation(); }}
                  title={`${descendantCount} pending decision${descendantCount > 1 ? 's' : ''} in child items`}
                  style={{
                    fontSize: 10, padding: '1px 6px', borderRadius: 4,
                    backgroundColor: '#8b5cf610', color: '#8b5cf6', fontWeight: 400,
                    whiteSpace: 'nowrap', flexShrink: 0, fontStyle: 'italic', opacity: 0.8,
                  }}
                >
                  {descendantCount} decision{descendantCount > 1 ? 's' : ''} pending below
                </span>
              )}
            </>
          );
        })()}
      </div>

      {expanded && (
        <>
          {children.map((child: any) => (
            child.type ? (
              <HierarchyNode key={child.id} node={child} depth={depth + 1} expandMode={expandMode} ownerOptions={ownerOptions} onApprove={onApprove} onDismiss={onDismiss} onNodeClick={onNodeClick} onNodeUpdate={onNodeUpdate} onNodeDelete={onNodeDelete} onTaskUpdate={onTaskUpdate} onTaskRemove={onTaskRemove} onTaskAdd={onTaskAdd} onChildAdd={onChildAdd} nodeDecisions={nodeDecisions} descendantPendingCounts={descendantPendingCounts} onDecisionClick={onDecisionClick} />
            ) : (
              <TaskLeaf key={child.id} task={child} depth={depth + 1} ownerOptions={ownerOptions} onApprove={onApprove} onDismiss={onDismiss} onUpdate={onTaskUpdate} onRemove={onTaskRemove} />
            )
          ))}
          {/* Add task row for story/epic nodes that have task children */}
          {(node.type === 'story' || node.type === 'epic') && children.some((c: any) => !c.type) && (
            <AddTaskRow
              depth={depth + 1}
              parentTaskId={children.find((c: any) => !c.type)?.id || ''}
              onAdd={(newTask) => onTaskAdd?.(node, newTask)}
            />
          )}
          {/* Add child hierarchy node rows */}
          {node.type === 'initiative' && (
            <AddChildRow depth={depth + 1} parentNode={node} childType="epic" onAdd={(p, c) => onChildAdd?.(p, c)} />
          )}
          {node.type === 'epic' && (
            <AddChildRow depth={depth + 1} parentNode={node} childType="story" onAdd={(p, c) => onChildAdd?.(p, c)} />
          )}
        </>
      )}
    </div>
  );
}

/* Task leaf node */
const TASK_STATUS_COLORS: Record<string, string> = {
  done: '#22c55e', in_progress: '#3b82f6', review: '#f59e0b', open: '#64748b',
};

const PREVIEW_COUNT = 10;

function CollapsibleTaskSection({ title, count, subtitle, color, tasks, ownerOptions, onApprove, onDismiss, onUpdate, onRemove }: {
  title: string; count: number; subtitle: string; color: string;
  tasks: any[]; ownerOptions: string[];
  onApprove: (type: string, id: string) => void;
  onDismiss: (type: string, id: string) => void;
  onUpdate: (id: string, updates: Record<string, any>) => void;
  onRemove: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? tasks : tasks.slice(0, PREVIEW_COUNT);
  const hasMore = tasks.length > PREVIEW_COUNT;

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
        <h3 style={{ fontSize: 14, fontWeight: 500, color }}>
          {title} ({count})
        </h3>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{subtitle}</span>
      </div>
      {visible.map((t: any) => (
        <TaskLeaf key={t.id} task={t} borderColor={color} ownerOptions={ownerOptions} onApprove={onApprove} onDismiss={onDismiss} onUpdate={onUpdate} onRemove={onRemove} />
      ))}
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            border: 'none', background: 'none', cursor: 'pointer',
            fontSize: 12, color: 'var(--accent)', padding: '6px 8px',
            marginTop: 2,
          }}
        >
          {expanded ? 'Show less' : `Show all ${count} tasks`}
        </button>
      )}
    </div>
  );
}

function TaskLeaf({ task, depth = 0, borderColor = '#94a3b8', ownerOptions = [], onApprove, onDismiss, onRemove, onUpdate }: {
  task: any; depth?: number; borderColor?: string; ownerOptions?: string[];
  onApprove: (type: string, id: string) => void;
  onDismiss: (type: string, id: string) => void;
  onRemove?: (id: string) => void;
  onUpdate?: (id: string, updates: Record<string, any>) => void;
}) {
  const isAuto = task.source === 'auto';
  const isDone = task.status === 'done';
  const [editingField, setEditingField] = useState<'description' | 'owner' | null>(null);
  const [editValue, setEditValue] = useState('');
  const [ownerSearch, setOwnerSearch] = useState('');
  const [hovered, setHovered] = useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const ownerInputRef = React.useRef<HTMLInputElement>(null);
  const ownerDropRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (editingField === 'description' && inputRef.current) inputRef.current.focus();
    if (editingField === 'owner' && ownerInputRef.current) ownerInputRef.current.focus();
  }, [editingField]);

  // Close owner picker on outside click
  React.useEffect(() => {
    if (editingField !== 'owner') return;
    const handler = (e: MouseEvent) => {
      if (ownerDropRef.current && !ownerDropRef.current.contains(e.target as Node)) {
        setEditingField(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [editingField]);

  const startEdit = (field: 'description' | 'owner') => {
    setEditingField(field);
    if (field === 'description') setEditValue(task.description || '');
    if (field === 'owner') setOwnerSearch('');
  };

  const saveEdit = () => {
    if (!editingField) return;
    if (editingField === 'description') {
      const val = editValue.trim();
      if (val && val !== task.description) {
        task.description = val;
        onUpdate?.(task.id, { description: val });
      }
    }
    setEditingField(null);
  };

  const selectOwner = (name: string) => {
    if (name !== task.owner) {
      task.owner = name;
      onUpdate?.(task.id, { owner: name });
    }
    setEditingField(null);
  };

  const filteredOwners = ownerOptions.filter(o =>
    o.toLowerCase().includes(ownerSearch.toLowerCase())
  );

  const toggleDone = () => {
    const newStatus = isDone ? 'open' : 'done';
    task.status = newStatus;
    onUpdate?.(task.id, { status: newStatus });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') saveEdit();
    if (e.key === 'Escape') setEditingField(null);
  };

  const status = task.status || 'open';
  const statusColor = TASK_STATUS_COLORS[status] || '#64748b';

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '3px 8px', paddingLeft: depth * 20 + 28,
        borderLeft: `3px ${isAuto ? 'dashed' : 'solid'} ${borderColor}`,
        marginBottom: 0,
        backgroundColor: hovered ? 'var(--bg-hover)' : 'transparent',
        color: isAuto ? 'var(--text-muted)' : 'var(--text-secondary)',
        fontSize: 12,
        opacity: isDone ? 0.5 : 1,
        transition: 'background-color 0.1s',
      }}
    >
      {/* Checkbox */}
      <button
        onClick={toggleDone}
        title={isDone ? 'Mark open' : 'Mark done'}
        style={{
          flexShrink: 0, width: 16, height: 16, borderRadius: 4, cursor: 'pointer',
          border: `1.5px solid ${isDone ? '#22c55e' : 'var(--border)'}`,
          backgroundColor: isDone ? '#22c55e' : 'transparent',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 0, transition: 'all 0.15s',
        }}
      >
        {isDone && <Check size={10} style={{ color: '#fff' }} />}
      </button>

      {/* Description + remove button grouped together */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4, minWidth: 0 }}>
        {editingField === 'description' ? (
          <input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={saveEdit}
            onKeyDown={handleKeyDown}
            style={{
              flex: 1, fontSize: 12, padding: '2px 6px', border: '1px solid var(--accent)',
              borderRadius: 4, backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)',
              outline: 'none',
            }}
          />
        ) : (
          <span
            onClick={() => startEdit('description')}
            style={{
              cursor: 'text', borderRadius: 4, padding: '1px 4px',
              textDecoration: isDone ? 'line-through' : 'none',
              transition: 'background-color 0.1s',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            {task.description || '(no description)'}
          </span>
        )}

        {/* Remove button — right next to title */}
        {!isAuto && onRemove && (
          <button
            onClick={() => onRemove(task.id)}
            title="Remove task"
            style={{
              display: 'flex', alignItems: 'center', padding: 2, border: 'none', background: 'none',
              cursor: 'pointer', color: 'var(--text-muted)', flexShrink: 0,
              opacity: hovered ? 0.7 : 0, transition: 'opacity 0.15s',
            }}
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* Owner badge / picker */}
      {editingField === 'owner' ? (
        <div ref={ownerDropRef} style={{ position: 'relative', flexShrink: 0 }}>
          <input
            ref={ownerInputRef}
            value={ownerSearch}
            onChange={(e) => setOwnerSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && filteredOwners.length > 0) selectOwner(filteredOwners[0]);
              if (e.key === 'Enter' && ownerSearch.trim() && filteredOwners.length === 0) selectOwner(ownerSearch.trim());
              if (e.key === 'Escape') setEditingField(null);
            }}
            placeholder="Search..."
            style={{
              width: 110, fontSize: 11, padding: '2px 6px', border: '1px solid var(--accent)',
              borderRadius: 4, backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)',
              outline: 'none',
            }}
          />
          <div style={{
            position: 'absolute', top: '100%', right: 0, zIndex: 100,
            backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
            borderRadius: 6, marginTop: 2, maxHeight: 150, overflowY: 'auto',
            minWidth: 120, boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          }}>
            {filteredOwners.map(o => (
              <div
                key={o}
                onClick={() => selectOwner(o)}
                style={{
                  padding: '4px 10px', fontSize: 11, cursor: 'pointer',
                  color: o === task.owner ? 'var(--accent)' : 'var(--text-secondary)',
                  fontWeight: o === task.owner ? 600 : 400,
                  transition: 'background-color 0.1s',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                {o}
              </div>
            ))}
            {filteredOwners.length === 0 && ownerSearch.trim() && (
              <div
                onClick={() => selectOwner(ownerSearch.trim())}
                style={{ padding: '4px 10px', fontSize: 11, cursor: 'pointer', color: 'var(--accent)', fontStyle: 'italic' }}
              >
                Add "{ownerSearch.trim()}"
              </div>
            )}
          </div>
        </div>
      ) : (
        <span
          onClick={() => startEdit('owner')}
          style={{
            fontSize: 10, color: 'var(--text-muted)', cursor: 'pointer',
            padding: '2px 8px', borderRadius: 10,
            backgroundColor: 'var(--bg-tertiary)',
            transition: 'background-color 0.1s', flexShrink: 0,
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)'}
        >
          {task.owner || '—'}
        </span>
      )}

      {/* Status pill */}
      <span style={{
        fontSize: 10, fontWeight: 500, padding: '2px 8px', borderRadius: 10, flexShrink: 0,
        backgroundColor: statusColor + '20', color: statusColor,
      }}>
        {status.replace(/_/g, ' ')}
      </span>

      {/* AI actions */}
      {isAuto && (
        <>
          <button onClick={() => onApprove('tasks', task.id)} title="Approve"
            style={{ display: 'flex', alignItems: 'center', padding: 2, border: 'none', background: 'none', cursor: 'pointer', color: '#22c55e' }}>
            <Check size={14} />
          </button>
          <button onClick={() => onDismiss('tasks', task.id)} title="Dismiss"
            style={{ display: 'flex', alignItems: 'center', padding: 2, border: 'none', background: 'none', cursor: 'pointer', color: '#ef4444' }}>
            <X size={14} />
          </button>
        </>
      )}

    </div>
  );
}

/* Inline add task input */
function AddChildRow({ depth, parentNode, childType, onAdd }: {
  depth: number; parentNode: any; childType: 'epic' | 'story';
  onAdd: (parentNode: any, child: any) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [value, setValue] = useState('');
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (adding && inputRef.current) inputRef.current.focus();
  }, [adding]);

  const save = () => {
    const title = value.trim();
    if (!title) { setAdding(false); return; }
    const endpoint = childType === 'epic' ? '/api/epics' : '/api/stories';
    const parentKey = childType === 'epic' ? 'initiative_id' : 'epic_id';
    api.post<any>(endpoint, { title, [parentKey]: parentNode.id })
      .then((res) => { if (res[childType]) onAdd(parentNode, { ...res[childType], type: childType, children: [] }); })
      .catch(() => {});
    setValue('');
    setAdding(false);
  };

  if (!adding) {
    return (
      <div
        onClick={() => setAdding(true)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '4px 8px', paddingLeft: depth * 20 + 28,
          marginBottom: 1, fontSize: 12, color: 'var(--text-muted)',
          cursor: 'pointer', transition: 'color 0.1s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent)'}
        onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
      >
        <Plus size={12} />
        <span>Add {childType}</span>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '4px 8px', paddingLeft: depth * 20 + 28,
      marginBottom: 1,
    }}>
      <Plus size={12} style={{ color: 'var(--accent)', flexShrink: 0 }} />
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') { setValue(''); setAdding(false); } }}
        placeholder={`New ${childType} title...`}
        style={{
          flex: 1, fontSize: 12, padding: '3px 8px', border: '1px solid var(--accent)',
          borderRadius: 4, backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)',
          outline: 'none',
        }}
      />
    </div>
  );
}

function AddTaskRow({ depth, parentTaskId, onAdd }: {
  depth: number; parentTaskId: string;
  onAdd: (task: any) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [value, setValue] = useState('');
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (adding && inputRef.current) inputRef.current.focus();
  }, [adding]);

  const save = () => {
    const desc = value.trim();
    if (!desc) { setAdding(false); return; }
    api.post<any>(`/api/intel/tasks/${parentTaskId}/create-from-step`, { step_description: desc })
      .then((res) => { if (res.task) onAdd(res.task); })
      .catch(() => {});
    setValue('');
    setAdding(false);
  };

  if (!adding) {
    return (
      <div
        onClick={() => setAdding(true)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '4px 8px', paddingLeft: depth * 20 + 28,
          marginBottom: 1, fontSize: 12, color: 'var(--text-muted)',
          cursor: 'pointer', transition: 'color 0.1s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent)'}
        onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
      >
        <Plus size={12} />
        <span>Add task</span>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '4px 8px', paddingLeft: depth * 20 + 28,
      marginBottom: 1,
    }}>
      <Plus size={12} style={{ color: 'var(--accent)', flexShrink: 0 }} />
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') { setValue(''); setAdding(false); } }}
        placeholder="New task description..."
        style={{
          flex: 1, fontSize: 12, padding: '3px 8px', border: '1px solid var(--accent)',
          borderRadius: 4, backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)',
          outline: 'none',
        }}
      />
    </div>
  );
}

/* ---------- Initiatives ---------- */

/* ---------- Health Dashboard ---------- */

interface NodeMetrics { total: number; done: number; blocked: number; inProgress: number; }

function aggregateMetrics(node: any): NodeMetrics {
  // Task leaf (no type field)
  if (!node.type) {
    return { total: 1, done: node.status === 'done' ? 1 : 0, blocked: 0, inProgress: 0 };
  }
  // Story — check if blocked
  if (node.type === 'story') {
    const childMetrics = (node.children || []).reduce(
      (acc: NodeMetrics, c: any) => { const m = aggregateMetrics(c); return { total: acc.total + m.total, done: acc.done + m.done, blocked: acc.blocked + m.blocked, inProgress: acc.inProgress + m.inProgress }; },
      { total: 0, done: 0, blocked: 0, inProgress: 0 },
    );
    if (node.status === 'blocked') childMetrics.blocked += 1;
    return childMetrics;
  }
  return (node.children || []).reduce(
    (acc: NodeMetrics, c: any) => { const m = aggregateMetrics(c); return { total: acc.total + m.total, done: acc.done + m.done, blocked: acc.blocked + m.blocked, inProgress: acc.inProgress + m.inProgress }; },
    { total: 0, done: 0, blocked: 0, inProgress: 0 },
  );
}

function countByStatus(nodes: any[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const n of nodes) counts[n.status || 'unknown'] = (counts[n.status || 'unknown'] || 0) + 1;
  return counts;
}

function HealthBar({ counts, total }: { counts: Record<string, number>; total: number }) {
  if (total === 0) return null;
  const segments = [
    { key: 'completed', color: '#16a34a' }, { key: 'on_track', color: '#4ade80' },
    { key: 'at_risk', color: '#f59e0b' }, { key: 'paused', color: '#94a3b8' },
    { key: 'off_track', color: '#ef4444' },
  ];
  return (
    <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', backgroundColor: 'var(--border)', width: 80, flexShrink: 0 }}>
      {segments.map(({ key, color }) => {
        const c = counts[key] || 0;
        if (c === 0) return null;
        return <div key={key} style={{ width: `${(c / total) * 100}%`, backgroundColor: color, transition: 'width 0.3s' }} />;
      })}
    </div>
  );
}

function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 120 }}>
      <div style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: 'var(--border)', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', backgroundColor: pct === 100 ? '#22c55e' : 'var(--accent)', borderRadius: 2, transition: 'width 0.3s' }} />
      </div>
      <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 32, textAlign: 'right' }}>{pct}%</span>
    </div>
  );
}

function CompletionSparkline({ data }: { data: { date: string; count: number }[] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  const max = Math.max(...data.map((d) => d.count), 1);
  const w = 600, h = 48, pad = 2;

  const points = data.map((d, i) => {
    const x = pad + (i / (data.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((d.count / max) * (h - 2 * pad));
    return `${x},${y}`;
  });
  const line = points.join(' ');
  const area = `${pad},${h - pad} ${line} ${w - pad},${h - pad}`;

  return (
    <div style={{
      ...cardStyle, padding: '12px 20px', marginBottom: 20,
      display: 'flex', alignItems: 'center', gap: 16,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Completions · Last 30 days</span>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{total} completed</span>
        </div>
        <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 48 }} preserveAspectRatio="none">
          <polygon points={area} fill="var(--accent)" opacity="0.15" />
          <polyline points={line} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        </svg>
      </div>
    </div>
  );
}

function HealthDashboard() {
  const [tree, setTree] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [review, setReview] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [expandedThemes, setExpandedThemes] = useState<Set<string>>(new Set());
  const [expandedInits, setExpandedInits] = useState<Set<string>>(new Set());
  const [selectedEpic, setSelectedEpic] = useState<any>(null);
  const [trendData, setTrendData] = useState<{ date: string; count: number }[]>([]);

  useEffect(() => {
    Promise.all([
      api.get<any>('/api/hierarchy').catch(() => ({ tree: [] })),
      api.get<any>('/api/strategic-summary').catch(() => null),
      api.get<any>('/api/review/weekly').catch(() => null),
      api.get<any>('/api/analytics/completion-trend').catch(() => ({ days: [] })),
    ]).then(([hierData, sumData, revData, trendRes]) => {
      setTree(hierData.tree || []);
      setSummary(sumData);
      setReview(revData);
      setTrendData(trendRes?.days || []);
      setLoading(false);
    });
  }, []);

  if (loading) return <LoadingState />;

  // Collect owners for dropdowns
  const collectOwnersFn = (nodes: any[]): Record<string, number> => {
    const counts: Record<string, number> = {};
    for (const n of nodes) {
      if (n.owner) counts[n.owner] = (counts[n.owner] || 0) + 1;
      if (n.children) { const sub = collectOwnersFn(n.children); for (const [k, v] of Object.entries(sub)) counts[k] = (counts[k] || 0) + v; }
    }
    return counts;
  };
  const ownerOptions = Object.entries(collectOwnersFn(tree)).sort((a, b) => b[1] - a[1]).map(([name]) => name);

  // Compute metrics
  const themeMetrics = new Map<string, NodeMetrics>();
  let totalTasks = 0, totalDone = 0, totalBlocked = 0, totalInProgress = 0, totalOverdue = 0;
  for (const theme of tree) {
    const m = aggregateMetrics(theme);
    themeMetrics.set(theme.id, m);
    totalTasks += m.total;
    totalDone += m.done;
    totalBlocked += m.blocked;
    totalInProgress += m.inProgress;
  }
  totalOverdue = review?.smart_tasks?.overdue?.length || 0;

  const initStats = summary?.initiatives;

  // Collect attention items
  const attentionItems: { label: string; detail: string; color: string }[] = [];
  for (const theme of tree) {
    for (const init of theme.children || []) {
      if (init.status === 'off_track') attentionItems.push({ label: init.title, detail: `Off track · ${init.owner || 'No owner'}`, color: '#ef4444' });
      if (init.status === 'at_risk') attentionItems.push({ label: init.title, detail: `At risk · ${init.owner || 'No owner'}`, color: '#f59e0b' });
      for (const epic of init.children || []) {
        const epicM = aggregateMetrics(epic);
        if (epicM.blocked > 0) attentionItems.push({ label: epic.title, detail: `${epicM.blocked} blocked stories`, color: '#ef4444' });
      }
    }
  }

  const handleStatusChange = (type: string, id: string, newStatus: string) => {
    const endpoint = type === 'initiative' ? '/api/initiatives' : '/api/epics';
    setTree((prev) => {
      const update = (nodes: any[]): any[] => nodes.map((n) => {
        if (n.id === id) return { ...n, status: newStatus };
        if (n.children) return { ...n, children: update(n.children) };
        return n;
      });
      return update(prev);
    });
    api.patch<any>(`${endpoint}/${id}`, { status: newStatus }).catch(() => {});
  };

  const toggleTheme = (id: string) => setExpandedThemes((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
  const toggleInit = (id: string) => setExpandedInits((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });

  return (
    <>
      {/* Section A: Summary Ribbon */}
      {/* Row 1: Hero progress bar */}
      <div style={{ ...cardStyle, padding: '16px 20px', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 16 }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>Overall Progress</span>
        <div style={{ flex: 1, height: 8, borderRadius: 4, backgroundColor: 'var(--border)', overflow: 'hidden' }}>
          <div style={{
            width: `${totalTasks > 0 ? Math.round((totalDone / totalTasks) * 100) : 0}%`,
            height: '100%',
            backgroundColor: totalDone === totalTasks && totalTasks > 0 ? '#22c55e' : 'var(--accent)',
            borderRadius: 4,
            transition: 'width 0.3s',
          }} />
        </div>
        <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
          {totalTasks > 0 ? Math.round((totalDone / totalTasks) * 100) : 0}%
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
          {totalDone} / {totalTasks} tasks
        </span>
      </div>

      {/* Row 2: Metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 12 }}>
        <MiniStatCard label="Init On Track" value={`${initStats?.on_track || 0}/${initStats?.total || 0}`} color="#22c55e" />
        <MiniStatCard label="At Risk" value={initStats?.at_risk_count || 0} color="#f59e0b" />
        <MiniStatCard label="Off Track" value={initStats?.off_track_count || 0} color="#ef4444" />
        <MiniStatCard label="In Progress" value={totalInProgress} color="#3b82f6" />
        <MiniStatCard label="Overdue" value={totalOverdue} color="#ef4444" />
        <MiniStatCard label="Blocked" value={totalBlocked} color="#ef4444" />
      </div>

      {/* Row 3: Completion trend sparkline — only show when there's data */}
      {trendData.some(d => d.count > 0) && <CompletionSparkline data={trendData} />}

      {/* Section B: Theme Health Cards */}
      {tree.length === 0 ? (
        <EmptyState message="No themes yet. Run Classify Tasks from the Hierarchy tab." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {tree.map((theme) => {
            const m = themeMetrics.get(theme.id) || { total: 0, done: 0, blocked: 0, inProgress: 0 };
            const initiatives = (theme.children || []).filter((c: any) => c.type === 'initiative');
            const initStatusCounts = countByStatus(initiatives);
            const epicsInProgress = initiatives.flatMap((i: any) => (i.children || []).filter((e: any) => e.status === 'in_progress')).length;
            const expanded = expandedThemes.has(theme.id);
            const pct = m.total > 0 ? Math.round((m.done / m.total) * 100) : 0;

            return (
              <div key={theme.id}>
                {/* Theme row */}
                <div
                  onClick={() => toggleTheme(theme.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
                    borderLeft: '3px solid #a855f7', cursor: 'pointer',
                    color: 'var(--text-primary)',
                    transition: 'background-color 0.1s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <span style={{ fontSize: 14, fontWeight: 600, whiteSpace: 'nowrap', color: 'var(--text-primary)' }}>{theme.title}</span>
                  <span style={{ flex: 1, borderBottom: '1px dotted var(--border)', marginBottom: 2, opacity: 0.25 }} />
                  <HealthBar counts={initStatusCounts} total={initiatives.length} />
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {initiatives.length} init · {epicsInProgress} epics active · {pct}% done
                  </span>
                </div>

                {/* Expanded initiatives */}
                {expanded && initiatives.map((init: any) => {
                  const initM = aggregateMetrics(init);
                  const epics = (init.children || []).filter((c: any) => c.type === 'epic');
                  const initExpanded = expandedInits.has(init.id);

                  return (
                    <div key={init.id}>
                      <div
                        onClick={() => toggleInit(init.id)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 8, padding: '4px 12px', paddingLeft: 36,
                          borderLeft: `3px solid ${STATUS_COLORS[init.status] || '#64748b'}`,
                          cursor: 'pointer', color: 'var(--text-primary)', transition: 'background-color 0.1s',
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                      >
                        {initExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        <span style={{ fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', color: 'var(--text-primary)' }}>{init.title}</span>
                        <span style={{ flex: 1, borderBottom: '1px dotted var(--border)', marginBottom: 2, opacity: 0.25 }} />
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{init.owner || ''}</span>
                        {init.quarter && <span style={{ fontSize: 10, color: 'var(--text-muted)', padding: '1px 5px', backgroundColor: 'var(--bg-tertiary)', borderRadius: 4 }}>{init.quarter}</span>}
                        <ProgressBar done={initM.done} total={initM.total} />
                        <HealthStatusPill status={init.status} type="initiative" id={init.id} onChange={handleStatusChange} />
                      </div>

                      {/* Expanded epics */}
                      {initExpanded && epics.map((epic: any) => {
                        const epicM = aggregateMetrics(epic);
                        const storiesDone = (epic.children || []).filter((s: any) => s.type === 'story' && s.status === 'done').length;
                        const storyCount = (epic.children || []).filter((s: any) => s.type === 'story').length;
                        return (
                          <div
                            key={epic.id}
                            onClick={() => setSelectedEpic(epic)}
                            style={{
                              display: 'flex', alignItems: 'center', gap: 8, padding: '3px 12px', paddingLeft: 56,
                              borderLeft: `3px solid ${STATUS_COLORS[epic.status] || '#64748b'}`,
                              cursor: 'pointer', color: 'var(--text-primary)', transition: 'background-color 0.1s', fontSize: 12,
                            }}
                            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                          >
                            <span style={{ color: 'var(--text-secondary)' }}>{epic.title}</span>
                            <span style={{ flex: 1, borderBottom: '1px dotted var(--border)', marginBottom: 2, opacity: 0.25 }} />
                            {epicM.blocked > 0 && <span style={{ fontSize: 10, color: '#ef4444', fontWeight: 600 }}>{epicM.blocked} blocked</span>}
                            <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{storiesDone}/{storyCount} stories</span>
                            <ProgressBar done={epicM.done} total={epicM.total} />
                            <HealthStatusPill status={epic.status} type="epic" id={epic.id} onChange={handleStatusChange} />
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}

      {/* Section C: Attention Required */}
      {attentionItems.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3 style={{ fontSize: 14, fontWeight: 500, color: '#f59e0b', marginBottom: 8 }}>Attention Required ({attentionItems.length})</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {attentionItems.slice(0, 10).map((item, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '4px 12px',
                borderLeft: `3px solid ${item.color}`, fontSize: 12,
              }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#f59e0b', flexShrink: 0 }} />
                <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{item.label}</span>
                <span style={{ flex: 1, borderBottom: '1px dotted var(--border)', marginBottom: 2, opacity: 0.25 }} />
                <span style={{ color: 'var(--text-muted)' }}>{item.detail}</span>
              </div>
            ))}
            {attentionItems.length > 10 && (
              <span style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 12px' }}>+ {attentionItems.length - 10} more</span>
            )}
          </div>
        </div>
      )}

      {/* Epic detail panel */}
      {selectedEpic && (
        <DetailPanel
          open={!!selectedEpic}
          onClose={() => setSelectedEpic(null)}
          title={selectedEpic.title}
          subtitle={`Epic · ${selectedEpic.owner || 'Unassigned'}`}
          fields={[
            { key: 'description', label: 'Description', value: selectedEpic.description, type: 'textarea' },
            { key: 'status', label: 'Status', value: selectedEpic.status || 'backlog', type: 'select', options: ['backlog', 'in_progress', 'done', 'cancelled'] },
            { key: 'owner', label: 'Owner', value: selectedEpic.owner, type: 'select', options: ownerOptions },
            { key: 'priority', label: 'Priority', value: selectedEpic.priority || 'high', type: 'select', options: ['high', 'medium', 'low'] },
            { key: 'quarter', label: 'Quarter', value: selectedEpic.quarter || '', type: 'select', options: QUARTER_OPTIONS, hint: 'Target delivery quarter' },
            { key: 'acceptance_criteria', label: 'Acceptance Criteria', value: selectedEpic.acceptance_criteria || [], type: 'tags' },
          ]}
          onFieldChange={(key, value) => {
            setSelectedEpic((prev: any) => prev ? { ...prev, [key]: value } : null);
            api.patch<any>(`/api/epics/${selectedEpic.id}`, { [key]: value }).catch(() => {});
          }}
        />
      )}
    </>
  );
}

/* Inline status pill with dropdown for health dashboard */
function HealthStatusPill({ status, type, id, onChange }: {
  status: string; type: string; id: string;
  onChange: (type: string, id: string, newStatus: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const options = type === 'initiative'
    ? ['on_track', 'at_risk', 'off_track', 'completed', 'paused']
    : ['backlog', 'in_progress', 'done', 'cancelled'];

  return (
    <div ref={ref} style={{ position: 'relative', flexShrink: 0 }}>
      <span
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        style={{
          fontSize: 10, padding: '1px 6px', borderRadius: 4, cursor: 'pointer',
          backgroundColor: (STATUS_COLORS[status] || '#666') + '20',
          color: STATUS_COLORS[status] || '#666',
        }}
      >
        {(status || '').replace(/_/g, ' ')}
      </span>
      {open && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, zIndex: 100, marginTop: 4,
          backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 6, overflow: 'hidden', minWidth: 120,
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
        }}>
          {options.map((s) => (
            <div
              key={s}
              onClick={(e) => { e.stopPropagation(); onChange(type, id, s); setOpen(false); }}
              style={{
                padding: '4px 10px', fontSize: 11, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 6,
                fontWeight: s === status ? 600 : 400,
                color: s === status ? 'var(--text-primary)' : 'var(--text-secondary)',
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: STATUS_COLORS[s] || '#666' }} />
              {s.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- Decisions ---------- */

function DecisionsView() {
  const [decisions, setDecisions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<any>(null);
  const [filter, setFilter] = useState<string>('all');
  // Inline add
  const [adding, setAdding] = useState(false);
  const [addValue, setAddValue] = useState('');
  const addRef = React.useRef<HTMLInputElement>(null);
  // Decision request form
  const [requesting, setRequesting] = useState(false);
  const [requestForm, setRequestForm] = useState({ title: '', requested_from: '', request_reason: '', from_workstream: '' });
  // Hover delete
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  // Notion import
  const [notionOpen, setNotionOpen] = useState(false);
  const [notionDecisions, setNotionDecisions] = useState<any[]>([]);
  const [notionSelected, setNotionSelected] = useState<Set<number>>(new Set());
  const [notionLoading, setNotionLoading] = useState(false);

  // Load hierarchy tree for breadcrumb context
  const [hierTree, setHierTree] = useState<any[]>([]);

  useEffect(() => {
    api.get<any>('/api/decisions').then((data) => {
      setDecisions(data.decisions || []);
      setLoading(false);
    }).catch((e) => { setError(e.message); setLoading(false); });
    api.get<any>('/api/hierarchy').then((data) => setHierTree(data.tree || [])).catch(() => {});
  }, []);


  React.useEffect(() => {
    if (adding && addRef.current) addRef.current.focus();
  }, [adding]);

  const handleSave = useCallback((updates: Record<string, any>) => {
    if (!selected) return;
    setDecisions((prev) => prev.map((d) => d.id === selected.id ? { ...d, ...updates } : d));
    setSelected((prev: any) => prev ? { ...prev, ...updates } : null);
    api.patch<any>(`/api/decisions/${selected.id}`, updates).catch(() => {});
  }, [selected]);

  const handleAdd = () => {
    const title = addValue.trim();
    if (!title) { setAdding(false); return; }
    api.post<any>('/api/decisions', { title, status: 'pending', source: 'manual' })
      .then((res) => { if (res.decision) setDecisions((prev) => [res.decision, ...prev]); })
      .catch(() => {});
    setAddValue('');
    setAdding(false);
  };

  const handleRequest = () => {
    const title = requestForm.title.trim();
    if (!title) { setRequesting(false); return; }
    api.post<any>('/api/decisions', {
      title, status: 'request', source: 'request', requested_by: 'Me',
      requested_from: requestForm.requested_from, request_reason: requestForm.request_reason,
      from_workstream: requestForm.from_workstream,
    }).then((res) => { if (res.decision) setDecisions((prev) => [res.decision, ...prev]); })
      .catch(() => {});
    setRequestForm({ title: '', requested_from: '', request_reason: '', from_workstream: '' });
    setRequesting(false);
  };

  const handleDelete = (id: string) => {
    setDecisions((prev) => prev.filter((d) => d.id !== id));
    api.delete<any>(`/api/decisions/${id}`).catch(() => {});
  };

  const handleStatusCycle = (d: any, e: React.MouseEvent) => {
    e.stopPropagation();
    const order = ['pending', 'decided', 'request', 'revisit'];
    const idx = order.indexOf(d.status);
    const next = order[(idx + 1) % order.length];
    setDecisions((prev) => prev.map((dec) => dec.id === d.id ? { ...dec, status: next } : dec));
    api.patch<any>(`/api/decisions/${d.id}`, { status: next }).catch(() => {});
  };

  const openNotionImport = () => {
    setNotionOpen(true);
    setNotionLoading(true);
    api.get<any>('/api/decisions/notion-preview').then((data) => {
      setNotionDecisions(data.decisions || []);
      setNotionLoading(false);
    }).catch(() => { setNotionLoading(false); });
  };

  const toggleNotionSelect = (idx: number) => {
    setNotionSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const handleNotionImport = () => {
    const items = Array.from(notionSelected).map((i) => notionDecisions[i]).filter((d) => !d.already_imported);
    if (!items.length) return;
    api.post<any>('/api/decisions/notion-import', { decisions: items }).then((res) => {
      if (res.decisions) setDecisions((prev) => [...res.decisions, ...prev]);
      setNotionOpen(false);
      setNotionSelected(new Set());
    }).catch(() => {});
  };

  // Handle inline field changes for decisions
  const handleDecisionFieldChange = useCallback((key: string, value: any) => {
    if (!selected) return;
    setDecisions((prev) => prev.map((d) => d.id === selected.id ? { ...d, [key]: value } : d));
    setSelected((prev: any) => prev ? { ...prev, [key]: value } : null);
    api.patch<any>(`/api/decisions/${selected.id}`, { [key]: value }).catch(() => {});
  }, [selected]);

  // Link decision to a hierarchy item
  const handleLinkToHierarchy = useCallback((node: { type: string; title: string; id: string }) => {
    if (!selected) return;
    const updates = { linked_type: node.type, linked_id: node.id, linked_title: node.title };
    setDecisions((prev) => prev.map((d) => d.id === selected.id ? { ...d, ...updates } : d));
    setSelected((prev: any) => prev ? { ...prev, ...updates } : null);
    api.patch<any>(`/api/decisions/${selected.id}`, updates).catch(() => {});
  }, [selected]);

  const handleUnlinkHierarchy = useCallback(() => {
    if (!selected) return;
    const updates = { linked_type: '', linked_id: '', linked_title: '' };
    setDecisions((prev) => prev.map((d) => d.id === selected.id ? { ...d, ...updates } : d));
    setSelected((prev: any) => prev ? { ...prev, ...updates } : null);
    api.patch<any>(`/api/decisions/${selected.id}`, updates).catch(() => {});
  }, [selected]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  const filtered = filter === 'all' ? decisions : decisions.filter((d) => d.status === filter);

  const fields: DetailField[] = selected ? [
    { key: 'status', label: 'Status', value: selected.status, type: 'select', options: ['pending', 'decided', 'revisit', 'request'], color: STATUS_COLORS[selected.status] },
    { key: 'decided_by', label: 'Decided By', value: selected.decided_by, type: 'text' },
    { key: 'stakeholders', label: 'Stakeholders', value: selected.stakeholders || [], type: 'tags' },
    { key: 'rationale', label: 'Rationale', value: selected.rationale, type: 'textarea' },
    { key: 'context', label: 'Context', value: selected.context, type: 'textarea' },
    { key: 'requested_from', label: 'Decision Needed From', value: selected.requested_from || '', type: 'text' },
    { key: 'request_reason', label: 'Request Reason', value: selected.request_reason || '', type: 'textarea' },
    { key: 'outcome_notes', label: 'Outcome Notes', value: selected.outcome_notes, type: 'textarea' },
    { key: 'source', label: 'Source', value: selected.source || 'manual', type: 'readonly' },
    { key: 'created_at', label: 'Created', value: selected.created_at ? new Date(selected.created_at).toLocaleDateString() : '—', type: 'readonly' },
    { key: 'updated_at', label: 'Last Updated', value: selected.updated_at ? new Date(selected.updated_at).toLocaleDateString() : '—', type: 'readonly' },
  ] : [];

  const btnStyle: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 4, padding: '5px 12px',
    fontSize: 12, borderRadius: 6, cursor: 'pointer', border: '1px solid var(--border)',
    backgroundColor: 'transparent', color: 'var(--text-secondary)', transition: 'all 0.15s',
  };

  return (
    <>
      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <button style={btnStyle} onClick={() => { setAdding(!adding); setRequesting(false); }}>
          <Plus size={12} /> Add Decision
        </button>
        <button style={btnStyle} onClick={() => { setRequesting(!requesting); setAdding(false); }}>
          <Plus size={12} /> Request Decision
        </button>
        <button style={btnStyle} onClick={openNotionImport}>
          <Sparkles size={12} /> Import from Notion
        </button>
      </div>

      {/* Inline add input */}
      {adding && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
          <Plus size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
          <input
            ref={addRef}
            value={addValue}
            onChange={(e) => setAddValue(e.target.value)}
            onBlur={handleAdd}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); if (e.key === 'Escape') { setAddValue(''); setAdding(false); } }}
            placeholder="Decision title..."
            style={{
              flex: 1, fontSize: 13, padding: '6px 10px', border: '1px solid var(--accent)',
              borderRadius: 6, backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)', outline: 'none',
            }}
          />
        </div>
      )}

      {/* Decision request form */}
      {requesting && (
        <div style={{ ...cardStyle, marginBottom: 12, borderLeft: '3px solid #8b5cf6' }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: 'var(--text-primary)' }}>Request a Decision</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {([
              ['title', 'What decision is needed?'],
              ['requested_from', 'Decision needed from (e.g. Steering Committee, CTO)'],
              ['request_reason', 'Why? What\'s blocked?'],
              ['from_workstream', 'From which workstream/task?'],
            ] as [string, string][]).map(([key, placeholder]) => (
              <input
                key={key}
                value={(requestForm as any)[key]}
                onChange={(e) => setRequestForm((prev) => ({ ...prev, [key]: e.target.value }))}
                onKeyDown={(e) => { if (e.key === 'Enter' && key === 'from_workstream') handleRequest(); if (e.key === 'Escape') setRequesting(false); }}
                placeholder={placeholder}
                style={{
                  fontSize: 12, padding: '5px 10px', border: '1px solid var(--border)',
                  borderRadius: 4, backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)', outline: 'none',
                }}
              />
            ))}
            <div style={{ display: 'flex', gap: 6 }}>
              <button onClick={handleRequest} style={{ ...btnStyle, backgroundColor: '#8b5cf6', color: '#fff', border: 'none' }}>
                <Check size={12} /> Submit Request
              </button>
              <button onClick={() => setRequesting(false)} style={btnStyle}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Notion import section */}
      {notionOpen && (
        <div style={{ ...cardStyle, marginBottom: 12, borderLeft: '3px solid var(--accent)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Import from Notion Knowledge Graph</div>
            <button onClick={() => setNotionOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}><X size={14} /></button>
          </div>
          {notionLoading ? (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: 12 }}>Loading Notion decisions...</div>
          ) : notionDecisions.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: 12 }}>No decisions found in Notion pages. Run a Notion scan first.</div>
          ) : (
            <>
              <div style={{ maxHeight: 260, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {notionDecisions.map((nd, i) => (
                  <label key={i} style={{
                    display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 8px', borderRadius: 4,
                    fontSize: 12, cursor: nd.already_imported ? 'default' : 'pointer',
                    opacity: nd.already_imported ? 0.5 : 1,
                    backgroundColor: notionSelected.has(i) ? 'var(--accent-light)' : 'transparent',
                  }}>
                    <input
                      type="checkbox"
                      checked={notionSelected.has(i)}
                      disabled={nd.already_imported}
                      onChange={() => toggleNotionSelect(i)}
                      style={{ marginTop: 2 }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{nd.text}</div>
                      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                        {nd.by && `By: ${nd.by} · `}From: {nd.page_title || 'Unknown page'}
                        {nd.last_edited && ` · ${new Date(nd.last_edited).toLocaleDateString()}`}
                        {nd.already_imported && ' · Already imported'}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
              <div style={{ marginTop: 10, display: 'flex', gap: 6 }}>
                <button onClick={handleNotionImport} disabled={notionSelected.size === 0} style={{
                  ...btnStyle, backgroundColor: notionSelected.size > 0 ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: notionSelected.size > 0 ? '#fff' : 'var(--text-muted)', border: 'none',
                }}>
                  <Check size={12} /> Import Selected ({notionSelected.size})
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Filter chips */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        {['all', 'pending', 'decided', 'request', 'revisit'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: '5px 12px', fontSize: 12, borderRadius: 16, cursor: 'pointer',
              border: filter === f ? '1px solid var(--accent)' : '1px solid var(--border)',
              backgroundColor: filter === f ? 'var(--accent-light)' : 'transparent',
              color: filter === f ? 'var(--accent)' : 'var(--text-muted)',
              fontWeight: filter === f ? 500 : 400, textTransform: 'capitalize',
            }}
          >
            {f} {f !== 'all' && `(${decisions.filter((d) => d.status === f).length})`}
            {f === 'all' && ` (${decisions.length})`}
          </button>
        ))}
      </div>

      {/* Decision cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {filtered.length === 0 ? (
          <EmptyState message={filter === 'all' ? 'No decisions logged yet. Click "+ Add Decision" to get started.' : `No ${filter} decisions.`} />
        ) : (
          filtered.map((d) => (
            <div
              key={d.id}
              onClick={() => setSelected(d)}
              onMouseEnter={(e) => { setHoveredId(d.id); e.currentTarget.style.backgroundColor = 'var(--bg-hover)'; e.currentTarget.style.boxShadow = 'var(--shadow)'; }}
              onMouseLeave={(e) => { setHoveredId(null); e.currentTarget.style.backgroundColor = 'var(--bg-card)'; e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; }}
              style={{
                ...cardStyle, cursor: 'pointer', transition: 'all 0.15s', position: 'relative',
                borderLeft: `3px solid ${STATUS_COLORS[d.status] || '#94a3b8'}`,
              }}
            >
              {/* Delete button on hover */}
              {hoveredId === d.id && (
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(d.id); }}
                  title="Delete decision"
                  style={{
                    position: 'absolute', top: 8, right: 8, background: 'none', border: 'none',
                    cursor: 'pointer', color: 'var(--text-muted)', padding: 2, borderRadius: 4,
                    display: 'flex', alignItems: 'center',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.color = '#ef4444'}
                  onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
                >
                  <X size={14} />
                </button>
              )}

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4, paddingRight: 24 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{d.title}</h3>
                <span onClick={(e) => handleStatusCycle(d, e)} title="Click to cycle status" style={{ cursor: 'pointer' }}>
                  <StatusBadge status={d.status} />
                </span>
              </div>

              {d.rationale && <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6, lineHeight: 1.5 }}>{d.rationale}</p>}

              {/* Request metadata */}
              {d.status === 'request' && (d.requested_from || d.request_reason || d.from_workstream) && (
                <div style={{ fontSize: 12, color: '#8b5cf6', marginBottom: 6, padding: '4px 8px', backgroundColor: '#8b5cf620', borderRadius: 4 }}>
                  {d.requested_from && <span>Requested from: <strong>{d.requested_from}</strong></span>}
                  {d.request_reason && <span> · Reason: {d.request_reason}</span>}
                  {d.from_workstream && <span> · From: {d.from_workstream}</span>}
                </div>
              )}

              <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                <span>By: {d.decided_by || 'Unknown'}</span>
                {d.stakeholders?.length > 0 && <span>Stakeholders: {d.stakeholders.join(', ')}</span>}
                {d.initiative && <span>Initiative: {d.initiative}</span>}
                {d.linked_title && (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                    <span style={{
                      fontSize: 10, padding: '1px 5px', borderRadius: 3, fontWeight: 500, textTransform: 'capitalize',
                      backgroundColor: (STATUS_COLORS[d.linked_type] || '#64748b') + '20',
                      color: STATUS_COLORS[d.linked_type] || '#64748b',
                    }}>{d.linked_type}</span>
                    {d.linked_title}
                  </span>
                )}
                {d.source && d.source !== 'manual' && (
                  <span style={{ fontStyle: 'italic' }}>via {d.source}</span>
                )}
                <span>{d.created_at ? new Date(d.created_at).toLocaleDateString() : ''}</span>
              </div>
            </div>
          ))
        )}
      </div>

      <DetailPanel
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.title || ''}
        subtitle={selected?.rationale}
        badge={selected ? { label: (selected.status || '').replace(/_/g, ' '), color: STATUS_COLORS[selected.status] || '#94a3b8' } : undefined}
        fields={fields}
        onFieldChange={handleDecisionFieldChange}
        onSave={handleSave}
      >
        {/* Hierarchy link — breadcrumb + picker */}
        {selected && (
          <HierarchyLinker
            linkedId={selected.linked_id}
            tree={hierTree}
            onLink={handleLinkToHierarchy}
            onUnlink={handleUnlinkHierarchy}
          />
        )}
      </DetailPanel>
    </>
  );
}

/* ---------- Hierarchy Breadcrumb (shows path to linked item) ---------- */

function HierarchyBreadcrumb({ linkedId, tree }: { linkedId?: string; tree: any[] }) {
  const path = useMemo(() => {
    if (!linkedId) return null;
    function find(nodes: any[], trail: { type: string; title: string; id: string }[]): { type: string; title: string; id: string }[] | null {
      for (const n of nodes) {
        const current = [...trail, { type: n.type, title: n.title || n.description || '', id: n.id }];
        if (n.id === linkedId) return current;
        if (n.children) {
          const found = find(n.children, current);
          if (found) return found;
        }
      }
      return null;
    }
    return find(tree, []);
  }, [linkedId, tree]);

  if (!path) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <GitBranch size={14} style={{ color: 'var(--text-muted)' }} />
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>From Hierarchy</span>
      </div>
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 0,
        borderLeft: '2px solid var(--border)', marginLeft: 6, paddingLeft: 12,
      }}>
        {path.map((seg, i) => {
          const isLast = i === path.length - 1;
          const typeColor = TYPE_COLORS[seg.type] || '#666';
          return (
            <div key={seg.id} style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0',
              position: 'relative',
            }}>
              <span style={{
                position: 'absolute', left: -17, width: 8, height: 8,
                borderRadius: '50%', backgroundColor: isLast ? typeColor : 'var(--border)',
                border: isLast ? `2px solid ${typeColor}` : '2px solid var(--bg-primary)',
              }} />
              <span style={{
                fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px',
                color: typeColor, minWidth: 48,
              }}>
                {seg.type}
              </span>
              <span style={{
                fontSize: 12, color: isLast ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontWeight: isLast ? 600 : 400,
              }}>
                {seg.title}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------- Hierarchy Linker (breadcrumb + tree picker for decisions) ---------- */

function HierarchyLinker({ linkedId, tree, onLink, onUnlink }: {
  linkedId?: string;
  tree: any[];
  onLink: (node: { type: string; title: string; id: string }) => void;
  onUnlink: () => void;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);

  // Find path for current linked item
  const path = useMemo(() => {
    if (!linkedId) return null;
    function find(nodes: any[], trail: { type: string; title: string; id: string }[]): { type: string; title: string; id: string }[] | null {
      for (const n of nodes) {
        const current = [...trail, { type: n.type, title: n.title || n.description || '', id: n.id }];
        if (n.id === linkedId) return current;
        if (n.children) {
          const found = find(n.children, current);
          if (found) return found;
        }
      }
      return null;
    }
    return find(tree, []);
  }, [linkedId, tree]);

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <GitBranch size={14} style={{ color: 'var(--text-muted)' }} />
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Linked Hierarchy Item</span>
      </div>

      {/* Show current link as breadcrumb */}
      {path && (
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 0,
          borderLeft: '2px solid var(--border)', marginLeft: 6, paddingLeft: 12, marginBottom: 8,
        }}>
          {path.map((seg, i) => {
            const isLast = i === path.length - 1;
            const typeColor = TYPE_COLORS[seg.type] || '#666';
            return (
              <div key={seg.id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 0', position: 'relative' }}>
                <span style={{
                  position: 'absolute', left: -17, width: 8, height: 8, borderRadius: '50%',
                  backgroundColor: isLast ? typeColor : 'var(--border)',
                  border: isLast ? `2px solid ${typeColor}` : '2px solid var(--bg-primary)',
                }} />
                <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: typeColor, minWidth: 48 }}>
                  {seg.type}
                </span>
                <span style={{ fontSize: 12, color: isLast ? 'var(--text-primary)' : 'var(--text-secondary)', fontWeight: isLast ? 600 : 400 }}>
                  {seg.title}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        <button
          onClick={() => setPickerOpen(!pickerOpen)}
          style={{
            fontSize: 11, padding: '3px 8px', borderRadius: 8,
            border: '1px dashed var(--border)', background: 'none',
            color: 'var(--text-muted)', cursor: 'pointer', transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-muted)'; }}
        >
          {path ? 'Change' : '+ Link to hierarchy'}
        </button>
        {path && (
          <button
            onClick={onUnlink}
            style={{
              fontSize: 11, padding: '3px 8px', borderRadius: 8,
              border: '1px dashed var(--border)', background: 'none',
              color: 'var(--text-muted)', cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#ef4444'; e.currentTarget.style.color = '#ef4444'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-muted)'; }}
          >
            Unlink
          </button>
        )}
      </div>

      {/* Expandable tree picker */}
      {pickerOpen && (
        <div style={{
          marginTop: 8, maxHeight: 280, overflowY: 'auto',
          border: '1px solid var(--border)', borderRadius: 'var(--radius)',
          backgroundColor: 'var(--bg-secondary)', padding: 4,
        }}>
          {tree.map((node) => (
            <PickerNode key={node.id} node={node} depth={0} selectedId={linkedId} onSelect={(n) => {
              onLink(n);
              setPickerOpen(false);
            }} />
          ))}
        </div>
      )}
    </div>
  );
}

function PickerNode({ node, depth, selectedId, onSelect }: {
  node: any; depth: number; selectedId?: string;
  onSelect: (n: { type: string; title: string; id: string }) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 1);
  const children = (node.children || []).filter((c: any) => c.type);
  const isSelected = node.id === selectedId;
  const typeColor = TYPE_COLORS[node.type] || '#666';

  return (
    <div>
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 4, padding: '3px 6px',
          paddingLeft: depth * 14 + 6, cursor: 'pointer', borderRadius: 4,
          backgroundColor: isSelected ? (typeColor + '20') : 'transparent',
          transition: 'background-color 0.1s',
        }}
        onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--bg-hover)'; }}
        onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent'; }}
      >
        {children.length > 0 ? (
          <span onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }} style={{ display: 'flex', padding: 1 }}>
            {expanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          </span>
        ) : <span style={{ width: 12 }} />}
        <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', color: typeColor, minWidth: 36 }}>
          {(node.type || '').slice(0, 4)}
        </span>
        <span
          onClick={() => onSelect({ type: node.type, title: node.title || node.description || '', id: node.id })}
          style={{
            fontSize: 11, color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: isSelected ? 600 : 400, flex: 1,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}
        >
          {node.title || node.description || '(untitled)'}
        </span>
        {isSelected && <Check size={12} style={{ color: typeColor, flexShrink: 0 }} />}
      </div>
      {expanded && children.map((child: any) => (
        <PickerNode key={child.id} node={child} depth={depth + 1} selectedId={selectedId} onSelect={onSelect} />
      ))}
    </div>
  );
}

/* ---------- Decision Request Section (inline in DetailPanel) ---------- */

function DecisionRequestSection({ nodeDecisions, adding, form, onToggleAdding, onFormChange, onSubmit, onDecisionClick }: {
  nodeDecisions: any[];
  adding: boolean;
  form: { title: string; requested_from: string };
  onToggleAdding: (v: boolean) => void;
  onFormChange: (f: { title: string; requested_from: string }) => void;
  onSubmit: () => void;
  onDecisionClick: (d: any) => void;
}) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  React.useEffect(() => { if (adding && inputRef.current) inputRef.current.focus(); }, [adding]);

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <Scale size={14} style={{ color: 'var(--text-muted)' }} />
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Decisions</span>
      </div>

      {/* Existing decisions linked to this node */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
        {nodeDecisions.length === 0 && !adding && (
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>—</span>
        )}
        {nodeDecisions.map((d: any) => (
          <span
            key={d.id}
            onClick={() => onDecisionClick(d)}
            style={{
              fontSize: 11, padding: '3px 8px', borderRadius: 8, cursor: 'pointer',
              backgroundColor: (STATUS_COLORS[d.status] || '#94a3b8') + '20',
              color: STATUS_COLORS[d.status] || '#94a3b8',
              display: 'inline-flex', alignItems: 'center', gap: 4, maxWidth: '100%',
            }}
            title={d.title}
          >
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.title}</span>
            <span style={{ fontSize: 9, opacity: 0.7 }}>({d.status})</span>
          </span>
        ))}

        {/* + Request button / inline form */}
        {adding ? (
          <div style={{ width: '100%', marginTop: 4, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <input
              ref={inputRef}
              value={form.title}
              onChange={(e) => onFormChange({ ...form, title: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && form.title.trim()) onSubmit();
                if (e.key === 'Escape') { onToggleAdding(false); }
              }}
              placeholder="What decision is needed?"
              style={{
                fontSize: 11, padding: '4px 8px', borderRadius: 8,
                border: '1px solid var(--accent)', backgroundColor: 'var(--bg-secondary)',
                color: 'var(--text-primary)', outline: 'none', width: '100%',
              }}
            />
            <input
              value={form.requested_from}
              onChange={(e) => onFormChange({ ...form, requested_from: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && form.title.trim()) onSubmit();
                if (e.key === 'Escape') { onToggleAdding(false); }
              }}
              placeholder="Decision needed from (e.g. CTO, Steering Committee)"
              style={{
                fontSize: 11, padding: '4px 8px', borderRadius: 8,
                border: '1px solid var(--border)', backgroundColor: 'var(--bg-secondary)',
                color: 'var(--text-primary)', outline: 'none', width: '100%',
              }}
            />
            <div style={{ display: 'flex', gap: 4 }}>
              <button
                onClick={() => { if (form.title.trim()) onSubmit(); }}
                disabled={!form.title.trim()}
                style={{
                  fontSize: 11, padding: '3px 8px', borderRadius: 8, border: 'none',
                  backgroundColor: form.title.trim() ? '#8b5cf6' : 'var(--bg-secondary)',
                  color: form.title.trim() ? '#fff' : 'var(--text-muted)',
                  cursor: form.title.trim() ? 'pointer' : 'default',
                }}
              >Submit</button>
              <button
                onClick={() => onToggleAdding(false)}
                style={{
                  fontSize: 11, padding: '3px 8px', borderRadius: 8,
                  border: '1px solid var(--border)', background: 'none',
                  color: 'var(--text-muted)', cursor: 'pointer',
                }}
              >Cancel</button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => onToggleAdding(true)}
            style={{
              fontSize: 11, padding: '3px 8px', borderRadius: 8,
              border: '1px dashed var(--border)', background: 'none',
              color: 'var(--text-muted)', cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#8b5cf6'; e.currentTarget.style.color = '#8b5cf6'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-muted)'; }}
          >
            + Request
          </button>
        )}
      </div>
    </div>
  );
}

/* ---------- Portfolio ---------- */

function PortfolioView() {
  const [portfolio, setPortfolio] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<{ name: string; data: any } | null>(null);

  useEffect(() => {
    api.get<any>('/api/portfolio').then((data) => {
      setPortfolio(data.portfolio || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;

  // Sort by total workload descending — busiest people first, hide zero-workload entries
  const allMembers = Object.entries(portfolio);
  const members = allMembers
    .filter(([, data]) => (data.workload?.total_items || 0) > 0)
    .sort(([, a], [, b]) => (b.workload?.total_items || 0) - (a.workload?.total_items || 0));
  const hiddenCount = allMembers.length - members.length;

  const wl = selected?.data?.workload || {};

  // Build compact summary for sidebar
  const epicsSummary = selected?.data?.epics?.length
    ? selected.data.epics.map((e: any) => {
        const stories = e.story_count ? `${e.story_count} stories` : 'no stories';
        return `[${(e.status || 'backlog').replace(/_/g, ' ')}] ${e.title} (${stories})`;
      }).join('\n')
    : '';

  const needsEpicSummary = selected?.data?.needs_epic?.length
    ? selected.data.needs_epic.map((t: any) => `- ${t.description}`).join('\n')
    : '';

  const fields: DetailField[] = selected ? [
    ...(selected.data.role ? [{ key: 'role', label: 'Role', value: selected.data.role, type: 'readonly' as const }] : []),
    { key: 'summary', label: 'Workload Summary', value: [
      `${wl.epics || 0} epics, ${wl.stories || 0} stories, ${wl.smart_tasks || 0} tasks, ${wl.tracked_tasks || 0} tracked`,
      ...(wl.blocked > 0 ? [`${wl.blocked} blocked`] : []),
      ...(wl.overdue > 0 ? [`${wl.overdue} overdue`] : []),
    ].join(' · '), type: 'readonly' as const },
    ...(epicsSummary ? [{ key: 'epics_detail', label: `Epics (${selected.data.epics.length})`, value: epicsSummary, type: 'expandable' as const }] : []),
    ...(needsEpicSummary ? [{ key: 'needs_epic', label: `Needs Epic (${selected.data.needs_epic.length})`, value: needsEpicSummary, type: 'expandable' as const }] : []),
  ] : [];

  return (
    <>
      {members.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, fontSize: 12, color: 'var(--text-muted)' }}>
          <span>{members.length} member{members.length !== 1 ? 's' : ''} with active work</span>
          {hiddenCount > 0 && <span>{hiddenCount} with no assigned items</span>}
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
        {members.length === 0 ? (
          <EmptyState message={allMembers.length > 0 ? `${allMembers.length} team members found but none have assigned epics, stories, or tasks. Assign owners in the Hierarchy tab.` : 'No portfolio data. Run a Notion scan first.'} />
        ) : (
          members.map(([name, data]: [string, any]) => {
            const w = data.workload || {};
            const totalItems = w.total_items || 0;
            const blocked = w.blocked || 0;
            const overdue = w.overdue || 0;
            const needsEpic = data.needs_epic_count || 0;
            // Compact inline stats
            const stats = [
              w.epics ? `${w.epics} epics` : null,
              w.stories ? `${w.stories} stories` : null,
              (w.smart_tasks || 0) + (w.tracked_tasks || 0) > 0 ? `${(w.smart_tasks || 0) + (w.tracked_tasks || 0)} tasks` : null,
            ].filter(Boolean);
            return (
              <div
                key={name}
                onClick={() => setSelected({ name, data })}
                style={{
                  ...cardStyle, cursor: 'pointer', transition: 'all 0.15s',
                  padding: '12px 14px',
                  borderLeft: `3px solid ${blocked > 0 ? '#ef4444' : overdue > 0 ? '#f59e0b' : 'var(--border)'}`,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--bg-hover)';
                  e.currentTarget.style.boxShadow = 'var(--shadow)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--bg-card)';
                  e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%', background: 'var(--accent)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#fff', fontSize: 12, fontWeight: 600, flexShrink: 0,
                  }}>
                    {name.charAt(0)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
                      {stats.join(' · ') || 'no items'}
                    </div>
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', flexShrink: 0 }}>{totalItems}</span>
                </div>
                {(blocked > 0 || overdue > 0 || needsEpic > 0) && (
                  <div style={{ display: 'flex', gap: 6, marginTop: 6, marginLeft: 36, fontSize: 10 }}>
                    {blocked > 0 && <span style={{ color: '#ef4444' }}>{blocked} blocked</span>}
                    {overdue > 0 && <span style={{ color: '#f59e0b' }}>{overdue} overdue</span>}
                    {needsEpic > 0 && <span style={{ color: '#8b5cf6' }}>{needsEpic} need epic</span>}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <DetailPanel
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.name || ''}
        subtitle={selected?.data?.role || 'Team member'}
        fields={fields}
      />
    </>
  );
}

/* ---------- Review ---------- */

function ReviewView() {
  const [review, setReview] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState<any>(null);

  useEffect(() => {
    api.get<any>('/api/review/weekly').then((data) => {
      setReview(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;
  if (!review) return <EmptyState message="No review data available." />;

  const st = review.smart_tasks || {};
  const delegation = review.delegation || {};
  const topics = review.topics || {};

  const overdueFields: DetailField[] = selectedTask ? [
    { key: 'owner', label: 'Owner', value: selectedTask.owner, type: 'readonly' },
    { key: 'follow_up_date', label: 'Follow-up Date', value: selectedTask.follow_up_date, type: 'readonly' },
    { key: 'days_overdue', label: 'Days Overdue', value: selectedTask.days_overdue, type: 'readonly' },
  ] : [];

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <MiniStatCard label="Open Tasks" value={st.open || 0} />
        <MiniStatCard label="Completed" value={st.done || 0} color="#22c55e" />
        <MiniStatCard label="Overdue" value={st.overdue_count || 0} color="#ef4444" />
        <MiniStatCard label="Tracked" value={review.tracked_tasks?.open || 0} />
      </div>

      {/* Quadrant breakdown */}
      {st.quadrants && (
        <div style={{ ...cardStyle, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--text-primary)' }}>Priority Distribution</h3>
          <div style={{ display: 'flex', gap: 12 }}>
            {Object.entries(st.quadrants as Record<string, number>).map(([q, count]) => {
              const qi = parseInt(q);
              const ql = (qi >= 1 && qi <= 4) ? { 1: 'Do First', 2: 'Schedule', 3: 'Delegate', 4: 'Defer' }[qi] : q;
              const colors: Record<number, string> = { 1: '#ef4444', 2: '#3b82f6', 3: '#f59e0b', 4: '#94a3b8' };
              return (
                <div key={q} style={{ flex: 1, textAlign: 'center', padding: '12px 8px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius)', borderTop: `3px solid ${colors[qi] || '#94a3b8'}` }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>{count}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{ql}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Delegation summary */}
      {Object.keys(delegation).length > 0 && (
        <div style={{ ...cardStyle, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--text-primary)' }}>Delegation Summary</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {Object.entries(delegation).map(([owner, data]: [string, any]) => (
              <div key={owner} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 12px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius)',
              }}>
                <span style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>{owner}</span>
                <div style={{ display: 'flex', gap: 12, fontSize: 12 }}>
                  <span style={{ color: 'var(--text-muted)' }}>{data.count} tasks</span>
                  {data.overdue > 0 && <span style={{ color: '#ef4444' }}>{data.overdue} overdue</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Topics */}
      {Object.keys(topics).length > 0 && (
        <div style={{ ...cardStyle, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--text-primary)' }}>Active Topics</h3>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {Object.entries(topics).sort(([, a]: any, [, b]: any) => b - a).slice(0, 15).map(([topic, count]: [string, any]) => (
              <span key={topic} style={{
                fontSize: 12, padding: '4px 10px', borderRadius: 12,
                backgroundColor: 'var(--bg-secondary)', color: 'var(--text-secondary)',
              }}>
                {topic} ({count})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Overdue items */}
      {st.overdue?.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: '#ef4444' }}>Overdue Items</h3>
          {st.overdue.slice(0, 15).map((t: any, i: number) => (
            <div
              key={i}
              onClick={() => setSelectedTask(t)}
              style={{
                padding: '10px 12px', marginBottom: 4,
                borderBottom: '1px solid var(--border-light)', fontSize: 13,
                cursor: 'pointer', borderRadius: 'var(--radius)',
                transition: 'background-color 0.1s',
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-primary)', flex: 1 }}>{t.description}</span>
                <span style={{ color: '#ef4444', fontSize: 12, marginLeft: 8, flexShrink: 0 }}>
                  {t.days_overdue}d overdue
                </span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                {t.owner} · Due: {t.follow_up_date}
              </div>
            </div>
          ))}
        </div>
      )}

      <DetailPanel
        open={!!selectedTask}
        onClose={() => setSelectedTask(null)}
        title={selectedTask?.description || ''}
        subtitle={selectedTask?.owner ? `Owner: ${selectedTask.owner}` : undefined}
        badge={selectedTask?.days_overdue ? { label: `${selectedTask.days_overdue} days overdue`, color: '#ef4444' } : undefined}
        fields={overdueFields}
      />
    </>
  );
}

/* ---------- Shared Components ---------- */

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || '#94a3b8';
  return (
    <span style={{
      fontSize: 11, padding: '3px 10px', borderRadius: 10,
      backgroundColor: color + '20', color, fontWeight: 500,
      display: 'inline-flex', alignItems: 'center', gap: 4,
    }}>
      {status === 'on_track' && <CheckCircle2 size={10} />}
      {status === 'pending' && <Circle size={10} />}
      {status.replace(/_/g, ' ')}
    </span>
  );
}



function MiniStatCard({ label, value, color }: { label: string; value: number | string; color?: string }) {
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

function ErrorState({ message }: { message: string }) {
  return (
    <div style={{ textAlign: 'center', padding: 40, color: '#ef4444', fontSize: 13, backgroundColor: 'var(--danger-light)', borderRadius: 'var(--radius-lg)', border: '1px solid #ef4444' }}>
      Failed to load: {message}
    </div>
  );
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
