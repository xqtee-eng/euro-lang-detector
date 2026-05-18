/**
 * ELD PRO - Unified Application Logic
 */

// --- Global Utilities ---

function sameOriginAdminTarget(value) {
    try {
        const target = new URL(value || '/admin', window.location.origin);
        if (target.origin === window.location.origin && target.pathname.startsWith('/admin')) {
            return target.pathname + target.search + target.hash;
        }
    } catch (err) {
        // Fall back to the admin dashboard if a stale or malformed target appears.
    }
    return '/admin';
}

function setupCustomSelects() {
    document.querySelectorAll('select:not(.custom-select-hidden)').forEach(select => {
        const wrapper = document.createElement('div');
        wrapper.className = 'custom-select';
        
        const trigger = document.createElement('div');
        trigger.className = 'custom-select-trigger';
        const selectedText = select.options[select.selectedIndex]?.text || 'Select...';
        trigger.innerHTML = `<span>${selectedText}</span><i data-lucide="chevron-down" style="width:16px;"></i>`;
        
        const optionsContainer = document.createElement('div');
        optionsContainer.className = 'custom-select-options';
        
        Array.from(select.options).forEach(opt => {
            const div = document.createElement('div');
            div.className = 'custom-select-option' + (opt.selected ? ' selected' : '');
            div.textContent = opt.text;
            div.onclick = () => {
                select.value = opt.value;
                select.dispatchEvent(new Event('change'));
                trigger.querySelector('span').textContent = opt.text;
                optionsContainer.querySelectorAll('.custom-select-option').forEach(d => d.classList.remove('selected'));
                div.classList.add('selected');
                optionsContainer.style.display = 'none';
            };
            optionsContainer.appendChild(div);
        });
        
        trigger.onclick = (e) => {
            e.stopPropagation();
            const isOpen = optionsContainer.style.display === 'block';
            document.querySelectorAll('.custom-select-options').forEach(o => o.style.display = 'none');
            optionsContainer.style.display = isOpen ? 'none' : 'block';
        };
        
        select.classList.add('custom-select-hidden');
        select.style.display = 'none';
        
        wrapper.appendChild(trigger);
        wrapper.appendChild(optionsContainer);
        select.parentNode.insertBefore(wrapper, select);
    });
    if (window.lucide) lucide.createIcons();
}

document.addEventListener('DOMContentLoaded', () => {
    setupCustomSelects();
    // Close dropdowns on outside click
    document.addEventListener('click', () => {
        document.querySelectorAll('.custom-select-options').forEach(o => o.style.display = 'none');
    });
});

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getConfidenceColor(pct) {
    if (pct > 80) return 'var(--good)';
    if (pct > 50) return 'var(--warn)';
    return 'var(--bad)';
}

// --- Detector Page ---

async function detect() {
    const text = document.getElementById('text').value;
    const resultsArea = document.getElementById('results');
    const meta = document.getElementById('meta');
    
    if (!text.trim()) {
        if (resultsArea) resultsArea.style.display = 'none';
        return;
    }

    if (meta) meta.innerHTML = '<i data-lucide="loader" class="spin" style="width:14px; height:14px; display:inline-block; margin-right:8px;"></i>Detecting...';
    if (window.lucide) lucide.createIcons();

    try {
        const response = await fetch('/detect', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: text, top_k: 5})
        });
        const data = await response.json();
        
        if (resultsArea) resultsArea.style.display = 'block';
        
        const mainLang = (data.language || 'UNKNOWN').toUpperCase();
        const mainName = (window.LANG_NAMES && window.LANG_NAMES[mainLang]) ? window.LANG_NAMES[mainLang] : mainLang;
        
        const langEl = document.getElementById('language-name');
        if (langEl) langEl.textContent = mainName;
        
        const badgeIso = document.getElementById('badge-iso');
        if (badgeIso) badgeIso.textContent = 'ISO: ' + mainLang;
        
        if (meta) {
            meta.innerHTML = `
                <span style="display:inline-flex; align-items:center; gap:6px;"><i data-lucide="database" style="width:12px;"></i> Source: <b>${data.source}</b></span> 
                <span style="opacity:0.4;">&bull;</span>
                <span style="opacity:0.6;">Vector Signature Validated</span>
            `;
        }
        
        if (window.confidenceBar) window.confidenceBar(data.confidence || 0);
        if (window.renderCandidates) window.renderCandidates(data.candidates || []);
        if (window.lucide) lucide.createIcons();
    } catch (e) {
        if (meta) meta.textContent = 'Error during detection.';
        console.error(e);
    }
}

async function analyze() {
    const text = document.getElementById('text').value;
    const meta = document.getElementById('meta');
    const resultsArea = document.getElementById('results');

    if (!text.trim()) return;
    
    if (meta) meta.innerHTML = '<i data-lucide="loader" class="spin" style="width:14px; height:14px; display:inline-block; margin-right:8px;"></i>Analyzing...';
    if (window.lucide) lucide.createIcons();

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: text, top_k: 5})
        });
        const data = await response.json();
        
        if (resultsArea) resultsArea.style.display = 'block';
        
        const mainLang = (data.language || 'MIXED').toUpperCase();
        const mainName = (window.LANG_NAMES && window.LANG_NAMES[mainLang]) ? window.LANG_NAMES[mainLang] : mainLang;
        
        const langEl = document.getElementById('language-name');
        if (langEl) langEl.textContent = mainName + (mainLang !== 'MIXED' ? ' (' + mainLang + ')' : '');

        if (meta) {
            meta.innerHTML = `${data.token_count} words analyzed &bull; ${Math.round((data.coverage || 0) * 100)}% recognized`;
        }
        
        if (window.confidenceBar) window.confidenceBar(data.coverage || 0);
        if (window.renderCandidates && data.language_counts) {
            window.renderCandidates(Object.entries(data.language_counts).map(p => ({language: p[0], confidence: p[1]/data.token_count})));
        }
        if (window.renderTokens) window.renderTokens(data.tokens || []);
        if (window.lucide) lucide.createIcons();
    } catch (e) {
        if (meta) meta.textContent = 'Error during analysis.';
        console.error(e);
    }
}

window.confidenceBar = function(value) {
    const bar = document.getElementById('fill');
    const pctSpan = document.getElementById('confidence-pct');
    const pct = Math.round((Math.max(0, Math.min(1, value || 0)) * 100));
    if (bar) {
        bar.style.width = pct + '%';
        const color = getConfidenceColor(pct);
        bar.style.background = color;
        bar.style.boxShadow = `0 0 20px ${color}44`;
    }
    if (pctSpan) {
        pctSpan.textContent = pct + '%';
        pctSpan.style.color = getConfidenceColor(pct);
    }
};

window.renderCandidates = function(items) {
    const container = document.getElementById('candidates-container');
    const list = document.getElementById('candidates');
    if (!container || !list) return;

    if (!items || items.length < 2) {
        container.style.display = 'none';
        return;
    }
    container.style.display = 'block';
    list.innerHTML = items.slice(1).map(function(item) {
        const pct = item.confidence * 100;
        const score = Number(pct).toFixed(1) + '%';
        const color = getConfidenceColor(pct);
        const langCode = item.language.toUpperCase();
        const langName = (window.LANG_NAMES && window.LANG_NAMES[langCode]) ? window.LANG_NAMES[langCode] : langCode;

        return `
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.01); padding:16px 20px; border-radius:16px; border:none; cursor:default; position:relative; overflow:hidden;">
              <div style="position:absolute; left:0; top:0; height:100%; width:4px; background:${color}; opacity:0.6;"></div>
              <div style="display:flex; flex-direction:column; gap:4px;">
                <span style="font-weight:800; font-size:16px; letter-spacing:-0.01em; color:var(--ink);">${escapeHtml(langName)}</span>
                <div style="display:flex; align-items:center; gap:8px;">
                   <span style="font-size:10px; font-weight:800; color:var(--muted); text-transform:uppercase; letter-spacing:0.1em;">Fingerprint:</span>
                   <span style="font-family:monospace; font-size:10px; color:var(--accent); font-weight:700;">${langCode}</span>
                </div>
              </div>
              <div style="display:flex; align-items:center; gap:20px;">
                <div style="text-align:right;">
                   <div style="font-size:14px; font-weight:800; color:${color}">${score}</div>
                   <div style="font-size:9px; font-weight:800; text-transform:uppercase; color:var(--muted); opacity:0.5; letter-spacing:0.05em;">Probability</div>
                </div>
                <div style="width:40px; height:40px; border-radius:12px; background:${color}15; display:flex; align-items:center; justify-content:center; border:1px solid ${color}33;">
                   <i data-lucide="activity" style="width:16px; height:16px; color:${color}"></i>
                </div>
              </div>
            </div>
        `;
    }).join('');
    if (window.lucide) lucide.createIcons();
};

window.renderTokens = function(tokens) {
    const container = document.getElementById('tokens');
    if (!container) return;

    if (!tokens || tokens.length === 0) {
        container.innerHTML = `<div class="muted" style="text-align:center; padding: 60px 0;">Token-level breakdown will be displayed after identification.</div>`;
        return;
    }
    
    const SOURCE_LABELS = {
        'lexicon': 'Dictionary Match',
        'rule': 'Linguistic Rule',
        'name': 'Proper Name',
        'unknown': 'Probabilistic Model'
    };

    container.innerHTML = tokens.map(function(token) {
        const pct = token.confidence * 100;
        const color = getConfidenceColor(pct);
        const icon = token.source === 'lexicon' ? 'book' : (token.source === 'name' ? 'user' : (token.source === 'rule' ? 'zap' : 'hash'));
        const langCode = token.language.toUpperCase();
        const langName = (window.LANG_NAMES && window.LANG_NAMES[langCode]) ? window.LANG_NAMES[langCode] : langCode;
        const sourceLabel = SOURCE_LABELS[token.source] || token.source.toUpperCase();
        
        return `
            <div class="token" style="background:var(--sidebar-bg); border-radius:18px; margin-bottom:12px; padding:20px; border:1px solid var(--panel-border); transition: none; box-shadow: none;">
              <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                <div style="display:flex; align-items:center; gap:12px;">
                  <div style="width:36px; height:36px; border-radius:10px; background:var(--accent-soft); display:flex; align-items:center; justify-content:center; color:var(--accent);">
                    <i data-lucide="${icon}" style="width:18px; height:18px;"></i>
                  </div>
                  <strong style="font-size:18px; letter-spacing:-0.02em;">${escapeHtml(token.text)}</strong>
                </div>
                <span style="font-size:10px; font-weight:800; text-transform:uppercase; color:${color}; background:${color}15; border:1px solid ${color}33; padding: 4px 10px; border-radius: 8px; letter-spacing:0.05em;">${escapeHtml(langName)}</span>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <div class="muted" style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.03em; opacity:0.7;">
                  ${escapeHtml(sourceLabel)}
                </div>
                <div style="font-size:11px; font-weight:800; color:${color}; opacity:0.8;">
                  ${Math.round(token.confidence * 100)}% RELIABILITY
                </div>
              </div>
            </div>
        `;
    }).join('');
    if (window.lucide) lucide.createIcons();
};

async function sendFeedback() {
    const lang = document.getElementById('feedbackLang').value.trim().toLowerCase();
    const text = document.getElementById('text').value;
    const status = document.getElementById('feedbackStatus');
    if (!lang || !text || !status) return;
    
    try {
        const response = await fetch('/feedback', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: text, lang: lang})
        });
        const data = await response.json();
        status.textContent = data.ok ? 'Feedback saved! Model will improve after retraining.' : (data.error || 'Error.');
        status.style.color = data.ok ? 'var(--good)' : 'var(--bad)';
    } catch (e) {
        status.textContent = 'Network error.';
        console.error(e);
    }
}

function sample(value) {
    const el = document.getElementById('text');
    if (el) {
        el.value = value;
        detect();
    }
}

// --- Admin Dashboard & Background Tasks ---

let _taskInterval = null;

function pollTaskStatus() {
    if (_taskInterval) return;
    _taskInterval = setInterval(async () => {
        try {
            const res = await fetch('/admin/status/task');
            if (!res.ok) return;
            const data = await res.json();
            const status = document.getElementById('action-status');
            
            if (data.running) {
                if (status) {
                    status.innerHTML = `<i data-lucide="refresh-cw" class="spin" style="width:14px; margin-right:8px;"></i> BACKGROUND TASK ACTIVE: <b>${data.last_action.toUpperCase()}ING...</b>`;
                    if (window.lucide) lucide.createIcons();
                }
                // Disable control buttons while task is running
                document.querySelectorAll('.panel button').forEach(b => {
                    if (b.onclick && b.onclick.toString().includes('runAdminAction')) b.disabled = true;
                });
            } else {
                if (status && status.innerHTML.includes('BACKGROUND')) {
                    if (data.error) {
                        status.innerHTML = `<span style="color:var(--bad)"><i data-lucide="alert-circle" style="width:14px;"></i> Task failed: ${data.error}</span>`;
                    } else {
                        status.innerHTML = `<span style="color:var(--good)"><i data-lucide="check-circle" style="width:14px;"></i> ${data.last_action.toUpperCase()} completed successfully.</span>`;
                    }
                    if (window.lucide) lucide.createIcons();
                }
                document.querySelectorAll('.panel button').forEach(b => b.disabled = false);
                clearInterval(_taskInterval);
                _taskInterval = null;
            }
        } catch (e) {
            clearInterval(_taskInterval);
            _taskInterval = null;
        }
    }, 2000);
}

async function runAdminAction(path) {
    const status = document.getElementById('action-status');
    const output = document.getElementById('action-output');
    if (!status) return;
    
    status.textContent = 'Initiating request...';
    if (output) {
        output.textContent = '';
        output.style.display = 'none';
    }
    
    try {
        const response = await fetch(path, {method: 'POST'});
        const data = await response.json();
        
        if (data.ok) {
            status.textContent = data.message || 'Action started.';
            if (path.includes('train') || path.includes('rebuild')) {
                pollTaskStatus();
            }
        } else {
            status.textContent = data.error || 'Request rejected.';
            status.style.color = 'var(--bad)';
        }
    } catch (e) {
        status.textContent = 'Network protocol error.';
        console.error(e);
    }
}

// --- Logs Page ---

function formatLogLine(line) {
    if (!line) return '';
    let color = 'var(--muted)';
    if (line.includes(' INFO ')) color = 'var(--good)';
    else if (line.includes(' WARN ')) color = 'var(--warn)';
    else if (line.includes(' ERROR ')) color = 'var(--bad)';
    
    const formatted = line.replace(/ (INFO|WARN|ERROR) /, (match) => {
        return ` <span style="color:${color}; font-weight:800; background:rgba(255,255,255,0.05); padding:2px 6px; border-radius:4px; font-size:10px;">${match.trim()}</span> `;
    });
    return `<div style="margin-bottom:6px; border-bottom:1px solid var(--panel-border); padding-bottom:6px; white-space:pre-wrap; opacity:0.9;">${formatted}</div>`;
}

async function loadLogs() {
    const container = document.getElementById('log-content');
    if (!container) return;
    
    try {
        const response = await fetch('/admin/logs/raw');
        const data = await response.json();
        const lines = data.lines || [];
        const isAtBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 50;
        container.innerHTML = lines.map(formatLogLine).join('');
        if (isAtBottom) container.scrollTop = container.scrollHeight;
    } catch (e) { console.error(e); }
}

// --- Lexicon & Names Manager ---

async function loadLexicon() {
    const searchEl = document.getElementById('search');
    const container = document.getElementById('lexicon');
    if (!container || !searchEl) return;
    
    const query = encodeURIComponent(searchEl.value.trim());
    try {
        const response = await fetch('/admin/lexicon/entries?query=' + query);
        const data = await response.json();
        
        if (!data.entries || !data.entries.length) {
            container.innerHTML = '<div class="empty" style="padding:60px;">No matching lexicon entries found.</div>';
            return;
        }

        const rows = data.entries.map(function(item) {
            const flags = item.ambiguous ? `<span class="pill warn" style="font-size:10px;">ambiguous: ${item.languages.map(escapeHtml).join(', ')}</span>` : '';
            return `
                <tr>
                  <td style="font-weight:700; color:var(--accent);">${escapeHtml(item.word)}</td>
                  <td><span class="pill">${escapeHtml(item.language)}</span></td>
                  <td>${item.frequency}</td>
                  <td>${flags}</td>
                  <td style="text-align:right;">
                    <button class="danger" onclick="deleteWord(${JSON.stringify(item.language).replaceAll('"', '&quot;')}, ${JSON.stringify(item.word).replaceAll('"', '&quot;')})" style="padding:6px 12px; font-size:11px;">Delete</button>
                  </td>
                </tr>
            `;
        }).join('');
        
        container.innerHTML = `
          <div class="table-container">
          <table style="width:100%; border-collapse:collapse;">
            <thead>
              <tr style="border-bottom: 2px solid var(--panel-border);">
                <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Word</th>
                <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Language</th>
                <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Freq</th>
                <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Status</th>
                <th style="text-align:right; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Actions</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
          </div>
        `;
    } catch (e) { console.error(e); }
}

async function addWord() {
    const lang = document.getElementById('lang').value;
    const word = document.getElementById('word').value.trim();
    const status = document.getElementById('status');
    
    try {
        const response = await fetch('/admin/lexicon/items', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                lang: lang,
                word: word,
                frequency: Number(document.getElementById('frequency').value || 1),
                notes: document.getElementById('notes').value.trim()
            })
        });
        const data = await response.json();
        if (status) status.textContent = data.message || data.error || 'Saved.';
        if (response.ok) {
            document.getElementById('word').value = '';
            await loadLexicon();
        }
    } catch (e) { console.error(e); }
}

async function analyzeWord() {
    const wordInput = document.getElementById('word').value.trim() || document.getElementById('search').value.trim();
    const container = document.getElementById('word-analysis-container');
    if (!wordInput || !container) return;
    
    container.innerHTML = '<div class="muted" style="text-align:center; padding:40px;"><i data-lucide="loader" class="spin"></i><br>Analyzing word semantics...</div>';
    if (window.lucide) lucide.createIcons();

    try {
        const response = await fetch('/admin/words/analyze?word=' + encodeURIComponent(wordInput));
        const data = await response.json();
        
        let html = `
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:16px;">
            <div style="background:var(--sidebar-bg); padding:16px; border-radius:16px; border:1px solid var(--panel-border);">
              <div style="font-size:10px; font-weight:800; text-transform:uppercase; color:var(--muted); margin-bottom:4px;">Word Status</div>
              <div style="font-weight:800; font-size:16px; color:${data.known ? 'var(--good)' : 'var(--bad)'}">${data.known ? 'KNOWN TERM' : 'UNKNOWN'}</div>
            </div>
            <div style="background:var(--sidebar-bg); padding:16px; border-radius:16px; border:1px solid var(--panel-border);">
              <div style="font-size:10px; font-weight:800; text-transform:uppercase; color:var(--muted); margin-bottom:4px;">Ambiguity</div>
              <div style="font-weight:800; font-size:16px; color:${data.ambiguous ? 'var(--warn)' : 'var(--good)'}">${data.ambiguous ? 'AMBIGUOUS' : 'UNIQUE'}</div>
            </div>
            <div style="background:var(--sidebar-bg); padding:16px; border-radius:16px; border:1px solid var(--panel-border);">
              <div style="font-size:10px; font-weight:800; text-transform:uppercase; color:var(--muted); margin-bottom:4px;">Languages</div>
              <div style="font-weight:800; font-size:16px; color:var(--accent);">${data.languages.length ? data.languages.join(', ').toUpperCase() : 'NONE'}</div>
            </div>
          </div>
        `;
        
        if (data.entries && data.entries.length) {
          html += '<div style="margin-top:16px; font-size:11px; font-weight:800; text-transform:uppercase; color:var(--muted); letter-spacing:0.1em;">Lexical Mapping</div>';
          data.entries.forEach(e => {
            html += `
              <div style="background:rgba(255,255,255,0.02); padding:12px 20px; border-radius:12px; border:1px solid var(--panel-border); display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:700;">${e.language.toUpperCase()}</span>
                <span class="muted">Frequency: <b>${e.frequency}</b></span>
                <span style="font-size:10px; opacity:0.6;">${e.source.toUpperCase()}</span>
              </div>
            `;
          });
        }
        
        container.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (e) { console.error(e); }
}

async function deleteWord(lang, word) {
    if (!confirm(`Delete ${word} from ${lang}?`)) return;
    try {
        await fetch('/admin/lexicon/items', {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({lang: lang, word: word})
        });
        await loadLexicon();
    } catch (e) { console.error(e); }
}

async function loadNames() {
    const searchEl = document.getElementById('search');
    const container = document.getElementById('names');
    if (!container || !searchEl) return;
    
    const query = encodeURIComponent(searchEl.value.trim());
    try {
        const response = await fetch('/admin/names/items?query=' + query);
        const data = await response.json();
        
        if (!data.names || !data.names.length) {
            container.innerHTML = '<div class="empty" style="padding:60px;">No registered entities found.</div>';
            return;
        }

        const rows = data.names.map(function(item) {
            return `
                <tr>
                  <td style="font-weight:700; color:var(--accent);">${escapeHtml(item.name)}</td>
                  <td><span class="pill">${escapeHtml(item.language)}</span></td>
                  <td>${escapeHtml(item.country || 'Global')}</td>
                  <td style="text-transform:capitalize;">${escapeHtml(item.name_type || 'person')}</td>
                  <td><div style="display:flex; align-items:center; gap:8px;"><div style="width:40px; height:4px; background:rgba(0,0,0,0.1); border-radius:2px;"><div style="width:${item.confidence * 100}%; height:100%; background:var(--accent); border-radius:2px;"></div></div> ${item.confidence}</div></td>
                  <td style="text-align:right;">
                    <button class="danger" onclick="deleteName(${JSON.stringify(item.name).replaceAll('"', '&quot;')}, ${JSON.stringify(item.language).replaceAll('"', '&quot;')})" style="padding:6px 12px; font-size:11px;">Remove</button>
                  </td>
                </tr>
            `;
        }).join('');

        container.innerHTML = `
          <div class="table-container">
          <table style="width:100%; border-collapse:collapse;">
            <thead>
              <tr style="border-bottom: 2px solid var(--panel-border);">
                <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Entity</th>
                <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Language</th>
                <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Origin</th>
                <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Type</th>
                <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Confidence</th>
                <th style="text-align:right; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Actions</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
          </div>
        `;
    } catch (e) { console.error(e); }
}

async function addName() {
    const payload = {
        lang: document.getElementById('lang').value,
        name: document.getElementById('name').value.trim(),
        country: document.getElementById('country').value.trim(),
        name_type: document.getElementById('name_type').value.trim() || 'person',
        confidence: Number(document.getElementById('confidence').value || 0.9)
    };
    const status = document.getElementById('status');
    try {
        const response = await fetch('/admin/names/items', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (status) status.textContent = data.message || data.error || 'Saved.';
        if (response.ok) {
            document.getElementById('name').value = '';
            await loadNames();
        }
    } catch (e) { console.error(e); }
}

async function deleteName(name, lang) {
    if (!confirm(`Delete ${name} from ${lang}?`)) return;
    try {
        await fetch('/admin/names/items', {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, lang: lang})
        });
        await loadNames();
    } catch (e) { console.error(e); }
}

async function analyzeName() {
    const nameInput = document.getElementById('name').value.trim() || document.getElementById('search').value.trim();
    const container = document.getElementById('name-analysis-container');
    if (!nameInput || !container) return;
    
    container.innerHTML = '<div class="muted" style="text-align:center; padding:40px;"><i data-lucide="loader" class="spin"></i><br>Evaluating identity markers...</div>';
    if (window.lucide) lucide.createIcons();

    try {
        const response = await fetch('/admin/names/analyze?name=' + encodeURIComponent(nameInput));
        const data = await response.json();
        
        container.innerHTML = `
          <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:16px;">
            <div style="background:var(--sidebar-bg); padding:16px; border-radius:16px; border:1px solid var(--panel-border);">
              <div style="font-size:10px; font-weight:800; text-transform:uppercase; color:var(--muted); margin-bottom:4px;">Classification</div>
              <div style="font-weight:800; font-size:16px; color:var(--accent);">${data.language.toUpperCase()}</div>
            </div>
            <div style="background:var(--sidebar-bg); padding:16px; border-radius:16px; border:1px solid var(--panel-border);">
              <div style="font-size:10px; font-weight:800; text-transform:uppercase; color:var(--muted); margin-bottom:4px;">Entity Type</div>
              <div style="font-weight:800; font-size:16px; color:var(--ink);">${data.entity_type.replace('_', ' ').toUpperCase()}</div>
            </div>
            <div style="background:var(--sidebar-bg); padding:16px; border-radius:16px; border:1px solid var(--panel-border);">
              <div style="font-size:10px; font-weight:800; text-transform:uppercase; color:var(--muted); margin-bottom:4px;">Engine Source</div>
              <div style="font-weight:800; font-size:16px; color:var(--muted);">${data.source.toUpperCase()}</div>
            </div>
          </div>
          
          <div style="background:rgba(255,255,255,0.02); padding:20px; border-radius:16px; border:1px solid var(--panel-border); display:flex; align-items:center; gap:16px; margin-top:16px;">
             <div style="width:48px; height:48px; background:rgba(59, 130, 246, 0.1); border-radius:14px; display:flex; align-items:center; justify-content:center; color:var(--accent);">
                <i data-lucide="shield-check" style="width:24px;"></i>
             </div>
             <div>
                <div style="font-size:11px; font-weight:800; text-transform:uppercase; color:var(--muted); letter-spacing:0.05em;">Diagnostic Message</div>
                <div style="font-weight:600; font-size:14px;">The entity "${escapeHtml(data.text)}" is indexed as part of the ${data.language} linguistic domain.</div>
             </div>
          </div>
        `;
        if (window.lucide) lucide.createIcons();
    } catch (e) { console.error(e); }
}

async function loadCorpus() {
    const container = document.getElementById('corpus-list');
    if (!container) return;
    try {
        const res = await fetch('/corpus/files');
        const data = await res.json();
        const files = data.files || [];
        container.innerHTML = '<div class="table-container"><table><thead><tr><th>Language</th><th>Size</th><th>Lines</th><th>Quality</th></tr></thead><tbody>' + 
          files.map(f => `<tr><td><b>${f.lang.toUpperCase()}</b></td><td>${f.size_kb} KB</td><td>${f.lines}</td><td><span class="pill good">OK</span></td></tr>`).join('') + 
          '</tbody></table></div>';
        if (window.lucide) lucide.createIcons();
    } catch (e) { console.error(e); }
}

async function loadQuality() {
    const container = document.getElementById('quality-stats');
    const ambContainer = document.getElementById('ambiguity-stats');
    if (!container) return;
    try {
        const res = await fetch('/admin/quality.json');
        const data = await res.json();
        
        // Match src/data_quality.py structure
        const dataset = data.dataset || {};
        const train = data.train || {};
        const test = data.test || {};
        const benchmark = data.benchmark || {};
        
        container.innerHTML = `
          <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap:16px;">
            <div style="background:var(--solid-input-bg); padding:16px; border-radius:12px; border:1px solid var(--panel-border);">
              <div class="muted" style="font-size:10px; font-weight:800; text-transform:uppercase; margin-bottom:4px;">Dataset Rows</div>
              <div style="font-weight:800; font-size:20px;">${(dataset.total_rows || 0).toLocaleString()}</div>
            </div>
            <div style="background:var(--solid-input-bg); padding:16px; border-radius:12px; border:1px solid var(--panel-border);">
              <div class="muted" style="font-size:10px; font-weight:800; text-transform:uppercase; margin-bottom:4px;">Accuracy</div>
              <div style="font-weight:800; font-size:20px; color:var(--good);">${((benchmark.accuracy || 0) * 100).toFixed(1)}%</div>
            </div>
            <div style="background:var(--solid-input-bg); padding:16px; border-radius:12px; border:1px solid var(--panel-border);">
              <div class="muted" style="font-size:10px; font-weight:800; text-transform:uppercase; margin-bottom:4px;">Train/Test</div>
              <div style="font-weight:700; font-size:14px;">${(train.total_rows || 0).toLocaleString()} / ${(test.total_rows || 0).toLocaleString()}</div>
            </div>
          </div>
        `;
        
        if (ambContainer) {
            const cats = benchmark.by_category || {};
            const ambStats = cats["ambiguous_word"] || {samples: 0, correct: 0};
            if (ambStats.samples > 0) {
                ambContainer.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:12px; background:rgba(249,115,22,0.05); border-radius:10px; border:1px solid rgba(249,115,22,0.1);">
                        <span style="font-weight:700;">Ambiguous Words Test</span>
                        <span class="pill ${ambStats.correct < ambStats.samples ? 'bad' : 'good'}" style="font-size:11px;">${ambStats.correct}/${ambStats.samples} Correct</span>
                    </div>
                `;
            } else {
                ambContainer.innerHTML = `<div class="muted" style="text-align:center; padding:20px; font-size:13px;">No critical ambiguity detected in current samples.</div>`;
            }
        }
    } catch (e) { 
        console.error(e);
        container.innerHTML = `<div class="pill bad">Failed to load quality metrics.</div>`;
    }
}

async function updateSidebarStats() {
    const lex = document.getElementById('stat-lexicon');
    const nam = document.getElementById('stat-names');
    const dbs = document.getElementById('stat-db');
    if (!lex && !nam && !dbs) return;
    
    try {
        const res = await fetch('/admin/stats');
        const data = await res.json();
        if (lex) lex.textContent = data.summary.lexicon_words || 0;
        if (nam) nam.textContent = data.summary.name_hints || 0;
        if (dbs) {
            const bytes = data.files.database.size_bytes || 0;
            const mb = (bytes / (1024 * 1024)).toFixed(2);
            dbs.textContent = mb + ' MB';
        }
    } catch (e) { console.error(e); }
}

// --- Auth Logic ---

window.handleLogin = async function(e) {
    e.preventDefault();
    const form = e.target;
    const status = document.getElementById('auth-status');
    if (!status) return;
    
    status.textContent = 'Authenticating...';
    status.style.color = 'var(--accent)';
    
    const formData = new FormData(form);
    try {
        const res = await fetch(form.action, {
            method: 'POST',
            headers: {'Accept': 'application/json'},
            body: formData
        });
        
        if (res.ok) {
            const data = await res.json();
            window.location.href = sameOriginAdminTarget(data.next || formData.get('next'));
        } else {
            const data = await res.json();
            status.textContent = data.error || 'Login failed.';
            status.style.color = 'var(--bad)';
            form.classList.add('shake');
            setTimeout(() => form.classList.remove('shake'), 400);
        }
    } catch (err) {
        status.textContent = "Network error.";
        status.style.color = "var(--bad)";
    }
};

window.togglePass = function(show) {
    const pass = document.getElementById('admin-pass');
    if (!pass) return;
    pass.type = show ? 'text' : 'password';
    const open = document.getElementById('eye-open');
    const closed = document.getElementById('eye-closed');
    if (open) open.style.display = show ? 'block' : 'none';
    if (closed) closed.style.display = show ? 'none' : 'block';
};

window.toggleForget = function(show) {
    const login = document.getElementById('login-form');
    const forget = document.getElementById('forget-form');
    const status = document.getElementById('auth-status');
    if (!login || !forget) return;
    
    if (show) {
        const u = document.getElementById('forget-username');
        const m = document.getElementById('forget-message');
        if (u) u.value = '';
        if (m) m.value = '';
        if (status) status.textContent = '';
        
        login.style.opacity = '0';
        login.style.transform = 'translateY(-15px)';
        setTimeout(() => {
            login.style.display = 'none';
            forget.style.display = 'flex';
            setTimeout(() => {
                forget.style.opacity = '1';
                forget.style.transform = 'translateY(0)';
            }, 50);
        }, 400);
    } else {
        forget.style.opacity = '0';
        forget.style.transform = 'translateY(15px)';
        if (status) status.textContent = '';
        setTimeout(() => {
            forget.style.display = 'none';
            login.style.display = 'flex';
            setTimeout(() => {
                login.style.opacity = '1';
                login.style.transform = 'translateY(0)';
            }, 50);
        }, 400);
    }
};

window.requestReset = async function() {
    const uEl = document.getElementById('forget-username');
    const mEl = document.getElementById('forget-message');
    const status = document.getElementById('auth-status');
    if (!uEl || !mEl || !status) return;
    
    const u = uEl.value;
    const m = mEl.value;
    if(!u || !m) return;
    
    try {
        const res = await fetch('/admin/forget-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: u, message: m})
        });
        if(res.ok) {
            status.style.color = 'var(--good)';
            status.textContent = 'Request sent. Please wait for the owner.';
            setTimeout(() => window.toggleForget(false), 2000);
        } else {
            const data = await res.json();
            status.style.color = 'var(--bad)';
            status.textContent = data.error || 'Recovery request failed.';
        }
    } catch (err) {
        status.textContent = "Network error.";
        status.style.color = "var(--bad)";
    }
};

async function downloadBackup() {
    const status = document.getElementById('action-status');
    if (!status) return;
    status.innerHTML = '<div style="display:flex; align-items:center; gap:8px;"><i data-lucide="refresh-cw" class="spin" style="width:14px; height:14px;"></i> <span>Preparing JSON package...</span></div>';
    if (window.lucide) lucide.createIcons();
    
    try {
        const res = await fetch('/admin/actions/backup');
        if (!res.ok) throw new Error("Server error: " + res.status);
        
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const date = new Date().toISOString().split('T')[0];
        a.download = 'eld_pro_backup_' + date + '.json';
        document.body.appendChild(a);
        a.click();
        
        setTimeout(() => { 
            window.URL.revokeObjectURL(url); 
            document.body.removeChild(a); 
        }, 100);
        
        status.innerHTML = '<div style="display:flex; align-items:center; gap:8px; color:var(--good);"><i data-lucide="check-circle" style="width:14px; height:14px;"></i> <span>Backup downloaded successfully.</span></div>';
    } catch(e) {
        status.innerHTML = '<div style="display:flex; align-items:center; gap:8px; color:var(--bad);"><i data-lucide="alert-circle" style="width:14px; height:14px;"></i> <span>Failed: ' + e.message + '</span></div>';
    }
    if (window.lucide) lucide.createIcons();
}

let _restorePending = false;
async function uploadRestore(input) {
    if (!input.files || !input.files[0]) return;
    const status = document.getElementById('action-status');
    
    if (!_restorePending) {
        if (status) status.innerHTML = '<div style="color:var(--orange); font-weight:800; cursor:pointer;" onclick="document.getElementById(\'restore-file\').dispatchEvent(new Event(\'change\'))">Click here again to CONFIRM OVERWRITE</div>';
        _restorePending = true;
        return;
    }
    _restorePending = false;

    const reader = new FileReader();
    reader.onload = async (e) => {
        try {
            const data = JSON.parse(e.target.result);
            if (status) {
                status.innerHTML = '<div style="display:flex; align-items:center; gap:8px;"><i data-lucide="refresh-cw" class="spin" style="width:14px; height:14px;"></i> <span>Restoring data...</span></div>';
                if (window.lucide) lucide.createIcons();
            }
            
            const res = await fetch('/admin/actions/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data })
            });
            const json = await res.json();
            if (json.ok) { 
                if (status) status.innerHTML = '<div style="color:var(--good); font-weight:800;">RESTORATION SUCCESSFUL. Reloading...</div>';
                setTimeout(() => window.location.reload(), 1500);
            } else { 
                if (status) status.innerHTML = '<div style="display:flex; align-items:center; gap:8px; color:var(--bad);"><i data-lucide="alert-circle" style="width:14px; height:14px;"></i> <span>Restore failed: ' + json.error + '</span></div>';
            }
        } catch(err) { 
             if (status) status.innerHTML = '<div style="color:var(--bad);">Invalid JSON format.</div>';
        }
    };
    reader.readAsText(input.files[0]);
}

let _wipeConfirmations = {};
async function runWipeAction(target) {
    const status = document.getElementById('action-status');
    if (!status) return;

    if (!_wipeConfirmations[target]) {
        status.innerHTML = `<div style="color:var(--orange); font-weight:800; cursor:pointer;" onclick="runWipeAction('${target}')">⚠️ CLICK AGAIN TO CONFIRM PURGE: ${target.toUpperCase()}</div>`;
        _wipeConfirmations[target] = true;
        return;
    }
    delete _wipeConfirmations[target];

    status.innerHTML = '<div style="display:flex; align-items:center; gap:8px;"><i data-lucide="trash-2" style="width:14px; height:14px;"></i> <span>Purging records...</span></div>';
    if (window.lucide) lucide.createIcons();
    
    try {
        const res = await fetch('/admin/actions/wipe/' + target, { method: 'POST' });
        const json = await res.json();
        if (json.ok) { 
            status.innerHTML = '<div style="color:var(--good); font-weight:800;">PURGE COMPLETE.</div>';
            setTimeout(() => window.location.reload(), 1000);
        } else { 
            status.innerHTML = '<div style="display:flex; align-items:center; gap:8px; color:var(--bad);"><i data-lucide="alert-circle" style="width:14px; height:14px;"></i> <span>Wipe failed: ' + json.error + '</span></div>';
        }
    } catch(e) { 
        status.innerHTML = '<div style="display:flex; align-items:center; gap:8px; color:var(--bad);"><i data-lucide="alert-circle" style="width:14px; height:14px;"></i> <span>Network error.</span></div>'; 
    }
}

function promoteUnknown(text) {
    let modal = document.getElementById('promote-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'promote-modal';
        modal.innerHTML = `
        <div style="position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:9999; display:flex; align-items:center; justify-content:center; backdrop-filter: blur(10px);">
            <div class="panel" style="max-width: 400px; width: 90%; background: var(--panel-bg); border: 1px solid var(--panel-border); border-radius: 24px; padding: 32px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);">
                <h3 style="margin-top: 0; display:flex; align-items:center; gap:8px;"><i data-lucide="plus-circle" style="color:var(--accent);"></i> Promote to Lexicon</h3>
                <p class="muted" style="margin-bottom: 24px; font-size: 13px;">Assign a language code to this unknown pattern so the engine learns it.</p>
                <div style="background: rgba(0,0,0,0.2); padding: 16px; border-radius: 12px; margin-bottom: 24px; font-family: monospace; font-size: 12px; color: var(--ink); word-break: break-all; max-height: 120px; overflow-y: auto; border: 1px solid rgba(255,255,255,0.05);">
                    <strong id="promote-text-display"></strong>
                </div>
                <input type="text" id="promote-lang-input" placeholder="Language code (e.g. uk, en, fr)" style="width: 100%; margin-bottom: 24px; height: 48px; font-size: 14px; text-align: center;" autocomplete="off">
                <div style="display: flex; gap: 12px; justify-content: flex-end;">
                    <button id="promote-cancel-btn" style="border-radius: 12px; height: 44px; padding: 0 20px;">Cancel</button>
                    <button class="primary" id="promote-confirm-btn" style="border-radius: 12px; height: 44px; padding: 0 20px;">Add to Lexicon</button>
                </div>
            </div>
        </div>
        `;
        document.body.appendChild(modal);
        if (window.lucide) lucide.createIcons();
    }
    
    document.getElementById('promote-text-display').textContent = text;
    const input = document.getElementById('promote-lang-input');
    input.value = '';
    modal.style.display = 'flex';
    input.focus();
    
    document.getElementById('promote-cancel-btn').onclick = () => {
        modal.style.display = 'none';
    };
    
    document.getElementById('promote-confirm-btn').onclick = async () => {
        const lang = input.value.toLowerCase().trim();
        if (!lang) return;
        
        const btn = document.getElementById('promote-confirm-btn');
        btn.disabled = true;
        btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Adding...';
        
        try {
            const res = await fetch('/admin/actions/learning/promote', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text: text, lang: lang})
            });
            const data = await res.json();
            if (data.ok) {
                window.location.reload();
            } else {
                alert("Error: " + data.error);
                btn.disabled = false;
                btn.textContent = 'Add to Lexicon';
            }
        } catch (e) {
            console.error(e);
            alert("Network error");
            btn.disabled = false;
            btn.textContent = 'Add to Lexicon';
        }
    };
}

function dismissUnknown(text) {
    let modal = document.getElementById('dismiss-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'dismiss-modal';
        modal.innerHTML = `
        <div style="position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:9999; display:flex; align-items:center; justify-content:center; backdrop-filter: blur(10px);">
            <div class="panel" style="max-width: 400px; width: 90%; background: var(--panel-bg); border: 1px solid var(--panel-border); border-radius: 24px; padding: 32px; box-shadow: 0 25px 50px -12px rgba(244,63,94,0.1);">
                <h3 style="margin-top: 0; color: var(--bad); display:flex; align-items:center; gap:8px;"><i data-lucide="trash-2"></i> Dismiss Unknown</h3>
                <p class="muted" style="margin-bottom: 24px; font-size: 13px;">Are you sure you want to dismiss this item? It will be permanently removed from the learning queue.</p>
                <div style="background: rgba(0,0,0,0.2); padding: 16px; border-radius: 12px; margin-bottom: 24px; font-family: monospace; font-size: 12px; color: var(--ink); word-break: break-all; max-height: 120px; overflow-y: auto; border: 1px solid rgba(255,255,255,0.05);">
                    <strong id="dismiss-text-display"></strong>
                </div>
                <div style="display: flex; gap: 12px; justify-content: flex-end;">
                    <button id="dismiss-cancel-btn" style="border-radius: 12px; height: 44px; padding: 0 20px;">Cancel</button>
                    <button class="danger" id="dismiss-confirm-btn" style="border-radius: 12px; height: 44px; padding: 0 20px; background: var(--bad); color: white; border: none;">Dismiss</button>
                </div>
            </div>
        </div>
        `;
        document.body.appendChild(modal);
        if (window.lucide) lucide.createIcons();
    }
    
    document.getElementById('dismiss-text-display').textContent = text;
    modal.style.display = 'flex';
    
    document.getElementById('dismiss-cancel-btn').onclick = () => {
        modal.style.display = 'none';
    };
    
    document.getElementById('dismiss-confirm-btn').onclick = async () => {
        const btn = document.getElementById('dismiss-confirm-btn');
        btn.disabled = true;
        btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Removing...';
        
        try {
            const res = await fetch('/admin/actions/learning/dismiss', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text: text})
            });
            const data = await res.json();
            if (data.ok) {
                window.location.reload();
            } else {
                alert("Error: " + data.error);
                btn.disabled = false;
                btn.textContent = 'Dismiss';
            }
        } catch (e) {
            console.error(e);
            alert("Network error");
            btn.disabled = false;
            btn.textContent = 'Dismiss';
        }
    };
}

window.promoteUnknown = promoteUnknown;
window.dismissUnknown = dismissUnknown;

window.downloadBackup = downloadBackup;
window.uploadRestore = uploadRestore;
window.runWipeAction = runWipeAction;

// --- Lifecycle ---

document.addEventListener('DOMContentLoaded', function() {
    if (window.lucide) {
        lucide.createIcons();
    }


    if (document.getElementById('lexicon')) loadLexicon();
    if (document.getElementById('names')) loadNames();
    if (document.getElementById('corpus-list')) loadCorpus();
    if (document.getElementById('quality-stats')) loadQuality();
    if (document.getElementById('stat-lexicon')) {
        updateSidebarStats();
        setInterval(updateSidebarStats, 10000);
    }
    if (document.getElementById('log-content')) {
        loadLogs();
        setInterval(loadLogs, 4000);
    }
    // Start polling in case a task is running in background
    pollTaskStatus();
});
