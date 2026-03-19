/**
 * Command Center — the home dashboard, layout driven by theme.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import {
  Calendar, AlertTriangle, Mail, TrendingUp, CheckCircle2, ChevronRight,
  Target, Scale, Users, CalendarCheck, Clock,
} from 'lucide-react';
import DetailPanel from '../components/DetailPanel';
import type { DetailField } from '../components/DetailPanel';

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
  const [selectedAlert, setSelectedAlert] = useState<AlertData | null>(null);
  const [meetingPrep, setMeetingPrep] = useState<any>(null);

  useEffect(() => {
    Promise.all([
      api.get<any>('/api/alerts').catch(() => ({ alerts: [] })),
      api.get<any>('/api/strategic-summary').catch(() => ({})),
      api.get<any>('/api/review/weekly').catch(() => ({})),
      api.get<any>('/api/meeting-prep').catch(() => null),
    ]).then(([alertsData, summaryData, reviewData, meetingData]) => {
      setAlerts(alertsData.alerts || []);
      setSummary(summaryData);
      setTaskStats(reviewData.smart_tasks || {});
      setMeetingPrep(meetingData?.available ? meetingData : null);
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

  const alertFields: DetailField[] = selectedAlert ? [
    { key: 'severity', label: 'Severity', value: selectedAlert.severity, type: 'badge',
      color: selectedAlert.severity === 'critical' ? '#ef4444' : selectedAlert.severity === 'warning' ? '#f59e0b' : '#3b82f6' },
    { key: 'type', label: 'Type', value: selectedAlert.type?.replace(/_/g, ' '), type: 'readonly' },
    { key: 'detail', label: 'Details', value: selectedAlert.detail, type: 'readonly' },
    ...(selectedAlert.person ? [{ key: 'person', label: 'Person', value: selectedAlert.person, type: 'readonly' as const }] : []),
    ...(selectedAlert.task_count ? [{ key: 'task_count', label: 'Task Count', value: selectedAlert.task_count, type: 'readonly' as const }] : []),
    ...(selectedAlert.days_overdue ? [{ key: 'days_overdue', label: 'Days Overdue', value: selectedAlert.days_overdue, type: 'readonly' as const }] : []),
    ...(selectedAlert.suggested_action ? [{ key: 'suggested_action', label: 'Suggested Action', value: selectedAlert.suggested_action, type: 'readonly' as const }] : []),
  ] : [];

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
            onClick={() => { /* scroll to alerts section */ }}
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
        <div style={cardStyle}>
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
              displayAlerts.map((alert, i) => (
                <div
                  key={i}
                  onClick={() => setSelectedAlert(alert)}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 10,
                    padding: '10px 12px', backgroundColor: 'var(--bg-secondary)',
                    borderRadius: 'var(--radius)',
                    borderLeft: `3px solid ${alert.severity === 'critical' ? 'var(--danger)' : alert.severity === 'warning' ? 'var(--warning)' : 'var(--info)'}`,
                    cursor: 'pointer', transition: 'background-color 0.1s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-hover)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-secondary)'}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                      {alert.title}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                      {alert.detail?.slice(0, 100)}
                    </div>
                  </div>
                  <ChevronRight size={14} style={{ color: 'var(--text-muted)', flexShrink: 0, marginTop: 2 }} />
                </div>
              ))
            )}
            {alerts.length > displayAlerts.length && (
              <div
                onClick={() => { /* TODO: expand all alerts */ }}
                style={{ fontSize: 12, color: 'var(--accent)', textAlign: 'center', padding: 8, cursor: 'pointer', fontWeight: 500 }}
              >
                View all {alerts.length} alerts
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
              onClick={() => navigate('/strategy')}
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

      {/* Alert detail panel */}
      <DetailPanel
        open={!!selectedAlert}
        onClose={() => setSelectedAlert(null)}
        title={selectedAlert?.title || ''}
        subtitle={selectedAlert?.detail}
        badge={selectedAlert ? {
          label: selectedAlert.severity,
          color: selectedAlert.severity === 'critical' ? '#ef4444' : selectedAlert.severity === 'warning' ? '#f59e0b' : '#3b82f6',
        } : undefined}
        fields={alertFields}
      />
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
