from flask import Blueprint, jsonify
from src.openapi import openapi_spec
from src.lingua_detector import lingua_available

core_bp = Blueprint('core', __name__)

@core_bp.route("/health")
def health():
    return jsonify({
        "status": "online",
        "lingua": "available" if lingua_available() else "unavailable"
    })

@core_bp.route("/openapi.json")
def openapi():
    return jsonify(openapi_spec())

@core_bp.route("/api-docs")
def api_docs():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>ELD PRO API Docs</title>
      <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@latest/swagger-ui.css">
    </head>
    <body>
      <div id="swagger-ui"></div>
      <script src="https://unpkg.com/swagger-ui-dist@latest/swagger-ui-bundle.js"></script>
      <script>
        SwaggerUIBundle({
          url: '/openapi.json',
          dom_id: '#swagger-ui'
        });
      </script>
    </body>
    </html>
    """

@core_bp.route("/corpus/files")
def corpus_files():
    from src.corpus import list_corpus_files
    files = list_corpus_files()
    # Format according to app.js expectation: { files: [{lang, size_kb, lines}, ...] }
    formatted_files = []
    for f in files:
        formatted_files.append({
            "lang": f["language"],
            "size_kb": round(f["size"] / 1024, 2),
            "lines": f["lines"]
        })
    return jsonify({"files": formatted_files})
