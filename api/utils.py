import json
import uuid
from functools import wraps
from urllib.parse import urlsplit
from flask import has_request_context, render_template, request, session, redirect, jsonify
from src.european_languages import EUROPEAN_LANGUAGE_SPECS
from src.config import ADMIN_PASSWORD, PUBLIC_BASE_URL

SERVER_RUN_ID = str(uuid.uuid4())

PUBLIC_PATHS = {
    "/",
    "/health",
    "/detect",
    "/analyze",
    "/feedback",
    "/api-docs",
    "/openapi.json",
    "/safety",
    "/safety.json",
    "/admin/login",
    "/admin/logout",
    "/admin/forget-password",
}

def language_options():
    return "\n".join(
        f"<option value='{item['code']}'>{item['code']} - {item['name']}</option>"
        for item in EUROPEAN_LANGUAGE_SPECS
    )

def admin_authenticated():
    if not ADMIN_PASSWORD:
        return True
    return bool(session.get("admin_authenticated"))

def wants_json_response():
    return (
        request.path.endswith(".json")
        or request.accept_mimetypes.best == "application/json"
    )

def public_href(href):
    public_base_url = request_public_base_url()
    if not public_base_url:
        return href
    if not href.startswith("/") or href.startswith("//"):
        return href
    return f"{public_base_url}{href}"

def request_public_base_url():
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    if not has_request_context():
        return ""

    forwarded_host = request.headers.get("X-Forwarded-Host", "")
    host = (forwarded_host or request.host or "").split(",", maxsplit=1)[0].strip()
    if not host.endswith(".app.github.dev"):
        return ""

    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    proto = (forwarded_proto or request.scheme or "https").split(",", maxsplit=1)[0].strip()
    if proto not in {"http", "https"}:
        proto = "https"
    return f"{proto}://{host}"

def safe_next_path(value, default="/admin"):
    path = str(value or "").strip()
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or not path.startswith("/") or path.startswith("//"):
        return default
    return path

def is_valid_credentials(text, min_len=3, is_password=False):
    if not text:
        return False, "Cannot be empty."
    if len(text) < min_len:
        return False, f"Must be at least {min_len} characters long."
    if any(ord(c) > 127 for c in text):
        return False, "Only Latin (English) characters are allowed."
    if is_password:
        if not any(c.isupper() for c in text):
            return False, "Missing Uppercase (A-Z)."
        if not any(c.islower() for c in text):
            return False, "Missing Lowercase (a-z)."
        if not any(c.isdigit() for c in text):
            return False, "Missing Digit (0-9)."
        if not any(not c.isalnum() for c in text):
            return False, "Missing Special Character (symbol)."
    else:
        if not any(c.isupper() for c in text):
            return False, "Username must have at least one Uppercase letter."
        if not any(c.islower() for c in text):
            return False, "Username must have at least one Lowercase letter."
    return True, ""

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if admin_authenticated():
            return fn(*args, **kwargs)
        if wants_json_response():
            return jsonify({"error": "Admin access required."}), 403
        return redirect("/admin/login")
    return wrapper

def super_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if admin_authenticated():
            role = session.get("admin_role")
            if role in ("owner", "super_admin"):
                return fn(*args, **kwargs)
        if wants_json_response():
            return jsonify({"error": "Elevated privileges required."}), 403
        return redirect("/admin")
    return wrapper

def owner_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if admin_authenticated() and session.get("admin_role") == "owner":
            return fn(*args, **kwargs)
        if wants_json_response():
            return jsonify({"error": "Owner privileges required."}), 403
        return redirect("/admin")
    return wrapper

def page(title, body, area="public"):
    if area == "admin":
        role = session.get("admin_role", "viewer")
        
        # Define role-based navigation
        # Owner: All access
        # Super Admin: Operational access, no Admin Manager
        # Viewer: Read-only analysis tabs
        
        nav_items = [("/admin", "Admin Dashboard", "layout-dashboard")]
        
        if role == "owner":
            nav_items.append(("/admin/users", "Admin Manager", "users"))
            
        # Analysis and Data tabs (available to all roles)
        nav_items.extend([
            ("/admin/quality", "Data Quality", "shield-check"),
            ("/admin/benchmark", "Benchmark", "gauge"),
            ("/admin/report", "Evaluation Report", "file-bar-chart"),
            ("/admin/model-card", "Model Card", "info"),
        ])
        
        # Management and Advanced tabs (Owner and Super Admin)
        if role in ("owner", "super_admin"):
            nav_items.extend([
                ("/admin/groups", "Language Groups", "layers"),
                ("/admin/characters", "Character Signatures", "type"),
                ("/admin/corpus", "Corpus Manager", "database"),
                ("/admin/frequency", "Frequency Analysis", "bar-chart-3"),
                ("/admin/lexicon", "Lexicon Manager", "book-open"),
                ("/admin/names", "Name Manager", "user-check"),
                ("/admin/learn", "Active Learning", "brain"),
                ("/admin/review", "Review Unknown Texts", "eye"),
                ("/admin/runs", "Training Runs", "history"),
                ("/admin/logs", "System Logs", "terminal"),
                ("/admin/safety", "Safety Policy", "shield-alert"),
            ])

        nav_items.extend([
            ("/detect", "Detector", "external-link"),
            ("/admin/logout", "Logout", "log-out"),
        ])
        
        shell_class = "admin-shell"
        eyebrow = "Management Console"
    else:
        nav_items = [
            ("/detect", "Detector", "search"),
            ("/admin", "Admin Login", "lock"),
        ]
        shell_class = "public-shell"
        eyebrow = "Public App"

    nav_html = "\n      ".join(
        f'<a href="{public_href(href)}" class="{"active" if request.path == href or (href == "/admin" and request.path == "/admin/login") else ""}" title="{label}"><i data-lucide="{icon}"></i> <span>{label}</span></a>'
        for href, label, icon in nav_items
    )

    current_icon = "shield"
    for href, label, icon in nav_items:
        if label == title or request.path == href:
            current_icon = icon
            break

    stats_html = ""
    if area == "admin":
        stats_html = """
    <div style="margin-top: 24px; padding: 16px; border-radius: 12px; background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border);">
      <div class="muted" style="font-size:11px; font-weight:700; text-transform:uppercase; margin-bottom:12px;">System Stats</div>
      <div style="display:flex; flex-direction:column; gap:8px; font-size:12px;">
        <div style="display:flex; justify-content:space-between;"><span>Lexicon:</span> <span style="color:var(--accent)" id="stat-lexicon">...</span></div>
        <div style="display:flex; justify-content:space-between;"><span>Names:</span> <span style="color:var(--accent)" id="stat-names">...</span></div>
        <div style="display:flex; justify-content:space-between;"><span>Database:</span> <span style="color:var(--muted)" id="stat-db">...</span></div>
      </div>
    </div>"""

    return render_template(
        "base.html",
        title=title,
        body=body,
        shell_class=shell_class,
        eyebrow=eyebrow,
        nav_html=nav_html,
        stats_html=stats_html,
        favicon_icon=current_icon,
        public_base_url=request_public_base_url(),
        static_version=SERVER_RUN_ID,
        language_specs=EUROPEAN_LANGUAGE_SPECS,
        language_names_json=json.dumps({s['code'].upper(): s['name'] for s in EUROPEAN_LANGUAGE_SPECS})
    )
