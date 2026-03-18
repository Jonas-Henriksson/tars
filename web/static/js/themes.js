/* ═══════════════════════════════════════════════════════════════════
   TARS Theme Switcher
   Loads the saved theme from localStorage and applies it immediately
   (before paint) to avoid FOUC.  Exposes tarsTheme.set(name) for
   the Settings page picker.
   ═══════════════════════════════════════════════════════════════════ */
(function() {
    'use strict';

    var STORAGE_KEY = 'tars-theme';
    var DEFAULT = 'default';
    var THEMES = ['default', 'mission-control', 'broadsheet', 'war-room'];

    // Google Fonts URLs per theme (loaded lazily)
    var FONTS = {
        'mission-control': 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap',
        'broadsheet': 'https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,700;1,6..72,400;1,6..72,500&family=Inter:wght@400;500;600;700&display=swap',
        'war-room': 'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap',
    };

    var _loadedFonts = {};

    function loadFonts(theme) {
        var url = FONTS[theme];
        if (!url || _loadedFonts[theme]) return;
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = url;
        document.head.appendChild(link);
        _loadedFonts[theme] = true;
    }

    function apply(theme) {
        if (THEMES.indexOf(theme) === -1) theme = DEFAULT;
        if (theme === DEFAULT) {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
            loadFonts(theme);
        }
    }

    function get() {
        try { return localStorage.getItem(STORAGE_KEY) || DEFAULT; }
        catch(e) { return DEFAULT; }
    }

    function set(theme) {
        try { localStorage.setItem(STORAGE_KEY, theme); }
        catch(e) {}
        apply(theme);
        // Notify other tabs
        try { window.dispatchEvent(new CustomEvent('tars-theme-change', { detail: theme })); }
        catch(e) {}
    }

    // Apply immediately (this script is loaded in <head> before paint)
    apply(get());

    // Listen for changes from other tabs via storage event
    window.addEventListener('storage', function(e) {
        if (e.key === STORAGE_KEY) apply(e.newValue || DEFAULT);
    });

    // Expose API
    window.tarsTheme = {
        get: get,
        set: set,
        themes: THEMES,
        labels: {
            'default': 'Default',
            'mission-control': 'Mission Control',
            'broadsheet': 'The Broadsheet',
            'war-room': 'War Room',
        },
        descriptions: {
            'default': 'Clean dark interface. The original TARS look.',
            'mission-control': 'CRT phosphor aesthetic. Dense, monospace, zero decoration.',
            'broadsheet': 'Editorial. Serif headlines, warm palette, typographic authority.',
            'war-room': 'Strategic ops. Layered depth, heat gradients, spatial.',
        }
    };
})();
