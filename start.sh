echo "European Language Detector"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] Python3 not found"
    exit
fi

echo "[INFO] Installing dependencies..."
python3 -m pip install -r requirements.txt

if [ ! -f "data/train.jsonl" ]; then
    echo "[INFO] Building starter dataset..."
    python3 -m src.seed_dataset
    python3 -m src.build_dataset
fi

if [ ! -f "models/profiles.json" ]; then
    echo "[INFO] Training local profiles..."
    python3 -m src.train
fi

echo ""
echo "1 - Console mode"
echo "2 - API server"
echo "3 - Evaluate and refresh report"
echo "4 - Production server"
read -p "Select mode: " choice

if [ "$choice" == "1" ]; then
    python3 run.py
elif [ "$choice" == "2" ]; then
    python3 api/app.py
elif [ "$choice" == "3" ]; then
    python3 -m src.evaluate
elif [ "$choice" == "4" ]; then
    ELD_DEBUG=0 python3 serve.py
else
    echo "Invalid choice"
fi
