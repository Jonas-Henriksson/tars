/* Header status indicator — shows integration health, last sync, and scan progress. */
(function() {
    var style = document.createElement('style');
    style.textContent = [
        '.hdr-status { display:inline-flex; align-items:center; gap:10px; margin-left:10px; vertical-align:middle; font-size:11px; }',
        '.hdr-status a { display:inline-flex; align-items:center; gap:5px; padding:2px 8px; border-radius:5px; cursor:pointer; text-decoration:none; border:1px solid transparent; transition:all .15s; }',
        '.hdr-status a:hover { background:rgba(255,255,255,.05); }',
        /* Integration summary dot */
        '.hdr-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; }',
        '.hdr-dot.green { background:#22c55e; box-shadow:0 0 6px rgba(34,197,94,.4); }',
        '.hdr-dot.amber { background:#f59e0b; box-shadow:0 0 6px rgba(245,158,11,.4); }',
        '.hdr-dot.red { background:#ef4444; box-shadow:0 0 6px rgba(239,68,68,.4); }',
        '.hdr-dot.grey { background:#52525b; }',
        '.hdr-lbl { color:#a1a1aa; }',
        '.hdr-lbl.green { color:#4ade80; }',
        '.hdr-lbl.amber { color:#fbbf24; }',
        '.hdr-lbl.red { color:#ef4444; }',
        /* Scan spinner */
        '.hdr-scan { display:inline-flex; align-items:center; gap:5px; color:#a1a1aa; }',
        '.hdr-scan-spinner { width:10px; height:10px; border:1.5px solid #27272a; border-top-color:#3b82f6; border-radius:50%; animation:hdr-spin .7s linear infinite; }',
        '@keyframes hdr-spin { to { transform:rotate(360deg); } }',
        '.hdr-scan-text { max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }',
    ].join('\n');
    document.head.appendChild(style);

    function timeAgo(isoStr) {
        if (!isoStr) return null;
        try {
            var diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
            if (diff < 0) diff = 0;
            if (diff < 60) return 'just now';
            if (diff < 3600) return Math.floor(diff / 60) + ' min ago';
            if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
            return Math.floor(diff / 86400) + 'd ago';
        } catch(e) { return null; }
    }

    function render(data) {
        var el = document.getElementById('hdr-status');
        if (!el) {
            el = document.createElement('span');
            el.id = 'hdr-status';
            el.className = 'hdr-status';
            var brand = document.querySelector('.brand');
            if (brand) brand.appendChild(el);
        }

        var parts = [];

        // ── Integration health summary dot ──
        var ig = data.integrations || {};
        var dotCls = 'green';
        if (ig.red > 0) dotCls = 'red';
        else if (ig.amber > 0) dotCls = 'amber';

        // Build label: "4/4" or "3/4" style
        var total = (ig.green || 0) + (ig.amber || 0) + (ig.red || 0);
        var ok = (ig.green || 0);

        var syncLabel = '';
        var wh = data.webhook || {};
        if (wh.last_event_at) {
            syncLabel = 'Synced ' + timeAgo(wh.last_event_at);
        } else if (wh.enabled) {
            syncLabel = 'Awaiting first sync';
        } else {
            syncLabel = ok + '/' + total + ' services';
        }

        parts.push(
            '<a href="/settings" title="Integration status — click to configure">' +
                '<span class="hdr-dot ' + dotCls + '"></span>' +
                '<span class="hdr-lbl ' + dotCls + '">' + syncLabel + '</span>' +
            '</a>'
        );

        // ── Scan progress ──
        var scan = data.scan || {};
        if (scan.running) {
            var scanText = 'Scanning';
            if (scan.total > 0) {
                scanText = 'Scanning ' + scan.current + '/' + scan.total;
            }
            if (scan.page_title && scan.status === 'processing') {
                scanText = scan.page_title;
            }
            if (scan.status === 'enriching') {
                scanText = scan.page_title || 'Enriching…';
            }
            parts.push(
                '<a href="/settings#scan" class="hdr-scan" title="Scan in progress — click for details">' +
                    '<span class="hdr-scan-spinner"></span>' +
                    '<span class="hdr-scan-text">' + scanText + '</span>' +
                '</a>'
            );
        }

        el.innerHTML = parts.join('');
    }

    function poll() {
        fetch('/api/header/status')
            .then(function(r) { return r.json(); })
            .then(render)
            .catch(function() {});
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', poll);
    } else {
        poll();
    }
    // Poll more frequently during scans (every 3s), otherwise every 30s
    var _interval = setInterval(function() {
        var scanEl = document.querySelector('.hdr-scan-spinner');
        if (scanEl) {
            clearInterval(_interval);
            _interval = setInterval(poll, 3000);
            // Restore slower interval when scan finishes
            var _check = setInterval(function() {
                if (!document.querySelector('.hdr-scan-spinner')) {
                    clearInterval(_check);
                    clearInterval(_interval);
                    _interval = setInterval(poll, 30000);
                }
            }, 5000);
        }
        poll();
    }, 30000);
    // Also do a fast initial poll burst to catch scans quickly
    setTimeout(poll, 3000);
})();
