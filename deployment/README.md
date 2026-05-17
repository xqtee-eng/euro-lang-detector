# Production Deployment

Recommended local production-style run:

```powershell
cd D:\euro-lang-detector
python -m pip install -r requirements.txt
$env:ELD_DEBUG="0"
$env:ELD_ADMIN_PASSWORD="replace-with-strong-password"
$env:ELD_SECRET_KEY="replace-with-random-secret-at-least-32-chars"
python serve.py
```

Open:

```text
http://127.0.0.1:5000/detect
http://127.0.0.1:5000/admin
```

For Windows service/process managers, run `python serve.py` with the same
environment variables. The app writes rotating logs to `logs/app.log`.

Important:

- Change `ELD_ADMIN_PASSWORD`.
- Change `ELD_SECRET_KEY`.
- Keep `data/`, `models/`, and `logs/` on persistent storage.
- Put a reverse proxy in front if exposing outside localhost.
