/**
 * Command Center — the home dashboard, layout driven by theme.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import {
  Calendar, AlertTriangle, Mail, TrendingUp, CheckCircle2, ChevronRight, ChevronDown, ChevronLeft,
  Target, Scale, Users, CalendarCheck, Clock, Zap, User, Package, Eye, X, Pencil, RefreshCw,
} from 'lucide-react';

interface AlertData {
  type: string;
  severity: string;
  title: string;
  detail: string;
  person?: string;
  task_count?: number;
  days_overdue?: number;
  task_id?: string;
  suggested_action?: string;
}

export default function CommandCenter() {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [taskStats, setTaskStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [expandedAlert, setExpandedAlert] = useState<number | null>(null);
  const [showAllAlerts, setShowAllAlerts] = useState(false);
  const [meetingPrep, setMeetingPrep] = useState<any>(null);
  const [meetingReview, setMeetingReview] = useState<any>(null);

  useEffect(() => {
    Promise.all([
      api.get<any>('/api/alerts').catch(() => ({ alerts: [] })),
      api.get<any>('/api/strategic-summary').catch(() => ({})),
      api.get<any>('/api/review/weekly').catch(() => ({})),
      api.get<any>('/api/meeting-prep').catch(() => null),
      api.get<any>('/api/meeting-review').catch(() => ({ meetings: [], summary: {} })),
    ]).then(([alertsData, summaryData, reviewData, meetingData, meetingReviewData]) => {
      setAlerts(alertsData.alerts || []);
      setSummary(summaryData);
      setTaskStats(reviewData.smart_tasks || {});
      setMeetingPrep(meetingData?.available ? meetingData : null);
      setMeetingReview(meetingReviewData?.summary?.total_items > 0 ? meetingReviewData : null);
      setLoading(false);
    });
  }, []);

  const criticalAlerts = alerts.filter((a) => a.severity === 'critical');
  const warningAlerts = alerts.filter((a) => a.severity === 'warning');
  const otherAlerts = alerts.filter((a) => a.severity !== 'critical' && a.severity !== 'warning');
  const displayAlerts = [
    ...criticalAlerts,
    ...warningAlerts.slice(0, 3),
    ...otherAlerts,
  ].slice(0, 5);
  const initSummary = summary?.initiatives;
  const decSummary = summary?.decisions;

  const alertsRef = React.useRef<HTMLDivElement>(null);

  return (
    <div>
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
          {(() => {
            const h = new Date().getHours();
            const greeting = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
            return `${greeting}, Jonas`;
          })()}
        </h1>
        {criticalAlerts.length > 0 && (
          <span style={{ fontSize: 13, color: 'var(--text-muted)', marginLeft: 12 }}>
            {criticalAlerts.length} {criticalAlerts.length === 1 ? 'item needs' : 'items need'} your attention
          </span>
        )}
        <span style={{ color: 'var(--text-muted)', fontSize: 13, marginLeft: 'auto' }}>
          {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
        </span>
      </div>

      {/* Alert banner */}
      {criticalAlerts.length > 0 && (
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--danger-light)',
            border: '1px solid var(--danger)',
            borderRadius: 'var(--radius)',
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <AlertTriangle size={18} style={{ color: 'var(--danger)', flexShrink: 0 }} />
          <div style={{ fontSize: 13, color: 'var(--text-primary)', flex: 1 }}>
            <strong>{criticalAlerts.length} critical alert{criticalAlerts.length !== 1 ? 's' : ''}</strong>
            {' — '}
            {criticalAlerts.slice(0, 2).map((a) => a.title).join('; ')}
          </div>
          <button
            onClick={() => {
              setShowAllAlerts(true);
              alertsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }}
            style={{
              fontSize: 12, color: 'var(--danger)', background: 'none', border: 'none',
              cursor: 'pointer', fontWeight: 500, whiteSpace: 'nowrap',
            }}
          >
            View all
          </button>
        </div>
      )}

      {/* Stats cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 24 }}>
        <StatCard
          icon={<CheckCircle2 size={20} />}
          label="Open Tasks"
          value={taskStats?.open != null ? `${taskStats.open}` : loading ? '...' : '0'}
          color="var(--accent)"
          onClick={() => navigate('/work')}
        />
        <StatCard
          icon={<AlertTriangle size={20} />}
          label="Alerts"
          value={`${alerts.length}`}
          color="var(--warning)"
        />
        <StatCard
          icon={<Calendar size={20} />}
          label="Overdue"
          value={taskStats?.overdue_count != null ? `${taskStats.overdue_count}` : loading ? '...' : '0'}
          color="var(--danger)"
          onClick={() => navigate('/strategy?tab=review')}
        />
        <StatCard
          icon={<Mail size={20} />}
          label="Completed"
          value={taskStats?.done != null ? `${taskStats.done}` : loading ? '...' : '0'}
          color="var(--success)"
        />
      </div>

      {/* Two column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20 }}>
        {/* Alerts list */}
        <div style={cardStyle} ref={alertsRef}>
          <h2 style={cardHeaderStyle}>
            <AlertTriangle size={16} />
            Alerts & Attention
            {alerts.length > 0 && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 'auto' }}>
                {alerts.length} total
              </span>
            )}
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {loading ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 20, textAlign: 'center' }}>Loading...</div>
            ) : alerts.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 20, textAlign: 'center' }}>
                No alerts — all clear
              </div>
            ) : (
              (showAllAlerts ? alerts : displayAlerts).map((alert, i) => {
                const isExpanded = expandedAlert === i;
                const severityColor = alert.severity === 'critical' ? 'var(--danger)' : alert.severity === 'warning' ? 'var(--warning)' : 'var(--info)';
                return (
                  <div key={i}>
                    <div
                      onClick={() => setExpandedAlert(isExpanded ? null : i)}
                      style={{
                        display: 'flex', alignItems: 'flex-start', gap: 10,
                        padding: '10px 12px', backgroundColor: isExpanded ? 'var(--bg-hover)' : 'var(--bg-secondary)',
                        borderRadius: isExpanded ? 'var(--radius) var(--radius) 0 0' : 'var(--radius)',
                        borderLeft: `3px solid ${severityColor}`,
                        cursor: 'pointer', transition: 'background-color 0.1s',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                      onMouseLeave={(e) => { if (!isExpanded) e.currentTarget.style.backgroundColor = 'var(--bg-secondary)'; }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                          {alert.title}
                        </div>
                        {!isExpanded && (
                          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {alert.detail?.slice(0, 100)}
                          </div>
                        )}
                      </div>
                      {isExpanded
                        ? <ChevronDown size={14} style={{ color: 'var(--text-muted)', flexShrink: 0, marginTop: 2 }} />
                        : <ChevronRight size={14} style={{ color: 'var(--text-muted)', flexShrink: 0, marginTop: 2 }} />
                      }
                    </div>
                    {isExpanded && (
                      <AlertExpandedContent alert={alert} severityColor={severityColor} navigate={navigate} />
                    )}
                  </div>
                );
              })
            )}
            {!showAllAlerts && alerts.length > displayAlerts.length && (
              <div
                onClick={() => setShowAllAlerts(true)}
                style={{ fontSize: 12, color: 'var(--accent)', textAlign: 'center', padding: 8, cursor: 'pointer', fontWeight: 500 }}
              >
                View all {alerts.length} alerts
              </div>
            )}
            {showAllAlerts && alerts.length > 5 && (
              <div
                onClick={() => setShowAllAlerts(false)}
                style={{ fontSize: 12, color: 'var(--accent)', textAlign: 'center', padding: 8, cursor: 'pointer', fontWeight: 500 }}
              >
                Show less
              </div>
            )}
          </div>
        </div>

        {/* Strategic overview */}
        <div style={cardStyle}>
          <h2 style={cardHeaderStyle}>
            <TrendingUp size={16} />
            Strategic Overview
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <OverviewItem
              icon={<Target size={14} />}
              label="Initiatives"
              count={initSummary?.total || 0}
              detail={initSummary?.on_track ? `${initSummary.on_track} on track` : undefined}
              color="#22c55e"
              onClick={() => navigate('/strategy?tab=hierarchy')}
            />
            <OverviewItem
              icon={<Scale size={14} />}
              label="Pending Decisions"
              count={decSummary?.pending_count || 0}
              detail={decSummary?.revisit_count ? `${decSummary.revisit_count} need revisit` : undefined}
              color="#f59e0b"
              onClick={() => navigate('/strategy?tab=decisions')}
            />
            <OverviewItem
              icon={<CheckCircle2 size={14} />}
              label="Total Tasks"
              count={taskStats?.total || 0}
              detail={taskStats?.quadrants ? `Q1: ${taskStats.quadrants['1'] || 0} urgent · Q2: ${taskStats.quadrants['2'] || 0}` : undefined}
              color="var(--accent)"
              onClick={() => navigate('/work')}
            />
            <OverviewItem
              icon={<Users size={14} />}
              label="Team Overview"
              count="—"
              detail="View portfolio"
              color="var(--info)"
              onClick={() => navigate('/strategy?tab=portfolio')}
            />
          </div>
        </div>
      </div>

      {/* Meeting Review */}
      {meetingReview && (
        <MeetingReviewCard data={meetingReview} navigate={navigate} onUpdate={(date?: string) => {
          const params = date ? `?date=${date}` : '';
          api.get<any>(`/api/meeting-review${params}`).catch(() => ({ meetings: [], summary: {} }))
            .then((d) => setMeetingReview(d || { meetings: [], summary: {} }));
        }} />
      )}

      {/* Next Meeting card */}
      {meetingPrep && (
        <div
          onClick={() => navigate('/people?tab=meeting-prep')}
          style={{
            ...cardStyle,
            marginTop: 20,
            borderLeft: `4px solid var(--accent)`,
            cursor: 'pointer',
            transition: 'all 0.15s',
            ...((() => {
              const t = meetingPrep.time_until as string | undefined;
              const isUrgent = t && (
                t.toLowerCase().includes('now') ||
                (t.toLowerCase().includes('minute') && parseInt(t) < 30)
              );
              return isUrgent ? { animation: 'meetingPulse 2s ease-in-out infinite', borderLeftColor: 'var(--warning)' } : {};
            })()),
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
          <style>{`
            @keyframes meetingPulse {
              0%, 100% { border-left-color: var(--warning); }
              50% { border-left-color: var(--accent); }
            }
          `}</style>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
              <CalendarCheck size={18} style={{ color: 'var(--accent)', flexShrink: 0 }} />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {meetingPrep.event?.subject || 'Upcoming Meeting'}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--text-muted)' }}>
                    <Clock size={12} />
                    {meetingPrep.time_until}
                  </span>
                  {meetingPrep.event?.attendees?.length != null && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--text-muted)' }}>
                      <Users size={12} />
                      {meetingPrep.event.attendees.length} attendee{meetingPrep.event.attendees.length !== 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              </div>
            </div>
            {meetingPrep.talking_points?.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginLeft: 20, flexShrink: 0, maxWidth: 300 }}>
                {meetingPrep.talking_points.slice(0, 2).map((point: string, i: number) => (
                  <div key={i} style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    &bull; {point}
                  </div>
                ))}
              </div>
            )}
            <ChevronRight size={16} style={{ color: 'var(--text-muted)', flexShrink: 0, marginLeft: 12 }} />
          </div>
        </div>
      )}

      {/* Alert detail panel removed — alerts now expand inline */}
    </div>
  );
}

/* ---------- Meeting Review card ---------- */

const entityColors: Record<string, string> = {
  tasks: '#3b82f6',
  stories: '#22c55e',
  epics: '#a855f7',
  initiatives: '#f97316',
  decisions: '#f59e0b',
};

// --- Inline-editable meeting review item ---
const _ENTITY_ENDPOINTS: Record<string, string> = {
  tasks: '/api/intel/tasks',
  stories: '/api/stories',
  epics: '/api/epics',
  initiatives: '/api/initiatives',
  decisions: '/api/decisions',
};
const _ENTITY_LABEL: Record<string, string> = {
  tasks: 'task', stories: 'story', epics: 'epic', initiatives: 'init', decisions: 'decision',
};

function _ucFirst(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

// --- Hierarchy picker (reused from Work.tsx pattern) ---
const _HIER_COLORS: Record<string, string> = {
  theme: '#8b5cf6', initiative: '#3b82f6', epic: '#10b981', story: '#f59e0b',
};

function ReviewHierPicker({ node, depth, search, onSelect }: {
  node: any; depth: number; search: string; onSelect: (storyId: string) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 1);
  const children: any[] = (node.children || []).filter((c: any) => c.type);
  const isStory = node.type === 'story';
  const hasChildren = children.length > 0;
  const matchesSelf = search && (node.title || '').toLowerCase().includes(search.toLowerCase());
  const hasDescMatch = search ? reviewCheckDescMatch(node, search) : true;
  if (search && !matchesSelf && !hasDescMatch) return null;
  const eff = (search && hasDescMatch && !matchesSelf) ? true : expanded;

  return (
    <div>
      <div
        onClick={() => { if (isStory) { onSelect(node.id); return; } if (hasChildren) setExpanded(!expanded); }}
        style={{
          display: 'flex', alignItems: 'center', gap: 4, padding: '3px 6px',
          paddingLeft: depth * 14 + 6, cursor: isStory || hasChildren ? 'pointer' : 'default',
          borderRadius: 4, transition: 'background-color 0.1s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
      >
        {hasChildren
          ? <span onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }} style={{ display: 'flex', padding: 1 }}>
              {eff ? <ChevronDown size={10} /> : <span style={{ display: 'inline-block', width: 10, textAlign: 'center', fontSize: 10, color: 'var(--text-muted)' }}>›</span>}
            </span>
          : <span style={{ width: 12 }} />
        }
        <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', color: _HIER_COLORS[node.type] || '#666', minWidth: 28 }}>
          {(node.type || '').slice(0, 4)}
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: matchesSelf ? 600 : 400 }}>
          {node.title || '(untitled)'}
        </span>
      </div>
      {eff && hasChildren && children.map((c: any) => (
        <ReviewHierPicker key={c.id} node={c} depth={depth + 1} search={search} onSelect={onSelect} />
      ))}
    </div>
  );
}

function reviewCheckDescMatch(node: any, search: string): boolean {
  for (const c of (node.children || []).filter((c: any) => c.type)) {
    if ((c.title || '').toLowerCase().includes(search.toLowerCase())) return true;
    if (reviewCheckDescMatch(c, search)) return true;
  }
  return false;
}

function MeetingReviewItem({ item, hierTree, onReview, onDismiss, onNavigate, onUpdate }: {
  item: any;
  hierTree: any[];
  onReview: (entityType: string, id: string, title: string) => void;
  onDismiss: (entityType: string, id: string, title: string) => void;
  onNavigate: (item: any) => void;
  onUpdate: () => void;
}) {
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleVal, setTitleVal] = useState(item.title || '');
  const [editingOwner, setEditingOwner] = useState(false);
  const [ownerVal, setOwnerVal] = useState(item.owner || '');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerSearch, setPickerSearch] = useState('');
  const [classification, setClassification] = useState(item.classification || 'unclassified');

  const titleKey = item.entity_type === 'tasks' ? 'description' : 'title';
  const endpoint = _ENTITY_ENDPOINTS[item.entity_type];
  const isTask = item.entity_type === 'tasks';

  const saveTitle = () => {
    setEditingTitle(false);
    if (titleVal !== item.title && endpoint) {
      item.title = titleVal;
      api.patch<any>(`${endpoint}/${item.id}`, { [titleKey]: titleVal }).catch(() => {});
    }
  };

  const saveOwner = () => {
    setEditingOwner(false);
    const ownerKey = item.entity_type === 'decisions' ? 'decided_by' : 'owner';
    if (ownerVal !== item.owner && endpoint) {
      item.owner = ownerVal;
      api.patch<any>(`${endpoint}/${item.id}`, { [ownerKey]: ownerVal }).catch(() => {});
    }
  };

  const linkToStory = (storyId: string) => {
    api.post<any>(`/api/stories/${storyId}/link-task`, { task_id: item.id }).then(() => {
      setPickerOpen(false);
      setPickerSearch('');
      onUpdate();
    }).catch(() => {});
  };

  const markOperational = () => {
    setClassification('operational');
    api.post<any>(`/api/intel/tasks/${item.id}/assign`, { classification: 'operational' }).catch(() => {});
  };

  const markStrategic = () => {
    setClassification('unclassified');
    api.post<any>(`/api/intel/tasks/${item.id}/assign`, { classification: 'unclassified' }).catch(() => {});
  };

  const hierColor: Record<string, string> = {
    theme: '#64748b', initiative: '#f97316', epic: '#a855f7', story: '#22c55e',
  };

  const isOperational = classification === 'operational';

  return (
    <div style={{ position: 'relative' }}>
      <div
        style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          padding: '8px 10px', backgroundColor: 'var(--bg-card)',
          borderRadius: pickerOpen ? 'var(--radius) var(--radius) 0 0' : 'var(--radius)',
          transition: 'background-color 0.1s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-card)'}
      >
        {/* Entity type badge */}
        <span style={{
          fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px',
          padding: '2px 6px', borderRadius: 6, flexShrink: 0, marginTop: 2,
          backgroundColor: `${entityColors[item.entity_type] || '#888'}20`,
          color: entityColors[item.entity_type] || '#888',
        }}>
          {_ENTITY_LABEL[item.entity_type] || item.entity_type?.replace(/s$/, '')}
        </span>

        {/* Title + hierarchy + owner */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Editable title */}
          {editingTitle ? (
            <input
              autoFocus
              value={titleVal}
              onChange={(e) => setTitleVal(e.target.value)}
              onBlur={saveTitle}
              onKeyDown={(e) => { if (e.key === 'Enter') saveTitle(); if (e.key === 'Escape') { setTitleVal(item.title); setEditingTitle(false); } }}
              style={{
                fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', width: '100%',
                background: 'var(--bg-secondary)', border: '1px solid var(--accent)',
                borderRadius: 4, padding: '2px 6px', outline: 'none',
              }}
            />
          ) : (
            <div
              onClick={() => setEditingTitle(true)}
              title="Click to edit title"
              style={{
                fontSize: 12, fontWeight: 500, color: 'var(--text-primary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                cursor: 'text', borderRadius: 3, padding: '1px 0',
              }}
            >
              {_ucFirst(item.title)}
            </div>
          )}

          {/* Hierarchy path with link button */}
          <div style={{ fontSize: 10, marginTop: 2, display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden' }}>
            {isOperational ? (
              <span style={{ color: '#64748b', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: 4 }}>
                Operational
                {isTask && (
                  <button
                    onClick={() => markStrategic()}
                    title="Remove operational classification"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 1, color: 'var(--text-muted)', display: 'flex', borderRadius: 3 }}
                    onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
                    onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
                  >
                    <X size={9} />
                  </button>
                )}
              </span>
            ) : item.hierarchy_path?.length > 0 ? (
              <>
                {item.hierarchy_path.map((h: any, idx: number) => (
                  <React.Fragment key={h.id}>
                    {idx > 0 && <span style={{ color: 'var(--text-muted)' }}> › </span>}
                    <span style={{ color: hierColor[h.type] || 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {h.title}
                    </span>
                  </React.Fragment>
                ))}
                {isTask && (
                  <button
                    onClick={() => setPickerOpen(!pickerOpen)}
                    title="Change hierarchy link"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 1, color: 'var(--text-muted)', display: 'flex', borderRadius: 3, flexShrink: 0 }}
                    onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent)'}
                    onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
                  >
                    <Pencil size={9} />
                  </button>
                )}
              </>
            ) : (
              <span style={{ color: 'var(--text-muted)', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: 4 }}>
                No hierarchy assigned
                {isTask && (
                  <>
                    <button
                      onClick={() => setPickerOpen(!pickerOpen)}
                      title="Link to story in hierarchy"
                      style={{
                        fontSize: 9, fontWeight: 500, border: 'none', borderRadius: 4, padding: '1px 6px',
                        cursor: 'pointer', backgroundColor: 'rgba(99,102,241,0.1)', color: 'var(--accent)',
                        display: 'flex', alignItems: 'center', gap: 3,
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(99,102,241,0.2)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(99,102,241,0.1)'}
                    >
                      + Link
                    </button>
                    <button
                      onClick={markOperational}
                      title="Mark as operational (not strategic)"
                      style={{
                        fontSize: 9, fontWeight: 500, border: 'none', borderRadius: 4, padding: '1px 6px',
                        cursor: 'pointer', backgroundColor: 'rgba(100,116,139,0.1)', color: '#64748b',
                        display: 'flex', alignItems: 'center', gap: 3,
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(100,116,139,0.2)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(100,116,139,0.1)'}
                    >
                      Operational
                    </button>
                  </>
                )}
              </span>
            )}
          </div>

          {/* Editable owner */}
          {editingOwner ? (
            <input
              autoFocus
              value={ownerVal}
              onChange={(e) => setOwnerVal(e.target.value)}
              onBlur={saveOwner}
              onKeyDown={(e) => { if (e.key === 'Enter') saveOwner(); if (e.key === 'Escape') { setOwnerVal(item.owner); setEditingOwner(false); } }}
              style={{
                fontSize: 10, color: 'var(--text-primary)', marginTop: 2,
                background: 'var(--bg-secondary)', border: '1px solid var(--accent)',
                borderRadius: 3, padding: '1px 4px', outline: 'none', width: 120,
              }}
            />
          ) : (
            <div
              onClick={() => { setOwnerVal(item.owner || ''); setEditingOwner(true); }}
              title="Click to edit owner"
              style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1, cursor: 'text', display: 'flex', alignItems: 'center', gap: 3 }}
            >
              <User size={9} />
              {item.owner || 'Unassigned'}
            </div>
          )}
        </div>

        {/* Created timestamp */}
        {item.created_at && (
          <span style={{ fontSize: 10, color: 'var(--text-muted)', flexShrink: 0, marginTop: 3, whiteSpace: 'nowrap' }}>
            {(() => {
              const d = new Date(item.created_at);
              return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                + ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
            })()}
          </span>
        )}

        {/* Source badge */}
        <span style={{
          fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px',
          padding: '2px 6px', borderRadius: 6, flexShrink: 0, marginTop: 2,
          backgroundColor: item.source === 'auto' ? 'rgba(245,158,11,0.15)' : 'rgba(34,197,94,0.15)',
          color: item.source === 'auto' ? '#f59e0b' : '#22c55e',
        }}>
          {item.source}
        </span>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 4, flexShrink: 0, marginTop: 1 }}>
          <button
            title="Review (approve &amp; remove from review)"
            onClick={(e) => { e.stopPropagation(); onReview(item.entity_type, item.id, item.title); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 3, color: '#22c55e', borderRadius: 4, display: 'flex' }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(34,197,94,0.15)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            <CheckCircle2 size={14} />
          </button>
          <button
            title="Dismiss (delete item)"
            onClick={(e) => { e.stopPropagation(); onDismiss(item.entity_type, item.id, item.title); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 3, color: 'var(--danger)', borderRadius: 4, display: 'flex' }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(239,68,68,0.15)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            <X size={14} />
          </button>
          <button
            title="View"
            onClick={(e) => { e.stopPropagation(); onNavigate(item); }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 3, color: 'var(--text-muted)', borderRadius: 4, display: 'flex' }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Hierarchy picker dropdown */}
      {pickerOpen && isTask && (
        <div style={{
          border: '1px solid var(--border)', borderTop: 'none',
          borderRadius: '0 0 var(--radius) var(--radius)',
          backgroundColor: 'var(--bg-secondary)', overflow: 'hidden',
        }}>
          <div style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Eye size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            <input
              autoFocus
              value={pickerSearch}
              onChange={(e) => setPickerSearch(e.target.value)}
              placeholder="Search hierarchy..."
              style={{ flex: 1, border: 'none', background: 'none', outline: 'none', fontSize: 12, color: 'var(--text-primary)' }}
            />
            <button
              onClick={() => { setPickerOpen(false); setPickerSearch(''); }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, color: 'var(--text-muted)', display: 'flex' }}
            >
              <X size={12} />
            </button>
          </div>
          <div style={{ maxHeight: 220, overflowY: 'auto', padding: 4 }}>
            {hierTree.map((theme: any) => (
              <ReviewHierPicker key={theme.id} node={theme} depth={0} search={pickerSearch} onSelect={linkToStory} />
            ))}
            {hierTree.length === 0 && (
              <div style={{ padding: 12, fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
                No hierarchy available
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function MeetingReviewCard({ data, navigate, onUpdate }: {
  data: any;
  navigate: (path: string) => void;
  onUpdate: (date?: string) => void;
}) {
  const [expandedMeeting, setExpandedMeeting] = useState<string | null>(null);
  const [filterAutoOnly, setFilterAutoOnly] = useState(false);
  const [dateMode, setDateMode] = useState<'range' | 'single'>('range');
  const [selectedDate, setSelectedDate] = useState(() => {
    return data?.summary?.date || new Date().toISOString().split('T')[0];
  });
  const [undoStack, setUndoStack] = useState<{ label: string; items: { entity_type: string; id: string }[] }[]>([]);
  const [hierTree, setHierTree] = useState<any[]>([]);
  const [syncing, setSyncing] = useState(false);

  // Load hierarchy tree for linking tasks
  useEffect(() => {
    api.get<any>('/api/hierarchy').then((d) => setHierTree(d.tree || [])).catch(() => {});
  }, []);

  const handleSync = () => {
    setSyncing(true);
    api.post<any>('/api/intel/scan', { max_pages: 50 })
      .then(() => onUpdate(currentDateParam))
      .catch(() => {})
      .finally(() => setSyncing(false));
  };

  const todayStr = new Date().toISOString().split('T')[0];
  const currentDateParam = dateMode === 'single' ? selectedDate : undefined;

  const changeDate = (delta: number) => {
    const base = dateMode === 'range' ? todayStr : selectedDate;
    const d = new Date(base + 'T12:00:00');
    d.setDate(d.getDate() + delta);
    const next = d.toISOString().split('T')[0];
    setSelectedDate(next);
    setDateMode('single');
    onUpdate(next);
  };

  const formatDateLabel = () => {
    if (dateMode === 'range') return 'Last 3 days';
    if (selectedDate === todayStr) return 'Today';
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    if (selectedDate === yesterday.toISOString().split('T')[0]) return 'Yesterday';
    const d = new Date(selectedDate + 'T12:00:00');
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  };

  const handleReview = async (entityType: string, id: string, title: string) => {
    try {
      await api.post(`/api/review/${entityType}/${id}`, {});
      setUndoStack((prev) => [...prev.slice(-9), { label: `Reviewed: ${title.slice(0, 40)}`, items: [{ entity_type: entityType, id }] }]);
      onUpdate(currentDateParam);
    } catch { /* ignore */ }
  };

  const handleDismiss = async (entityType: string, id: string, title: string) => {
    try {
      await api.post(`/api/dismiss/${entityType}/${id}`, {});
      setUndoStack((prev) => [...prev.slice(-9), { label: `Dismissed: ${title.slice(0, 40)}`, items: [{ entity_type: entityType, id }] }]);
      onUpdate(currentDateParam);
    } catch { /* ignore */ }
  };

  const handleReviewAll = async (meeting: any) => {
    const items = (meeting.items || []).map((i: any) => ({ entity_type: i.entity_type, id: i.id }));
    if (items.length === 0) return;
    try {
      await api.post('/api/review-bulk', { items });
      setUndoStack((prev) => [...prev.slice(-9), { label: `Reviewed all: ${meeting.source_title || 'Other items'} (${items.length})`, items }]);
      onUpdate(currentDateParam);
    } catch { /* ignore */ }
  };

  const handleUndo = async () => {
    const last = undoStack[undoStack.length - 1];
    if (!last) return;
    try {
      await api.post('/api/unreview-bulk', { items: last.items });
      setUndoStack((prev) => prev.slice(0, -1));
      onUpdate(currentDateParam);
    } catch { /* ignore */ }
  };

  const navigateToItem = (item: any) => {
    if (item.entity_type === 'tasks') navigate('/work');
    else if (item.entity_type === 'decisions') navigate('/strategy?tab=decisions');
    else navigate('/strategy?tab=hierarchy');
  };

  const meetings = data.meetings || [];
  const summary = data.summary || {};

  return (
    <div style={{ ...cardStyle, marginBottom: 24 }}>
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      <div style={{ ...cardHeaderStyle, justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Eye size={16} />
          Meeting Review
          <span style={{
            fontSize: 11, color: 'var(--text-muted)', fontWeight: 400,
            padding: '1px 8px', backgroundColor: 'var(--bg-secondary)', borderRadius: 10,
          }}>
            {summary.total_items || 0} item{summary.total_items !== 1 ? 's' : ''}
            {summary.meetings_count > 0 && ` from ${summary.meetings_count} source${summary.meetings_count !== 1 ? 's' : ''}`}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Last sync + Sync button */}
          {summary.last_scan_at && !syncing && (
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }} title={`Last sync: ${new Date(summary.last_scan_at).toLocaleString()}`}>
              {(() => {
                const diff = Date.now() - new Date(summary.last_scan_at).getTime();
                const mins = Math.floor(diff / 60000);
                if (mins < 1) return 'just now';
                if (mins < 60) return `${mins}m ago`;
                const hrs = Math.floor(mins / 60);
                if (hrs < 24) return `${hrs}h ago`;
                return `${Math.floor(hrs / 24)}d ago`;
              })()}
            </span>
          )}
          <button
            onClick={handleSync}
            disabled={syncing}
            title="Fetch new meetings from Notion"
            style={{
              fontSize: 11, fontWeight: 500, border: 'none', borderRadius: 8,
              padding: '3px 10px', cursor: syncing ? 'default' : 'pointer', transition: 'all 0.1s',
              backgroundColor: syncing ? 'rgba(99,102,241,0.15)' : 'var(--bg-secondary)',
              color: syncing ? 'var(--accent)' : 'var(--text-muted)',
              display: 'flex', alignItems: 'center', gap: 4, opacity: syncing ? 0.7 : 1,
            }}
            onMouseEnter={(e) => { if (!syncing) e.currentTarget.style.backgroundColor = 'var(--bg-hover)'; }}
            onMouseLeave={(e) => { if (!syncing) e.currentTarget.style.backgroundColor = 'var(--bg-secondary)'; }}
          >
            <RefreshCw size={11} style={syncing ? { animation: 'spin 1s linear infinite' } : {}} />
            {syncing ? 'Syncing...' : 'Sync'}
          </button>
          {/* Date navigation */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <button
              onClick={() => changeDate(-1)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: 4,
                color: 'var(--text-muted)', borderRadius: 4, display: 'flex',
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              title="Previous day"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              onClick={() => {
                if (dateMode === 'single') {
                  // Go back to range mode
                  setDateMode('range');
                  setSelectedDate(todayStr);
                  
                  onUpdate();
                } else {
                  // Switch to single-date mode for today
                  setDateMode('single');
                  setSelectedDate(todayStr);
                  
                  onUpdate(todayStr);
                }
              }}
              style={{
                fontSize: 11, fontWeight: 500, border: 'none', borderRadius: 6,
                padding: '2px 8px', cursor: 'pointer', transition: 'all 0.1s',
                backgroundColor: dateMode === 'range' ? 'var(--bg-secondary)' : 'rgba(99,102,241,0.12)',
                color: dateMode === 'range' ? 'var(--text-muted)' : 'var(--accent)',
                minWidth: 80, textAlign: 'center',
              }}
              title={dateMode === 'single' ? 'Click to show last 3 days' : 'Click to filter by today'}
            >
              {formatDateLabel()}
            </button>
            <button
              onClick={() => changeDate(1)}
              disabled={dateMode === 'range' || selectedDate >= todayStr}
              style={{
                background: 'none', border: 'none',
                cursor: (dateMode === 'range' || selectedDate >= todayStr) ? 'default' : 'pointer',
                padding: 4,
                color: (dateMode === 'range' || selectedDate >= todayStr) ? 'var(--border)' : 'var(--text-muted)',
                borderRadius: 4, display: 'flex',
                opacity: (dateMode === 'range' || selectedDate >= todayStr) ? 0.3 : 1,
              }}
              onMouseEnter={(e) => { if (dateMode === 'single' && selectedDate < todayStr) e.currentTarget.style.backgroundColor = 'var(--bg-hover)'; }}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              title="Next day"
            >
              <ChevronRight size={14} />
            </button>
          </div>
          <button
            onClick={() => setFilterAutoOnly(!filterAutoOnly)}
            style={{
              fontSize: 11, fontWeight: 500, border: 'none', borderRadius: 8,
              padding: '3px 10px', cursor: 'pointer', transition: 'all 0.1s',
              backgroundColor: filterAutoOnly ? 'rgba(245,158,11,0.15)' : 'var(--bg-secondary)',
              color: filterAutoOnly ? '#f59e0b' : 'var(--text-muted)',
            }}
          >
            {filterAutoOnly ? 'Auto only' : 'All sources'}
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {meetings.length === 0 && (
          <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 20, textAlign: 'center' }}>
            No items for {formatDateLabel().toLowerCase()}
          </div>
        )}
        {meetings.map((meeting: any) => {
          const items = (meeting.items || [])
            .filter((i: any) => !filterAutoOnly || i.source === 'auto');
          if (items.length === 0) return null;

          const key = meeting.source_title || meeting.source_page_id || '__ungrouped__';
          const isExpanded = expandedMeeting === key;

          return (
            <div key={key}>
              {/* Meeting group header */}
              <div
                onClick={() => setExpandedMeeting(isExpanded ? null : key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 12px', backgroundColor: isExpanded ? 'var(--bg-hover)' : 'var(--bg-secondary)',
                  borderRadius: isExpanded ? 'var(--radius) var(--radius) 0 0' : 'var(--radius)',
                  borderLeft: '3px solid var(--accent)',
                  cursor: 'pointer', transition: 'background-color 0.1s',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                onMouseLeave={(e) => { if (!isExpanded) e.currentTarget.style.backgroundColor = 'var(--bg-secondary)'; }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {meeting.source_title || 'Other items'}
                    </span>
                    {meeting.meeting_date && (
                      <span style={{
                        fontSize: 10, fontWeight: 400, color: 'var(--text-muted)',
                        padding: '1px 6px', backgroundColor: 'var(--bg-card)',
                        borderRadius: 4, flexShrink: 0, whiteSpace: 'nowrap',
                      }}>
                        {(() => {
                          const d = new Date(meeting.meeting_date + 'T12:00:00');
                          return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                        })()}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, display: 'flex', gap: 8 }}>
                    <span>{items.length} item{items.length !== 1 ? 's' : ''}</span>
                    {meeting.counts?.auto > 0 && (
                      <span style={{ color: '#f59e0b' }}>{meeting.counts.auto} auto</span>
                    )}
                    {meeting.counts?.confirmed > 0 && (
                      <span style={{ color: '#22c55e' }}>{meeting.counts.confirmed} confirmed</span>
                    )}
                  </div>
                </div>
                {/* Review all button */}
                <button
                  title="Review all items in this meeting"
                  onClick={(e) => { e.stopPropagation(); handleReviewAll(meeting); }}
                  style={{
                    fontSize: 10, fontWeight: 500, border: 'none', borderRadius: 6,
                    padding: '4px 10px', cursor: 'pointer', transition: 'all 0.15s',
                    backgroundColor: 'rgba(34,197,94,0.1)', color: '#22c55e',
                    display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0,
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(34,197,94,0.25)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(34,197,94,0.1)'}
                >
                  <CheckCircle2 size={12} />
                  Review all
                </button>
                {isExpanded
                  ? <ChevronDown size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                  : <ChevronRight size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                }
              </div>

              {/* Expanded items */}
              {isExpanded && (
                <div style={{
                  backgroundColor: 'var(--bg-secondary)', borderLeft: '3px solid var(--accent)',
                  borderRadius: '0 0 var(--radius) var(--radius)', padding: '8px 12px',
                  borderTop: '1px solid var(--border)',
                  display: 'flex', flexDirection: 'column', gap: 6,
                }}>
                  {items.map((item: any) => (
                    <MeetingReviewItem
                      key={item.id}
                      item={item}
                      hierTree={hierTree}
                      onReview={handleReview}
                      onDismiss={handleDismiss}
                      onNavigate={navigateToItem}
                      onUpdate={() => onUpdate(currentDateParam)}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Undo toast */}
      {undoStack.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 12px', marginTop: 8,
          backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
        }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {undoStack[undoStack.length - 1].label}
          </span>
          <button
            onClick={handleUndo}
            style={{
              fontSize: 11, fontWeight: 500, border: 'none', borderRadius: 6,
              padding: '3px 10px', cursor: 'pointer',
              backgroundColor: 'rgba(99,102,241,0.12)', color: 'var(--accent)',
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(99,102,241,0.25)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(99,102,241,0.12)'}
          >
            Undo
          </button>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, color, onClick }: {
  icon: React.ReactNode; label: string; value: string; color: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        ...cardStyle, padding: '16px 20px',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.15s',
      }}
      onMouseEnter={(e) => {
        if (onClick) {
          e.currentTarget.style.backgroundColor = 'var(--bg-hover)';
          e.currentTarget.style.boxShadow = 'var(--shadow)';
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = 'var(--bg-card)';
        e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
          <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
        </div>
        <div style={{ color, opacity: 0.5 }}>{icon}</div>
      </div>
    </div>
  );
}

function OverviewItem({ icon, label, count, detail, color, onClick }: {
  icon: React.ReactNode; label: string; count: number | string; detail?: string; color: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 12px', backgroundColor: 'var(--bg-secondary)',
        borderRadius: 'var(--radius)', cursor: onClick ? 'pointer' : 'default',
        transition: 'background-color 0.1s',
      }}
      onMouseEnter={(e) => { if (onClick) e.currentTarget.style.backgroundColor = 'var(--bg-hover)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'var(--bg-secondary)'; }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color }}>{icon}</span>
        <div>
          <span style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>{label}</span>
          {detail && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{detail}</div>}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          fontSize: 14, fontWeight: 600, color: 'var(--text-primary)',
          padding: '2px 10px', backgroundColor: 'var(--bg-tertiary)', borderRadius: 12,
        }}>
          {count}
        </span>
        {onClick && <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />}
      </div>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  backgroundColor: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-lg)',
  padding: 20,
  boxShadow: 'var(--shadow-sm)',
};

const cardHeaderStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--text-primary)',
  marginBottom: 16,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
};

/* ---------- Alert inline expansion ---------- */

function parseAlertItems(detail: string): { label: string; meta?: string }[] {
  if (!detail) return [];
  // Split on semicolons, "and X more" patterns
  const cleaned = detail.replace(/\s+and\s+\d+\s+more$/, '');
  return cleaned.split(/;\s*/).filter(Boolean).map((s) => {
    // Try to extract person + count: "Rodrigo is overloaded (12 open tasks)"
    const personMatch = s.match(/^(.+?)\s+is\s+overloaded\s*\((\d+\s+open\s+tasks)\)/i);
    if (personMatch) return { label: personMatch[1].trim(), meta: personMatch[2] };
    // Try "Initiative at risk: Name"
    const initMatch = s.match(/^Initiative at risk:\s*(.+)/i);
    if (initMatch) return { label: initMatch[1].trim(), meta: 'at risk' };
    // Try "X has N deliverable tasks without an epic"
    const orphanMatch = s.match(/^(.+?)\s+has\s+(\d+\s+deliverable\s+tasks?\s+without\s+an?\s+\w+)/i);
    if (orphanMatch) return { label: orphanMatch[1].trim(), meta: orphanMatch[2] };
    return { label: s.trim() };
  });
}

function getAlertIcon(type: string) {
  if (type === 'bottleneck') return <User size={12} />;
  if (type === 'initiative_risk') return <Target size={12} />;
  if (type === 'orphaned_deliverable') return <Package size={12} />;
  return <Zap size={12} />;
}

function AlertExpandedContent({ alert, severityColor, navigate }: {
  alert: AlertData; severityColor: string;
  navigate: (path: string) => void;
}) {
  const items = parseAlertItems(alert.detail || '');
  const andMoreMatch = alert.detail?.match(/and\s+(\d+)\s+more$/);

  return (
    <div style={{
      backgroundColor: 'var(--bg-secondary)', borderLeft: `3px solid ${severityColor}`,
      borderRadius: '0 0 var(--radius) var(--radius)', padding: '12px 14px',
      borderTop: '1px solid var(--border)',
    }}>
      {/* Meta row */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={{
          fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px',
          padding: '2px 8px', borderRadius: 8,
          backgroundColor: severityColor === 'var(--danger)' ? 'rgba(239,68,68,0.15)' : severityColor === 'var(--warning)' ? 'rgba(245,158,11,0.15)' : 'rgba(59,130,246,0.15)',
          color: severityColor,
        }}>
          {alert.severity}
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {alert.type?.replace(/_/g, ' ')}
        </span>
        {alert.suggested_action && (
          <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 'auto', fontStyle: 'italic' }}>
            Suggested: {alert.suggested_action}
          </span>
        )}
      </div>

      {/* Structured items */}
      {items.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {items.map((item, j) => (
            <div
              key={j}
              onClick={(e) => {
                e.stopPropagation();
                if (alert.type === 'bottleneck') navigate(`/work?search=${encodeURIComponent(item.label)}`);
                else if (alert.type === 'initiative_risk') navigate('/strategy');
                else if (alert.type === 'orphaned_deliverable') navigate('/strategy');
              }}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '6px 10px', backgroundColor: 'var(--bg-card)',
                borderRadius: 'var(--radius)', cursor: 'pointer',
                transition: 'background-color 0.1s',
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-card)'}
            >
              <span style={{ color: severityColor, flexShrink: 0 }}>
                {getAlertIcon(alert.type)}
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, flex: 1 }}>
                {item.label}
              </span>
              {item.meta && (
                <span style={{
                  fontSize: 11, color: 'var(--text-muted)', flexShrink: 0,
                  padding: '1px 6px', backgroundColor: 'var(--bg-secondary)', borderRadius: 8,
                }}>
                  {item.meta}
                </span>
              )}
              <ChevronRight size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            </div>
          ))}
          {andMoreMatch && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 10px', fontStyle: 'italic' }}>
              and {andMoreMatch[1]} more...
            </div>
          )}
        </div>
      )}

      {/* Fallback if no structured items parsed */}
      {items.length === 0 && alert.detail && (
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {alert.detail}
        </div>
      )}
    </div>
  );
}
