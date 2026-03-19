/**
 * Strategy page — Initiatives, Decisions, Portfolio, Weekly Review.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useStore } from '../store';
import { getTheme } from '../themes';
import { api } from '../api/client';
import { Target, Scale, Users, BarChart3, CheckCircle2, Circle, GitBranch, Check, X, Sparkles, ChevronRight, ChevronDown, Plus } from 'lucide-react';
import DetailPanel from '../components/DetailPanel';
import type { DetailField } from '../components/DetailPanel';

type TabId = 'hierarchy' | 'initiatives' | 'decisions' | 'portfolio' | 'review';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'hierarchy', label: 'Hierarchy', icon: <GitBranch size={16} /> },
  { id: 'initiatives', label: 'Initiatives', icon: <Target size={16} /> },
  { id: 'decisions', label: 'Decisions', icon: <Scale size={16} /> },
  { id: 'portfolio', label: 'Portfolio', icon: <Users size={16} /> },
  { id: 'review', label: 'Review', icon: <BarChart3 size={16} /> },
];

const linkBtnStyle: React.CSSProperties = {
  border: 'none', background: 'none', cursor: 'pointer',
  fontSize: 12, color: 'var(--accent)', padding: 0,
  textDecoration: 'none',
};

const STATUS_COLORS: Record<string, string> = {
  on_track: '#22c55e', at_risk: '#f59e0b', off_track: '#ef4444',
  completed: '#6b7280', paused: '#94a3b8',
  decided: '#3b82f6', pending: '#f59e0b', revisit: '#ef4444',
  in_progress: '#3b82f6', active: '#3b82f6',
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
       tab === 'initiatives' ? <InitiativesView /> :
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

  const loadHierarchy = useCallback(() => {
    setLoading(true);
    api.get<any>('/api/hierarchy').then((data) => {
      setTree(data.tree || []);
      setOperational(data.operational_tasks || []);
      setUnclassified(data.unclassified_tasks || []);
      setCounts(data.counts || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  useEffect(() => { loadHierarchy(); }, [loadHierarchy]);

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
      { key: 'quarter', label: 'Quarter', value: node.quarter, type: 'text' },
      { key: 'status', label: 'Status', value: node.status || 'on_track', type: 'select', options: ['on_track', 'at_risk', 'off_track', 'completed', 'paused'] },
      { key: 'priority', label: 'Priority', value: node.priority || 'high', type: 'select', options: ['high', 'medium', 'low'] },
    ];
    if (t === 'epic') return [
      { key: 'title', label: 'Title', value: node.title, type: 'text' },
      { key: 'description', label: 'Description', value: node.description, type: 'textarea' },
      { key: 'owner', label: 'Owner', value: node.owner, type: 'select', options: ownerOptions },
      { key: 'status', label: 'Status', value: node.status || 'backlog', type: 'select', options: ['backlog', 'in_progress', 'done', 'cancelled'] },
      { key: 'priority', label: 'Priority', value: node.priority || 'high', type: 'select', options: ['high', 'medium', 'low'] },
      { key: 'quarter', label: 'Quarter', value: node.quarter, type: 'text' },
      { key: 'acceptance_criteria', label: 'Acceptance Criteria', value: node.acceptance_criteria || [], type: 'tags' },
    ];
    if (t === 'story') return [
      { key: 'title', label: 'Title', value: node.title, type: 'text' },
      { key: 'description', label: 'Description', value: node.description, type: 'textarea' },
      { key: 'owner', label: 'Owner', value: node.owner, type: 'select', options: ownerOptions },
      { key: 'status', label: 'Status', value: node.status || 'backlog', type: 'select', options: ['backlog', 'ready', 'in_progress', 'in_review', 'done', 'blocked'] },
      { key: 'priority', label: 'Priority', value: node.priority || 'medium', type: 'select', options: ['high', 'medium', 'low'] },
      { key: 'size', label: 'Size', value: node.size || 'M', type: 'select', options: ['XS', 'S', 'M', 'L', 'XL'] },
      { key: 'acceptance_criteria', label: 'Acceptance Criteria', value: node.acceptance_criteria || [], type: 'tags' },
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

  const handleApprove = useCallback((type: string, id: string) => {
    // Optimistic: mark as confirmed locally
    setTree((prev) => updateNodeInTree(prev, id, (n) => ({ ...n, source: 'confirmed' })));
    setOperational((prev) => prev.map((t) => t.id === id ? { ...t, source: 'confirmed' } : t));
    setUnclassified((prev) => prev.map((t) => t.id === id ? { ...t, source: 'confirmed' } : t));
    api.post(`/api/approve/${type}/${id}`, {}).catch(() => loadHierarchy());
  }, [updateNodeInTree, loadHierarchy]);

  const handleDismiss = useCallback((type: string, id: string) => {
    // Optimistic: remove from tree locally
    setTree((prev) => removeNodeFromTree(prev, id));
    setOperational((prev) => prev.filter((t) => t.id !== id));
    setUnclassified((prev) => prev.filter((t) => t.id !== id));
    api.post(`/api/dismiss/${type}/${id}`, {}).catch(() => loadHierarchy());
  }, [removeNodeFromTree, loadHierarchy]);

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
          <HierarchyNode key={node.id} node={node} depth={0} expandMode={expandMode} onApprove={handleApprove} onDismiss={handleDismiss} onNodeClick={handleNodeClick} onTaskUpdate={handleTaskUpdate} onTaskRemove={handleTaskRemove} onTaskAdd={handleTaskAdd} />
        ))}
      </div>

      {/* Operational tasks */}
      {operational.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
            <h3 style={{ fontSize: 14, fontWeight: 500, color: '#f59e0b' }}>
              Operational tasks ({operational.length})
            </h3>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Day-to-day work not tied to a strategic initiative
            </span>
          </div>
          {operational.map((t: any) => (
            <TaskLeaf key={t.id} task={t} borderColor="#f59e0b" onApprove={handleApprove} onDismiss={handleDismiss} onUpdate={handleTaskUpdate} onRemove={handleTaskRemove} />
          ))}
        </div>
      )}

      {/* Unclassified */}
      {unclassified.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
            <h3 style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)' }}>
              Unclassified tasks ({unclassified.length})
            </h3>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Needs review — could be strategic or operational
            </span>
          </div>
          {unclassified.map((t: any) => (
            <TaskLeaf key={t.id} task={t} borderColor="#64748b" onApprove={handleApprove} onDismiss={handleDismiss} onUpdate={handleTaskUpdate} onRemove={handleTaskRemove} />
          ))}
        </div>
      )}

      {/* Detail panel for editing hierarchy nodes */}
      <DetailPanel
        open={!!selectedNode}
        onClose={() => setSelectedNode(null)}
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
      />
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

function HierarchyNode({ node, depth, expandMode = 'default', onApprove, onDismiss, onNodeClick, onTaskUpdate, onTaskRemove, onTaskAdd }: {
  node: any; depth: number;
  expandMode?: 'default' | 'all' | 'none';
  onApprove: (type: string, id: string) => void;
  onDismiss: (type: string, id: string) => void;
  onNodeClick?: (node: any) => void;
  onTaskUpdate?: (id: string, updates: Record<string, any>) => void;
  onTaskRemove?: (id: string) => void;
  onTaskAdd?: (parentNode: any, newTask: any) => void;
}) {
  const defaultExpanded = expandMode === 'all' ? true : expandMode === 'none' ? false : depth < 2;
  const [expanded, setExpanded] = useState(defaultExpanded);
  const children = node.children || [];
  const isAuto = node.source === 'auto';
  const entityType = node.type + 's'; // themes, initiatives, epics, stories

  return (
    <div>
      <div
        onClick={() => onNodeClick?.(node)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '6px 8px', paddingLeft: depth * 20 + 8,
          borderLeft: `3px ${isAuto ? 'dashed' : 'solid'} ${TYPE_COLORS[node.type] || '#666'}`,
          backgroundColor: 'var(--bg-card)',
          borderRadius: 'var(--radius)',
          marginBottom: 1,
          color: isAuto ? 'var(--text-muted)' : 'var(--text-primary)',
          cursor: 'pointer',
          transition: 'all 0.15s',
        }}
      >
        <span
          onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
          style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', padding: 2 }}
        >
          {children.length > 0 ? (
            expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : <span style={{ width: 14 }} />}
        </span>

        <span style={{
          fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px',
          color: TYPE_COLORS[node.type] || '#666', minWidth: 60,
        }}>
          {TYPE_LABELS[node.type] || node.type}
        </span>

        <span style={{ fontSize: 13, fontWeight: 500, flex: 1 }}>
          {node.title || node.description || '(untitled)'}
        </span>

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

        {node.status && (
          <span style={{
            fontSize: 11, padding: '1px 6px', borderRadius: 4,
            backgroundColor: (STATUS_COLORS[node.status] || '#666') + '20',
            color: STATUS_COLORS[node.status] || '#666',
          }}>
            {(node.status || '').replace(/_/g, ' ')}
          </span>
        )}
      </div>

      {expanded && (
        <>
          {children.map((child: any) => (
            child.type ? (
              <HierarchyNode key={child.id} node={child} depth={depth + 1} expandMode={expandMode} onApprove={onApprove} onDismiss={onDismiss} onNodeClick={onNodeClick} onTaskUpdate={onTaskUpdate} onTaskRemove={onTaskRemove} onTaskAdd={onTaskAdd} />
            ) : (
              <TaskLeaf key={child.id} task={child} depth={depth + 1} onApprove={onApprove} onDismiss={onDismiss} onUpdate={onTaskUpdate} onRemove={onTaskRemove} />
            )
          ))}
          {/* Add task row for story nodes that have task children */}
          {(node.type === 'story' || node.type === 'epic') && children.some((c: any) => !c.type) && (
            <AddTaskRow
              depth={depth + 1}
              parentTaskId={children.find((c: any) => !c.type)?.id || ''}
              onAdd={(newTask) => onTaskAdd?.(node, newTask)}
            />
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

function TaskLeaf({ task, depth = 0, borderColor = '#94a3b8', onApprove, onDismiss, onRemove, onUpdate }: {
  task: any; depth?: number; borderColor?: string;
  onApprove: (type: string, id: string) => void;
  onDismiss: (type: string, id: string) => void;
  onRemove?: (id: string) => void;
  onUpdate?: (id: string, updates: Record<string, any>) => void;
}) {
  const isAuto = task.source === 'auto';
  const isDone = task.status === 'done';
  const [editingField, setEditingField] = useState<'description' | 'owner' | null>(null);
  const [editValue, setEditValue] = useState('');
  const [hovered, setHovered] = useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (editingField && inputRef.current) inputRef.current.focus();
  }, [editingField]);

  const startEdit = (field: 'description' | 'owner') => {
    setEditingField(field);
    setEditValue(field === 'description' ? (task.description || '') : (task.owner || ''));
  };

  const saveEdit = () => {
    if (!editingField) return;
    const val = editValue.trim();
    if (val && val !== (editingField === 'description' ? task.description : task.owner)) {
      task[editingField] = val;
      onUpdate?.(task.id, { [editingField]: val });
    }
    setEditingField(null);
  };

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
        padding: '4px 8px', paddingLeft: depth * 20 + 28,
        borderLeft: `3px ${isAuto ? 'dashed' : 'solid'} ${borderColor}`,
        marginBottom: 1,
        color: isAuto ? 'var(--text-muted)' : 'var(--text-secondary)',
        fontSize: 12,
        opacity: isDone ? 0.5 : 1,
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

      {/* Description */}
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
            flex: 1, cursor: 'text', borderRadius: 4, padding: '1px 4px',
            textDecoration: isDone ? 'line-through' : 'none',
            transition: 'background-color 0.1s',
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
        >
          {task.description || '(no description)'}
        </span>
      )}

      {/* Owner badge */}
      {editingField === 'owner' ? (
        <input
          ref={inputRef}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={saveEdit}
          onKeyDown={handleKeyDown}
          style={{
            width: 80, fontSize: 11, padding: '2px 6px', border: '1px solid var(--accent)',
            borderRadius: 4, backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)',
            outline: 'none', textAlign: 'right',
          }}
        />
      ) : (
        <span
          onClick={() => startEdit('owner')}
          style={{
            fontSize: 10, color: 'var(--text-muted)', cursor: 'text',
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

      {/* Remove button (on hover) */}
      {!isAuto && onRemove && (
        <button
          onClick={() => onRemove(task.id)}
          title="Remove task"
          style={{
            display: 'flex', alignItems: 'center', padding: 2, border: 'none', background: 'none',
            cursor: 'pointer', color: 'var(--text-muted)',
            opacity: hovered ? 0.7 : 0, transition: 'opacity 0.15s',
          }}
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}

/* Inline add task input */
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

function InitiativesView() {
  const [initiatives, setInitiatives] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);

  useEffect(() => {
    Promise.all([
      api.get<any>('/api/initiatives').catch(() => ({ initiatives: [] })),
      api.get<any>('/api/strategic-summary').catch(() => null),
    ]).then(([initData, sumData]) => {
      setInitiatives(initData.initiatives || []);
      setSummary(sumData);
      setLoading(false);
    }).catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  const handleSave = useCallback((updates: Record<string, any>) => {
    if (!selected) return;
    setInitiatives((prev) => prev.map((i) => i.id === selected.id ? { ...i, ...updates } : i));
    setSelected((prev: any) => prev ? { ...prev, ...updates } : null);
    api.patch<any>(`/api/initiatives/${selected.id}`, updates).catch(() => {});
  }, [selected]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  const stats = summary?.initiatives;

  const fields: DetailField[] = selected ? [
    { key: 'status', label: 'Status', value: selected.status, type: 'select', options: ['on_track', 'at_risk', 'off_track', 'completed', 'paused'], color: STATUS_COLORS[selected.status] },
    { key: 'owner', label: 'Owner', value: selected.owner, type: 'text' },
    { key: 'quarter', label: 'Quarter', value: selected.quarter, type: 'text' },
    { key: 'priority', label: 'Priority', value: selected.priority, type: 'select', options: ['high', 'medium', 'low'] },
    { key: 'description', label: 'Description', value: selected.description, type: 'textarea' },
    { key: 'milestone_progress', label: 'Milestone Progress', value: selected.milestone_progress, type: 'readonly' },
    { key: 'linked_task_count', label: 'Linked Tasks', value: selected.linked_task_count, type: 'readonly' },
    { key: 'created_at', label: 'Created', value: selected.created_at ? new Date(selected.created_at).toLocaleDateString() : '—', type: 'readonly' },
    { key: 'updated_at', label: 'Last Updated', value: selected.updated_at ? new Date(selected.updated_at).toLocaleDateString() : '—', type: 'readonly' },
  ] : [];

  return (
    <>
      {/* Summary stats row */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
          <MiniStatCard label="Total" value={stats.total || initiatives.length} />
          <MiniStatCard label="On Track" value={stats.on_track || 0} color="#22c55e" />
          <MiniStatCard label="At Risk" value={stats.at_risk_count || 0} color="#f59e0b" />
          <MiniStatCard label="Off Track" value={stats.off_track_count || 0} color="#ef4444" />
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {initiatives.length === 0 ? (
          <EmptyState message="No initiatives yet. Use TARS chat to create one." />
        ) : (
          initiatives.map((init) => (
            <div
              key={init.id}
              onClick={() => setSelected(init)}
              style={{
                ...cardStyle, cursor: 'pointer', transition: 'all 0.15s',
                borderLeft: `3px solid ${STATUS_COLORS[init.status] || '#94a3b8'}`,
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
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{init.title}</h3>
                <StatusBadge status={init.status} />
              </div>
              {init.description && <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8, lineHeight: 1.5 }}>{init.description}</p>}

              {/* Milestones progress bar */}
              {init.milestones?.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
                    {init.milestones.map((m: any, i: number) => (
                      <div key={i} style={{
                        flex: 1, height: 4, borderRadius: 2,
                        backgroundColor: m.completed ? '#22c55e' : 'var(--border)',
                      }} />
                    ))}
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {init.milestones.filter((m: any) => m.completed).length}/{init.milestones.length} milestones
                  </span>
                </div>
              )}

              <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
                {init.owner && <span>Owner: {init.owner}</span>}
                {init.quarter && <span>{init.quarter}</span>}
                {init.priority && <span style={{ textTransform: 'capitalize' }}>{init.priority} priority</span>}
                {init.linked_task_count > 0 && <span>{init.linked_task_count} tasks</span>}
              </div>
            </div>
          ))
        )}
      </div>

      <DetailPanel
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.title || ''}
        subtitle={selected?.description}
        badge={selected ? { label: (selected.status || '').replace(/_/g, ' '), color: STATUS_COLORS[selected.status] || '#94a3b8' } : undefined}
        fields={fields}
        onSave={handleSave}
      />
    </>
  );
}

/* ---------- Decisions ---------- */

function DecisionsView() {
  const [decisions, setDecisions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<any>(null);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    api.get<any>('/api/decisions').then((data) => {
      setDecisions(data.decisions || []);
      setLoading(false);
    }).catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  const handleSave = useCallback((updates: Record<string, any>) => {
    if (!selected) return;
    setDecisions((prev) => prev.map((d) => d.id === selected.id ? { ...d, ...updates } : d));
    setSelected((prev: any) => prev ? { ...prev, ...updates } : null);
    api.patch<any>(`/api/decisions/${selected.id}`, updates).catch(() => {});
  }, [selected]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  const filtered = filter === 'all' ? decisions : decisions.filter((d) => d.status === filter);

  const fields: DetailField[] = selected ? [
    { key: 'status', label: 'Status', value: selected.status, type: 'select', options: ['pending', 'decided', 'revisit'], color: STATUS_COLORS[selected.status] },
    { key: 'decided_by', label: 'Decided By', value: selected.decided_by, type: 'text' },
    { key: 'stakeholders', label: 'Stakeholders', value: selected.stakeholders || [], type: 'tags' },
    { key: 'rationale', label: 'Rationale', value: selected.rationale, type: 'textarea' },
    { key: 'context', label: 'Context', value: selected.context, type: 'textarea' },
    { key: 'initiative', label: 'Linked Initiative', value: selected.initiative, type: 'text' },
    { key: 'outcome_notes', label: 'Outcome Notes', value: selected.outcome_notes, type: 'textarea' },
    { key: 'created_at', label: 'Created', value: selected.created_at ? new Date(selected.created_at).toLocaleDateString() : '—', type: 'readonly' },
    { key: 'updated_at', label: 'Last Updated', value: selected.updated_at ? new Date(selected.updated_at).toLocaleDateString() : '—', type: 'readonly' },
  ] : [];

  return (
    <>
      {/* Filter chips */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        {['all', 'pending', 'decided', 'revisit'].map((f) => (
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

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {filtered.length === 0 ? (
          <EmptyState message={filter === 'all' ? 'No decisions logged yet.' : `No ${filter} decisions.`} />
        ) : (
          filtered.map((d) => (
            <div
              key={d.id}
              onClick={() => setSelected(d)}
              style={{
                ...cardStyle, cursor: 'pointer', transition: 'all 0.15s',
                borderLeft: `3px solid ${STATUS_COLORS[d.status] || '#94a3b8'}`,
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
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{d.title}</h3>
                <StatusBadge status={d.status} />
              </div>
              {d.rationale && <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6, lineHeight: 1.5 }}>{d.rationale}</p>}
              <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                <span>By: {d.decided_by || 'Unknown'}</span>
                {d.stakeholders?.length > 0 && <span>Stakeholders: {d.stakeholders.join(', ')}</span>}
                {d.initiative && <span>Initiative: {d.initiative}</span>}
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
        onSave={handleSave}
      />
    </>
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

  const members = Object.entries(portfolio);

  const fields: DetailField[] = selected ? [
    { key: 'total_epics', label: 'Total Epics', value: selected.data.workload?.total_epics || selected.data.epic_count || 0, type: 'readonly' },
    { key: 'total_stories', label: 'Total Stories', value: selected.data.workload?.total_stories || selected.data.story_count || 0, type: 'readonly' },
    { key: 'total_smart_tasks', label: 'Smart Tasks', value: selected.data.workload?.total_smart_tasks || selected.data.task_count || 0, type: 'readonly' },
    { key: 'total_tracked', label: 'Tracked Tasks', value: selected.data.workload?.total_tracked_tasks || 0, type: 'readonly' },
    { key: 'blocked', label: 'Blocked Stories', value: selected.data.workload?.blocked_stories || 0, type: 'readonly' },
    { key: 'overdue', label: 'Overdue Tasks', value: selected.data.workload?.overdue_tasks || 0, type: 'readonly' },
    { key: 'workload_status', label: 'Workload Status', value: selected.data.workload_status || 'normal', type: 'badge',
      color: selected.data.workload_status === 'overloaded' ? '#ef4444' : '#22c55e' },
  ] : [];

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
        {members.length === 0 ? (
          <EmptyState message="No portfolio data. Run a Notion scan first." />
        ) : (
          members.map(([name, data]: [string, any]) => {
            const isOverloaded = data.workload_status === 'overloaded';
            return (
              <div
                key={name}
                onClick={() => setSelected({ name, data })}
                style={{
                  ...cardStyle, cursor: 'pointer', transition: 'all 0.15s',
                  borderLeft: `3px solid ${isOverloaded ? '#ef4444' : 'var(--accent)'}`,
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
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: '50%', background: isOverloaded ? '#ef4444' : 'var(--accent)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#fff', fontSize: 14, fontWeight: 600, flexShrink: 0,
                  }}>
                    {name.charAt(0)}
                  </div>
                  <div>
                    <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{name}</h3>
                    {data.workload_status && (
                      <span style={{
                        fontSize: 11, padding: '1px 8px', borderRadius: 10,
                        backgroundColor: isOverloaded ? '#ef444420' : '#22c55e20',
                        color: isOverloaded ? '#ef4444' : '#22c55e',
                      }}>
                        {data.workload_status}
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
                  <MiniStat label="Epics" value={data.workload?.total_epics || data.epic_count || 0} />
                  <MiniStat label="Stories" value={data.workload?.total_stories || data.story_count || 0} />
                  <MiniStat label="Tasks" value={data.workload?.total_smart_tasks || data.task_count || 0} />
                </div>
                {(data.workload?.blocked_stories > 0 || data.workload?.overdue_tasks > 0) && (
                  <div style={{ display: 'flex', gap: 12, fontSize: 11 }}>
                    {data.workload?.blocked_stories > 0 && (
                      <span style={{ color: '#ef4444' }}>{data.workload.blocked_stories} blocked</span>
                    )}
                    {data.workload?.overdue_tasks > 0 && (
                      <span style={{ color: '#f59e0b' }}>{data.workload.overdue_tasks} overdue</span>
                    )}
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
        subtitle="Team member portfolio"
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
      fontSize: 11, padding: '3px 10px', borderRadius: 12,
      backgroundColor: color + '20', color, fontWeight: 500,
      display: 'inline-flex', alignItems: 'center', gap: 4,
    }}>
      {status === 'on_track' && <CheckCircle2 size={10} />}
      {status === 'pending' && <Circle size={10} />}
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
