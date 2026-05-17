import json
import os
import logging
import threading
import datetime
from html import escape
from flask import Blueprint, jsonify, request, session, send_file
import io

from api.utils import page, admin_required, super_admin_required, admin_authenticated
from src.storage import (
    admin_dashboard_stats, export_full_backup, import_full_backup, 
    wipe_table, import_jsonl_backup, resolve_unknowns
)
from src.app_logging import get_app_logger, tail_log
from src.train import train as run_training
from src.retrain import retrain as build_profiles
from src.build_dataset import build_dataset as rebuild_dataset
from src.benchmark import run_benchmark
from src.character_profiles import load_character_profiles
from src.frequency import read_frequency_file
from src.corpus import list_corpus_files
from src.safety import safety_status
from src.model_card import model_card as get_model_card
from src.word_lexicon import add_lexicon_word

admin_management_bp = Blueprint('admin_management', __name__)
logger = get_app_logger()

# --- Background Task Management ---
_TASK_STATUS = {"running": False, "last_action": None, "error": None}

def _run_background_task(func, action_name):
    global _TASK_STATUS
    _TASK_STATUS["running"] = True
    _TASK_STATUS["last_action"] = action_name
    _TASK_STATUS["error"] = None
    try:
        func()
    except Exception as e:
        _TASK_STATUS["error"] = str(e)
        logger.error(f"Background task {action_name} failed: {e}")
    finally:
        _TASK_STATUS["running"] = False

# --- API Endpoints: Stats & Status ---

@admin_management_bp.route("/stats")
@admin_required
def get_dashboard_stats():
    return jsonify(admin_dashboard_stats())

@admin_management_bp.route("/status/task", methods=["GET"])
@admin_required
def get_task_status():
    return jsonify(_TASK_STATUS)

@admin_management_bp.route("/logs/raw")
@admin_required
def logs_raw():
    return jsonify({"lines": tail_log(200)})

# --- API Endpoints: Actions ---

@admin_management_bp.route("/actions/seed", methods=["POST"])
@admin_required
def seed_data():
    try:
        res = import_jsonl_backup()
        return jsonify({"ok": True, "message": "Seed completed successfully.", "details": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@admin_management_bp.route("/actions/rebuild", methods=["POST"])
@admin_required
def rebuild_data():
    if _TASK_STATUS["running"]:
        return jsonify({"ok": False, "error": "Another task is already running"})
    thread = threading.Thread(target=_run_background_task, args=(rebuild_dataset, "rebuild"))
    thread.start()
    return jsonify({"ok": True, "message": "Rebuild started in background"})

@admin_management_bp.route("/actions/train", methods=["POST"])
@admin_required
def train_model():
    if _TASK_STATUS["running"]:
        return jsonify({"ok": False, "error": "Another task is already running"})
    thread = threading.Thread(target=_run_background_task, args=(run_training, "train"))
    thread.start()
    return jsonify({"ok": True, "message": "Training started in background"})

@admin_management_bp.route("/actions/retrain", methods=["POST"])
@admin_required
def retrain_profiles():
    try:
        res = build_profiles()
        return jsonify({"ok": True, "stats": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@admin_management_bp.route("/actions/backup", methods=["GET"])
@admin_required
def backup_data():
    try:
        data = export_full_backup()
        filename = f"eld_pro_backup_{datetime.date.today()}.json"
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        
        mem = io.BytesIO(json_str.encode('utf-8'))
        return send_file(
            mem,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return jsonify({"ok": False, "error": str(e)})

@admin_management_bp.route("/actions/download-db", methods=["GET"])
@admin_required
def download_db():
    try:
        from src.config import DATABASE_PATH
        return send_file(DATABASE_PATH, as_attachment=True, download_name="eld_pro.db")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@admin_management_bp.route("/actions/restore", methods=["POST"])
@admin_required
def restore_data():
    try:
        file_data = request.json.get("data")
        if not file_data:
            return jsonify({"ok": False, "error": "No data provided"})
        res = import_full_backup(file_data)
        return jsonify({"ok": True, "message": "Restored successfully", "details": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@admin_management_bp.route("/actions/wipe/<target>", methods=["POST"])
@super_admin_required
def wipe_data(target):
    try:
        table_map = {
            "learning": "active_learning_items",
            "feedback": "feedback_samples",
            "lexicon": "lexicon_words",
            "names": "name_hints",
            "all": "all"
        }
        table = table_map.get(target)
        if not table:
            return jsonify({"ok": False, "error": "Invalid target"})
        
        if table == "all":
            for t in ["active_learning_items", "feedback_samples", "lexicon_words", "name_hints"]:
                wipe_table(t)
        else:
            wipe_table(table)
            
        return jsonify({"ok": True, "message": f"Wiped {target} successfully"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@admin_management_bp.route("/actions/learning/promote", methods=["POST"])
@admin_required
def promote_unknown():
    try:
        data = request.json or {}
        text = data.get("text")
        lang = data.get("lang")
        if not text or not lang:
            return jsonify({"ok": False, "error": "Text and lang are required"})
        
        add_lexicon_word(lang, text, frequency=5, notes="promoted from unknown")
        resolve_unknowns([text], action="promoted")
        return jsonify({"ok": True, "message": f"Promoted '{text}' to {lang}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@admin_management_bp.route("/actions/learning/dismiss", methods=["POST"])
@admin_required
def dismiss_unknown():
    try:
        data = request.json or {}
        text = data.get("text")
        if not text:
            return jsonify({"ok": False, "error": "Text is required"})
        
        resolve_unknowns([text], action="dismissed")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# --- Views: Main Dashboard ---

def _admin_card(label, value, note="", icon="activity"):
    val_str = str(value)
    font_size = "28px"
    if len(val_str) > 10: font_size = "22px"
    if len(val_str) > 16: font_size = "18px"
    note_html = f"<div class='muted'>{escape(str(note))}</div>" if note else ""
    return (
        "<div class='panel' style='display:flex; flex-direction:column; justify-content:center; align-items:flex-start; overflow:hidden;'>"
        f"<div style='display:flex; justify-content:space-between; width:100%; margin-bottom:12px;'>"
        f"<div class='pill' style='background:rgba(59, 130, 246, 0.1); color:var(--accent); display:flex; align-items:center; gap:6px;'>"
        f"<i data-lucide='{icon}' style='width:14px; height:14px;'></i> {escape(str(label))}"
        "</div>"
        "</div>"
        f"<div style='font-size:{font_size}; font-weight:800; letter-spacing:-0.03em; margin-bottom:4px; white-space:nowrap;'>{escape(val_str)}</div>"
        f"{note_html}"
        "</div>"
    )

def _rows(items, columns, area="general"):
    if not items:
        return "<div class='muted' style='padding:20px;'>No records found.</div>"
    html = '<div class="table-container"><table><thead><tr>'
    for col in columns:
        label = col[1] if isinstance(col, (list, tuple)) else col.replace("_", " ").upper()
        html += f'<th>{label}</th>'
    if area == "unknowns":
        html += '<th>ACTIONS</th>'
    html += '</tr></thead><tbody>'
    for item in items:
        html += '<tr>'
        for col in columns:
            key = col[0] if isinstance(col, (list, tuple)) else col
            value = item.get(key, "")
            cell_content = escape(str(value))
            if key == "accuracy":
                try:
                    acc = float(value) * 100
                    color = "var(--good)" if acc > 80 else ("var(--warn)" if acc > 50 else "var(--bad)")
                    cell_content = f'<div style="font-weight:700;">{acc:.1f}%</div><div style="width:60px; height:4px; background:rgba(255,255,255,0.05); border-radius:2px; margin-top:4px;"><div style="width:{acc}%; height:100%; background:{color}; border-radius:2px;"></div></div>'
                except: pass
            elif isinstance(value, str) and "T" in value and ("+" in value or "Z" in value):
                try:
                    dt = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
                    cell_content = f'<div style="white-space:nowrap; font-family:monospace; font-size:12px;">{dt.strftime("%d.%m.%Y")}</div><div class="muted" style="font-size:10px;">{dt.strftime("%H:%M")} UTC</div>'
                except: pass
            html += f'<td>{cell_content}</td>'
        
        if area == "unknowns":
            txt = escape(item.get("text", ""))
            html += f"""
            <td style="white-space:nowrap;">
              <button class="pill good" data-text="{txt}" onclick="promoteUnknown(this.getAttribute('data-text'))" style="padding:4px 8px; font-size:10px; border:none; cursor:pointer;"><i data-lucide="plus"></i> Add</button>
              <button class="pill" data-text="{txt}" onclick="dismissUnknown(this.getAttribute('data-text'))" style="padding:4px 8px; font-size:10px; border:none; cursor:pointer; background:rgba(255,255,255,0.05);"><i data-lucide="x"></i></button>
            </td>
            """
        html += '</tr>'
    html += '</tbody></table></div>'
    return html

@admin_management_bp.route("/")
@admin_required
def admin_dashboard():
    stats = admin_dashboard_stats()
    summary, dataset, evaluation = stats["summary"], stats["dataset"], stats["latest_evaluation"]

    cards = "".join([
        _admin_card("Accuracy", evaluation.get("accuracy", 0), "latest evaluation", icon="target"),
        _admin_card("Unknown", summary.get("unknown", 0), "active items", icon="help-circle"),
        _admin_card("Learning Queue", summary.get("active_learning", 0), "needs human label", icon="brain"),
        _admin_card("Feedback", summary.get("feedback", 0), "waiting for retrain", icon="message-square"),
        _admin_card("Lexicon", summary.get("lexicon_words", 0), "enabled words", icon="book"),
        _admin_card("Names", summary.get("name_hints", 0), "enabled hints", icon="users"),
        _admin_card("Training Runs", summary.get("training_runs", 0), "saved in SQLite", icon="database"),
        _admin_card("Dataset", dataset.get("dataset_rows", 0), "all rows", icon="layers"),
        _admin_card("Train / Test", f"{dataset.get('train_rows', 0)} / {dataset.get('test_rows', 0)}", "split ratio", icon="git-branch"),
    ])

    role = session.get("admin_role")
    controls_html = ""
    if role in ("owner", "super_admin"):
        controls_html = f"""
    <div class="panel" style="background: var(--panel-bg); border: 1px solid var(--panel-border); box-shadow: var(--panel-shadow); border-radius: 24px; overflow: hidden; position: relative; margin-bottom: 32px;">
      <div style="position: absolute; top: 0; left: 0; width: 100%; height: 5px; background: linear-gradient(90deg, var(--accent) 0%, #ff4d4d 100%); opacity: 0.8;"></div>
      <div style="padding: 28px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 28px;">
          <div><h2 style="margin:0; font-size: 22px; color: var(--ink); font-weight: 800; display: flex; align-items: center; gap: 10px;"><i data-lucide="settings-2" style="color:var(--accent); width:24px; height:24px;"></i> System Control Center</h2><p class="muted" style="margin: 6px 0 0 0; font-size: 13px;">Management of linguistic models and system integrity.</p></div>
          <div class="pill" style="background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent); font-weight: 700; font-size: 10px; letter-spacing: 0.05em; display: flex; align-items: center; gap: 4px;"><i data-lucide="shield-check" style="width:12px;"></i> SECURE ADMIN MODE</div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 24px;">
          <div style="background: var(--solid-input-bg); border: 1px solid var(--panel-border); border-radius: 18px; padding: 20px; opacity: 0.9;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; color: var(--accent);"><i data-lucide="zap" style="width:16px; height:16px;"></i><span style="font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em;">Pipeline Operations</span></div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
              <button onclick="runAdminAction('/admin/actions/seed')" style="background: var(--panel-bg); border: 1px solid var(--panel-border); height: 44px; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 13px;"><i data-lucide="sprout" style="width:16px; height:16px;"></i> <span>Seed</span></button>
              <button onclick="runAdminAction('/admin/actions/rebuild')" style="background: var(--panel-bg); border: 1px solid var(--panel-border); height: 44px; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 13px;"><i data-lucide="database" style="width:16px; height:16px;"></i> <span>Rebuild</span></button>
              <button class="primary" onclick="runAdminAction('/admin/actions/train')" style="grid-column: span 2; height: 48px; display: flex; align-items: center; justify-content: center; gap: 10px; font-weight: 800;"><i data-lucide="play" style="width:18px; height:18px;"></i> <span>START SYSTEM TRAINING</span></button>
            </div>
          </div>
          <div style="background: rgba(229, 62, 62, 0.03); border: 1px solid rgba(229, 62, 62, 0.1); border-radius: 18px; padding: 20px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; color: #e53e3e;"><i data-lucide="alert-triangle" style="width:16px; height:16px;"></i><span style="font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em;">Danger Zone</span></div>
            <div style="display: flex; flex-direction: column; gap: 12px;">
              <div style="display: flex; gap: 10px;">
                <button onclick="downloadBackup()" style="flex: 1; background: var(--panel-bg); border: 1px solid rgba(229, 62, 62, 0.2); height: 48px; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 13px; font-weight: 700; color: #e53e3e; border-radius: 12px;"><i data-lucide="download" style="width:16px; height:16px;"></i> <span>Backup JSON</span></button>
                <button onclick="window.location.href='/admin/actions/download-db'" style="flex: 1; background: var(--panel-bg); border: 1px solid rgba(229, 62, 62, 0.2); height: 48px; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 13px; font-weight: 700; color: #e53e3e; border-radius: 12px;"><i data-lucide="database" style="width:16px; height:16px;"></i> <span>Download DB</span></button>
              </div>
              <div style="display: flex; gap: 10px;">
                <label class="button" style="flex: 1; height: 48px; display: flex; align-items: center; justify-content: center; cursor: pointer; background: var(--panel-bg); border: 1px solid rgba(229, 62, 62, 0.2); font-size: 13px; font-weight: 700; margin: 0; padding: 0; color: #e53e3e; gap: 8px; border-radius: 12px;"><i data-lucide="upload" style="width:16px; height:16px;"></i> <span>Restore JSON</span><input type="file" id="restore-file" style="display:none;" onchange="uploadRestore(this)"></label>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                <button class="bad" style="font-size: 12px; font-weight: 700; height: 48px; display: flex; align-items: center; justify-content: center; gap: 8px; background: rgba(229, 62, 62, 0.05); border-radius: 12px; border: 1px solid rgba(229, 62, 62, 0.1);" onclick="runWipeAction('learning')"><i data-lucide="trash-2" style="width:16px; height:16px;"></i> <span>Wipe Queue</span></button>
                <button class="bad" style="font-size: 12px; font-weight: 800; height: 48px; display: flex; align-items: center; justify-content: center; gap: 8px; background: #e53e3e; color: white; border: none; border-radius: 12px; box-shadow: 0 4px 12px rgba(229, 62, 62, 0.2);" onclick="runWipeAction('all')"><i data-lucide="skull" style="width:16px; height:16px;"></i> <span>FACTORY RESET</span></button>
              </div>
            </div>
          </div>
        </div>
        <div id="action-status" class="status" style="margin-top: 20px; font-weight: 700; font-size: 13px; display: flex; align-items: center; gap: 10px; color: var(--ink);"></div>
        <pre id="action-output" style="margin-top: 12px; font-family: 'JetBrains Mono', monospace; font-size: 11px; max-height: 150px; overflow: auto; border-radius: 12px; background: var(--solid-input-bg); padding: 14px; display: none; border: 1px solid var(--panel-border); color: var(--ink); opacity: 0.8;"></pre>
      </div>
    </div>
    """
    body = f"""
    <div class="grid" style="grid-template-columns: 1fr; gap: 24px;">{controls_html}</div>
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">{cards}</div>
    <div class="grid">
      <div class="panel"><h2><i data-lucide="message-square" style="width:20px; height:20px; vertical-align:middle; margin-right:10px;"></i>Recent Feedback</h2>{_rows(stats["recent_feedback"], [("id", "ID"), ("text", "Text"), ("lang", "Lang"), ("source", "Source"), ("promoted", "Promoted"), ("created_at", "Created")])}</div>
      <div class="panel"><h2><i data-lucide="help-circle" style="width:20px; height:20px; vertical-align:middle; margin-right:10px;"></i>Recent Unknowns</h2>{_rows(stats["recent_unknowns"], [("text", "Text"), ("count", "Count")], area="unknowns")}</div>
    </div>
    <div class="panel"><h2><i data-lucide="brain" style="width:20px; height:20px; vertical-align:middle; margin-right:10px;"></i>Active Learning Queue</h2>{_rows(stats["recent_learning_items"], [("id", "ID"), ("text", "Text"), ("suggested_language", "Suggested"), ("confidence", "Confidence"), ("reason", "Reason")], area="unknowns")}</div>
    """
    return page("Admin Dashboard", body, area="admin")

# --- Views: Other Admin Pages ---

@admin_management_bp.route("/benchmark")
@admin_required
def benchmark_view():
    report = run_benchmark(limit=250)
    acc = report.get("accuracy", 0) * 100
    color = "var(--good)" if acc > 80 else ("var(--warn)" if acc > 50 else "var(--bad)")
    html = f"""
    <div class="panel">
      <h3><i data-lucide="gauge"></i> Engine Benchmark</h3>
      <div style="font-size:24px; font-weight:800; color:{color}; margin-bottom:12px;">Accuracy: {acc:.1f}%</div>
      <div id="quality-stats"></div>
    </div>
    """
    return page("Benchmarking", html, area="admin")

@admin_management_bp.route("/characters")
@admin_required
def characters_view():
    profiles = load_character_profiles()
    rows = ""
    for lang, p in profiles.items():
        chars = p.get("signature", "")
        rows += f"<tr><td style='font-weight:800; font-family:monospace; color:var(--accent);'>{lang.upper()}</td><td style='font-size:16px; letter-spacing:4px; font-family:\"Fira Code\", monospace; line-height:1.8;'>{chars}</td><td><span class='pill good' style='font-size:10px;'>{len(p.get('unique_characters', []))} UNIQUE SYMBOLS</span></td></tr>"
    html = f"""
    <div class="panel">
      <h3><i data-lucide="type"></i> Character Signatures</h3>
      <div class="table-container">
        <table style="width:100%; border-collapse:collapse;">
          <thead>
            <tr style="border-bottom: 2px solid var(--panel-border);">
              <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Language</th>
              <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Signature Pattern</th>
              <th style="text-align:left; padding:20px 24px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Status</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>
    """
    return page("Character Signatures", html, area="admin")

@admin_management_bp.route("/logs")
@admin_required
def logs_view():
    html = """
    <div class="panel">
      <h3><i data-lucide="terminal"></i> System Logs</h3>
      <div id="log-content" style="height:600px; overflow-y:auto; background:var(--sidebar-bg); border-radius:12px; border:1px solid var(--panel-border); padding:16px; font-family:'Fira Code', monospace; font-size:12px; line-height:1.5;"></div>
    </div>
    """
    return page("System Logs", html, area="admin")

@admin_management_bp.route("/safety")
def safety_view():
    area = "admin" if admin_authenticated() else "public"
    html = """
    <div class="panel">
      <h3><i data-lucide="shield-alert"></i> Safety Policy</h3>
      <p>ELD PRO ensures that user inputs are securely processed. We do not store queries permanently without consent.</p>
    </div>
    """
    return page("Safety Policy", html, area=area)

@admin_management_bp.route("/model-card")
@admin_required
def model_card_view():
    card = get_model_card()
    
    name = escape(card.get("name", "European Language Detector"))
    version = escape(card.get("version", "local-mvp"))
    model_path = escape(card.get("model_path", "models/profiles.json"))
    task = escape(card.get("task", "Detect popular European languages"))
    languages = card.get("languages", [])
    
    langs_html = ""
    for lang in languages:
        code = escape(lang.get("code", ""))
        lang_name = escape(lang.get("name", ""))
        lingua = escape(lang.get("lingua", ""))
        langs_html += f"""
        <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border); border-radius: 12px; padding: 12px; display: flex; flex-direction: column; gap: 4px; transition: transform 0.2s, background 0.2s; cursor: default;" onmouseover="this.style.background='rgba(59, 130, 246, 0.08)'; this.style.transform='translateY(-2px)';" onmouseout="this.style.background='rgba(255,255,255,0.03)'; this.style.transform='translateY(0)';">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong style="color: var(--accent); font-size: 14px;">{lang_name}</strong>
                <span style="font-family: monospace; font-size: 10px; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 6px;">{code.upper()}</span>
            </div>
            <div style="font-size: 11px; color: var(--muted); display: flex; align-items: center; gap: 4px;">
                <i data-lucide="cpu" style="width: 10px; height: 10px;"></i> Lingua: {lingua}
            </div>
        </div>
        """

    html = f"""
    <div style="display: flex; flex-direction: column; gap: 24px;">
        <div class="panel" style="background: linear-gradient(145deg, rgba(30,41,59,0.7) 0%, rgba(15,23,42,0.9) 100%); border: 1px solid rgba(255,255,255,0.05); position: relative; overflow: hidden; padding: 32px;">
            <div style="position: absolute; top: -50%; right: -10%; width: 300px; height: 300px; background: radial-gradient(circle, rgba(59,130,246,0.15) 0%, rgba(0,0,0,0) 70%); border-radius: 50%; pointer-events: none;"></div>
            
            <div style="display: flex; align-items: flex-start; gap: 24px; position: relative; z-index: 1;">
                <div style="width: 72px; height: 72px; background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.2); border-radius: 20px; display: flex; align-items: center; justify-content: center; color: var(--accent); flex-shrink: 0; box-shadow: 0 10px 25px -5px rgba(59,130,246,0.2);">
                    <i data-lucide="box" style="width: 36px; height: 36px;"></i>
                </div>
                <div>
                    <h2 style="margin: 0 0 8px 0; font-size: 32px; font-weight: 800; letter-spacing: -0.03em; color: white;">{name}</h2>
                    <p style="margin: 0; color: var(--muted); font-size: 15px; line-height: 1.6;">{task}</p>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-top: 36px; position: relative; z-index: 1;">
                <div style="background: rgba(0,0,0,0.2); border-radius: 16px; padding: 20px; border: 1px solid rgba(255,255,255,0.04); backdrop-filter: blur(10px);">
                    <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; letter-spacing: 0.1em;">Version</div>
                    <div style="font-size: 20px; font-weight: 700; color: var(--good); display: flex; align-items: center; gap: 10px;">
                        <i data-lucide="git-branch" style="width: 18px; height: 18px;"></i> {version}
                    </div>
                </div>
                <div style="background: rgba(0,0,0,0.2); border-radius: 16px; padding: 20px; border: 1px solid rgba(255,255,255,0.04); backdrop-filter: blur(10px);">
                    <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; letter-spacing: 0.1em;">Engine Status</div>
                    <div style="font-size: 20px; font-weight: 700; color: var(--accent); display: flex; align-items: center; gap: 10px;">
                        <i data-lucide="activity" style="width: 18px; height: 18px;"></i> Active
                    </div>
                </div>
                <div style="background: rgba(0,0,0,0.2); border-radius: 16px; padding: 20px; border: 1px solid rgba(255,255,255,0.04); backdrop-filter: blur(10px);">
                    <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; letter-spacing: 0.1em;">Path Storage</div>
                    <div style="font-size: 13px; font-family: 'Fira Code', monospace; font-weight: 500; color: var(--ink); word-break: break-all; opacity: 0.8; margin-top: 4px;">
                        {model_path}
                    </div>
                </div>
            </div>
        </div>

        <div class="panel">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                <h3 style="margin: 0; display: flex; align-items: center; gap: 12px; font-size: 22px;">
                    <i data-lucide="globe" style="width: 24px; height: 24px; color: var(--accent);"></i>
                    Supported Languages <span class="pill" style="margin-left: 8px; background: rgba(59,130,246,0.1); color: var(--accent); border: 1px solid rgba(59,130,246,0.2);">{len(languages)} Total</span>
                </h3>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px;">
                {langs_html}
            </div>
        </div>
    </div>
    """
    return page("Model Card", html, area="admin")

@admin_management_bp.route("/corpus")
@admin_required
def corpus_manager_view():
    html = """
    <div class="panel">
      <h3><i data-lucide="database"></i> Corpus Manager</h3>
      <div id="corpus-list"></div>
    </div>
    """
    return page("Corpus Manager", html, area="admin")

@admin_management_bp.route("/groups")
@admin_required
def groups_view():
    from src.european_languages import EUROPEAN_LANGUAGE_SPECS
    
    # Explicit mapping since the original specs lack genealogical data
    FAMILIES = {
        "ca": "Romance", "fr": "Romance", "it": "Romance", "pt": "Romance", "ro": "Romance", "es": "Romance",
        "da": "Germanic", "nl": "Germanic", "en": "Germanic", "de": "Germanic", "is": "Germanic", "nb": "Germanic", "nn": "Germanic", "sv": "Germanic",
        "be": "Slavic", "bs": "Slavic", "bg": "Slavic", "hr": "Slavic", "cs": "Slavic", "mk": "Slavic", "pl": "Slavic", "ru": "Slavic", "sr": "Slavic", "sk": "Slavic", "sl": "Slavic", "uk": "Slavic",
        "ga": "Celtic", "cy": "Celtic",
        "lv": "Baltic", "lt": "Baltic",
        "el": "Hellenic",
        "sq": "Albanian",
        "hy": "Armenian",
        "et": "Uralic", "fi": "Uralic", "hu": "Uralic",
        "az": "Turkic", "tr": "Turkic",
        "eu": "Language Isolate",
        "ka": "Kartvelian"
    }

    groups = {}
    for spec in EUROPEAN_LANGUAGE_SPECS:
        fam = FAMILIES.get(spec['code'], 'Unknown')
        groups.setdefault(fam, []).append(spec)
    
    html = f"""
    <div style="margin-bottom: 24px;">
        <h2 style="font-size: 28px; font-weight: 800; margin-bottom: 8px; color: var(--ink); letter-spacing:-0.02em;">Linguistic Families</h2>
        <p class="muted" style="margin: 0; font-size:15px;">Categorization of the supported languages by their genealogical language families.</p>
    </div>
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px;">
    """
    
    family_colors = {
        "Romance": "#f43f5e",
        "Germanic": "var(--accent)",
        "Slavic": "var(--good)",
        "Celtic": "#14b8a6",
        "Baltic": "#8b5cf6",
        "Hellenic": "#0ea5e9",
        "Albanian": "#f59e0b",
        "Armenian": "#d946ef",
        "Uralic": "#84cc16",
        "Turkic": "var(--warn)",
        "Language Isolate": "#ec4899",
        "Kartvelian": "#06b6d4",
        "Unknown": "var(--muted)"
    }
    
    for fam, langs in groups.items():
        color = family_colors.get(fam, "var(--accent)")
        html += f"""
        <div class="panel" style="border-top: 4px solid {color}; padding: 0; overflow: hidden; display: flex; flex-direction: column;">
            <div style="padding: 24px 24px 20px 24px; background: linear-gradient(180deg, {color}11 0%, rgba(0,0,0,0) 100%);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; font-size: 20px; font-weight:800; display: flex; align-items: center; gap: 10px;">
                        <i data-lucide="network" style="width: 20px; height: 20px; color: {color};"></i>
                        {fam}
                    </h3>
                    <span class="pill" style="background: {color}22; color: {color}; border: 1px solid {color}44; font-weight:800; font-size:11px;">{len(langs)} LANGUAGES</span>
                </div>
            </div>
            <div style="padding: 0 24px 24px 24px; flex: 1;">
                <ul style="list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px;">
        """
        for l in langs:
            html += f"""
                    <li style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: rgba(255,255,255,0.02); border: 1px solid var(--panel-border); border-radius: 12px; transition: all 0.2s; cursor: default;" onmouseover="this.style.transform='translateX(6px)'; this.style.borderColor='{color}44'; this.style.background='rgba(255,255,255,0.04)';" onmouseout="this.style.transform='translateX(0)'; this.style.borderColor='var(--panel-border)'; this.style.background='rgba(255,255,255,0.02)';">
                        <span style="font-weight: 700; font-size:15px; color:var(--ink);">{l['name']}</span>
                        <span style="font-family: 'Fira Code', monospace; font-size: 11px; font-weight: 800; color: {color}; background: {color}15; padding: 4px 10px; border-radius: 8px;">{l['code'].upper()}</span>
                    </li>
            """
        html += """
                </ul>
            </div>
        </div>
        """
    html += "</div>"
    return page("Language Groups", html, area="admin")

@admin_management_bp.route("/quality")
@admin_required
def quality_view():
    html = """
    <div class="panel">
      <h3><i data-lucide="shield-check"></i> Dataset Quality Assurance</h3>
      <div id="quality-stats"></div>
    </div>
    <div class="panel">
      <h3><i data-lucide="alert-triangle"></i> Ambiguity Analysis</h3>
      <div id="ambiguity-stats"></div>
    </div>
    """
    return page("Data Quality", html, area="admin")

@admin_management_bp.route("/quality.json")
@admin_required
def quality_json():
    try:
        from src.data_quality import evaluate_dataset
        stats = evaluate_dataset()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)})

@admin_management_bp.route("/report")
@admin_required
def report_view():
    from src.storage import _latest_evaluation_report
    report = _latest_evaluation_report()
    
    if not report:
        html = """
        <div class="panel" style="text-align:center; padding:80px 20px;">
            <div style="width: 80px; height: 80px; background: rgba(59,130,246,0.1); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 24px; color: var(--accent);">
                <i data-lucide="file-warning" style="width: 40px; height: 40px;"></i>
            </div>
            <h2 style="margin:0 0 12px 0; font-size:28px;">No Evaluation Report Found</h2>
            <p class="muted">Run a benchmark or full training cycle to generate performance metrics.</p>
            <button class="primary" onclick="window.location.href='/admin/benchmark'" style="margin-top:24px;"><i data-lucide="play"></i> Go to Benchmark</button>
        </div>
        """
        return page("Evaluation Report", html, area="admin")
        
    acc = round(report.get("accuracy", 0) * 100, 2)
    samples = report.get("samples", 0)
    dataset_path = escape(str(report.get("dataset", "Unknown")))
    
    by_lang = report.get("by_language", {})
    
    labels = list(by_lang.keys())
    accuracies = [round(by_lang[l]["accuracy"] * 100, 2) for l in labels]
    
    html = f"""
    <div style="display: flex; flex-direction: column; gap: 24px;">
        <div style="background: linear-gradient(135deg, rgba(16,185,129,0.1) 0%, rgba(0,0,0,0) 100%); border-radius: 24px; padding: 32px; border: 1px solid rgba(16,185,129,0.2);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 32px;">
                <div style="display: flex; align-items: center; gap: 20px;">
                    <div style="width: 64px; height: 64px; background: rgba(16,185,129,0.15); border-radius: 20px; display: flex; align-items: center; justify-content: center; color: var(--good); box-shadow: 0 10px 25px -5px rgba(16,185,129,0.2);">
                        <i data-lucide="file-bar-chart" style="width: 32px; height: 32px;"></i>
                    </div>
                    <div>
                        <h2 style="margin: 0 0 8px 0; font-size: 32px; font-weight: 800; color: white; letter-spacing:-0.03em;">Model Evaluation Report</h2>
                        <p class="muted" style="margin: 0; font-size: 15px;">Detailed metrics on model performance from the latest benchmark run.</p>
                    </div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
                <div style="background: rgba(0,0,0,0.2); border-radius: 16px; padding: 20px; border: 1px solid rgba(255,255,255,0.04);">
                    <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--muted); margin-bottom: 8px;">Overall Accuracy</div>
                    <div style="font-size: 28px; font-weight: 800; color: var(--good);">{acc}%</div>
                </div>
                <div style="background: rgba(0,0,0,0.2); border-radius: 16px; padding: 20px; border: 1px solid rgba(255,255,255,0.04);">
                    <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--muted); margin-bottom: 8px;">Total Samples Tested</div>
                    <div style="font-size: 28px; font-weight: 800; color: white;">{samples:,}</div>
                </div>
                <div style="background: rgba(0,0,0,0.2); border-radius: 16px; padding: 20px; border: 1px solid rgba(255,255,255,0.04);">
                    <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--muted); margin-bottom: 8px;">Dataset Source</div>
                    <div style="font-size: 13px; font-family: 'Fira Code', monospace; color: var(--accent); margin-top: 10px; word-break: break-all;">{dataset_path}</div>
                </div>
            </div>
        </div>
        
        <div class="panel">
            <h3 style="margin-top: 0; display:flex; align-items:center; gap:10px;"><i data-lucide="bar-chart-2" style="color:var(--accent);"></i> Per-Class Accuracy</h3>
            <div style="height: 400px; width: 100%; position: relative;">
                <canvas id="accuracyChart"></canvas>
            </div>
        </div>
    </div>
    
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        if(typeof Chart === 'undefined') return;
        const ctx = document.getElementById('accuracyChart').getContext('2d');
        const labels = {json.dumps(labels)};
        const data = {json.dumps(accuracies)};
        
        const bgColors = data.map(val => val > 90 ? 'rgba(16, 185, 129, 0.6)' : (val > 70 ? 'rgba(245, 158, 11, 0.6)' : 'rgba(239, 68, 68, 0.6)'));
        const borderColors = data.map(val => val > 90 ? 'rgb(16, 185, 129)' : (val > 70 ? 'rgb(245, 158, 11)' : 'rgb(239, 68, 68)'));

        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: labels.map(l => l.toUpperCase()),
                datasets: [{{
                    label: 'Accuracy (%)',
                    data: data,
                    backgroundColor: bgColors,
                    borderColor: borderColors,
                    borderWidth: 1,
                    borderRadius: 6
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleFont: {{ family: 'Outfit', size: 14 }},
                        bodyFont: {{ family: 'Inter', size: 13 }},
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        grid: {{ color: 'rgba(255,255,255,0.05)' }},
                        ticks: {{ color: '#94a3b8', font: {{ family: 'Inter' }} }}
                    }},
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ color: '#94a3b8', font: {{ family: 'Fira Code, monospace', size: 11, weight: 'bold' }} }}
                    }}
                }}
            }}
        }});
    }});
    </script>
    """
    return page("Evaluation Report", html, area="admin")

@admin_management_bp.route("/frequency")
@admin_required
def frequency_view():
    from src.character_profiles import load_character_profiles
    profiles = load_character_profiles()
    
    default_lang = 'en' if 'en' in profiles else (list(profiles.keys())[0] if profiles else '')
    
    html = f"""
    <div style="margin-bottom: 24px;">
        <h2 style="font-size: 28px; font-weight: 800; margin-bottom: 8px; color: var(--ink); letter-spacing:-0.02em;">N-Gram Frequency Analysis</h2>
        <p class="muted" style="margin: 0; font-size:15px;">Explore the most common character sequences (trigrams) that define each language's unique signature.</p>
    </div>
    """
    
    if not profiles:
        html += """
        <div class="panel" style="text-align:center; padding:64px;"><p class="muted">No character profiles found. Please generate them first.</p></div>
        """
        return page("Frequency Analysis", html, area="admin")
        
    lang_opts = "\n".join(f"<option value='{k}'>{k.upper()}</option>" for k in sorted(profiles.keys()))
    
    js_data = {}
    for lang, data in profiles.items():
        trigrams = data.get("trigrams", {})
        top = sorted(trigrams.items(), key=lambda x: x[1], reverse=True)[:20]
        js_data[lang] = {
            "labels": [t[0].replace(' ', '␣') for t in top],
            "values": [t[1] for t in top]
        }
        
    html += f"""
    <div class="panel" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px;">
        <h3 style="margin:0; display:flex; align-items:center; gap:10px;"><i data-lucide="bar-chart-3" style="color:var(--accent);"></i> Top Trigrams</h3>
        <select id="lang-select" style="width: 200px; font-weight:bold; background: var(--input-bg); border: 1px solid var(--panel-border); border-radius: 8px; padding: 8px 12px; color: var(--ink);">
            {lang_opts}
        </select>
    </div>
    <div class="panel">
        <div style="height: 400px; width: 100%;">
            <canvas id="freqChart"></canvas>
        </div>
    </div>
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        if(typeof Chart === 'undefined') return;
        const profilesData = {json.dumps(js_data)};
        const select = document.getElementById('lang-select');
        select.value = '{default_lang}';
        
        const ctx = document.getElementById('freqChart').getContext('2d');
        let chart = new Chart(ctx, {{
            type: 'bar',
            data: {{ labels: [], datasets: [] }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{ backgroundColor: 'rgba(15,23,42,0.9)' }}
                }},
                scales: {{
                    y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#94a3b8' }} }},
                    x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8', font: {{ family: 'Fira Code, monospace', size: 14, weight: 'bold' }} }} }}
                }}
            }}
        }});
        
        function updateChart() {{
            const lang = select.value;
            const data = profilesData[lang];
            if(!data) return;
            
            chart.data.labels = data.labels;
            chart.data.datasets = [{{
                label: 'Relative Frequency',
                data: data.values,
                backgroundColor: 'rgba(59, 130, 246, 0.5)',
                borderColor: 'rgb(59, 130, 246)',
                borderWidth: 1,
                borderRadius: 4
            }}];
            chart.update();
        }}
        
        select.addEventListener('change', updateChart);
        updateChart();
    }});
    </script>
    """
    
    return page("Frequency Analysis", html, area="admin")

@admin_management_bp.route("/runs")
@admin_required
def runs_view():
    from src.storage import list_training_runs
    runs = list_training_runs(limit=50)
    
    html = f"""
    <div style="margin-bottom: 24px;">
        <h2 style="font-size: 28px; font-weight: 800; margin-bottom: 8px; color: var(--ink); letter-spacing:-0.02em;">Training History</h2>
        <p class="muted" style="margin: 0; font-size:15px;">Log of all model optimization and evaluation runs.</p>
    </div>
    """
    
    if not runs:
        html += """
        <div class="panel" style="text-align:center; padding:64px 20px;">
            <div style="width: 80px; height: 80px; background: rgba(255,255,255,0.05); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 24px; color: var(--muted);">
                <i data-lucide="history" style="width: 40px; height: 40px;"></i>
            </div>
            <h3 style="margin:0 0 12px 0; font-size:24px;">No Training Runs Recorded</h3>
            <p class="muted">Start a training cycle or benchmark to populate this history.</p>
        </div>
        """
    else:
        cols = [
            ("id", "Run ID"),
            ("kind", "Type"),
            ("samples", "Samples"),
            ("accuracy", "Accuracy"),
            ("created_at", "Date")
        ]
        html += _rows(runs, cols, area="runs")
    
    return page("Training Runs", html, area="admin")
