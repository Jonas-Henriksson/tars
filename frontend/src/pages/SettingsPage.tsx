/**
 * Settings page — theme, integrations, team management.
 */
import { useEffect, useState } from 'react';
import { useStore } from '../store';
import { themes } from '../themes';
import { api } from '../api/client';
import { Palette, Plug, Users } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 24 }}>Settings</h1>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <AppearanceSection />
        <IntegrationStatus />
        <TeamSection />
      </div>
    </div>
  );
}

function AppearanceSection() {
  const { themeId, darkMode, density, setTheme, setDarkMode, setDensity } = useStore();

  return (
    <div style={sectionStyle}>
      <h2 style={sectionHeaderStyle}>
        <Palette size={18} />
        Appearance
      </h2>

      {/* Theme selector */}
      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>Theme</label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          {Object.values(themes).map((theme) => (
            <button
              key={theme.id}
              onClick={() => setTheme(theme.id)}
              style={{
                padding: 16,
                border: themeId === theme.id ? '2px solid var(--accent)' : '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)',
                backgroundColor: 'var(--bg-secondary)',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)', marginBottom: 4 }}>
                {theme.label}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.4 }}>
                {theme.description}
              </div>
              {theme.forceDark && (
                <div style={{ fontSize: 10, marginTop: 6, padding: '2px 6px', backgroundColor: 'var(--bg-tertiary)', borderRadius: 4, display: 'inline-block', color: 'var(--text-muted)' }}>
                  Forces dark mode
                </div>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Dark mode */}
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <label style={labelStyle}>Dark Mode</label>
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Toggle dark/light appearance</p>
        </div>
        <button
          onClick={() => setDarkMode(!darkMode)}
          style={{
            width: 48, height: 28, borderRadius: 14,
            backgroundColor: darkMode ? 'var(--accent)' : 'var(--border)',
            border: 'none', cursor: 'pointer', position: 'relative', transition: 'background 0.2s',
          }}
        >
          <div style={{
            width: 22, height: 22, borderRadius: '50%', backgroundColor: '#fff',
            position: 'absolute', top: 3, left: darkMode ? 23 : 3, transition: 'left 0.2s',
            boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
          }} />
        </button>
      </div>

      {/* Density */}
      <div>
        <label style={labelStyle}>Density</label>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['compact', 'comfortable', 'spacious'] as const).map((d) => (
            <button
              key={d}
              onClick={() => setDensity(d)}
              style={{
                padding: '6px 16px', border: density === d ? '1px solid var(--accent)' : '1px solid var(--border)',
                borderRadius: 'var(--radius)', backgroundColor: density === d ? 'var(--accent-light)' : 'transparent',
                color: density === d ? 'var(--accent)' : 'var(--text-secondary)',
                fontSize: 13, cursor: 'pointer', textTransform: 'capitalize',
              }}
            >
              {d}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function IntegrationStatus() {
  const [statuses, setStatuses] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any>('/api/settings/status').then((data) => {
      setStatuses(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <div style={sectionStyle}>
      <h2 style={sectionHeaderStyle}>
        <Plug size={18} />
        Integrations
      </h2>
      {loading ? (
        <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
          {Object.entries(statuses).map(([key, status]: [string, any]) => (
            <div
              key={key}
              style={{
                padding: 14,
                backgroundColor: 'var(--bg-secondary)',
                borderRadius: 'var(--radius)',
                borderLeft: `3px solid ${status.configured ? 'var(--success)' : 'var(--border)'}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                  {key.replace(/365/, ' 365')}
                </span>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  backgroundColor: status.configured ? (status.signed_in !== false ? 'var(--success)' : 'var(--warning)') : 'var(--text-muted)',
                }} />
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {status.services?.join(' · ')}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TeamSection() {
  const { teams, activeTeamId } = useStore();

  return (
    <div style={sectionStyle}>
      <h2 style={sectionHeaderStyle}>
        <Users size={18} />
        Team
      </h2>
      {teams.length === 0 ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          No teams yet. Create one to collaborate with others.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {teams.map((t) => (
            <div
              key={t.id}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 14px', backgroundColor: t.id === activeTeamId ? 'var(--accent-light)' : 'var(--bg-secondary)',
                borderRadius: 'var(--radius)', border: t.id === activeTeamId ? '1px solid var(--accent)' : '1px solid var(--border)',
              }}
            >
              <div>
                <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{t.name}</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>{t.role}</span>
              </div>
              {t.id === activeTeamId && (
                <span style={{ fontSize: 11, color: 'var(--accent)' }}>Active</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const sectionStyle: React.CSSProperties = {
  backgroundColor: 'var(--bg-card)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-lg)',
  padding: 24,
  boxShadow: 'var(--shadow-sm)',
};

const sectionHeaderStyle: React.CSSProperties = {
  fontSize: 16, fontWeight: 600, color: 'var(--text-primary)',
  marginBottom: 20, display: 'flex', alignItems: 'center', gap: 10,
};

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 13, fontWeight: 500,
  color: 'var(--text-primary)', marginBottom: 8,
};
