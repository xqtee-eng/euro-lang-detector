import json
import sys
from contextlib import redirect_stdout
from functools import wraps
from hmac import compare_digest
from html import escape
from io import StringIO
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify, redirect, request, session

from src.analyzer import analyze_words
from src.app_logging import get_app_logger, tail_log
from src.benchmark import run_benchmark
from src.character_profiles import character_candidates, character_profile_summary, generate_character_profiles
from src.config import ADMIN_PASSWORD, APP_DEBUG, APP_HOST, APP_PORT, EVALUATION_REPORT_PATH, SECRET_KEY
from src.corpus import (
    apply_curated_close_language_pack,
    dataset_stats,
    list_corpus_files,
    preview_corpus_file,
    rebuild_corpus_dataset,
    save_corpus_text,
)
from src.data_quality import data_quality_report
from src.evaluate import evaluate
from src.frequency import generate_frequency_lists, import_frequency_lists, list_frequency_files, save_frequency_text
from src.european_languages import EUROPEAN_LANGUAGE_SPECS, SUPPORTED_LANGUAGE_CODES
from src.hybrid import smart_detect_details
from src.model_card import model_card
from src.name_detector import add_name_hint, delete_name_hint, detect_name, list_name_hints
from src.openapi import openapi_spec
from src.related_report import related_language_report
from src.retrain import retrain
from src.safety import safety_status
from src.self_learning import (
    add_feedback_sample,
    clear_review_storage,
    clear_unknown_items,
    list_unknown_items,
    review_storage_summary,
)
from src.storage import (
    admin_dashboard_stats,
    list_active_learning_items,
    clear_active_learning_items,
    list_training_runs,
    resolve_active_learning_item,
    rollback_model_to_run,
    storage_summary,
)
from src.train import train
from src.word_lexicon import (
    add_lexicon_word,
    analyze_word_knowledge,
    delete_lexicon_word,
    import_lexicon_words,
    list_lexicon_entries,
    list_lexicon_words,
)

app = Flask(__name__)
app.secret_key = SECRET_KEY
logger = get_app_logger()


def language_options():
    return "\n".join(
        f"<option value='{item['code']}'>{item['code']} - {item['name']}</option>"
        for item in EUROPEAN_LANGUAGE_SPECS
    )


def _nav_link(href, label):
    return f'<a href="{href}">{label}</a>'


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
}


def admin_authenticated():
    if not ADMIN_PASSWORD:
        return True
    return bool(session.get("admin_authenticated"))


def wants_json_response():
    return request.path.endswith(".json") or request.accept_mimetypes.best == "application/json"


@app.before_request
def require_admin_auth():
    if request.path in PUBLIC_PATHS:
        return None
    if request.path.startswith("/detect") or request.path.startswith("/analyze"):
        return None
    if admin_authenticated():
        return None
    if wants_json_response():
        return jsonify({"error": "Admin authentication required."}), 401
    return redirect(f"/admin/login?next={request.path}")


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if admin_authenticated():
            return fn(*args, **kwargs)
        if wants_json_response():
            return jsonify({"error": "Admin authentication required."}), 401
        return redirect(f"/admin/login?next={request.path}")

    return wrapper


def page(title, body, area="public"):
    if area == "admin":
        nav_items = [
            ("/admin", "Dashboard", "layout-dashboard"),
            ("/quality", "Quality", "check-circle"),
            ("/benchmark", "Benchmark", "gauge"),
            ("/groups", "Close Languages", "copy"),
            ("/characters", "Characters", "type"),
            ("/corpus", "Corpus Manager", "database"),
            ("/frequency", "Frequency", "bar-chart"),
            ("/lexicon", "Lexicon", "book-open"),
            ("/names", "Names", "user"),
            ("/learn", "Active Learning", "brain"),
            ("/review", "Review Unknowns", "eye"),
            ("/runs", "Training Runs", "play-circle"),
            ("/report", "Eval Report", "file-text"),
            ("/model-card", "Model Card", "info"),
            ("/logs", "System Logs", "list"),
            ("/safety", "Safety Policy", "shield"),
            ("/detect", "View Public App", "external-link"),
            ("/admin/logout", "Logout", "log-out"),
        ]
        shell_class = "admin-shell"
        eyebrow = "Admin console"
    else:
        nav_items = [
            ("/detect", "Detector", "search"),
            ("/api-docs", "API Docs", "code"),
            ("/safety", "Safety Policy", "shield"),
            ("/admin", "Admin Login", "lock"),
        ]
        shell_class = "public-shell"
        eyebrow = "Public app"
    
    nav_html = "\n      ".join(
        f'<a href="{href}" class="{"active" if request.path == href else ""}" title="{label}"><i data-lucide="{icon}"></i> <span>{label}</span></a>'
        for href, label, icon in nav_items
    )
    
    template = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{title}}</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    :root {
      --bg: #030712; 
      --panel-bg: rgba(17, 24, 39, 0.7); 
      --panel-border: rgba(255, 255, 255, 0.08);
      --ink: #f9fafb; --muted: #9ca3af; 
      --accent: #3b82f6; --accent-hover: #60a5fa; --accent-soft: rgba(59, 130, 246, 0.15);
      --bad: #ef4444; --warn: #f59e0b; --good: #10b981;
      --sidebar-width: 280px;
    }
    :root.light {
      --bg: #f8fafc; 
      --panel-bg: rgba(255, 255, 255, 0.88); 
      --panel-border: rgba(148, 163, 184, 0.2);
      --ink: #0f172a; --muted: #64748b;
      --accent: #2563eb; --accent-hover: #1d4ed8; --accent-soft: rgba(37, 99, 235, 0.08);
      --sidebar-bg: rgba(255, 255, 255, 0.5);
      --glass-tint: rgba(255, 255, 255, 0.7);
    }
    :root {
      --sidebar-bg: rgba(15, 23, 42, 0.6);
      --glass-tint: rgba(17, 24, 39, 0.7);
      --shadow: 0 10px 40px -12px rgba(0,0,0,0.3);
    }
    .light { --shadow: 0 10px 30px -10px rgba(0,0,0,0.1); }
    * { box-sizing: border-box; transition: background-color 0.4s ease, border-color 0.4s ease, color 0.3s ease, transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease; }
    body { 
      margin: 0; background: var(--bg); color: var(--ink); 
      font-family: "Inter", system-ui, sans-serif; line-height: 1.6; 
      display: flex; min-height: 100vh; overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
    }
    
    .sidebar { 
      width: var(--sidebar-width); 
      background: var(--sidebar-bg); 
      border-right: 1px solid var(--panel-border); 
      backdrop-filter: blur(20px);
      padding: 32px 20px; display: flex; flex-direction: column; 
      position: fixed; height: 100vh; z-index: 100; 
      backdrop-filter: blur(24px) saturate(180%); 
    }
    .sidebar .brand { margin-bottom: 40px; padding: 0 12px; }
    .sidebar .brand .eyebrow { color: var(--accent); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.15em; margin-bottom: 6px; opacity: 0.8; }
    .sidebar .brand h1 { font-family: "Outfit", sans-serif; font-size: 22px; margin: 0; font-weight: 800; letter-spacing: -0.03em; }
    
    .sidebar nav { display: flex; flex-direction: column; gap: 6px; overflow-y: auto; flex: 1; padding-right: 4px; }
    .sidebar nav a { 
      display: flex; align-items: center; gap: 14px; padding: 12px 16px; border-radius: 12px; 
      color: var(--muted); font-size: 14px; font-weight: 500; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
    }
    .sidebar nav a i { width: 20px; height: 20px; stroke-width: 2; opacity: 0.7; }
    .sidebar nav a:hover { background: var(--accent-soft); color: var(--ink); }
    .sidebar nav a.active { background: var(--accent-soft); color: var(--accent); border: 1px solid rgba(59, 130, 246, 0.2); }
    .sidebar nav a.active i { opacity: 1; }
    
    .main-content { 
      flex: 1; margin-left: var(--sidebar-width); padding: 50px 60px; 
      max-width: 1400px; animation: fadeIn 0.6s ease-out;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    
    .top-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px; }
    .page-title h2 { font-family: "Outfit", sans-serif; margin: 0; font-size: 36px; font-weight: 800; letter-spacing: -0.04em; }
    
    .panel { 
      border: 1px solid var(--panel-border); border-radius: 20px; 
      background: var(--panel-bg); padding: 28px; margin-bottom: 30px; 
      backdrop-filter: blur(20px); 
      box-shadow: var(--shadow);
      transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .panel:hover { transform: translateY(-2px); border-color: var(--accent-soft); }
    h3 { margin: 0 0 20px; font-size: 18px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
    
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 30px; }
    
    button { 
      cursor: pointer; font-weight: 600; padding: 12px 22px; border-radius: 12px; 
      border: 1px solid var(--panel-border); background: rgba(255,255,255,0.03); 
      color: var(--ink); display: inline-flex; align-items: center; gap: 10px; 
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); font-size: 14px; 
    }
    button:hover { background: rgba(255,255,255,0.08); border-color: var(--accent); box-shadow: 0 8px 20px -5px rgba(0,0,0,0.3); }
    button.primary { background: var(--accent); color: white; border-color: var(--accent); box-shadow: 0 4px 15px -3px rgba(59, 130, 246, 0.4); }
    button.primary:hover { background: var(--accent-hover); transform: translateY(-1px); box-shadow: 0 8px 25px -5px rgba(59, 130, 246, 0.5); }
    button.danger { color: var(--bad); border-color: rgba(239, 68, 68, 0.2); }
    button.danger:hover { background: rgba(239, 68, 68, 0.1); border-color: var(--bad); }

    input, select, textarea { 
      background: rgba(0,0,0,0.3); border: 1px solid var(--panel-border); 
      border-radius: 12px; padding: 12px 16px; color: var(--ink); 
      font-size: 14px; transition: all 0.3s;
    }
    input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); background: rgba(0,0,0,0.4); box-shadow: 0 0 0 4px var(--accent-soft); }

    table { width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 16px; }
    th { text-align: left; padding: 16px; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.15em; font-weight: 800; border-bottom: 1px solid var(--panel-border); }
    td { padding: 16px; font-size: 14px; border-bottom: 1px solid var(--panel-border); }
    tr:last-child td { border-bottom: 0; }
    tr:hover td { background: rgba(255, 255, 255, 0.03); }

    .pill { padding: 6px 12px; border-radius: 10px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
    .pill.good { background: rgba(16, 185, 129, 0.1); color: var(--good); border: 1px solid rgba(16, 185, 129, 0.2); }
    .pill.warn { background: rgba(245, 158, 11, 0.1); color: var(--warn); border: 1px solid rgba(245, 158, 11, 0.2); }
    .pill.bad { background: rgba(239, 68, 68, 0.1); color: var(--bad); border: 1px solid rgba(239, 68, 68, 0.2); }

    .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 10px; position: relative; }
    .status-dot.good { background: var(--good); }
    .status-dot.good::after { content: ''; position: absolute; inset: -3px; border-radius: 50%; background: var(--good); opacity: 0.3; animation: pulse 2s infinite; }

    @media (max-width: 1024px) {
      .sidebar { width: 90px; padding: 32px 12px; }
      .sidebar .brand h1, .sidebar nav a span, .sidebar .muted, .sidebar .brand .eyebrow { display: none; }
      .sidebar nav a { justify-content: center; padding: 16px; }
      .main-content { margin-left: 90px; padding: 30px; }
    }
  </style>
</head>
<body class="{{shell_class}}">
    <aside class="sidebar">
    <div class="brand">
      <div class="eyebrow">{{eyebrow}}</div>
      <h1>ELD System</h1>
    </div>
    <nav>
      {{nav_html}}
    </nav>
    <div style="margin-top: 24px; padding: 16px; border-radius: 12px; background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border);">
      <div class="muted" style="font-size:11px; font-weight:700; text-transform:uppercase; margin-bottom:12px;">System Stats</div>
      <div style="display:flex; flex-direction:column; gap:8px; font-size:12px;">
        <div style="display:flex; justify-content:space-between;"><span>Lexicon:</span> <span style="color:var(--accent)" id="stat-lexicon">...</span></div>
        <div style="display:flex; justify-content:space-between;"><span>Names:</span> <span style="color:var(--accent)" id="stat-names">...</span></div>
        <div style="display:flex; justify-content:space-between;"><span>Database:</span> <span style="color:var(--muted)" id="stat-db">...</span></div>
      </div>
    </div>
    <div style="margin-top: auto; padding: 16px 8px; border-top: 1px solid var(--panel-border);">
      <button onclick="toggleTheme()" style="width:100%; justify-content:center; border-radius:8px; padding:8px;">
        <i data-lucide="sun"></i> <span style="margin-left:8px">Theme</span>
      </button>
    </div>
  </aside>

  <main class="main-content">
    <div class="top-row">
      <div class="page-title">
        <h2>{{title}}</h2>
      </div>
      <div class="row muted" style="font-size:13px; font-weight:500;">
        <span class="status-dot good"></span> 40 Languages Configured
      </div>
    </div>
    
    {{body}}
  </main>

  <script>
    lucide.createIcons();

    async function updateStats() {
      try {
        const response = await fetch('/admin/status');
        const data = await response.json();
        if (document.getElementById('stat-lexicon')) {
          document.getElementById('stat-lexicon').textContent = data.lexicon_words || '0';
          document.getElementById('stat-names').textContent = data.name_hints || '0';
          document.getElementById('stat-db').textContent = data.db_size || '0 MB';
        }
      } catch (e) {}
    }
    updateStats();
    setInterval(updateStats, 30000);

    function toggleTheme() {
      document.documentElement.classList.toggle('light');
      localStorage.setItem('theme', document.documentElement.classList.contains('light') ? 'light' : 'dark');
      lucide.createIcons();
    }
    if (localStorage.getItem('theme') === 'light') document.documentElement.classList.add('light');

    function filterTable(inputId, tableId) {
      const input = document.getElementById(inputId);
      const filter = input.value.toLowerCase();
      const table = document.getElementById(tableId);
      const rows = table.getElementsByTagName('tr');
      for (let i = 1; i < rows.length; i++) {
        const cells = rows[i].getElementsByTagName('td');
        let match = false;
        for (let j = 0; j < cells.length; j++) {
          if (cells[j].textContent.toLowerCase().includes(filter)) {
            match = true;
            break;
          }
        }
        rows[i].style.display = match ? '' : 'none';
      }
    }
  </script>
</body>
</html>
"""
    return (template
            .replace("{{title}}", str(title))
            .replace("{{body}}", str(body))
            .replace("{{nav_html}}", nav_html)
            .replace("{{shell_class}}", shell_class)
            .replace("{{eyebrow}}", eyebrow))


@app.get("/admin/login")
def login_form():
    if admin_authenticated():
        return redirect(request.args.get("next", "/admin"))
    body = """
    <div style="max-width: 400px; margin: 100px auto;">
      <div class="panel" style="text-align:center;">
        <i data-lucide="lock" style="width:48px; height:48px; margin-bottom:16px; color:var(--accent);"></i>
        <h2 style="border:0; margin-bottom:24px;">Admin Access</h2>
        <form action="/admin/login" method="POST" style="display:flex; flex-direction:column; gap:16px;">
          <input type="password" name="password" placeholder="Enter Admin Password" autofocus required style="text-align:center; font-size:18px;">
          <input type="hidden" name="next" value="{{next}}">
          <button type="submit" class="primary" style="justify-content:center;">Unlock System</button>
        </form>
        <div id="error" class="status" style="color:var(--bad); margin-top:16px;"></div>
      </div>
      <div class="muted" style="text-align:center;">Default password is <code>admin</code></div>
    </div>
    """
    return page("Login", body.replace("{{next}}", request.args.get("next", "/admin")))


@app.post("/admin/login")
def login_action():
    password = request.form.get("password")
    if password and compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8")):
        session["admin_authenticated"] = True
        session.permanent = True
        return redirect(request.form.get("next", "/admin"))
    return page("Login", "<div class='panel' style='max-width:400px; margin:100px auto; text-align:center;'><h2 style='color:var(--bad)'>Access Denied</h2><p>Incorrect password.</p><a href='/admin/login'>Try again</a></div>")


@app.get("/admin/logout")
def logout_action():
    session.pop("admin_authenticated", None)
    return redirect("/")


@app.get("/admin/status")
@admin_required
def admin_status_api():
    stats = admin_dashboard_stats()
    summary = stats["summary"]
    db_path = Path("data/app.db")
    db_size = f"{db_path.stat().st_size / 1024 / 1024:.1f} MB" if db_path.exists() else "0 MB"
    return jsonify({
        "lexicon_words": summary.get("lexicon_words", 0),
        "name_hints": summary.get("name_hints", 0),
        "db_size": db_size,
        "uptime": "99.9%",
    })


@app.get("/")
def index():
    return redirect("/detect")



@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/storage")
def storage_api():
    return jsonify(storage_summary())


@app.get("/openapi.json")
def openapi_json_api():
    return jsonify(openapi_spec())


@app.get("/safety.json")
def safety_json_api():
    return jsonify(safety_status())


@app.get("/safety")
def safety_page():
    status = safety_status()
    policy = status["policy"]
    rows = "".join(
        f"<tr><td>{escape(key)}</td><td>{escape(str(value))}</td></tr>"
        for key, value in policy.items()
        if key != "notes"
    )
    notes = "".join(f"<li>{escape(note)}</li>" for note in policy.get("notes", []))
    return page(
        "Safety Controls",
        f"""
    <div class="panel">
      <h2>Human-approved learning policy</h2>
      <table><tbody>{rows}</tbody></table>
      <ul>{notes}</ul>
      <div class="muted">The detector may queue uncertain examples, but it does not train on guesses automatically.</div>
    </div>
        """,
    )


@app.get("/logs.json")
def logs_json_api():
    try:
        limit = int(request.args.get("limit", 200))
    except ValueError:
        limit = 200
    return jsonify({"lines": tail_log(limit=limit)})


@app.get("/logs")
def logs_page():
    lines = tail_log(limit=300)
    return page(
        "Application Logs",
        f"""
    <div class="panel">
      <h2>Recent Logs</h2>
      <div class="muted">Production-style rotating request and detection logs.</div>
    </div>
    <div class="panel"><pre>{escape(chr(10).join(lines))}</pre></div>
        """,
        area="admin",
    )


@app.get("/model-card.json")
def model_card_json_api():
    return jsonify(model_card())


@app.get("/model-card")
def model_card_page():
    card = model_card()
    return page(
        "Model Card",
        f"""
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
      {_admin_card("AI Score", card['quality']['ai_application'], "application readiness")}
      {_admin_card("Data Readiness", card['quality']['data_readiness'], "corpus and lexicon coverage")}
      {_admin_card("Benchmark", card['benchmark']['accuracy'], f"{card['benchmark']['correct']}/{card['benchmark']['samples']} correct")}
    </div>
    <div class="panel">
      <h2>Pipeline</h2>
      <table><tbody>{_rows([{"step": step} for step in card["pipeline"]], [("step", "Step")])}</tbody></table>
    </div>
    <div class="panel">
      <h2>Limitations</h2>
      <ul>{''.join(f"<li>{escape(item)}</li>" for item in card['limitations'])}</ul>
    </div>
        """,
        area="admin",
    )


@app.get("/api-docs")
def api_docs_page():
    spec = openapi_spec()
    return page(
        "API Docs",
        f"""
    <div class="panel">
      <h2>REST examples</h2>
      <pre>Invoke-RestMethod -Method Post -Uri http://{APP_HOST}:{APP_PORT}/detect -ContentType "application/json" -Body '{{"text":"Bonjour","top_k":3}}'

python examples/api_client.py "Bonjour tout le monde"</pre>
      <div class="toolbar">
        <a class="pill" href="/openapi.json">OpenAPI JSON</a>
        <a class="pill" href="/health">Health</a>
      </div>
    </div>
        """,
    )


@app.get("/admin.json")
def admin_json_api():
    return jsonify(admin_dashboard_stats())


@app.get("/quality.json")
def quality_json_api():
    return jsonify(data_quality_report())


@app.get("/quality")
def quality_page():
    report = data_quality_report()
    scores = report["scores"]
    recommendations = "".join(f"<li>{escape(item)}</li>" for item in report["recommendations"])
    dataset_rows = _rows(
        [
            {
                "language": language,
                "dataset": report["dataset"]["by_language"].get(language, 0),
                "train": report["train"]["by_language"].get(language, 0),
                "test": report["test"]["by_language"].get(language, 0),
                "corpus": report["corpus"]["by_language"].get(language, 0),
                "lexicon": report["knowledge"]["lexicon_by_language"].get(language, 0),
                "names": report["knowledge"]["names_by_language"].get(language, 0),
            }
            for language in SUPPORTED_LANGUAGE_CODES
        ],
        [
            ("language", "Lang"),
            ("dataset", "Dataset"),
            ("train", "Train"),
            ("test", "Test"),
            ("corpus", "Corpus"),
            ("lexicon", "Lexicon"),
            ("names", "Names"),
        ],
    )
    body = f"""
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
      {_admin_card("Course Project Score", f"{scores['course_project']}/10", "target: 10/10")}
      {_admin_card("AI Application Score", f"{scores['ai_application']}/10", "target: 7.5-8/10")}
      {_admin_card("Data Readiness", f"{scores['data_readiness']}/10", "needs real corpus growth")}
      {_admin_card("Benchmark", f"{report['benchmark']['accuracy']}", f"{report['benchmark']['correct']}/{report['benchmark']['samples']} correct")}
      {_admin_card("Character Profiles", report['character_profiles']['languages'], "alphabet/signature coverage")}
      {_admin_card("Dataset Rows", report['dataset']['total_rows'], f"min per language: {report['dataset']['min_rows_per_language']}")}
      {_admin_card("Lexicon / Freq / Names", f"{report['knowledge']['lexicon_entries']} / {report['knowledge']['frequency_entries']} / {report['knowledge']['name_hints']}", "editable knowledge")}
    </div>
    <div class="panel">
      <h2>Next Improvements</h2>
      <ul>{recommendations or "<li>No urgent recommendations.</li>"}</ul>
    </div>
    <div class="panel">
      <h2>Coverage By Language</h2>
      <div class="search-box">
        <input id="quality-search" type="text" placeholder="Search languages..." onkeyup="filterTable('quality-search', 'qualityTable')">
      </div>
      <table class="sortable" id="qualityTable">
        <thead>
          <tr>
            <th data-tooltip="Language code">Lang</th>
            <th data-tooltip="Total samples in the raw dataset">Dataset</th>
            <th data-tooltip="Samples used for training">Train</th>
            <th data-tooltip="Samples used for testing">Test</th>
            <th data-tooltip="Lines in the raw corpus files">Corpus</th>
            <th data-tooltip="Words in the manual lexicon">Lexicon</th>
            <th data-tooltip="Custom name detection hints">Names</th>
          </tr>
        </thead>
        <tbody>{dataset_rows}</tbody>
      </table>
    </div>
    """
    return page("Data Quality", body, area="admin")


@app.get("/characters.json")
def characters_json_api():
    return jsonify(character_profile_summary())


@app.post("/characters/generate")
def characters_generate_api():
    profiles = generate_character_profiles()
    return jsonify({"ok": True, "languages": len(profiles)})


@app.get("/characters/candidates")
def characters_candidates_api():
    text = request.args.get("text", "")
    return jsonify({"text": text, "candidates": character_candidates(text)})


@app.get("/characters")
def characters_page():
    summary = character_profile_summary()
    rows = _rows(
        summary["profiles"],
        [
            ("language", "Lang"),
            ("name", "Name"),
            ("total_letters", "Letters"),
            ("alphabet_size", "Alphabet"),
            ("signature", "Signature"),
            ("unique_characters", "Unique Characters"),
        ],
    )
    body = f"""
    <div class="panel">
      <h2>Character Profiles</h2>
      <div class="muted">Language-specific character statistics generated from reviewed corpus files.</div>
      <div class="row" style="margin-top:12px">
        <input id="char-text" placeholder="Text to explain by characters" style="min-width:280px">
        <button onclick="explainCharacters()">Explain</button>
        <button class="primary" onclick="generateCharacters()">Regenerate profiles</button>
      </div>
      <pre id="char-status" style="margin-top:12px">{{}}</pre>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>Lang</th><th>Name</th><th>Letters</th><th>Alphabet</th><th>Signature</th><th>Unique Characters</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <script>
      async function generateCharacters() {{
        const response = await fetch('/characters/generate', {{method: 'POST'}});
        const data = await response.json();
        document.getElementById('char-status').textContent = JSON.stringify(data, null, 2);
        if (response.ok) setTimeout(() => location.reload(), 700);
      }}
      async function explainCharacters() {{
        const text = encodeURIComponent(document.getElementById('char-text').value);
        const response = await fetch('/characters/candidates?text=' + text);
        const data = await response.json();
        document.getElementById('char-status').textContent = JSON.stringify(data, null, 2);
      }}
    </script>
    """
    return page("Character Profiles", body, area="admin")


@app.get("/benchmark.json")
def benchmark_json_api():
    return jsonify(run_benchmark())


@app.get("/benchmark")
def benchmark_page():
    report = run_benchmark()
    category_rows = _rows(
        [
            {"category": category, **stats}
            for category, stats in report["by_category"].items()
        ],
        [("category", "Category"), ("samples", "Samples"), ("correct", "Correct"), ("accuracy", "Accuracy")],
    )
    rows = _rows(
        report["rows"],
        [
            ("text", "Text"),
            ("expected", "Expected"),
            ("predicted", "Predicted"),
            ("category", "Category"),
            ("correct", "Correct"),
            ("confidence", "Confidence"),
            ("source", "Source"),
            ("reason", "Reason"),
        ],
    )
    body = f"""
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
      {_admin_card("Benchmark Accuracy", report['accuracy'], f"{report['correct']}/{report['samples']} correct")}
      {_admin_card("Categories", len(report['by_category']), "single words, names, scripts, mixed text")}
    </div>
    <div class="panel">
      <h2>By Category</h2>
      <div class="search-box">
        <input id="bench-search" type="text" placeholder="Filter categories..." onkeyup="filterTable('bench-search', 'benchTable')">
      </div>
      <table id="benchTable">
        <thead>
          <tr>
            <th>Category</th>
            <th>Samples</th>
            <th>Correct</th>
            <th data-tooltip="Percentage of correct predictions in this category">Accuracy</th>
          </tr>
        </thead>
        <tbody>{category_rows}</tbody>
      </table>
    </div>
    <div class="panel">
      <h2>Samples</h2>
      <table>
        <thead><tr><th>Text</th><th>Expected</th><th>Predicted</th><th>Category</th><th>Correct</th><th>Confidence</th><th>Source</th><th>Reason</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """
    return page("AI Benchmark", body, area="admin")


@app.get("/groups.json")
def related_groups_json_api():
    return jsonify(related_language_report())


@app.get("/groups")
def related_groups_page():
    report = related_language_report()
    rows = _rows(
        report["groups"],
        [
            ("group", "Group"),
            ("name", "Name"),
            ("languages", "Languages"),
            ("samples", "Samples"),
            ("correct", "Exact Correct"),
            ("group_correct", "Group Correct"),
            ("accuracy", "Exact Accuracy"),
            ("group_accuracy", "Group Accuracy"),
        ],
    )
    internal_confusion_rows = _rows(
        report.get("internal_confusions", []),
        [
            ("group", "Group"),
            ("expected", "Expected"),
            ("predicted", "Predicted"),
            ("count", "Count"),
        ],
    )
    external_confusion_rows = _rows(
        report.get("external_confusions", []),
        [
            ("group", "Group"),
            ("expected", "Expected"),
            ("predicted", "Predicted"),
            ("count", "Count"),
        ],
    )
    marker_rows = _rows(
        [
            {
                "group": group["group"],
                "language": language,
                "markers": ", ".join(group.get("markers", {}).get(language, [])),
            }
            for group in report["groups"]
            for language in group.get("languages", [])
        ],
        [
            ("group", "Group"),
            ("language", "Language"),
            ("markers", "Marker Hints"),
        ],
    )
    low_margin_rows = _rows(
        report.get("low_margin_cases", []),
        [
            ("group", "Group"),
            ("expected", "Expected"),
            ("predicted", "Predicted"),
            ("related_suggested_language", "Suggested"),
            ("related_margin", "Margin"),
            ("confidence", "Confidence"),
            ("text", "Text"),
        ],
    )
    body = f"""
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
      {_admin_card("Source", report['source'], "evaluation report if available")}
      {_admin_card("Samples", report['total']['samples'], f"{report['total']['correct']} exact / {report['total']['group_correct']} group")}
      {_admin_card("Exact Accuracy", report['total']['accuracy'], "all languages")}
      {_admin_card("Group Accuracy", report['total']['group_accuracy'], "close-language groups")}
    </div>
    <div class="panel">
      <h2>Close Language Groups</h2>
      <div class="search-box">
        <input id="group-search" type="text" placeholder="Filter groups..." onkeyup="filterTable('group-search', 'groupTable')">
      </div>
      <table id="groupTable">
        <thead>
          <tr>
            <th>Group</th>
            <th>Name</th>
            <th>Languages</th>
            <th>Samples</th>
            <th data-tooltip="Exact label matches">Exact Correct</th>
            <th data-tooltip="Predictions that stayed within the correct group">Group Correct</th>
            <th data-tooltip="Accuracy on exact labels">Exact Accuracy</th>
            <th data-tooltip="Accuracy on group families">Group Accuracy</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div class="grid" style="display:block;">
      <div class="panel">
        <h2>Notes</h2>
        <ul>
          <li>Exact accuracy measures the top label.</li>
          <li>Group accuracy treats mutually close languages as one family.</li>
          <li>Internal confusion means the model stayed inside the correct close-language family.</li>
          <li>External confusion means the model fell outside the family and needs stronger data or rules.</li>
        </ul>
      </div>
    </div>
    <div class="panel">
      <h2>Internal Confusions</h2>
      <table>
        <thead><tr><th>Group</th><th>Expected</th><th>Predicted</th><th>Count</th></tr></thead>
        <tbody>{internal_confusion_rows}</tbody>
      </table>
    </div>
    <div class="panel">
      <h2>External Confusions</h2>
      <table>
        <thead><tr><th>Group</th><th>Expected</th><th>Predicted</th><th>Count</th></tr></thead>
        <tbody>{external_confusion_rows}</tbody>
      </table>
    </div>
    <div class="panel">
      <h2>Learned Marker Hints</h2>
      <table>
        <thead><tr><th>Group</th><th>Language</th><th>Marker Hints</th></tr></thead>
        <tbody>{marker_rows}</tbody>
      </table>
    </div>
    <div class="panel">
      <h2>Low-Margin Cases</h2>
      <table>
        <thead><tr><th>Group</th><th>Expected</th><th>Predicted</th><th>Suggested</th><th>Margin</th><th>Confidence</th><th>Text</th></tr></thead>
        <tbody>{low_margin_rows}</tbody>
      </table>
    </div>
    """
    return page("Close Languages", body, area="admin")


@app.get("/frequency")
def frequency_page():
    files = list_frequency_files()
    rows = _rows(
        files,
        [
            ("language", "Lang"),
            ("name", "Name"),
            ("entries", "Entries"),
            ("total_frequency", "Total Frequency"),
            ("path", "Path"),
        ],
    )
    body = f"""
    <div class="panel">
      <h2>Frequency Lists</h2>
      <div class="muted">Generate TSV frequency lists from reviewed corpus text, then import them into the lexicon knowledge base.</div>
      <div class="row" style="margin-top:12px">
        <select id="freq-lang">{language_options()}</select>
        <select id="freq-mode"><option value="replace">replace</option><option value="append">append</option></select>
        <input id="freq-file" type="file" accept=".tsv,.txt,text/plain">
      </div>
      <textarea id="freq-text" style="margin-top:10px; min-height:90px" placeholder="word<TAB>frequency, one row per line"></textarea>
      <div class="row" style="margin-top:12px">
        <button onclick="uploadFrequency()">Upload TSV</button>
        <button class="primary" onclick="runFrequency('/frequency/generate')">Generate from corpus</button>
        <button class="primary" onclick="runFrequency('/frequency/import')">Import into lexicon</button>
        <a class="pill" href="/quality">Quality</a>
      </div>
      <pre id="frequency-status" style="margin-top:12px">{{}}</pre>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>Lang</th><th>Name</th><th>Entries</th><th>Total Frequency</th><th>Path</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <script>
      async function runFrequency(path) {{
        const response = await fetch(path, {{method: 'POST'}});
        const data = await response.json();
        document.getElementById('frequency-status').textContent = JSON.stringify(data, null, 2);
        if (response.ok) setTimeout(() => location.reload(), 700);
      }}
      async function uploadFrequency() {{
        const input = document.getElementById('freq-file');
        let text = document.getElementById('freq-text').value;
        if (input.files.length) {{
          text = await input.files[0].text();
        }}
        const response = await fetch('/frequency/upload', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            lang: document.getElementById('freq-lang').value,
            mode: document.getElementById('freq-mode').value,
            text: text
          }})
        }});
        const data = await response.json();
        document.getElementById('frequency-status').textContent = JSON.stringify(data, null, 2);
        if (response.ok) setTimeout(() => location.reload(), 700);
      }}
    </script>
    """
    return page("Frequency Manager", body, area="admin")


@app.get("/frequency/files")
def frequency_files_api():
    return jsonify({"files": list_frequency_files()})


@app.post("/frequency/upload")
def frequency_upload_api():
    payload = request.get_json(silent=True) or {}
    try:
        result = save_frequency_text(
            payload.get("lang", ""),
            payload.get("text", ""),
            mode=str(payload.get("mode", "replace")).strip().lower(),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, **result})


@app.post("/frequency/generate")
def frequency_generate_api():
    payload = request.get_json(silent=True) or {}
    result = generate_frequency_lists(max_words_per_language=payload.get("max_words_per_language", 1000))
    return jsonify({"ok": True, **result})


@app.post("/frequency/import")
def frequency_import_api():
    payload = request.get_json(silent=True) or {}
    result = import_frequency_lists(limit_per_language=payload.get("limit_per_language", 1000))
    return jsonify({"ok": True, **result})


def _admin_card(label, value, note="", icon="activity"):
    note_html = f"<div class='muted'>{escape(str(note))}</div>" if note else ""
    return (
        "<div class='panel' style='display:flex; flex-direction:column; justify-content:center; align-items:flex-start;'>"
        f"<div style='display:flex; justify-content:space-between; width:100%; margin-bottom:12px;'>"
        f"<div class='pill' style='background:rgba(59, 130, 246, 0.1); color:var(--accent); display:flex; align-items:center; gap:6px;'>"
        f"<i data-lucide='{icon}' style='width:14px; height:14px;'></i> {escape(str(label))}"
        "</div>"
        "</div>"
        f"<div style='font-size:32px; font-weight:800; letter-spacing:-0.03em; margin-bottom:4px;'>{escape(str(value))}</div>"
        f"{note_html}"
        "</div>"
    )


def _rows(items, columns):
    if not items:
        return "<tr><td colspan='%d' class='muted'>No data yet.</td></tr>" % len(columns)
    output = []
    for item in items:
        cells = []
        for key, label in columns:
            value = item.get(key, "")
            cell_content = escape(str(value))
            
            # Visual bar logic for accuracy/confidence/ratios
            try:
                # If key contains 'accuracy', 'confidence', 'margin' or value is a float between 0 and 1
                is_metric = any(m in key.lower() for m in ["accuracy", "confidence", "margin", "ratio"])
                if is_metric and isinstance(value, (float, int)):
                    val = float(value)
                    if 0 <= val <= 1:
                        pct = round(val * 100, 1)
                        cls = "good" if val >= 0.85 else ("warn" if val >= 0.6 else "")
                        cell_content = f"{pct}% <div class='table-bar-bg'><div class='table-bar-fill {cls}' style='width:{pct}%'></div></div>"
            except (ValueError, TypeError):
                pass

            if isinstance(value, (dict, list)):
                cell_content = f"<pre style='max-height:100px;font-size:11px'>{escape(json.dumps(value, ensure_ascii=False, indent=2))}</pre>"
            
            cells.append(f"<td>{cell_content}</td>")
        output.append("<tr>" + "".join(cells) + "</tr>")
    return "".join(output)


def _capture_admin_action(action):
    output = StringIO()
    with redirect_stdout(output):
        result = action()
    return {"result": result, "output": output.getvalue()}


@app.get("/admin")
def admin_dashboard():
    stats = admin_dashboard_stats()
    summary = stats["summary"]
    dataset = stats["dataset"]
    evaluation = stats["latest_evaluation"]

    cards = "".join(
        [
            _admin_card("Accuracy", evaluation.get("accuracy", 0), "latest evaluation", icon="target"),
            _admin_card("Unknown", summary.get("unknown", 0), "active items", icon="help-circle"),
            _admin_card("Learning Queue", summary.get("active_learning", 0), "needs human label", icon="brain"),
            _admin_card("Feedback", summary.get("feedback", 0), "waiting for retrain", icon="message-square"),
            _admin_card("Lexicon", summary.get("lexicon_words", 0), "enabled words", icon="book"),
            _admin_card("Names", summary.get("name_hints", 0), "enabled hints", icon="users"),
            _admin_card("Training Runs", summary.get("training_runs", 0), "saved in SQLite", icon="database"),
            _admin_card("Dataset", dataset.get("dataset_rows", 0), "all rows", icon="layers"),
            _admin_card("Train / Test", f"{dataset.get('train_rows', 0)} / {dataset.get('test_rows', 0)}", "split ratio", icon="git-branch"),
        ]
    )

    file_rows = _rows(
        [
            {"name": name, **info}
            for name, info in stats["files"].items()
        ],
        [("name", "Name"), ("exists", "Exists"), ("size_bytes", "Size"), ("path", "Path")],
    )

    body = f"""
    <div class="grid" style="grid-template-columns: 200px 1fr; gap: 24px;">
      <div class="panel" style="text-align: center;">
        <h2>Language Distribution</h2>
        <div class="pie-chart"></div>
        <div class="muted" style="margin-top: 8px;">Top language families by volume.</div>
      </div>
      <div class="panel">
      <h2>Pipeline Controls</h2>
      <div class="muted" style="margin-bottom: 16px;">Step-by-step system initialization and refinement.</div>
      <div class="toolbar">
        <button onclick="runAdminAction('/admin/actions/seed')"><i data-lucide="sprout"></i> 1. Seed Data</button>
        <button onclick="runAdminAction('/admin/actions/rebuild')"><i data-lucide="database"></i> 2. Build Dataset</button>
        <button class="primary" onclick="runAdminAction('/admin/actions/train')"><i data-lucide="play"></i> 3. Train & Eval</button>
        <button onclick="runAdminAction('/admin/actions/retrain')"><i data-lucide="refresh-cw"></i> Retrain Profiles</button>
      </div>
      <div id="action-status" class="status" style="margin-top: 16px; font-weight: 600;"></div>
      <pre id="action-output" style="margin-top: 12px; font-size: 11px; max-height: 200px; overflow: auto; border-radius: 8px; background: rgba(0,0,0,0.05); padding: 12px; display: none;"></pre>
    </div>
    </div>
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));">
      {cards}
    </div>
    <div class="grid">
      <div class="panel">
        <h2>Recent Feedback</h2>
        <table>
          <thead><tr><th>ID</th><th>Text</th><th>Lang</th><th>Source</th><th>Promoted</th><th>Created</th></tr></thead>
          <tbody>{_rows(stats["recent_feedback"], [("id", "ID"), ("text", "Text"), ("lang", "Lang"), ("source", "Source"), ("promoted", "Promoted"), ("created_at", "Created")])}</tbody>
        </table>
      </div>
      <div class="panel">
        <h2>Recent Unknowns</h2>
        <table>
          <thead><tr><th>Text</th><th>Count</th><th>Status</th><th>Action</th><th>Updated</th></tr></thead>
          <tbody>{_rows(stats["recent_unknowns"], [("text", "Text"), ("count", "Count"), ("status", "Status"), ("action", "Action"), ("updated_at", "Updated")])}</tbody>
        </table>
      </div>
    </div>
    <div class="panel">
      <h2>Active Learning Queue</h2>
      <table>
        <thead><tr><th>ID</th><th>Text</th><th>Suggested</th><th>Confidence</th><th>Reason</th><th>Priority</th><th>Count</th></tr></thead>
        <tbody>{_rows(stats["recent_learning_items"], [("id", "ID"), ("text", "Text"), ("suggested_language", "Suggested"), ("confidence", "Confidence"), ("reason", "Reason"), ("priority", "Priority"), ("count", "Count")])}</tbody>
      </table>
    </div>
    <div class="grid">
      <div class="panel">
        <h2>Training Runs</h2>
        <table>
          <thead><tr><th>ID</th><th>Kind</th><th>Samples</th><th>Correct</th><th>Unknown</th><th>Accuracy</th><th>Created</th></tr></thead>
          <tbody>{_rows(stats["recent_training_runs"], [("id", "ID"), ("kind", "Kind"), ("samples", "Samples"), ("correct", "Correct"), ("unknown", "Unknown"), ("accuracy", "Accuracy"), ("created_at", "Created")])}</tbody>
        </table>
      </div>
      <div class="panel">
        <h2>Knowledge By Language</h2>
        <div class="grid" style="grid-template-columns: 1fr 1fr;">
          <div>
            <h2>Lexicon</h2>
            <table><thead><tr><th>Lang</th><th>Words</th></tr></thead><tbody>{_rows(stats["lexicon_by_language"], [("language", "Lang"), ("count", "Words")])}</tbody></table>
          </div>
          <div>
            <h2>Names</h2>
            <table><thead><tr><th>Lang</th><th>Names</th></tr></thead><tbody>{_rows(stats["names_by_language"], [("language", "Lang"), ("count", "Names")])}</tbody></table>
          </div>
        </div>
      </div>
    </div>
    <div class="panel" style="border-color: rgba(239, 68, 68, 0.2); background: rgba(239, 68, 68, 0.02);">
      <h2 style="color: var(--bad);"><i data-lucide="alert-triangle" style="width:20px; height:20px; vertical-align:middle; margin-right:8px;"></i> Danger Zone</h2>
      <p class="muted" style="font-size: 13px; margin-bottom: 20px;">The following actions are destructive and cannot be undone.</p>
      <div class="toolbar">
        <button class="danger" onclick="confirmReset()">Clear All Application Data</button>
      </div>
      <div id="action-status" class="status" style="margin-top: 12px;"></div>
      <pre id="action-output" style="margin-top: 12px; display: none;"></pre>
    </div>
    
    <div class="panel">
      <h2>Files</h2>
      <table>
        <thead><tr><th>Name</th><th>Exists</th><th>Size</th><th>Path</th></tr></thead>
        <tbody>{file_rows}</tbody>
      </table>
    </div>
    <script>
      async function confirmReset() {{
        if (confirm('Are you absolutely sure? This will delete all models, DB entries, and logs. Datasets will be preserved.')) {{
          runAdminAction('/admin/actions/reset');
        }}
      }}
      async function runAdminAction(path) {{
        const status = document.getElementById('action-status');
        const output = document.getElementById('action-output');
        status.textContent = 'Running...';
        output.textContent = '';
        const response = await fetch(path, {{method: 'POST'}});
        const data = await response.json();
        status.textContent = data.ok ? 'Done.' : (data.error || 'Failed.');
        output.textContent = JSON.stringify(data, null, 2);
      }}
    </script>
    """
    return page("Admin Dashboard", body, area="admin")


@app.post("/admin/actions/rebuild")
def admin_rebuild_dataset_api():
    try:
        result = _capture_admin_action(lambda: rebuild_corpus_dataset())
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, **result})


@app.post("/admin/actions/seed")
@admin_required
def admin_seed_api():
    from src.seeding.seed_dataset import seed_raw_dataset
    try:
        def action():
            seed_raw_dataset(overwrite=True)
            return {"message": "Seed data created successfully."}
        result = _capture_admin_action(action)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, **result})


@app.post("/admin/actions/train")
@admin_required
def admin_train_api():
    try:
        def action():
            profiles = train(kind="admin_train")
            accuracy = evaluate()
            return {
                "profiles": len(profiles),
                "accuracy": f"{accuracy:.2%}"
            }
        result = _capture_admin_action(action)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, **result})


@app.post("/admin/actions/retrain")
def admin_retrain_api():
    try:
        result = _capture_admin_action(retrain)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, **result})


@app.post("/admin/actions/evaluate")
def admin_evaluate_api():
    try:
        result = _capture_admin_action(lambda: {"accuracy": evaluate()})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, **result})


@app.get("/runs.json")
def training_runs_json_api():
    return jsonify({"runs": list_training_runs(limit=200)})


@app.post("/runs/<int:run_id>/rollback")
def rollback_training_run_api(run_id):
    try:
        result = rollback_model_to_run(run_id)
    except (FileNotFoundError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify({"ok": True, **result})


@app.get("/runs")
def training_runs_page():
    runs = list_training_runs(limit=200)
    rows = []
    for run in runs:
        run_id = str(run.get("id", ""))
        kind = str(run.get("kind", ""))
        samples = str(run.get("samples", ""))
        correct = str(run.get("correct", ""))
        unknown = str(run.get("unknown", ""))
        accuracy = f"{run.get('accuracy', 0):.2%}"
        created = str(run.get("created_at", ""))
        snapshot = str(run.get("model_snapshot_path", "") or "")
        
        rollback_button = ""
        if run.get("rollback_available"):
            rollback_button = f"<button onclick='rollbackRun({run_id})'>Rollback</button>"
            
        rows.append(
            "<tr>"
            f"<td>{escape(run_id)}</td>"
            f"<td>{escape(kind)}</td>"
            f"<td>{escape(samples)}</td>"
            f"<td>{escape(correct)}</td>"
            f"<td>{escape(unknown)}</td>"
            f"<td>{escape(accuracy)}</td>"
            f"<td>{escape(created)}</td>"
            f"<td>{escape(snapshot)}</td>"
            f"<td>{rollback_button}</td>"
            "</tr>"
        )

    body = f"""
    <div class="panel">
      <div class="muted">Train and retrain runs create model snapshots. Rollback restores models/profiles.json from the selected snapshot.</div>
    </div>
    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Kind</th><th>Samples</th><th>Correct</th><th>Unknown</th>
            <th>Accuracy</th><th>Created</th><th>Snapshot</th><th></th>
          </tr>
        </thead>
        <tbody>{''.join(rows) if rows else "<tr><td colspan='9' class='muted'>No training runs yet.</td></tr>"}</tbody>
      </table>
    </div>
    <div class="panel"><pre id="status">{escape(json.dumps({"runs": runs}, ensure_ascii=False, indent=2))}</pre></div>
    <script>
      async function rollbackRun(id) {{
        const ok = confirm('Rollback model to training run #' + id + '?');
        if (!ok) return;
        const response = await fetch('/runs/' + id + '/rollback', {{method: 'POST'}});
        const data = await response.json();
        document.getElementById('status').textContent = JSON.stringify(data, null, 2);
        if (response.ok) {{
          setTimeout(() => location.reload(), 700);
        }}
      }}
    </script>
    """
    return page("Training Runs", body, area="admin")


@app.get("/languages")
def languages():
    return jsonify({"languages": EUROPEAN_LANGUAGE_SPECS})


@app.post("/admin/actions/reset")
@admin_required
def admin_reset_api():
    from src.storage import reset_application_data
    try:
        result = reset_application_data()
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify(result)


@app.get("/detect")
def detect_form():
    return page(
        "European Language Detector",
        """
    <textarea id="text" autofocus placeholder="Type text here..." style="font-size: 18px; padding: 20px; min-height: 120px;">Bonjour tout le monde</textarea>
    <div class="toolbar" style="margin: 20px 0 32px;">
      <button class="primary" onclick="detect()"><i data-lucide="search"></i> Detect Language</button>
      <button onclick="analyze()"><i data-lucide="microscope"></i> Word Analysis</button>
      <div style="margin-left: auto; display: flex; gap: 8px;">
        <span class="muted" style="align-self:center; font-size:12px;">Try:</span>
        <button onclick="sample('Привіт, як твої справи?')">UK</button>
        <button onclick="sample('Dobry дзень')">BE</button>
        <button onclick="sample('Na nádraží čekáme na vlak')">CS</button>
        <button onclick="sample('hello привіт bonjour')">Mixed</button>
      </div>
    </div>
    <section class="grid">
      <div class="panel">
        <div id="language" class="language" style="display:flex; align-items:center; gap:16px;">
          <i data-lucide="globe" style="width:40px; height:40px; stroke-width:2.5;"></i>
          <span id="language-name">--</span>
        </div>
        <div id="meta" class="meta">Run detection to see the result.</div>
        <div class="bar"><div id="fill" class="fill"></div></div>
        
        <div id="candidates" style="margin-top: 16px;"></div>
        
        <div class="item" style="border-top: 1px solid var(--panel-border); margin-top: 20px; padding-top: 16px;">
          <h3 style="font-size: 14px; color: var(--muted); margin-bottom: 8px;">Feedback</h3>
          <div class="row">
            <input id="feedbackLang" maxlength="3" style="width: 60px" placeholder="uk">
            <button onclick="sendFeedback()">Submit correction</button>
          </div>
          <div id="feedbackStatus" class="status"></div>
        </div>
      </div>
      
      <div class="panel">
        <div class="row" style="justify-content: space-between; margin-bottom: 12px;">
          <h2 style="border:0; margin:0; font-size: 16px;">Details</h2>
          <button onclick="toggleJson()" style="padding: 4px 8px; font-size: 11px;">Toggle JSON</button>
        </div>
        <div id="tokens"></div>
        <div id="json-container" style="display: none; margin-top: 12px;">
          <pre id="result" style="font-size: 11px; max-height: 300px;"></pre>
        </div>
      </div>
    </section>
    <script>
      let detectTimer = null;

      function sample(value) {
        document.getElementById('text').value = value;
        detect();
      }

      document.getElementById('text').addEventListener('input', function() {
        clearTimeout(detectTimer);
        detectTimer = setTimeout(detect, 450);
      });

      function confidenceBar(value) {
        document.getElementById('fill').style.width = (Math.max(0, Math.min(1, value || 0)) * 100) + '%';
      }

      function renderCandidates(items) {
        document.getElementById('candidates').innerHTML = (items || []).map(function(item) {
          const country = item.country ? ' - ' + item.country : '';
          const group = item.language_group ? ' <span class="pill warn">group ' + escapeHtml(item.language_group) + '</span>' : '';
          const ambiguous = item.ambiguous_group ? ' <span class="pill warn">ambiguous</span>' : '';
          return '<div class="candidate"><strong><i data-lucide="map-pin" style="width:14px; height:14px; vertical-align:middle; margin-right:6px;"></i>' + escapeHtml(item.language + country) + '</strong><span>' + item.confidence + '</span>' + group + ambiguous + '</div>';
        }).join('');
        lucide.createIcons();
      }

      function renderTokens(tokens) {
        document.getElementById('tokens').innerHTML = (tokens || []).map(function(token) {
          const bad = token.language === 'unknown' ? ' bad' : (token.reliability === 'low' ? ' warn' : '');
          const group = token.language_group ? ' / group ' + token.language_group + ' (' + (token.group_reliability || 'unknown') + ')' : '';
          const icon = token.source === 'lexicon' ? 'book' : (token.source === 'name' ? 'user' : 'hash');
          return '<div class="token"><div class="token-line"><strong><i data-lucide="' + icon + '" style="width:14px; height:14px; vertical-align:middle; margin-right:6px; opacity:0.6;"></i>' + escapeHtml(token.text) + '</strong><span class="pill' + bad + '">' + escapeHtml(token.language) + '</span></div><div class="muted">' + escapeHtml(token.source || 'unknown') + ' / ' + escapeHtml(token.reason || token.entity_type || 'token') + ' / ' + token.confidence + escapeHtml(group) + '</div></div>';
        }).join('');
        lucide.createIcons();
      }

      function toggleJson() {
        const el = document.getElementById('json-container');
        el.style.display = el.style.display === 'none' ? 'block' : 'none';
      }

      async function detect() {
        const text = document.getElementById('text').value;
        document.getElementById('tokens').innerHTML = '';
        if (!text.trim()) {
          document.getElementById('language-name').textContent = '--';
          document.getElementById('meta').textContent = 'Run detection to see the result.';
          confidenceBar(0);
          renderCandidates([]);
          document.getElementById('result').textContent = '{}';
          return;
        }
        document.getElementById('meta').innerHTML = '<span class="spinner"></span>Detecting...';
        const response = await fetch('/detect', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({text: text, top_k: 5})
        });
        const data = await response.json();
        document.getElementById('result').textContent = JSON.stringify(data, null, 2);
        document.getElementById('language-name').textContent = data.language || '--';
        const entity = data.entity_type ? data.entity_type + ' - ' : '';
        const group = data.language_group ? ' - group ' + data.language_group + ' (' + (data.group_reliability || 'unknown') + ')' : '';
        const ambiguous = data.ambiguous_group ? ' - ambiguous group' : '';
        document.getElementById('meta').textContent = entity + (data.source || 'unknown') + ' - ' + (data.reliability || 'unknown') + ' - confidence ' + (data.confidence ?? 0) + group + ambiguous;
        confidenceBar(data.confidence || 0);
        renderCandidates(data.name_candidates || data.candidates || []);
      }

      async function analyze() {
        const text = document.getElementById('text').value;
        if (!text.trim()) return;
        document.getElementById('meta').innerHTML = '<span class="spinner"></span>Analyzing words...';
        const response = await fetch('/analyze', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({text: text, top_k: 5})
        });
        const data = await response.json();
        document.getElementById('result').textContent = JSON.stringify(data, null, 2);
        document.getElementById('language-name').textContent = data.language || '--';
        document.getElementById('meta').textContent = 'word analysis - coverage ' + data.coverage + ' - known ' + data.known_token_count + '/' + data.token_count;
        confidenceBar(data.coverage || 0);
        renderCandidates(Object.entries(data.language_counts || {}).map(function(pair) { return {language: pair[0], confidence: pair[1]}; }));
        renderTokens(data.tokens || []);
      }

      async function sendFeedback() {
        const lang = document.getElementById('feedbackLang').value.trim().toLowerCase();
        const text = document.getElementById('text').value;
        const response = await fetch('/feedback', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({text: text, lang: lang})
        });
        const data = await response.json();
        document.getElementById('feedbackStatus').textContent = data.message || data.error || 'Feedback saved.';
      }

      function escapeHtml(value) {
        return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
      }
    </script>
        """,
    )


@app.post("/detect")
def detect_api():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    try:
        top_k = int(payload.get("top_k", 3))
    except (TypeError, ValueError):
        top_k = 3
    result = smart_detect_details(text, top_k=max(1, min(top_k, 10)))
    logger.info(
        "detect language=%s confidence=%s source=%s reliability=%s text_length=%s",
        result.get("language"),
        result.get("confidence"),
        result.get("source"),
        result.get("reliability"),
        len(str(text or "")),
    )
    return jsonify(result)


@app.post("/analyze")
def analyze_api():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    try:
        top_k = int(payload.get("top_k", 3))
    except (TypeError, ValueError):
        top_k = 3
    return jsonify(analyze_words(text, top_k=max(1, min(top_k, 10))))


@app.get("/learn")
def active_learning_form():
    return page(
        "Active Learning",
        f"""
    <div class="toolbar">
      <button class="primary" onclick="loadItems()">Refresh</button>
      <button class="danger" onclick="clearQueue()">Clear queue</button>
      <span id="status" class="status"></span>
    </div>
    <div class="panel">
      <div class="muted">Review the highest-priority uncertain examples. Confirming a language saves feedback for retraining.</div>
    </div>
    <div id="items"></div>
    <template id="languageOptions">{language_options()}</template>
    <script>
      async function loadItems() {{
        const response = await fetch('/learn/items');
        const data = await response.json();
        const container = document.getElementById('items');
        document.getElementById('status').textContent = data.items.length + ' active learning item(s)';
        if (!data.items.length) {{
          container.innerHTML = '<div class="empty">No active learning items yet.</div>';
          return;
        }}
        container.innerHTML = data.items.map(function(item) {{
          const options = document.getElementById('languageOptions').innerHTML;
          const candidates = (item.candidates || []).map(function(candidate) {{
            const country = candidate.country ? ' - ' + candidate.country : '';
            return '<span class="pill">' + escapeHtml(candidate.language + country) + ': ' + escapeHtml(candidate.confidence) + '</span>';
          }}).join(' ');
          return '<div class="item"><div style="font-size:18px"><strong>' + escapeHtml(item.text) + '</strong></div><div class="meta">Suggested: ' + escapeHtml(item.suggested_language) + ' / confidence ' + item.confidence + ' / source ' + escapeHtml(item.source || '') + ' / reason ' + escapeHtml(item.reason || '') + ' / priority ' + item.priority + ' / seen ' + item.count + '</div><div style="margin:8px 0">' + candidates + '</div><div class="row"><select id="learn-lang-' + item.id + '">' + options + '</select><button class="primary" onclick="approveItem(' + item.id + ')">Save feedback</button><button class="danger" onclick="discardItem(' + item.id + ')">Discard</button></div></div>';
        }}).join('');
      }}

      async function approveItem(id) {{
        const lang = document.getElementById('learn-lang-' + id).value;
        const response = await fetch('/learn/items/' + id + '/feedback', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{lang: lang}})
        }});
        const data = await response.json();
        document.getElementById('status').textContent = data.message || data.error || 'Saved.';
        await loadItems();
      }}

      async function discardItem(id) {{
        await fetch('/learn/items/' + id, {{method: 'DELETE'}});
        await loadItems();
      }}

      async function clearQueue() {{
        const ok = confirm('Clear all active learning items?');
        if (!ok) return;
        await fetch('/learn/items', {{method: 'DELETE'}});
        await loadItems();
      }}

      function escapeHtml(value) {{
        return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
      }}
      loadItems();
    </script>
        """,
        area="admin",
    )


@app.get("/learn/items")
def active_learning_items_api():
    return jsonify({"items": list_active_learning_items()})


@app.delete("/learn/items")
def clear_active_learning_items_api():
    removed = clear_active_learning_items()
    return jsonify({"ok": True, "removed": removed})


@app.post("/learn/items/<int:item_id>/feedback")
def active_learning_feedback_api(item_id):
    payload = request.get_json(silent=True) or {}
    lang = str(payload.get("lang", "")).strip().lower()
    if lang not in SUPPORTED_LANGUAGE_CODES:
        return jsonify({"error": f"Unsupported language code: {lang}"}), 400

    item = resolve_active_learning_item(item_id, action="feedback", language=lang)
    if not item:
        return jsonify({"error": "Learning item not found."}), 404

    add_feedback_sample(item["text"], lang, source="active_learning")
    clear_unknown_items([item["text"]])
    return jsonify(
        {
            "ok": True,
            "message": f"Feedback saved as {lang}. Run python -m src.retrain to train it.",
            "item": item,
        }
    )


@app.delete("/learn/items/<int:item_id>")
def discard_active_learning_item_api(item_id):
    item = resolve_active_learning_item(item_id, action="discarded")
    if not item:
        return jsonify({"error": "Learning item not found."}), 404
    return jsonify({"ok": True, "item": item})


@app.get("/review")
def review_form():
    return page(
        "Review Unknown Texts",
        f"""
    <div class="toolbar">
      <button class="primary" onclick="loadItems()">Refresh</button>
      <button onclick="clearAll()">Clear visible unknowns</button>
      <button class="danger" onclick="resetReviewFiles()">Clear review files</button>
      <span id="status" class="status"></span>
    </div>
    <div class="panel">
      <div id="storage" class="muted">Storage: loading...</div>
    </div>
    <div id="items"></div>
    <template id="languageOptions">{language_options()}</template>
    <script>
      async function loadItems() {{
        const response = await fetch('/review/items');
        const data = await response.json();
        const container = document.getElementById('items');
        document.getElementById('status').textContent = data.items.length + ' unique items';
        renderStorage(data.storage || {{}});
        if (!data.items.length) {{
          container.innerHTML = '<div class="empty">No unknown texts yet.</div>';
          return;
        }}
        container.innerHTML = data.items.map(function(item, index) {{
          return '<div class="item"><div style="font-size:18px">' + escapeHtml(item.text) + '</div><div class="meta">Seen ' + item.count + ' time(s). Details: ' + escapeHtml(JSON.stringify(item.details || {{}})) + '</div><div class="row"><select id="lang-' + index + '">' + document.getElementById('languageOptions').innerHTML + '</select><button onclick="approve(' + index + ', ' + JSON.stringify(item.text).replaceAll('"', '&quot;') + ')">Add feedback</button><button class="danger" onclick="discard(' + JSON.stringify(item.text).replaceAll('"', '&quot;') + ')">Discard</button></div></div>';
        }}).join('');
      }}

      async function approve(index, text) {{
        const lang = document.getElementById('lang-' + index).value;
        const response = await fetch('/feedback', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{text: text, lang: lang}})
        }});
        const data = await response.json();
        document.getElementById('status').textContent = data.message || data.error || 'Saved.';
        await loadItems();
      }}

      async function discard(text) {{
        await fetch('/review/items', {{
          method: 'DELETE',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{texts: [text]}})
        }});
        await loadItems();
      }}

      async function clearAll() {{
        await fetch('/review/items', {{method: 'DELETE', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{all: true}})}});
        await loadItems();
      }}

      async function resetReviewFiles() {{
        const ok = confirm('Clear unknown.jsonl and resolved_unknown.jsonl? Feedback samples will stay.');
        if (!ok) return;
        const response = await fetch('/review/storage', {{
          method: 'DELETE',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{include_resolved: true}})
        }});
        const data = await response.json();
        document.getElementById('status').textContent = 'Review files cleared.';
        renderStorage(data.after || {{}});
        await loadItems();
      }}

      function renderStorage(storage) {{
        document.getElementById('storage').textContent = 'Storage files: unknown.jsonl=' + (storage.unknown ?? 0) + ', resolved_unknown.jsonl=' + (storage.resolved_unknown ?? 0) + ', feedback.jsonl=' + (storage.feedback ?? 0);
      }}

      function escapeHtml(value) {{
        return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
      }}
      loadItems();
    </script>
        """,
        area="admin",
    )


@app.get("/review/items")
def review_items_api():
    return jsonify({"items": list_unknown_items(), "storage": review_storage_summary()})


@app.delete("/review/items")
def clear_review_items_api():
    payload = request.get_json(silent=True) or {}
    if payload.get("all"):
        removed = clear_unknown_items()
    else:
        removed = clear_unknown_items(payload.get("texts", []))
    return jsonify({"ok": True, "removed": removed, "storage": review_storage_summary()})


@app.get("/review/storage")
def review_storage_api():
    return jsonify(review_storage_summary())


@app.delete("/review/storage")
def clear_review_storage_api():
    payload = request.get_json(silent=True) or {}
    result = clear_review_storage(
        include_resolved=bool(payload.get("include_resolved")),
        include_feedback=bool(payload.get("include_feedback")),
        include_learning=bool(payload.get("include_learning")),
    )
    return jsonify({"ok": True, **result})


@app.get("/corpus")
def corpus_form():
    return page(
        "Corpus Manager",
        f"""
    <div class="panel">
      <div class="row">
        <select id="lang">{language_options()}</select>
        <select id="mode"><option value="append">append</option><option value="replace">replace</option></select>
        <input id="file" type="file" accept=".txt,text/plain">
        <button class="primary" onclick="uploadCorpus()">Upload reviewed .txt</button>
        <button onclick="applyClosePack()">Apply close-language train pack</button>
        <button onclick="buildDataset()">Rebuild dataset/train/test</button>
        <button onclick="loadCorpus()">Refresh</button>
      </div>
      <textarea id="text" style="margin-top:10px; min-height:100px" placeholder="Or paste reviewed sentences here, one per line"></textarea>
      <div id="status" class="status"></div>
    </div>
    <div class="grid">
      <div class="panel">
        <h2>Reviewed corpus files</h2>
        <div id="files"></div>
      </div>
      <div class="panel">
        <h2>Dataset stats</h2>
        <pre id="dataset"></pre>
      </div>
    </div>
    <script>
      async function loadCorpus() {{
        const response = await fetch('/corpus/files');
        const data = await response.json();
        document.getElementById('dataset').textContent = JSON.stringify(data.dataset, null, 2);
        const rows = (data.files || []).filter(function(item) {{ return item.exists || item.non_empty_lines > 0; }}).map(function(item) {{
          return '<tr><td>' + escapeHtml(item.language) + '</td><td>' + escapeHtml(item.name || '') + '</td><td>' + item.non_empty_lines + '</td><td>' + item.size + '</td><td><button onclick="previewCorpus(' + JSON.stringify(item.language).replaceAll('"', '&quot;') + ')">Preview</button></td></tr>';
        }}).join('');
        document.getElementById('files').innerHTML = rows ? '<table><thead><tr><th>Lang</th><th>Name</th><th>Lines</th><th>Bytes</th><th></th></tr></thead><tbody>' + rows + '</tbody></table><pre id="preview" style="margin-top:12px"></pre>' : '<div class="empty">No corpus files yet.</div>';
      }}

      async function uploadCorpus() {{
        const lang = document.getElementById('lang').value;
        const mode = document.getElementById('mode').value;
        const input = document.getElementById('file');
        let text = document.getElementById('text').value;
        if (input.files.length) {{
          text = await input.files[0].text();
        }}
        const response = await fetch('/corpus/files', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{lang: lang, text: text, mode: mode}})
        }});
        const data = await response.json();
        document.getElementById('status').textContent = data.message || data.error || 'Saved.';
        if (response.ok) {{
          document.getElementById('text').value = '';
          input.value = '';
          await loadCorpus();
        }}
      }}

      async function buildDataset() {{
        const response = await fetch('/corpus/build', {{method: 'POST'}});
        const data = await response.json();
        document.getElementById('status').textContent = data.message || data.error || 'Built.';
        await loadCorpus();
      }}

      async function applyClosePack() {{
        const mode = document.getElementById('mode').value;
        const response = await fetch('/corpus/close-pack', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{mode: mode}})
        }});
        const data = await response.json();
        document.getElementById('status').textContent = data.message || data.error || 'Applied.';
        if (response.ok) {{
          await loadCorpus();
        }}
      }}

      async function previewCorpus(lang) {{
        const response = await fetch('/corpus/preview?lang=' + encodeURIComponent(lang));
        const data = await response.json();
        document.getElementById('preview').textContent = JSON.stringify(data, null, 2);
      }}

      function escapeHtml(value) {{
        return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
      }}
      loadCorpus();
    </script>
        """,
        area="admin",
    )


@app.get("/corpus/files")
def corpus_files_api():
    return jsonify({"files": list_corpus_files(), "dataset": dataset_stats()})


@app.post("/corpus/files")
def save_corpus_file_api():
    payload = request.get_json(silent=True) or {}
    lang = str(payload.get("lang", "")).strip().lower()
    text = str(payload.get("text", ""))
    mode = str(payload.get("mode", "append")).strip().lower()
    try:
        result = save_corpus_text(lang, text, mode=mode)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "message": f"Saved {result['total_lines']} reviewed line(s) for {lang}.", **result})


@app.post("/corpus/build")
def corpus_build_api():
    payload = request.get_json(silent=True) or {}
    try:
        result = rebuild_corpus_dataset(
            max_samples_per_language=payload.get("max_samples_per_language", 5000),
            test_ratio=payload.get("test_ratio", 0.2),
            seed=payload.get("seed", 42),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "message": f"Dataset built: {result['built_rows']} row(s).", **result})


@app.post("/corpus/close-pack")
def corpus_close_pack_api():
    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode", "append")).strip().lower()
    languages = payload.get("languages")
    try:
        result = apply_curated_close_language_pack(mode=mode, languages=languages)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "ok": True,
            "message": f"Applied curated close-language pack to {len(result['languages'])} train-only file(s).",
            **result,
        }
    )


@app.get("/corpus/preview")
def corpus_preview_api():
    try:
        return jsonify(preview_corpus_file(request.args.get("lang", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/lexicon")
def lexicon_form():
    return page(
        "Lexicon Manager",
        f"""
    <div class="panel">
      <div class="row">
        <select id="lang">{language_options()}</select>
        <input id="word" placeholder="word">
        <input id="frequency" type="number" min="1" step="1" value="1" style="width:100px" title="frequency">
        <input id="notes" placeholder="notes">
        <button class="primary" onclick="addWord()">Add word</button>
        <button onclick="analyzeWord()">Analyze word</button>
        <input id="search" placeholder="search" oninput="loadLexicon()">
        <button onclick="loadLexicon()">Refresh</button>
      </div>
      <textarea id="bulk" style="margin-top:10px; min-height:90px" placeholder="Paste many words here, one per line or separated by spaces"></textarea>
      <div class="row" style="margin-top:10px">
        <button onclick="importWords()">Import words</button>
        <span id="status" class="status"></span>
      </div>
    </div>
    <div class="grid">
      <div class="panel"><div id="lexicon"></div></div>
      <div class="panel"><h2>Word knowledge</h2><pre id="word-analysis">{{}}</pre></div>
    </div>
    <script>
      async function loadLexicon() {{
        const query = encodeURIComponent(document.getElementById('search').value.trim());
        const response = await fetch('/lexicon/entries?query=' + query);
        const data = await response.json();
        const rows = (data.entries || []).map(function(item) {{
          const flags = item.ambiguous ? '<span class="pill warn">ambiguous: ' + item.languages.map(escapeHtml).join(', ') + '</span>' : '';
          return '<tr><td>' + escapeHtml(item.word) + '</td><td>' + escapeHtml(item.language) + '</td><td>' + item.frequency + '</td><td>' + flags + '</td><td><button class="danger" onclick="deleteWord(' + JSON.stringify(item.language).replaceAll('"', '&quot;') + ', ' + JSON.stringify(item.word).replaceAll('"', '&quot;') + ')">Delete</button></td></tr>';
        }}).join('');
        document.getElementById('lexicon').innerHTML = rows ? '<table><thead><tr><th>Word</th><th>Lang</th><th>Freq</th><th>Info</th><th></th></tr></thead><tbody>' + rows + '</tbody></table>' : '<div class="empty">No words found.</div>';
      }}

      async function addWord() {{
        const lang = document.getElementById('lang').value;
        const word = document.getElementById('word').value.trim();
        const response = await fetch('/lexicon/items', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            lang: lang,
            word: word,
            frequency: Number(document.getElementById('frequency').value || 1),
            notes: document.getElementById('notes').value.trim()
          }})
        }});
        const data = await response.json();
        document.getElementById('status').textContent = data.message || data.error || 'Saved.';
        if (response.ok) {{
          document.getElementById('word').value = '';
          await loadLexicon();
        }}
      }}

      async function analyzeWord() {{
        const word = encodeURIComponent(document.getElementById('word').value.trim() || document.getElementById('search').value.trim());
        const response = await fetch('/words/analyze?word=' + word);
        const data = await response.json();
        document.getElementById('word-analysis').textContent = JSON.stringify(data, null, 2);
      }}

      async function importWords() {{
        const lang = document.getElementById('lang').value;
        const words = document.getElementById('bulk').value;
        const response = await fetch('/lexicon/items', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{lang: lang, words: words}})
        }});
        const data = await response.json();
        document.getElementById('status').textContent = data.message || data.error || 'Imported.';
        if (response.ok) {{
          document.getElementById('bulk').value = '';
          await loadLexicon();
        }}
      }}

      async function deleteWord(lang, word) {{
        await fetch('/lexicon/items', {{
          method: 'DELETE',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{lang: lang, word: word}})
        }});
        await loadLexicon();
      }}

      function escapeHtml(value) {{
        return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
      }}
      loadLexicon();
    </script>
        """,
        area="admin",
    )


@app.get("/lexicon/items")
def lexicon_items_api():
    query = request.args.get("query", "")
    language = request.args.get("lang", "")
    return jsonify({"lexicons": list_lexicon_words(query=query, language=language)})


@app.get("/lexicon/entries")
def lexicon_entries_api():
    query = request.args.get("query", "")
    language = request.args.get("lang", "")
    return jsonify({"entries": list_lexicon_entries(query=query, language=language)})


@app.get("/words/analyze")
def word_analyze_api():
    return jsonify(analyze_word_knowledge(request.args.get("word", "")))


@app.post("/lexicon/items")
def add_lexicon_item_api():
    payload = request.get_json(silent=True) or {}
    lang = str(payload.get("lang", "")).strip().lower()
    word = str(payload.get("word", "")).strip()
    words = str(payload.get("words", "")).strip()
    frequency = payload.get("frequency", 1)
    notes = str(payload.get("notes", "")).strip()

    if lang not in SUPPORTED_LANGUAGE_CODES:
        return jsonify({"error": f"Unsupported language code: {lang}"}), 400
    if not word and not words:
        return jsonify({"error": "Word or words are required."}), 400

    if words:
        items = import_lexicon_words(lang, words)
        for item in items:
            clear_unknown_items([item["word"]])
        return jsonify({"ok": True, "message": f"Imported {len(items)} word(s) as {lang}.", "items": items})

    item = add_lexicon_word(lang, word, frequency=frequency, notes=notes)
    clear_unknown_items([word])
    return jsonify({"ok": True, "message": f"Saved {word} as {lang}.", "item": item})


@app.delete("/lexicon/items")
def delete_lexicon_item_api():
    payload = request.get_json(silent=True) or {}
    lang = str(payload.get("lang", "")).strip().lower()
    word = str(payload.get("word", "")).strip()
    if lang not in SUPPORTED_LANGUAGE_CODES:
        return jsonify({"error": f"Unsupported language code: {lang}"}), 400
    if not word:
        return jsonify({"error": "Word is required."}), 400
    return jsonify({"ok": True, "item": delete_lexicon_word(lang, word)})


@app.get("/names")
def names_form():
    return page(
        "Name Manager",
        f"""
    <div class="panel">
      <div class="row">
        <select id="lang">{language_options()}</select>
        <input id="name" placeholder="name">
        <input id="country" placeholder="country">
        <input id="name_type" placeholder="type" value="person" style="width:110px">
        <input id="confidence" type="number" min="0.01" max="1" step="0.01" value="0.9" style="width:100px">
        <button class="primary" onclick="addName()">Add name</button>
        <button onclick="analyzeName()">Analyze name</button>
        <input id="search" placeholder="search" oninput="loadNames()">
      </div>
      <div id="status" class="status"></div>
    </div>
    <div class="grid">
      <div class="panel"><div id="names"></div></div>
      <div class="panel"><h2>Name knowledge</h2><pre id="name-analysis">{{}}</pre></div>
    </div>
    <script>
      async function loadNames() {{
        const query = encodeURIComponent(document.getElementById('search').value.trim());
        const response = await fetch('/names/items?query=' + query);
        const data = await response.json();
        const rows = (data.names || []).map(function(item) {{
          return '<tr><td>' + escapeHtml(item.name) + '</td><td>' + escapeHtml(item.language) + '</td><td>' + escapeHtml(item.country || '') + '</td><td>' + escapeHtml(item.name_type || 'person') + '</td><td>' + item.confidence + '</td><td><button class="danger" onclick="deleteName(' + JSON.stringify(item.name).replaceAll('"', '&quot;') + ', ' + JSON.stringify(item.language).replaceAll('"', '&quot;') + ')">Delete</button></td></tr>';
        }}).join('');
        document.getElementById('names').innerHTML = rows ? '<table><thead><tr><th>Name</th><th>Language</th><th>Country</th><th>Type</th><th>Confidence</th><th></th></tr></thead><tbody>' + rows + '</tbody></table>' : '<div class="empty">No names found.</div>';
      }}

      async function addName() {{
        const payload = {{
          lang: document.getElementById('lang').value,
          name: document.getElementById('name').value.trim(),
          country: document.getElementById('country').value.trim(),
          name_type: document.getElementById('name_type').value.trim() || 'person',
          confidence: Number(document.getElementById('confidence').value || 0.9)
        }};
        const response = await fetch('/names/items', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify(payload)
        }});
        const data = await response.json();
        document.getElementById('status').textContent = data.message || data.error || 'Saved.';
        if (response.ok) {{
          document.getElementById('name').value = '';
          await loadNames();
        }}
      }}

      async function analyzeName() {{
        const name = encodeURIComponent(document.getElementById('name').value.trim() || document.getElementById('search').value.trim());
        const response = await fetch('/names/analyze?name=' + name);
        const data = await response.json();
        document.getElementById('name-analysis').textContent = JSON.stringify(data, null, 2);
      }}

      async function deleteName(name, lang) {{
        await fetch('/names/items', {{
          method: 'DELETE',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{name: name, lang: lang}})
        }});
        await loadNames();
      }}

      function escapeHtml(value) {{
        return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
      }}
      loadNames();
    </script>
        """,
        area="admin",
    )


@app.get("/names/items")
def names_items_api():
    query = request.args.get("query", "")
    language = request.args.get("lang", "")
    return jsonify({"names": list_name_hints(query=query, language=language)})


@app.get("/names/analyze")
def names_analyze_api():
    name = request.args.get("name", "")
    return jsonify(detect_name(name) or {"language": "unknown", "source": "name", "entity_type": "unknown_name", "text": name})


@app.post("/names/items")
def add_name_item_api():
    payload = request.get_json(silent=True) or {}
    lang = str(payload.get("lang", "")).strip().lower()
    name = str(payload.get("name", "")).strip()
    country = str(payload.get("country", "")).strip()
    name_type = str(payload.get("name_type", "person")).strip()
    confidence = payload.get("confidence", 0.9)

    if lang not in SUPPORTED_LANGUAGE_CODES:
        return jsonify({"error": f"Unsupported language code: {lang}"}), 400
    if not name:
        return jsonify({"error": "Name is required."}), 400

    item = add_name_hint(name, lang, country=country, confidence=confidence, name_type=name_type)
    clear_unknown_items([name])
    return jsonify({"ok": True, "message": f"Saved {name} as {lang}.", "item": item})


@app.delete("/names/items")
def delete_name_item_api():
    payload = request.get_json(silent=True) or {}
    lang = str(payload.get("lang", "")).strip().lower()
    name = str(payload.get("name", "")).strip()
    if lang not in SUPPORTED_LANGUAGE_CODES:
        return jsonify({"error": f"Unsupported language code: {lang}"}), 400
    if not name:
        return jsonify({"error": "Name is required."}), 400
    return jsonify({"ok": True, "item": delete_name_hint(name, lang)})


@app.get("/report")
def report_form():
    if EVALUATION_REPORT_PATH.exists():
        with open(EVALUATION_REPORT_PATH, "r", encoding="utf-8") as handle:
            report = json.load(handle)
    else:
        report = {"message": "Run python -m src.evaluate to create models/evaluation_report.json."}

    rows = ""
    for language, stats in report.get("by_language", {}).items():
        rows += (
            f"<tr><td>{language}</td><td>{stats['samples']}</td><td>{stats['correct']}</td>"
            f"<td>{stats['unknown']}</td><td>{stats['accuracy']}</td></tr>"
        )

    body = f"""
    <div class="panel">
      <div class="row">
        <strong>Samples:</strong> {report.get('samples', 0)}
        <strong>Accuracy:</strong> {report.get('accuracy', 0)}
        <strong>Unknown:</strong> {report.get('unknown', 0)}
      </div>
      <div class="muted" style="margin-top:8px">Run <code>python -m src.evaluate</code> after rebuilding the dataset to refresh this report.</div>
    </div>
    <div class="grid" style="display:block;">
      <div class="panel">
        <h2>By Language</h2>
        <table><thead><tr><th>Lang</th><th>Samples</th><th>Correct</th><th>Unknown</th><th>Accuracy</th></tr></thead><tbody>{rows}</tbody></table>
      </div>
    </div>
    """
    return page("Evaluation Report", body, area="admin")


@app.get("/report.json")
def report_json_api():
    if not EVALUATION_REPORT_PATH.exists():
        return jsonify({"error": "Report not found. Run python -m src.evaluate first."}), 404
    with open(EVALUATION_REPORT_PATH, "r", encoding="utf-8") as handle:
        return jsonify(json.load(handle))


@app.post("/feedback")
def feedback_api():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    lang = str(payload.get("lang", "")).strip().lower()

    if not text:
        return jsonify({"error": "Text is required."}), 400
    if lang not in SUPPORTED_LANGUAGE_CODES:
        return jsonify({"error": f"Unsupported language code: {lang}"}), 400

    add_feedback_sample(text, lang, source="browser")
    clear_unknown_items([text])
    return jsonify(
        {
            "ok": True,
            "message": f"Feedback saved as {lang}. Run python -m src.retrain to train it.",
        }
    )


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)
