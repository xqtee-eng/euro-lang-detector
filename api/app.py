import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote
from flask import Flask, redirect, session, jsonify, request

# Add ROOT_DIR to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import SECRET_KEY, APP_HOST, APP_PORT, APP_DEBUG
from src.app_logging import get_app_logger
from src.lingua_detector import get_detector
from api.utils import (
    admin_authenticated, wants_json_response, PUBLIC_PATHS, SERVER_RUN_ID,
    public_href,
)

# Blueprints
from api.routes.admin import admin_bp
from api.routes.detector import detector_bp
from api.routes.lexicon import lexicon_bp
from api.routes.admin_management import admin_management_bp
from api.routes.core import core_bp

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
logger = get_app_logger()

# Global Auth Middleware
@app.before_request
def require_admin_auth():
    # 1. Server restart or timeout check: if session has old run_id, clear it
    if session.get("admin_authenticated"):
        if session.get("server_run_id") != SERVER_RUN_ID:
            session.clear()
            if wants_json_response():
                return jsonify({"error": "Session expired or server restarted. Please login again."}), 401
            return redirect(public_href("/admin/login?reason=session_expired"))

    if request.path in PUBLIC_PATHS:
        return None
    if request.path.startswith("/detect") or request.path.startswith("/analyze"):
        return None
    if request.path.startswith("/static"):
        return None
        
    if admin_authenticated():
        return None
        
    if wants_json_response():
        return jsonify({"error": "Admin authentication required."}), 401
        
    return redirect(public_href(f"/admin/login?next={quote(request.path, safe='/')}"))

# Register Blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(detector_bp)
app.register_blueprint(lexicon_bp, url_prefix='/admin')
app.register_blueprint(admin_management_bp, url_prefix='/admin')
app.register_blueprint(core_bp)

def warm_up_detectors():
    print("[*] Warming up linguistic detectors...")
    get_detector()
    print("[*] Ready.")

if __name__ == "__main__":
    warm_up_detectors()
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG, use_reloader=False)
