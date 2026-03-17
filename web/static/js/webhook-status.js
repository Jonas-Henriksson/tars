/* Webhook status indicator — auto-injects into the header nav. */
(function() {
    var style = document.createElement('style');
    style.textContent = [
        '.wh-status { display:flex; align-items:center; gap:6px; padding:4px 10px; border-radius:6px; font-size:11px; cursor:pointer; border:1px solid transparent; transition:all .15s; }',
        '.wh-status:hover { background:rgba(255,255,255,.05); }',
        '.wh-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }',
        '.wh-dot.green { background:#22c55e; box-shadow:0 0 6px rgba(34,197,94,.4); }',
        '.wh-dot.amber { background:#f59e0b; box-shadow:0 0 6px rgba(245,158,11,.4); }',
        '.wh-dot.red { background:#ef4444; box-shadow:0 0 6px rgba(239,68,68,.4); }',
        '.wh-dot.grey { background:#52525b; }',
        '.wh-label { color:#a1a1aa; }',
        '.wh-label.green { color:#4ade80; }',
        '.wh-label.amber { color:#fbbf24; }',
        '.wh-label.red { color:#ef4444; }',
    ].join('\n');
    document.head.appendChild(style);

    function render(data) {
        var el = document.getElementById('wh-status');
        if (!el) {
            el = document.createElement('a');
            el.id = 'wh-status';
            el.className = 'wh-status';
            el.href = '/settings#webhook';
            el.title = 'Notion sync status — click to configure';
            var nav = document.querySelector('.nav-links');
            if (nav) nav.parentNode.insertBefore(el, nav);
        }
        var h = data.health || 'disabled';
        var dotCls = h === 'green' ? 'green' : h === 'amber' ? 'amber' : h === 'red' ? 'red' : 'grey';
        var labels = { green: 'Live', amber: 'Stale', red: 'Disconnected', waiting: 'Waiting', disabled: 'Push off' };
        var label = labels[h] || h;
        el.innerHTML = '<span class="wh-dot ' + dotCls + '"></span><span class="wh-label ' + dotCls + '">' + label + '</span>';
    }

    function poll() {
        fetch('/api/webhook/status')
            .then(function(r) { return r.json(); })
            .then(render)
            .catch(function() {});
    }

    // Initial load + poll every 30s
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', poll);
    } else {
        poll();
    }
    setInterval(poll, 30000);
})();
