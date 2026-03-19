/**
 * Main app layout — sidebar + topbar + content + chat panel.
 */
import { Outlet } from 'react-router-dom';
import { useStore } from '../store';
import { getTheme } from '../themes';
import Sidebar from '../components/Sidebar';
import TopBar from '../components/TopBar';
import ChatPanel from '../components/ChatPanel';

export default function AppLayout() {
  const { themeId, darkMode, density, chatOpen } = useStore();
  const theme = getTheme(themeId);

  const rootClasses = [
    darkMode || theme.forceDark ? 'dark' : '',
    theme.cssClass,
    `density-${density}`,
  ].filter(Boolean).join(' ');

  return (
    <div className={rootClasses} style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <TopBar />
        <main
          style={{
            flex: 1,
            overflow: 'auto',
            backgroundColor: 'var(--bg-secondary)',
            padding: '24px',
          }}
        >
          <Outlet />
        </main>
      </div>
      {chatOpen && <ChatPanel />}
    </div>
  );
}
