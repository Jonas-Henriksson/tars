/**
 * Left sidebar — navigation + team switcher.
 */
import { useLocation, useNavigate } from 'react-router-dom';
import { useStore } from '../store';
import {
  LayoutDashboard, Briefcase, Target, Users, Settings, LogOut,
} from 'lucide-react';

const NAV_ITEMS = [
  { path: '/', label: 'Command Center', icon: LayoutDashboard },
  { path: '/work', label: 'Work', icon: Briefcase },
  { path: '/strategy', label: 'Strategy', icon: Target },
  { path: '/people', label: 'People', icon: Users },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, teams, activeTeamId, setActiveTeam, logout } = useStore();

  return (
    <aside
      style={{
        width: 'var(--sidebar-width)',
        backgroundColor: 'var(--bg-sidebar)',
        color: 'var(--text-sidebar)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: '20px 16px 12px',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 'var(--radius)',
              background: 'var(--accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: 14,
              color: '#fff',
            }}
          >
            T
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 15 }}>TARS</div>
            <div style={{ fontSize: 11, color: 'var(--text-sidebar-muted)' }}>
              v2.0
            </div>
          </div>
        </div>
      </div>

      {/* Team switcher */}
      {teams.length > 0 && (
        <div style={{ padding: '12px 12px 4px' }}>
          <select
            value={activeTeamId}
            onChange={(e) => setActiveTeam(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 10px',
              backgroundColor: 'rgba(255,255,255,0.06)',
              color: 'var(--text-sidebar)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 'var(--radius)',
              fontSize: 13,
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            {teams.map((t) => (
              <option key={t.id} value={t.id} style={{ color: '#000' }}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Navigation */}
      <nav style={{ flex: 1, padding: '8px' }}>
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
          const isActive =
            path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                padding: '10px 12px',
                border: 'none',
                borderRadius: 'var(--radius)',
                backgroundColor: isActive ? 'rgba(255,255,255,0.1)' : 'transparent',
                color: isActive ? '#fff' : 'var(--text-sidebar-muted)',
                fontSize: 14,
                fontWeight: isActive ? 500 : 400,
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s',
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.06)';
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              <Icon size={18} />
              {label}
            </button>
          );
        })}
      </nav>

      {/* User */}
      {user && (
        <div
          style={{
            padding: '12px',
            borderTop: '1px solid rgba(255,255,255,0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: 'var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 12,
                fontWeight: 600,
                color: '#fff',
                flexShrink: 0,
              }}
            >
              {user.name.charAt(0).toUpperCase()}
            </div>
            <span
              style={{
                fontSize: 13,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {user.name}
            </span>
          </div>
          <button
            onClick={logout}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-sidebar-muted)',
              cursor: 'pointer',
              padding: 4,
            }}
            title="Log out"
          >
            <LogOut size={16} />
          </button>
        </div>
      )}
    </aside>
  );
}
