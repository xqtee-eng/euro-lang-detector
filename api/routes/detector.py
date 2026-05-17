from flask import Blueprint, request, jsonify, redirect
from api.utils import page
from src.hybrid import smart_detect_details
from src.analyzer import analyze_words
from src.app_logging import get_app_logger
from src.european_languages import SUPPORTED_LANGUAGE_CODES
from src.self_learning import add_feedback_sample

detector_bp = Blueprint('detector', __name__)
logger = get_app_logger()

LANG_NAMES = {
    'DE': 'German', 'TR': 'Turkish', 'UK': 'Ukrainian', 'EN': 'English', 'FR': 'French',
    'IT': 'Italian', 'ES': 'Spanish', 'PT': 'Portuguese', 'RU': 'Russian', 'PL': 'Polish',
    'CS': 'Czech', 'SK': 'Slovak', 'BG': 'Bulgarian', 'HR': 'Croatian', 'SR': 'Serbian',
    'SL': 'Slovenian', 'MK': 'Macedonian', 'BE': 'Belarusian', 'RO': 'Romanian', 'HU': 'Hungarian',
    'NL': 'Dutch', 'DA': 'Danish', 'NB': 'Norwegian', 'NN': 'Nynorsk', 'SV': 'Swedish',
    'IS': 'Icelandic', 'FI': 'Finnish', 'ET': 'Estonian', 'LV': 'Latvian', 'LT': 'Lithuanian',
    'EL': 'Greek', 'SQ': 'Albanian', 'MT': 'Maltese', 'CY': 'Welsh', 'GA': 'Irish',
    'CA': 'Catalan', 'GL': 'Galician', 'EU': 'Basque', 'LA': 'Latin', 'UNKNOWN': 'Unknown Language'
}
@detector_bp.route("/")
def index():
    return redirect("/detect")

@detector_bp.route("/detect", methods=["GET"])
def detect_form():
    samples = {
        "UK": "Привіт, як твої справи?",
        "BE": "Добры дзень",
        "CS": "Na nádraží čekáme na vlak",
        "FR": "Bonjour tout le monde",
        "DE": "Guten Tag, wie geht es Ihnen?",
        "ES": "Hola, ¿cómo estás?",
        "IT": "Ciao, come stai?",
        "PL": "Cześć, jak się masz?",
        "TR": "Merhaba, nasılsın?",
        "EL": "Καλημέра, πώς είστε;",
    }
    
    buttons_html = ""
    for code in ["UK", "BE", "CS", "FR", "DE", "ES", "IT"]:
        text = samples.get(code, f"Test sentence for {code}")
        buttons_html += f'<button onclick="sample(\'{text}\')" class="preset-btn">{code}</button>\n        '
    
    buttons_html += '<button onclick="sample(\'hello привіт bonjour\')" class="preset-btn">Mixed</button>'

    return page(
        "ELD PRO",
        f"""
    <div style="max-width: 1200px; margin: 0 auto; padding-bottom: 100px;">
      <div style="margin-bottom: 48px; text-align:center; animation: fadeIn 1s ease-out;">
        <h2 style="font-family:'Outfit'; font-size: 40px; font-weight: 800; letter-spacing: -0.05em; margin-bottom: 10px; background: linear-gradient(135deg, var(--ink) 0%, var(--accent) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Diagnostic Intelligence</h2>
        <p class="muted" style="font-size: 15px; max-width: 500px; margin: 0 auto;">High-precision linguistic fingerprinting for 40+ European languages.</p>
      </div>

      <div class="panel" style="padding: 0; overflow: hidden; border-color: var(--panel-border); backdrop-filter: blur(60px); background: var(--panel-bg); box-shadow: var(--shadow-3d);">
        <textarea id="text" autofocus placeholder="Paste text here to identify..." 
          style="font-size: 20px; padding: 40px; min-height: 320px; border: none; background: transparent; box-shadow: none; display: block; margin-bottom: 0; font-weight: 500; letter-spacing: -0.01em; color:var(--ink);"></textarea>
        
          <div style="padding: 24px 48px; background: rgba(255,255,255,0.02); border-top: 1px solid var(--panel-border); display: flex; justify-content: space-between; align-items: center;">
            <div style="display:flex; gap:16px;">
              <button class="primary" onclick="detect()" style="padding: 14px 32px; font-size: 15px; border-radius: 16px; font-weight:800; border:none; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.4), 0 0 10px -5px var(--accent); transition: all 0.2s; display:flex; align-items:center; justify-content:center; gap:10px;">
                <i data-lucide="zap" style="width:18px; height:18px;"></i> Identify Language
              </button>
              <button onclick="analyze()" style="padding: 14px 28px; font-size: 15px; border-radius: 16px; background: var(--input-bg); border: 1px solid var(--panel-border); font-weight:700; transition: transform 0.2s;">
                <i data-lucide="microscope" style="width:16px; height:16px;"></i> Deep Analysis
              </button>
            </div>
        </div>
      </div>

      <div style="margin: 48px 0;">
        <div class="muted" style="font-size:11px; font-weight:800; text-transform:uppercase; margin-bottom:16px; letter-spacing:0.1em;">Detection Presets</div>
        <div style="display: flex; flex-wrap: wrap; gap: 12px;">
          {buttons_html}
        </div>
      </div>

      <div id="results" style="display: none; animation: fadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1);">
        <div class="grid" style="grid-template-columns: 1.3fr 1fr; gap: 40px; align-items: start;">
          <div>
            <div class="panel" style="padding: 40px; background: rgba(255,255,255,0.01);">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 32px;">
                <div style="text-transform:uppercase; font-size:11px; font-weight:800; letter-spacing:0.2em; color:var(--accent);">Classification Result</div>
                <div id="meta" class="muted" style="font-size:11px; font-weight:700; display:flex; align-items:center; gap:8px;">Scanning...</div>
              </div>
              
              <div style="display:flex; align-items:center; gap:20px; margin-bottom: 24px;">
                 <div style="width:56px; height:56px; border-radius:16px; background:transparent; display:flex; align-items:center; justify-content:center; border: 2px solid var(--panel-border);">
                    <i data-lucide="languages" style="width:28px; height:28px; color:var(--accent);"></i>
                 </div>
                 <div style="flex:1;">
                    <div id="language-name" style="font-family:'Outfit'; font-size: 32px; font-weight: 800; letter-spacing: -0.04em; line-height:1; color:var(--ink);">--</div>
                    <div style="display:flex; gap:12px; margin-top:12px;">
                       <span id="badge-iso" class="pill good" style="background:var(--accent-soft); color:var(--accent); border:1px solid var(--accent); padding:4px 12px; border-radius:8px; font-family:monospace; font-size:12px;">ISO: --</span>
                       <span class="pill" style="background:rgba(255,255,255,0.05); color:var(--muted); font-size:11px; text-transform:uppercase; font-weight:800; letter-spacing:0.1em; padding:4px 12px; border-radius:8px;">Diagnostic Verified</span>
                    </div>
                 </div>
              </div>
              
              <div style="margin-bottom: 60px;">
                <div style="display:flex; justify-content:space-between; font-size:12px; font-weight:800; margin-bottom:16px; text-transform:uppercase; letter-spacing:0.05em;">
                  <span>Reliability Metric</span>
                  <span id="confidence-pct" style="color:var(--accent)">0%</span>
                </div>
                <div style="height:14px; background:rgba(255,255,255,0.05); border-radius:7px; overflow:hidden;">
                  <div id="fill" style="width:0%; height:100%; transition: width 1.2s cubic-bezier(0.16, 1, 0.3, 1), background 0.5s;"></div>
                </div>
              </div>

              <div style="text-transform:uppercase; font-size:10px; font-weight:800; letter-spacing:0.15em; color:var(--muted); margin-bottom: 20px;">Probability Ranking</div>
              <div id="candidates-container">
                <div id="candidates" style="display:flex; flex-direction:column; gap:8px;"></div>
              </div>

              <div id="correction-area" style="margin-top: 40px; padding-top: 32px; border-top: 1px solid var(--panel-border);">
                 <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
                    <div style="font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted);">Identity Verification</div>
                    <i data-lucide="shield-check" style="width:14px; opacity:0.4;"></i>
                 </div>
                 <div style="display:flex; gap:12px;">
                    <input type="text" id="feedbackLang" placeholder="ISO CODE" style="width:100px; height: 40px; text-align:center; font-weight:800; text-transform:uppercase; border-radius:12px; background:var(--input-bg); border:1px solid var(--panel-border); color:var(--ink); font-size: 11px;">
                    <button class="primary" onclick="sendFeedback()" style="flex:1; height: 40px; justify-content:center; border-radius:12px; font-weight:800; font-size: 13px;">
                       Validate & Integrate
                    </button>
                 </div>
                 <div id="feedbackStatus" class="status" style="margin-top:16px; font-size:12px; text-align:center;"></div>
              </div>
            </div>
          </div>

          <div>
            <div class="panel" style="padding: 32px; background: rgba(255,255,255,0.01);">
              <h3 style="margin-bottom:32px; font-family:'Outfit'; font-size:18px; color:var(--ink);"><i data-lucide="file-search" style="color:var(--accent); width:20px; height:20px; vertical-align:middle; margin-right:8px;"></i> Token breakdown</h3>
              <div id="tokens" style="max-height: 800px; overflow-y: auto; padding-right: 12px;">
                <div class="muted" style="text-align:center; padding: 60px 0;">Token-level breakdown will be displayed after identification.</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    """,
    )

@detector_bp.route("/detect", methods=["POST"])
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

@detector_bp.route("/analyze", methods=["POST"])
def analyze_api():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    try:
        top_k = int(payload.get("top_k", 3))
    except (TypeError, ValueError):
        top_k = 3
    return jsonify(analyze_words(text, top_k=max(1, min(top_k, 10))))


@detector_bp.route("/feedback", methods=["POST"])
def feedback_api():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text") or "").strip()
    language = str(payload.get("lang") or "").strip().lower()

    if not text:
        return jsonify({"ok": False, "error": "Text is required."}), 400
    if language not in SUPPORTED_LANGUAGE_CODES:
        return jsonify({"ok": False, "error": "Unsupported language code."}), 400

    add_feedback_sample(text, language, source="manual")
    return jsonify({"ok": True})
