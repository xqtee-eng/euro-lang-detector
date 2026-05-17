from flask import Blueprint, request, jsonify
from api.utils import page, admin_required, language_options
from src.word_lexicon import (
    list_lexicon_entries, add_lexicon_word, delete_lexicon_word,
    import_lexicon_words, analyze_word_knowledge, list_lexicon_words
)
from src.name_detector import (
    list_name_hints, add_name_hint, delete_name_hint, detect_name
)
from src.self_learning import clear_unknown_items
from src.european_languages import SUPPORTED_LANGUAGE_CODES

lexicon_bp = Blueprint('lexicon', __name__)

@lexicon_bp.route("/lexicon")
@admin_required
def lexicon_form():
    return page(
        "Lexicon Manager",
        f"""
    <div class="panel">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px;">
        <div>
          <h3><i data-lucide="book-open"></i> Terminology Lexicon</h3>
          <p class="muted">Deterministic matching for known European terminology and word lists.</p>
        </div>
        <div class="toolbar">
          <input id="search" placeholder="Search Lexicon..." oninput="loadLexicon()" style="max-width:200px;">
          <button class="primary" onclick="loadLexicon()"><i data-lucide="refresh-cw"></i> Refresh</button>
        </div>
      </div>
      
      <div style="background:var(--solid-input-bg); padding:24px; border-radius:24px; border:1px solid var(--panel-border); margin-bottom:32px;">
        <div style="display:grid; grid-template-columns: 220px 2fr 100px 1.5fr; gap:24px; margin-bottom:24px;">
          <select id="lang" style="width:100%;">{language_options()}</select>
          <input id="word" placeholder="Target Word">
          <input id="frequency" type="number" min="1" step="1" value="1" title="Frequency Score">
          <input id="notes" placeholder="Optional Notes">
        </div>
        <textarea id="bulk" placeholder="Bulk Import: Paste many words here (one per line or space-separated)" style="min-height: 120px; margin-bottom:24px;"></textarea>
        <div style="display:flex; gap:12px; align-items:center;">
          <button class="primary" onclick="addWord()"><i data-lucide="plus"></i> Add Entry</button>
          <button onclick="importWords()"><i data-lucide="upload-cloud"></i> Bulk Import</button>
          <button onclick="analyzeWord()"><i data-lucide="zap"></i> Global Analysis</button>
          <span id="status" class="status" style="margin-left:auto;"></span>
        </div>
      </div>
    </div>

    <div class="panel" style="padding:0; overflow:hidden;">
      <div id="lexicon"></div>
    </div>

    <div class="panel" style="border: 1px solid var(--panel-border); padding:32px;">
      <div style="display:flex; align-items:center; gap:12px; margin-bottom:24px;">
        <div style="width:40px; height:40px; background:rgba(59, 130, 246, 0.1); border-radius:12px; display:flex; align-items:center; justify-content:center; color:var(--accent);">
          <i data-lucide="brain-circuit" style="width:20px; height:20px;"></i>
        </div>
        <h3 style="margin:0; font-family:'Outfit'; font-size:20px;">Knowledge Extraction</h3>
      </div>
      
      <div id="word-analysis-container" style="min-height:100px; display:flex; flex-direction:column; gap:16px;">
        <div class="muted" style="text-align:center; padding:40px; border: 2px dashed var(--panel-border); border-radius:20px; font-weight:600; font-size:13px;">
          <i data-lucide="search" style="width:24px; margin-bottom:12px; opacity:0.5;"></i><br>
          Enter a term above and click Global Analysis to extract linguistic intelligence.
        </div>
      </div>
    </div>

    </div>
    """,
        area="admin",
    )

@lexicon_bp.route("/names")
@admin_required
def names_form():
    return page(
        "Name Manager",
        f"""
    <div class="panel">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px;">
        <div>
          <h3><i data-lucide="user-check"></i> Entity Name Registry</h3>
          <p class="muted">Manage person and location names for contextual classification hints.</p>
        </div>
        <div class="toolbar">
          <input id="search" placeholder="Search Entities..." oninput="loadNames()" style="max-width:200px;">
          <button class="primary" onclick="loadNames()"><i data-lucide="refresh-cw"></i> Refresh</button>
        </div>
      </div>

      <div style="background:var(--solid-input-bg); padding:24px; border-radius:24px; border:1px solid var(--panel-border); margin-bottom:32px;">
        <div style="display:grid; grid-template-columns: 220px 1.5fr 1fr 140px 100px; gap:24px; margin-bottom:24px;">
          <select id="lang" style="width:100%;">{language_options()}</select>
          <input id="name" placeholder="Entity Name">
          <input id="country" placeholder="Origin Country">
          <input id="name_type" placeholder="Type" value="person">
          <input id="confidence" type="number" min="0.01" max="1" step="0.01" value="0.9" title="Confidence">
        </div>
        <div style="display:flex; gap:12px; align-items:center;">
          <button class="primary" onclick="addName()"><i data-lucide="plus"></i> Register Entity</button>
          <button onclick="analyzeName()"><i data-lucide="shield"></i> Identity Check</button>
          <span id="status" class="status" style="margin-left:auto;"></span>
        </div>
      </div>
    </div>

    <div class="panel" style="padding:0; overflow:hidden;">
      <div id="names"></div>
    </div>

    <div class="panel" style="border: 1px solid var(--panel-border); padding:32px;">
      <div style="display:flex; align-items:center; gap:12px; margin-bottom:24px;">
        <div style="width:40px; height:40px; background:rgba(52, 211, 153, 0.1); border-radius:12px; display:flex; align-items:center; justify-content:center; color:var(--good);">
          <i data-lucide="fingerprint" style="width:20px; height:20px;"></i>
        </div>
        <h3 style="margin:0; font-family:'Outfit'; font-size:20px;">Identity Logic</h3>
      </div>
      
      <div id="name-analysis-container" style="min-height:100px; display:flex; flex-direction:column; gap:16px;">
        <div class="muted" style="text-align:center; padding:40px; border: 2px dashed var(--panel-border); border-radius:20px; font-weight:600; font-size:13px;">
          <i data-lucide="shield" style="width:24px; margin-bottom:12px; opacity:0.5;"></i><br>
          Run an Identity Check on any entity name to visualize classification logic.
        </div>
      </div>
    </div>
    """,
        area="admin",
    )

@lexicon_bp.route("/learn")
@admin_required
def learning_view():
    html = """
    <div style="display: flex; flex-direction: column; gap: 24px;">
        <div style="background: linear-gradient(135deg, rgba(139,92,246,0.1) 0%, rgba(0,0,0,0) 100%); border-radius: 24px; padding: 32px; border: 1px solid rgba(139,92,246,0.2);">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 20px;">
                    <div style="width: 64px; height: 64px; background: rgba(139,92,246,0.15); border-radius: 20px; display: flex; align-items: center; justify-content: center; color: #8b5cf6; box-shadow: 0 10px 25px -5px rgba(139,92,246,0.2);">
                        <i data-lucide="brain-circuit" style="width: 32px; height: 32px;"></i>
                    </div>
                    <div>
                        <h2 style="margin: 0 0 8px 0; font-size: 32px; font-weight: 800; color: white;">Active Learning Queue</h2>
                        <p class="muted" style="margin: 0; font-size: 15px;">Automated refinement based on high-confidence predictions. The system automatically promotes these when thresholds are met.</p>
                    </div>
                </div>
                <button class="primary" style="background:#8b5cf6; border-color:#8b5cf6;"><i data-lucide="zap"></i> Process Queue</button>
            </div>
        </div>
        
        <div class="panel">
            <h3 style="margin-top:0; font-size:18px; font-weight:800; display:flex; align-items:center; gap:8px;"><i data-lucide="list" style="color:var(--accent);"></i> Pending Items</h3>
            <p class="muted" style="margin-bottom:24px;">Items queued for automated promotion.</p>
            <div class="muted" style="text-align:center; padding:40px; border: 2px dashed var(--panel-border); border-radius:20px;">
                <i data-lucide="check-circle" style="width:32px; height:32px; margin-bottom:16px; opacity:0.5;"></i><br>
                <strong style="color:var(--ink); font-size:16px;">Queue is empty</strong><br>
                All high-confidence items have been processed.
            </div>
        </div>
    </div>
    """
    return page("Active Learning", html, area="admin")

@lexicon_bp.route("/review")
@admin_required
def review_view():
    html = """
    <div style="display: flex; flex-direction: column; gap: 24px;">
        <div style="background: linear-gradient(135deg, rgba(239,68,68,0.1) 0%, rgba(0,0,0,0) 100%); border-radius: 24px; padding: 32px; border: 1px solid rgba(239,68,68,0.2);">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 20px;">
                    <div style="width: 64px; height: 64px; background: rgba(239,68,68,0.15); border-radius: 20px; display: flex; align-items: center; justify-content: center; color: var(--bad); box-shadow: 0 10px 25px -5px rgba(239,68,68,0.2);">
                        <i data-lucide="eye" style="width: 32px; height: 32px;"></i>
                    </div>
                    <div>
                        <h2 style="margin: 0 0 8px 0; font-size: 32px; font-weight: 800; color: white;">Manual Audit</h2>
                        <p class="muted" style="margin: 0; font-size: 15px;">Human verification for ambiguous or unknown linguistic patterns identified by the model.</p>
                    </div>
                </div>
                <button class="primary" onclick="window.location.href='/admin'" style="background:var(--bad); border-color:var(--bad);"><i data-lucide="arrow-right"></i> Go to Dashboard</button>
            </div>
        </div>
        
        <div class="panel">
            <h3 style="margin-top:0; font-size:18px; font-weight:800; display:flex; align-items:center; gap:8px;"><i data-lucide="inbox" style="color:var(--accent);"></i> Needs Review</h3>
            <p class="muted" style="margin-bottom:24px;">Please review these items on the <a href="/admin" style="color:var(--accent);">Admin Dashboard</a> under "Recent Unknowns".</p>
            <div class="muted" style="text-align:center; padding:40px; border: 2px dashed var(--panel-border); border-radius:20px;">
                <i data-lucide="shield-check" style="width:32px; height:32px; margin-bottom:16px; opacity:0.5;"></i><br>
                <strong style="color:var(--ink); font-size:16px;">All Caught Up</strong><br>
                No pending manual reviews at this time.
            </div>
        </div>
    </div>
    """
    return page("Review Unknown Texts", html, area="admin")

@lexicon_bp.route("/lexicon/items")
@admin_required
def lexicon_items_api():
    query = request.args.get("query", "")
    language = request.args.get("lang", "")
    return jsonify({"lexicons": list_lexicon_words(query=query, language=language)})

@lexicon_bp.route("/lexicon/entries")
@admin_required
def lexicon_entries_api():
    query = request.args.get("query", "")
    language = request.args.get("lang", "")
    return jsonify({"entries": list_lexicon_entries(query=query, language=language)})

@lexicon_bp.route("/words/analyze")
@admin_required
def word_analyze_api():
    return jsonify(analyze_word_knowledge(request.args.get("word", "")))

@lexicon_bp.route("/lexicon/items", methods=["POST"])
@admin_required
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
        return jsonify({
            "ok": True,
            "message": f"Imported {len(items)} word(s) as {lang}.",
            "items": items,
        })

    item = add_lexicon_word(lang, word, frequency=frequency, notes=notes)
    clear_unknown_items([word])
    return jsonify({"ok": True, "message": f"Saved {word} as {lang}.", "item": item})

@lexicon_bp.route("/lexicon/items", methods=["DELETE"])
@admin_required
def delete_lexicon_item_api():
    payload = request.get_json(silent=True) or {}
    lang = str(payload.get("lang", "")).strip().lower()
    word = str(payload.get("word", "")).strip()
    if lang not in SUPPORTED_LANGUAGE_CODES:
        return jsonify({"error": f"Unsupported language code: {lang}"}), 400
    if not word:
        return jsonify({"error": "Word is required."}), 400
    return jsonify({"ok": True, "item": delete_lexicon_word(lang, word)})

@lexicon_bp.route("/names/items")
@admin_required
def names_items_api():
    query = request.args.get("query", "")
    language = request.args.get("lang", "")
    return jsonify({"names": list_name_hints(query=query, language=language)})

@lexicon_bp.route("/names/analyze")
@admin_required
def names_analyze_api():
    name = request.args.get("name", "")
    return jsonify(
        detect_name(name)
        or {
            "language": "unknown",
            "source": "name",
            "entity_type": "unknown_name",
            "text": name,
        }
    )

@lexicon_bp.route("/names/items", methods=["POST"])
@admin_required
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

@lexicon_bp.route("/names/items", methods=["DELETE"])
@admin_required
def delete_name_item_api():
    payload = request.get_json(silent=True) or {}
    lang = str(payload.get("lang", "")).strip().lower()
    name = str(payload.get("name", "")).strip()
    if lang not in SUPPORTED_LANGUAGE_CODES:
        return jsonify({"error": f"Unsupported language code: {lang}"}), 400
    if not name:
        return jsonify({"error": "Name is required."}), 400
    return jsonify({"ok": True, "item": delete_name_hint(name, lang)})
