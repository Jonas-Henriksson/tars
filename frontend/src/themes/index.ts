/**
 * Structural theme system — themes control layout, style, and TARS tone.
 */

export interface ThemeLayout {
  commandCenter: string[];
  defaultWorkTab: 'matrix' | 'board' | 'list' | 'timeline';
  defaultStrategyTab: 'health' | 'portfolio' | 'decisions';
  density: 'compact' | 'comfortable' | 'spacious';
  chatPanel: 'expanded' | 'collapsed';
}

export interface Theme {
  id: string;
  label: string;
  description: string;
  layout: ThemeLayout;
  cssClass: string;
  forceDark: boolean;
  tone: string;
}

export const themes: Record<string, Theme> = {
  executive: {
    id: 'executive',
    label: 'Executive',
    description: 'Clean, professional overview with balanced information density',
    layout: {
      commandCenter: ['calendar', 'alerts', 'email-summary', 'chat'],
      defaultWorkTab: 'matrix',
      defaultStrategyTab: 'health',
      density: 'comfortable',
      chatPanel: 'expanded',
    },
    cssClass: '',
    forceDark: false,
    tone: 'professional',
  },
  'war-room': {
    id: 'war-room',
    label: 'War Room',
    description: 'Dense, alert-focused view for crisis management',
    layout: {
      commandCenter: ['alerts', 'initiative-health', 'blockers', 'portfolio-heatmap'],
      defaultWorkTab: 'board',
      defaultStrategyTab: 'portfolio',
      density: 'compact',
      chatPanel: 'collapsed',
    },
    cssClass: 'theme-war-room',
    forceDark: true,
    tone: 'war-room',
  },
  ops: {
    id: 'ops',
    label: 'Ops / Sprint',
    description: 'Kanban-focused view for sprint execution',
    layout: {
      commandCenter: ['kanban-summary', 'sprint-burndown', 'today-stories', 'blockers'],
      defaultWorkTab: 'board',
      defaultStrategyTab: 'portfolio',
      density: 'compact',
      chatPanel: 'collapsed',
    },
    cssClass: 'theme-ops',
    forceDark: false,
    tone: 'agile',
  },
  focus: {
    id: 'focus',
    label: 'Personal Focus',
    description: 'Minimal view — your top tasks, your calendar, no noise',
    layout: {
      commandCenter: ['top-3-tasks', 'calendar', 'personal-alerts'],
      defaultWorkTab: 'list',
      defaultStrategyTab: 'health',
      density: 'spacious',
      chatPanel: 'expanded',
    },
    cssClass: 'theme-focus',
    forceDark: false,
    tone: 'supportive',
  },
};

export function getTheme(id: string): Theme {
  return themes[id] || themes.executive;
}
