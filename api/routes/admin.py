import random
import string
from flask import Blueprint, request, jsonify, session, redirect
from api.utils import (
    page, admin_required, super_admin_required, owner_required, 
    admin_authenticated, wants_json_response, is_valid_credentials,
    language_options, SERVER_RUN_ID
)
from src.storage import (
    get_user_by_username, verify_user, create_password_request,
    list_users, add_user, update_user, delete_user,
    list_forgot_passwords, clear_forgot_passwords
)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/admin/login", methods=["GET"])
def login_form():
    if admin_authenticated():
        return redirect(request.args.get("next", "/admin"))
    body = f"""
    <div style="max-width: 400px; margin: 100px auto;">
      <div class="panel" style="text-align:center;">
        <i data-lucide="lock" style="width:48px; height:48px; margin-bottom:16px; color:var(--accent);"></i>
        <h2 style="border:0; margin-bottom:24px;">Admin Access</h2>
        
        <form id="login-form" action="/admin/login" method="POST" onsubmit="handleLogin(event)" style="display:flex; flex-direction:column; gap:16px; transition: all 0.6s ease-out; opacity:1;" autocomplete="off">
          <input type="text" name="username" placeholder="Username" autofocus required style="text-align:center; font-size:16px; height: 56px; padding: 0 40px;" autocomplete="off" onpaste="return false;" oncontextmenu="return false;">
          
          <div style="position: relative; display: flex; align-items: center;">
            <input type="password" id="admin-pass" name="password" placeholder="Password" required style="text-align:center; font-size:16px; width: 100%; padding: 0 40px; height: 56px;" autocomplete="new-password" onpaste="return false;" oncontextmenu="return false;">
            <button type="button" style="position: absolute; right: 12px; background: none; border: none; cursor: pointer; color: var(--muted); padding: 0; display: flex; align-items: center; box-shadow: none;" onmousedown="togglePass(true)" onmouseup="togglePass(false)" onmouseleave="togglePass(false)" ontouchstart="togglePass(true)" ontouchend="togglePass(false)">
              <i id="eye-closed" data-lucide="eye-off" style="width: 20px; height: 20px; display: block;"></i>
              <i id="eye-open" data-lucide="eye" style="width: 20px; height: 20px; display: none;"></i>
            </button>
          </div>

          <input type="hidden" name="next" value="{request.args.get("next", "/admin")}">
          <button type="submit" class="primary" style="justify-content:center;">Unlock System</button>
          <a href="#" onclick="toggleForget(true)" style="font-size:12px; color:var(--muted); text-decoration:none; margin-top:8px;">Forget password?</a>
        </form>

        <div id="forget-form" style="display:none; flex-direction:column; gap:20px; width:100%; opacity:0; transition: all 0.6s ease-out; transform: translateY(15px);">
          <div style="text-align:center;">
            <p class="muted" style="font-size:14px; line-height:1.6;">Leave a message for the owner requesting a new password.</p>
          </div>
          <input type="text" id="forget-username" placeholder="Identity or Email" autocomplete="off" onpaste="return false;" oncontextmenu="return false;" style="text-align:center; font-size:16px; height: 56px; padding: 0 20px;">
          <textarea id="forget-message" placeholder="Short explanation of your request" autocomplete="off" onpaste="return false;" oncontextmenu="return false;" style="height: 120px; padding: 12px;"></textarea>
          <button type="button" class="primary" onclick="requestReset()" style="justify-content:center;">Send Request</button>
          <a href="#" onclick="toggleForget(false)" style="font-size:12px; color:var(--muted); text-decoration:none;">Back to Login</a>
        </div>

        <div id="auth-status" class="status" style="margin-top:16px; font-weight:600; min-height:1.2em;"></div>
      </div>
    </div>
    <style>
      @keyframes shake {{ 0%, 100% {{ transform: translateX(0); }} 25% {{ transform: translateX(-8px); }} 75% {{ transform: translateX(8px); }} }}
      .shake {{ animation: shake 0.4s ease-in-out; }}
    </style>
    """
    return page("Admin Login", body)

@admin_bp.route("/admin/login", methods=["POST"])
def login_action():
    username = request.form.get("username")
    password = request.form.get("password")
    is_ajax = wants_json_response()
    user = get_user_by_username(username)
    if not user:
        err = "This identity does not exist in the ELD PRO matrix."
        if is_ajax: return jsonify({"error": err}), 404
        return page("Admin Login", f"<div class='panel' style='max-width:400px; margin:100px auto; text-align:center;'><h2 style='color:var(--bad)'>Identity Unknown</h2><p>{{err}}</p><a href='/admin/login'>Try again</a></div>")

    if verify_user(username, password):
        session["admin_authenticated"] = True
        session["admin_username"] = user["username"]
        session["admin_id"] = user["id"]
        session["admin_role"] = user["role"]
        session["server_run_id"] = SERVER_RUN_ID
        session.permanent = True
        if is_ajax:
            return jsonify({"ok": True, "next": request.form.get("next", "/admin")})
        return redirect(request.form.get("next", "/admin"))
    
    err = "Incorrect password for this identity."
    if is_ajax: return jsonify({"error": err}), 401
    return page("Admin Login", f"<div class='panel' style='max-width:400px; margin:100px auto; text-align:center;'><h2 style='color:var(--bad)'>Access Denied</h2><p>{{err}}</p><a href='/admin/login'>Try again</a></div>")

@admin_bp.route("/admin/logout")
def logout():
    session.clear()
    return redirect("/")

@admin_bp.route("/admin/forget-password", methods=["POST"])
def forget_password_action():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    message = str(payload.get("message", "")).strip()
    
    if not username or not message:
        return jsonify({"error": "Username and message are required."}), 400

    user = get_user_by_username(username)
    if not user:
        return jsonify({"error": f"Identity '{{username}}' does not exist in the ELD PRO matrix."}), 404
        
    create_password_request(user["username"], message)
    return jsonify({"ok": True})

@admin_bp.route("/admin/users")
@admin_required
def admin_users_view():
    role = session.get("admin_role")
    if role not in ("owner", "super_admin"):
        return redirect("/admin")
    
    role_options = ""
    if role == 'owner':
        role_options = '<option value="super_admin">Super Admin (Managed Access)</option>'
        
    body = f"""
    <div class="muted" style="margin-bottom: 24px;">Security and Identity Control. Manage project contributors and system-wide permissions.</div>
    
    <div class="panel">
      <h3><i data-lucide="user-plus" style="width:18px; height:18px; vertical-align:middle; margin-right:10px;"></i> Provision New Account</h3>
      <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px;">
        <div>
          <label class="muted" style="font-size:11px; font-weight:700; display:block; margin-bottom:8px;">USERNAME (LATIN ONLY, 1 UPPER, 1 LOWER)</label>
          <input type="text" id="new-username" placeholder="e.g. JohnDoe" autocomplete="off" onpaste="return false;" oncontextmenu="return false;" ondrop="return false;" style="width:100%;">
        </div>
        <div>
          <label class="muted" style="font-size:11px; font-weight:700; display:block; margin-bottom:8px;">EMAIL ADDRESS</label>
          <input type="email" id="new-email" placeholder="e.g. john@example.com" onpaste="return false;" oncontextmenu="return false;" ondrop="return false;" style="width:100%;">
        </div>
      </div>
      <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px;">
        <div>
          <label class="muted" style="font-size:11px; font-weight:700; display:block; margin-bottom:8px;">INITIAL PASSWORD (UPPER, LOWER, DIGIT, SYMBOL)</label>
          <div style="display:flex; gap:12px; align-items:center;">
            <input type="text" id="new-password" placeholder="Min 8 chars" style="flex:1;" autocomplete="new-password" onpaste="return false;" oncontextmenu="return false;" ondrop="return false;">
            <button type="button" onclick="window.generatePass()" title="Generate Random Password" style="width: 64px; height: 52px; border-radius:16px; display:flex; justify-content:center; align-items:center; flex-shrink: 0; padding:0;"><i data-lucide="refresh-cw" style="width:18px; height:18px;"></i></button>
          </div>
        </div>
        <div>
          <label class="muted" style="font-size:11px; font-weight:700; display:block; margin-bottom:8px;">PERMISSIONS ROLE</label>
          <select id="new-role" style="width:100%;">
            <option value="viewer">Viewer (Read-only Analysis)</option>
            {role_options}
          </select>
        </div>
      </div>
      <div style="display:flex; justify-content:flex-end;">
        <button class="primary" onclick="window.createUser()" style="padding: 14px 40px; font-size:14px; font-weight:800; border-radius:16px;">Authorize User</button>
      </div>
      <div id="create-status" class="status" style="margin-top:20px; padding: 14px; border-radius: 14px; font-weight: 700; text-align: center; min-height: 20px;"></div>
    </div>

    <div class="panel">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px;">
        <h3 style="margin:0;"><i data-lucide="shield-check" style="width:18px; height:18px; vertical-align:middle; margin-right:10px;"></i> Active Identity Matrix</h3>
        <div class="identity-filters" style="display:flex; gap:12px; align-items:center;">
          <input type="text" id="filter-user" placeholder="User..." style="width:140px; height:44px;" oninput="window.applyFilters()" onpaste="return false;" oncontextmenu="return false;" ondrop="return false;" autocomplete="off">
          <input type="text" id="filter-email" placeholder="Email..." style="width:140px; height:44px;" oninput="window.applyFilters()" onpaste="return false;" oncontextmenu="return false;" ondrop="return false;" autocomplete="off">
          <select id="filter-role" style="width:140px; height:44px;" onchange="window.applyFilters()">
            <option value="">Roles</option>
            <option value="super_admin">Super Admin</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
      </div>
      <div id="users-table-container"></div>
    </div>

    <div class="panel">
      <h3><i data-lucide="key" style="width:18px; height:18px; vertical-align:middle; margin-right:10px;"></i> Recovery Queue</h3>
      <div class="toolbar" style="margin-bottom:20px;">
        <button class="danger" onclick="window.clearRequests()" style="border-radius:12px;"><i data-lucide="trash-2"></i> Flush All Requests</button>
      </div>
      <div id="requests-table-container"></div>
    </div>

    <div id="modify-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:1000; backdrop-filter:blur(10px);">
      <div class="panel" style="max-width:480px; margin:100px auto; position:relative; border-top: 4px solid var(--accent); border-radius:32px;">
        <h3 style="margin-bottom:12px;"><i data-lucide="edit-3"></i> Modify Identity</h3>
        <input type="hidden" id="mod-user-id">
        <div style="display:flex; flex-direction:column; gap:20px;">
          <div>
            <label class="muted" style="font-size:10px; font-weight:800; display:block; margin-bottom:8px;">USERNAME (READ-ONLY)</label>
            <input type="text" id="mod-username" readonly style="background:rgba(255,255,255,0.02); color:var(--muted); opacity:0.6;">
          </div>
          <div>
            <label class="muted" style="font-size:10px; font-weight:800; display:block; margin-bottom:8px;">EMAIL ADDRESS</label>
            <input type="email" id="mod-email" placeholder="Email Address">
          </div>
          <div>
            <label class="muted" style="font-size:10px; font-weight:800; display:block; margin-bottom:8px;">NEW PASSWORD</label>
            <input type="text" id="mod-password" placeholder="Leave blank to keep current" onpaste="return false;" oncontextmenu="return false;" ondrop="return false;">
          </div>
          <div>
            <label class="muted" style="font-size:10px; font-weight:800; display:block; margin-bottom:8px;">ACCESS ROLE</label>
            <select id="mod-role">
              <option value="viewer">Viewer</option>
              <option value="super_admin">Super Admin</option>
            </select>
          </div>
          <div style="display:flex; gap:12px; justify-content:flex-end; margin-top:12px; border-top:1px solid var(--panel-border); padding-top:24px;">
            <button onclick="document.getElementById('modify-modal').style.display='none'" style="border-radius:14px; font-weight:700;">Cancel</button>
            <button class="primary" onclick="window.submitUpdate()" style="padding: 12px 32px; border-radius:14px; font-weight:800;">Confirm Changes</button>
          </div>
        </div>
      </div>
    </div>

    <div id="delete-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:2000; backdrop-filter:blur(12px); animation: fadeIn 0.3s ease;">
      <div class="panel" style="max-width:460px; margin:140px auto; position:relative; text-align:center; padding: 48px 40px; border-radius:32px; border: 1px solid var(--panel-border); box-shadow: 0 40px 100px -20px rgba(0,0,0,0.5); overflow:hidden;">
        <div style="position:absolute; top:0; left:0; right:0; height:6px; background:linear-gradient(90deg, #f43f5e 0%, #fb7185 100%);"></div>
        <div style="width:80px; height:80px; background:rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.1); border-radius:24px; display:flex; align-items:center; justify-content:center; margin:0 auto 32px; transform: rotate(45deg); box-shadow: 0 15px 30px -5px rgba(244, 63, 94, 0.15);">
          <div style="transform: rotate(-45deg); display:flex; align-items:center; justify-content:center;">
            <i data-lucide="shield-alert" style="width:38px; height:38px; color:var(--bad);"></i>
          </div>
        </div>
        <h2 style="font-family:'Outfit'; font-size:30px; font-weight:800; margin:0 0 12px; letter-spacing:-0.04em; color:var(--ink);">Revoke Identity?</h2>
        <p class="muted" style="font-size:16px; line-height:1.6; margin-bottom:36px; padding: 0 10px;">
          You are about to permanently terminate access for 
          <span id="delete-username" style="color:var(--bad); font-weight:800; text-decoration: underline dotted;"></span>.
          <span style="display:block; margin-top:8px; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; opacity:0.7;">This action cannot be undone.</span>
        </p>
        <input type="hidden" id="delete-user-id">
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
          <button onclick="document.getElementById('delete-modal').style.display='none'" style="background:var(--input-bg); border:1px solid var(--panel-border); height:54px; border-radius:14px; font-weight:700; color:var(--muted); justify-content:center;">Cancel</button>
          <button class="danger" onclick="window.confirmDelete()" style="background:var(--bad); color:white; border:none; height:54px; border-radius:14px; font-weight:700; justify-content:center; box-shadow: 0 10px 20px -5px rgba(244, 63, 94, 0.4);">Revoke</button>
        </div>
      </div>
    </div>

    <script src="/static/admin_manager.js"></script>
    """
    return page("Admin Manager", body, area="admin")

@admin_bp.route("/admin/users/api")
@admin_required
def api_list_users():
    # Filter out owners from the list for all users (Photo 2 request)
    all_users = list_users()
    filtered_users = [u for u in all_users if u.get("role") != "owner"]
    
    return jsonify({
        "users": filtered_users,
        "requests": list_forgot_passwords(),
        "current_id": session.get("admin_id"),
        "current_role": session.get("admin_role")
    })

@admin_bp.route("/admin/users/create", methods=["POST"])
@super_admin_required
def api_create_user():
    data = request.get_json() or {}
    u = data.get("username", "").strip()
    e = data.get("email", "").strip()
    p = data.get("password", "").strip()
    r = data.get("role", "viewer").strip()
    
    ok, err = is_valid_credentials(u)
    if not ok: return jsonify({"error": err}), 400
    ok, err = is_valid_credentials(p, is_password=True)
    if not ok: return jsonify({"error": err}), 400

    if session.get("admin_role") == "super_admin" and r != "viewer":
        return jsonify({"error": "Super Admins can only create Viewer accounts."}), 403

    try:
        # Corrected argument order: username, password, role, email
        new_u = add_user(u, p, r, e, created_by=session.get("admin_id"))
        return jsonify({"ok": True, "user": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@admin_bp.route("/admin/users/update", methods=["POST"])
@admin_required
def api_update_user():
    data = request.get_json() or {}
    user_id = data.get("user_id")
    e = data.get("email", "").strip()
    p = data.get("password", "").strip()
    r = data.get("role", "viewer").strip()
    
    user = next((u for u in list_users() if str(u["id"]) == str(user_id)), None)
    if not user: return jsonify({"error": "User not found"}), 404
    
    current_role = session.get("admin_role")
    current_id = session.get("admin_id")
    
    if current_role == "super_admin":
        if user["role"] in ("owner", "super_admin"):
            return jsonify({"error": "Permission denied."}), 403
        if user.get("created_by") != current_id:
            return jsonify({"error": "You can only edit users you created."}), 403

    update_user(user_id, email=e, password=p if p else None, role=r)
    return jsonify({"ok": True})

@admin_bp.route("/admin/users/delete/<user_id>", methods=["POST"])
@admin_required
def api_delete_user(user_id):
    user = next((u for u in list_users() if str(u["id"]) == str(user_id)), None)
    if not user: return jsonify({"error": "User not found"}), 404
    
    current_role = session.get("admin_role")
    current_id = session.get("admin_id")
    
    if current_role == "super_admin":
        if user["role"] in ("owner", "super_admin"):
            return jsonify({"error": "Permission denied."}), 403
        if user.get("created_by") != current_id:
            return jsonify({"error": "You can only revoke users you created."}), 403

    delete_user(user_id)
    return jsonify({"ok": True})

@admin_bp.route("/admin/users/requests/clear", methods=["DELETE"])
@owner_required
def api_clear_requests():
    req_id = request.args.get("id")
    if req_id:
        clear_forgot_passwords() 
    else:
        clear_forgot_passwords()
    return jsonify({"ok": True})

@admin_bp.route("/admin/api/generate-password")
@admin_required
def api_generate_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    passwd = "".join(random.choice(chars) for _ in range(16))
    return jsonify({"password": passwd})

