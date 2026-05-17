/**
 * ELD Admin Manager v2.2 (Final)
 */

window.generatePass = function() {
    const c = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", l = "abcdefghijklmnopqrstuvwxyz", n = "0123456789", s = "!@#$%^&*()_+-=[]{};':\"\\|,.<>/?";
    let p = c[Math.floor(Math.random()*c.length)] + l[Math.floor(Math.random()*l.length)] + n[Math.floor(Math.random()*n.length)] + s[Math.floor(Math.random()*s.length)];
    const all = c + l + n + s;
    while(p.length < 12) p += all[Math.floor(Math.random()*all.length)];
    const final = p.split('').sort(() => 0.5 - Math.random()).join('');
    const el = document.getElementById('new-password');
    if(el) el.value = final;
};

window.loadAll = async function() {
    console.log("[ELD] Syncing Identity Matrix...");
    try {
        const res = await fetch('/admin/users/api', {
            headers: {'Accept': 'application/json'}
        });
        const data = await res.json();
        window.currentUsers = data.users;
        window.eld_role = data.current_role; // Store role for UI checks
        window.renderUsers(data.users, data.current_id, data.current_role);
        window.renderRequests(data.requests);
        if(window.lucide) lucide.createIcons();
    } catch(e) { console.error("[ELD] Sync failed", e); }
};

window.createUser = async function() {
    const u = document.getElementById('new-username').value.trim();
    const e = document.getElementById('new-email').value.trim();
    const p = document.getElementById('new-password').value.trim();
    const r = document.getElementById('new-role').value;
    const st = document.getElementById('create-status');
    
    if(!u || !p) { st.textContent = "Required data missing."; st.style.color = "var(--bad)"; return; }
    st.textContent = "Provisioning..."; st.style.color = "var(--accent)";
    
    try {
        const res = await fetch('/admin/users/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({username:u, email:e, password:p, role:r})
        });
        const data = await res.json();
        if(res.ok) {
            st.textContent = "Success: Identity provisioned."; st.style.color = "var(--good)";
            document.getElementById('new-username').value = '';
            document.getElementById('new-password').value = '';
            window.loadAll();
        } else {
            st.textContent = data.error || "Rejection."; st.style.color = "var(--bad)";
        }
    } catch(err) { st.textContent = "Network error."; st.style.color = "var(--bad)"; }
};

window.renderUsers = function(users, curId, curRole) {
    const c = document.getElementById('users-table-container');
    if(!users || !users.length) { c.innerHTML = '<div class="muted" style="text-align:center; padding:40px;">No managed identities found.</div>'; return; }
    
    let h = '<table style="font-size: 14px;"><thead><tr><th>Identity</th><th>Email</th><th>Created By</th><th>Role</th><th>Date</th><th style="text-align:right;">Actions</th></tr></thead><tbody>';
    users.forEach(u => {
        const canManage = (curRole === 'owner') || (curRole === 'super_admin' && u.role === 'viewer' && u.created_by === curId);
        h += `<tr>
            <td style="padding: 16px 12px;">
                <div style="font-size: 15px; font-weight: 800; color: var(--ink);">${window.escapeHtml(u.username)}</div>
                <div class="muted" style="font-size:11px; margin-top:2px;">ID: ${u.id}</div>
            </td>
            <td><span class="muted" style="font-weight: 500;">${window.escapeHtml(u.email || 'N/A')}</span></td>
            <td><span class="muted">${window.escapeHtml(u.creator_name || 'System')}</span></td>
            <td><span class="pill" style="background:rgba(255,255,255,0.04); border: 1px solid var(--panel-border); font-weight:700; font-size: 11px;">${u.role.toUpperCase()}</span></td>
            <td style="font-family: monospace; font-size: 13px; color: var(--muted);">${u.created_at.split('T')[0]}</td>
            <td style="text-align:right;">
                <div style="display:flex; gap:8px; justify-content:flex-end;">
                    ${canManage ? `
                    <button class="primary" style="padding:8px 16px; font-size:12px; font-weight:700; border-radius:10px;" onclick="window.promptUpdate(${u.id},'${window.escapeHtml(u.username)}')">Modify</button>
                    <button class="danger" style="padding:8px 16px; font-size:12px; font-weight:700; border-radius:10px;" onclick="window.deleteUser(${u.id},'${window.escapeHtml(u.username)}')">Revoke</button>
                    ` : '<span class="muted" style="font-size: 12px; font-weight: 700; opacity: 0.5;">[PROTECTED]</span>'}
                </div>
            </td>
        </tr>`;
    });
    c.innerHTML = h + '</tbody></table>';
};

window.renderRequests = function(rs) {
    const c = document.getElementById('requests-table-container');
    if(!rs || !rs.length) { c.innerHTML = '<div class="muted" style="text-align:center; padding:20px;">No pending recovery requests.</div>'; return; }
    let h = '<table><thead><tr><th>Identity</th><th>Context</th><th>Action</th></tr></thead><tbody>';
    rs.forEach(r => {
        h += `<tr>
            <td><strong>${window.escapeHtml(r.username)}</strong></td>
            <td>${window.escapeHtml(r.message)}</td>
            <td><button class="danger" style="padding:6px 12px; font-size:11px;" onclick="window.clearRequests(${r.id})">Dismiss</button></td>
        </tr>`;
    });
    c.innerHTML = h + '</tbody></table>';
};

window.applyFilters = function() {
    const u = document.getElementById('filter-user').value.toLowerCase();
    const e = document.getElementById('filter-email').value.toLowerCase();
    const r = document.getElementById('filter-role').value;
    document.querySelectorAll('#users-table-container tbody tr').forEach(row => {
        const um = !u || row.children[0].textContent.toLowerCase().includes(u);
        const em = !e || row.children[1].textContent.toLowerCase().includes(e);
        const rm = !r || row.children[3].textContent.toLowerCase().includes(r.replace('_',' '));
        row.style.display = (um && em && rm) ? '' : 'none';
    });
};

window.deleteUser = function(id, name) {
    document.getElementById('delete-user-id').value = id;
    document.getElementById('delete-username').textContent = name;
    document.getElementById('delete-modal').style.display = 'block';
};

window.confirmDelete = async function() {
    await fetch('/admin/users/delete/' + document.getElementById('delete-user-id').value, {
        method: 'POST',
        headers: {'Accept': 'application/json'}
    });
    document.getElementById('delete-modal').style.display = 'none';
    window.loadAll();
};

window.promptUpdate = function(id, name) {
    const u = window.currentUsers.find(user => user.id === id);
    if(!u) return;
    
    document.getElementById('mod-user-id').value = id;
    document.getElementById('mod-username').value = name;
    document.getElementById('mod-email').value = u.email || '';
    document.getElementById('mod-role').value = u.role;
    document.getElementById('mod-password').value = '';
    
    // Hide Super Admin option if current user is Super Admin
    const roleOpt = document.querySelector('#mod-role option[value="super_admin"]');
    if(roleOpt) {
        roleOpt.style.display = (window.eld_role === 'owner') ? 'block' : 'none';
    }
    
    document.getElementById('modify-modal').style.display = 'block';
};

window.submitUpdate = async function() {
    const id = document.getElementById('mod-user-id').value;
    const payload = {
        user_id: id,
        username: document.getElementById('mod-username').value,
        email: document.getElementById('mod-email').value,
        password: document.getElementById('mod-password').value,
        role: document.getElementById('mod-role').value
    };
    await fetch('/admin/users/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        body: JSON.stringify(payload)
    });
    document.getElementById('modify-modal').style.display = 'none';
    window.loadAll();
};

window.clearRequests = async function(id) {
    await fetch('/admin/users/requests/clear' + (id ? '?id=' + id : ''), {method: 'DELETE'});
    window.loadAll();
};

window.escapeHtml = function(v) {
    return String(v).replace(/[&<>"']/g, function(m) {
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#039;"}[m];
    });
};

// Auto-init
if(document.readyState === 'complete') { window.loadAll(); } 
else { window.addEventListener('load', window.loadAll); }
