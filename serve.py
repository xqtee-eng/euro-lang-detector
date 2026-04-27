from api.app import app
from src.config import APP_HOST, APP_PORT


def main():
    try:
        from waitress import serve
    except ImportError:
        print("Waitress is not installed. Falling back to Flask development server.")
        app.run(host=APP_HOST, port=APP_PORT, debug=False)
        return

    print(f"Serving European Language Detector on http://{APP_HOST}:{APP_PORT}")
    serve(app, host=APP_HOST, port=APP_PORT)


if __name__ == "__main__":
    main()
