/**
 * Global state store using Zustand.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { getTheme } from '../themes';

interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
}

interface Team {
  id: string;
  name: string;
  role: string;
}

interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  toolCalls?: Array<{ name: string; arguments: any }>;
  toolResults?: Array<{ name: string; result: any }>;
}

interface AppState {
  // Auth
  token: string;
  user: User | null;
  teams: Team[];
  activeTeamId: string;

  // Theme
  themeId: string;
  darkMode: boolean;
  density: 'compact' | 'comfortable' | 'spacious';

  // Chat
  chatOpen: boolean;
  chatMessages: ChatMessage[];
  conversationId: string;
  isStreaming: boolean;

  // Actions
  setAuth: (token: string, user: User, teams: Team[]) => void;
  logout: () => void;
  setTeams: (teams: Team[]) => void;
  setActiveTeam: (teamId: string) => void;
  setTheme: (themeId: string) => void;
  setDarkMode: (dark: boolean) => void;
  setDensity: (d: 'compact' | 'comfortable' | 'spacious') => void;
  toggleChat: () => void;
  setChatOpen: (open: boolean) => void;
  addChatMessage: (msg: ChatMessage) => void;
  appendToLastMessage: (text: string) => void;
  clearChat: () => void;
  setConversationId: (id: string) => void;
  setIsStreaming: (s: boolean) => void;
}

export const useStore = create<AppState>()(
  persist(
    (set, _get) => ({
      // Auth defaults
      token: '',
      user: null,
      teams: [],
      activeTeamId: '',

      // Theme defaults
      themeId: 'executive',
      darkMode: false,
      density: 'comfortable',

      // Chat defaults
      chatOpen: false,
      chatMessages: [],
      conversationId: '',
      isStreaming: false,

      // Auth actions
      setAuth: (token, user, teams) => set({ token, user, teams, activeTeamId: teams[0]?.id || '' }),
      logout: () => set({ token: '', user: null, teams: [], activeTeamId: '', chatMessages: [], conversationId: '' }),
      setTeams: (teams) => set((s) => ({ teams, activeTeamId: s.activeTeamId || teams[0]?.id || '' })),
      setActiveTeam: (teamId) => set({ activeTeamId: teamId }),

      // Theme actions
      setTheme: (themeId) => {
        const theme = getTheme(themeId);
        set({
          themeId,
          density: theme.layout.density,
          ...(theme.forceDark ? { darkMode: true } : {}),
        });
      },
      setDarkMode: (dark) => set({ darkMode: dark }),
      setDensity: (d) => set({ density: d }),

      // Chat actions
      toggleChat: () => set((s) => ({ chatOpen: !s.chatOpen })),
      setChatOpen: (open) => set({ chatOpen: open }),
      addChatMessage: (msg) => set((s) => ({ chatMessages: [...s.chatMessages, msg] })),
      appendToLastMessage: (text) => set((s) => {
        const msgs = [...s.chatMessages];
        if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
          msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], content: msgs[msgs.length - 1].content + text };
        }
        return { chatMessages: msgs };
      }),
      clearChat: () => set({ chatMessages: [], conversationId: '' }),
      setConversationId: (id) => set({ conversationId: id }),
      setIsStreaming: (s) => set({ isStreaming: s }),
    }),
    {
      name: 'tars-store',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        teams: state.teams,
        activeTeamId: state.activeTeamId,
        themeId: state.themeId,
        darkMode: state.darkMode,
        density: state.density,
      }),
    }
  )
);
