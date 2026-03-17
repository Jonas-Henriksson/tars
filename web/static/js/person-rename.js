/* Inline person rename — click any .person-editable to rename/merge.
   Shared across briefing, tasks, and people pages. */
(function() {
    var style = document.createElement('style');
    style.textContent = [
        '.person-editable { cursor: pointer; border-bottom: 1px dashed rgba(255,255,255,.15); transition: border-color .15s, color .15s; }',
        '.person-editable:hover { border-bottom-color: var(--accent, #3b82f6); color: var(--accent, #3b82f6); }',
        '.pr-overlay { position:fixed; inset:0; background:rgba(0,0,0,.55); z-index:9000; display:flex; align-items:center; justify-content:center; }',
        '.pr-modal { background:#18181b; border:1px solid #27272a; border-radius:10px; padding:20px 24px; width:340px; max-width:90vw; box-shadow:0 12px 40px rgba(0,0,0,.5); }',
        '.pr-title { font-size:14px; font-weight:600; color:#fafafa; margin-bottom:12px; }',
        '.pr-label { font-size:11px; color:#71717a; margin-bottom:4px; text-transform:uppercase; letter-spacing:.04em; }',
        '.pr-input { width:100%; background:#111113; border:1px solid #27272a; color:#fafafa; font-size:14px; padding:8px 10px; border-radius:6px; font-family:inherit; outline:none; }',
        '.pr-input:focus { border-color:#3b82f6; }',
        '.pr-hint { font-size:11px; color:#71717a; margin-top:6px; }',
        '.pr-hint.merge { color:#fbbf24; }',
        '.pr-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:14px; }',
        '.pr-btn { padding:6px 16px; border-radius:6px; font-size:13px; font-family:inherit; cursor:pointer; border:1px solid transparent; transition: background .15s; }',
        '.pr-btn-cancel { background:transparent; border-color:#27272a; color:#a1a1aa; }',
        '.pr-btn-cancel:hover { background:#27272a; }',
        '.pr-btn-save { background:#3b82f6; color:#fff; }',
        '.pr-btn-save:hover { background:#2563eb; }',
        '.pr-btn-save:disabled { opacity:.4; cursor:not-allowed; }',
    ].join('\n');
    document.head.appendChild(style);

    // Cache of known person names (populated on first open)
    var knownNames = null;

    function fetchNames() {
        return fetch('/api/people').then(function(r) { return r.json(); }).then(function(d) {
            knownNames = Object.keys(d.people || {});
            return knownNames;
        }).catch(function() { return knownNames || []; });
    }

    function showRenameModal(currentName, onDone) {
        // Build modal
        var overlay = document.createElement('div');
        overlay.className = 'pr-overlay';
        var modal = document.createElement('div');
        modal.className = 'pr-modal';
        modal.innerHTML =
            '<div class="pr-title">Rename Person</div>' +
            '<div class="pr-label">Current name</div>' +
            '<div style="font-size:14px;color:#a1a1aa;margin-bottom:10px">' + esc(currentName) + '</div>' +
            '<div class="pr-label">New name</div>' +
            '<input class="pr-input" id="prNewName" value="' + escAttr(currentName) + '" autocomplete="off" spellcheck="false">' +
            '<div class="pr-hint" id="prHint"></div>' +
            '<div class="pr-actions">' +
            '<button class="pr-btn pr-btn-cancel" id="prCancel">Cancel</button>' +
            '<button class="pr-btn pr-btn-save" id="prSave">Rename</button>' +
            '</div>';

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        var input = document.getElementById('prNewName');
        var hint = document.getElementById('prHint');
        var saveBtn = document.getElementById('prSave');

        input.select();
        input.focus();

        // Fetch names to detect merges
        fetchNames().then(function(names) { checkMerge(); });

        function checkMerge() {
            var v = input.value.trim();
            if (!v || v === currentName) {
                hint.textContent = '';
                hint.className = 'pr-hint';
                saveBtn.disabled = !v || v === currentName;
                saveBtn.textContent = 'Rename';
                return;
            }
            // Check if new name exists (case-insensitive)
            var match = (knownNames || []).find(function(n) { return n.toLowerCase() === v.toLowerCase() && n.toLowerCase() !== currentName.toLowerCase(); });
            if (match) {
                hint.textContent = 'Will merge with existing "' + match + '"';
                hint.className = 'pr-hint merge';
                saveBtn.textContent = 'Merge';
            } else {
                hint.textContent = '';
                hint.className = 'pr-hint';
                saveBtn.textContent = 'Rename';
            }
            saveBtn.disabled = false;
        }

        input.addEventListener('input', checkMerge);
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !saveBtn.disabled) doSave();
            if (e.key === 'Escape') close();
        });

        document.getElementById('prCancel').addEventListener('click', close);
        overlay.addEventListener('click', function(e) { if (e.target === overlay) close(); });

        saveBtn.addEventListener('click', doSave);

        function doSave() {
            var newName = input.value.trim();
            if (!newName || newName === currentName) return;
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';

            fetch('/api/people/' + encodeURIComponent(currentName) + '/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_name: newName }),
            })
            .then(function(r) { return r.json(); })
            .then(function(result) {
                if (result.error) {
                    hint.textContent = result.error;
                    hint.className = 'pr-hint merge';
                    saveBtn.disabled = false;
                    saveBtn.textContent = 'Rename';
                    return;
                }
                close();
                // Invalidate cache
                knownNames = null;
                if (onDone) onDone(currentName, newName, result);
            })
            .catch(function(err) {
                hint.textContent = 'Error: ' + err.message;
                hint.className = 'pr-hint merge';
                saveBtn.disabled = false;
                saveBtn.textContent = 'Rename';
            });
        }

        function close() {
            if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        }
    }

    function esc(s) { var el = document.createElement('span'); el.textContent = s; return el.innerHTML; }
    function escAttr(s) { return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;'); }

    // Delegate clicks on .person-editable elements
    document.addEventListener('click', function(e) {
        var el = e.target.closest('.person-editable');
        if (!el) return;
        e.preventDefault();
        e.stopPropagation();
        var name = el.dataset.person || el.textContent.trim();
        if (!name || name === 'Me' || name === 'Unassigned') return;

        showRenameModal(name, function(oldName, newName) {
            // Reload the page to reflect changes everywhere
            location.reload();
        });
    });
})();
