/**
 * Command Center — the home dashboard, layout driven by theme.
 */
import { useEffect, useState } from 'react';

import { api } from '../api/client';
import {
  Calendar, AlertTriangle, Mail, TrendingUp, CheckCircle2,
} from 'lucide-react';

interface AlertData {
  type: string;
  severity: string;
  title: string;
  detail: string;
}


export default function CommandCenter() {
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<any>('/api/alerts').catch(() => ({ alerts: [] })),
      api.get<any>('/api/strategic-summary').catch(() => ({})),
    ]).then(([alertsData, _summaryData]) => {
      setAlerts(alertsData.alerts || []);
      setLoading(false);
    });
  }, []);

  const criticalAlerts = alerts.filter((a) => a.severity === 'critical');

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)' }}>
          Command Center
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, marginTop: 4 }}>
          {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
        </p>
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
          <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>
            <strong>{criticalAlerts.length} critical alert{criticalAlerts.length !== 1 ? 's' : ''}</strong>
            {' — '}
            {criticalAlerts.slice(0, 2).map((a) => a.title).join('; ')}
          </div>
        </div>
      )}

      {/* Stats cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 16,
          marginBottom: 24,
        }}
      >
        <StatCard icon={<CheckCircle2 size={20} />} label="Open Tasks" value="--" color="var(--accent)" />
        <StatCard icon={<AlertTriangle size={20} />} label="Alerts" value={`${alerts.length}`} color="var(--warning)" />
        <StatCard icon={<Calendar size={20} />} label="Meetings Today" value="--" color="var(--info)" />
        <StatCard icon={<Mail size={20} />} label="Unread Email" value="--" color="var(--success)" />
      </div>

      {/* Two column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Alerts list */}
        <div style={cardStyle}>
          <h2 style={cardHeaderStyle}>
            <AlertTriangle size={16} />
            Alerts & Attention
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {loading ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 20, textAlign: 'center' }}>
                Loading...
              </div>
            ) : alerts.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 20, textAlign: 'center' }}>
                No alerts — all clear
              </div>
            ) : (
              alerts.slice(0, 8).map((alert, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: '10px 12px',
                    backgroundColor: 'var(--bg-secondary)',
                    borderRadius: 'var(--radius)',
                    borderLeft: `3px solid ${alert.severity === 'critical' ? 'var(--danger)' : alert.severity === 'warning' ? 'var(--warning)' : 'var(--info)'}`,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                      {alert.title}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                      {alert.detail?.slice(0, 100)}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Quick overview */}
        <div style={cardStyle}>
          <h2 style={cardHeaderStyle}>
            <TrendingUp size={16} />
            Strategic Overview
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <OverviewItem label="Initiatives" status="on_track" count={0} />
            <OverviewItem label="Pending Decisions" status="pending" count={0} />
            <OverviewItem label="Epics In Progress" status="in_progress" count={0} />
            <OverviewItem label="Team Members Active" status="active" count={0} />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) {
  return (
    <div style={{ ...cardStyle, padding: '16px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
          <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
        </div>
        <div style={{ color, opacity: 0.3 }}>{icon}</div>
      </div>
    </div>
  );
}

function OverviewItem({ label, count }: { label: string; status: string; count: number }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 12px',
        backgroundColor: 'var(--bg-secondary)',
        borderRadius: 'var(--radius)',
      }}
    >
      <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{label}</span>
      <span
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--text-primary)',
          padding: '2px 8px',
          backgroundColor: 'var(--bg-tertiary)',
          borderRadius: 12,
        }}
      >
        {count}
      </span>
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
