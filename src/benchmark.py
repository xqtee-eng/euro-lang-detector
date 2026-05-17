from collections import defaultdict
import json
import argparse
from src.config import BENCHMARK_PATH, DATASET_PATH
from src.hybrid import smart_detect_details
from src.related_languages import same_related_group

BENCHMARK_SAMPLES = [
    {"text": "Привіт", "expected": "uk", "category": "short_greeting"},
    {"text": "Добры дзень", "expected": "be", "category": "short_greeting"},
    {"text": "Bonjour", "expected": "fr", "category": "short_greeting"},
    {"text": "Merhaba nasılsınız", "expected": "tr", "category": "phrase"},
    {"text": "Na nádraží čekáme na vlak", "expected": "cs", "category": "phrase"},
    {"text": "Liczenie owiec", "expected": "pl", "category": "phrase"},
    {"text": "sprache", "expected": "de", "category": "frequency_word"},
    {"text": "palabra", "expected": "es", "category": "frequency_word"},
    {"text": "kelime", "expected": "tr", "category": "frequency_word"},
    {"text": "language", "expected": "en", "category": "frequency_word"},
    {"text": "коза", "expected": "unknown", "category": "ambiguous_word"},
    {"text": "собака", "expected": "unknown", "category": "ambiguous_word"},
    {"text": "Анастасія", "expected": "unknown", "category": "ambiguous_name"},
    {"text": "Іван", "expected": "unknown", "category": "ambiguous_name"},
    {"text": "hello привіт bonjour", "expected": "unknown", "category": "mixed_text"},
    {"text": "python api/app.py", "expected": "unknown", "category": "non_language"},
]

def load_benchmark_samples(total_limit=None, per_language_limit=None):
    samples = []
    # 1. Load manual benchmark samples
    if BENCHMARK_PATH.exists():
        with open(BENCHMARK_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    if row.get("text") and row.get("expected"):
                        samples.append({
                            "text": row["text"],
                            "expected": row["expected"],
                            "category": row.get("category", "external")
                        })
                except: continue
    
    # 2. Add samples from dataset.jsonl with balancing
    if DATASET_PATH.exists():
        from src.european_languages import SUPPORTED_LANGUAGE_CODES
        lang_counts = defaultdict(int)
        for s in samples:
            lang_counts[s["expected"]] += 1
            
        seen_texts = {s["text"] for s in samples}
        
        # If per_language_limit is set, we want that many for each.
        # Otherwise if total_limit is set, we just fill up.
        
        with open(DATASET_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    text = row.get("text", "").strip()
                    lang = row.get("lang", "").strip()
                    if not text or not lang or text in seen_texts:
                        continue
                    
                    if per_language_limit:
                        if lang_counts[lang] < per_language_limit:
                            samples.append({"text": text, "expected": lang, "category": "dataset_sample"})
                            lang_counts[lang] += 1
                            seen_texts.add(text)
                    elif total_limit:
                        if len(samples) < total_limit:
                            samples.append({"text": text, "expected": lang, "category": "dataset_sample"})
                            seen_texts.add(text)
                        else:
                            break
                    else:
                        # Truly all
                        samples.append({"text": text, "expected": lang, "category": "dataset_sample"})
                        seen_texts.add(text)
                except: continue
    
    return samples if samples else BENCHMARK_SAMPLES

def write_seed_benchmark(path=BENCHMARK_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in BENCHMARK_SAMPLES:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"path": str(path), "samples": len(BENCHMARK_SAMPLES)}

def run_benchmark(limit=500, per_language_limit=None):
    samples = load_benchmark_samples(total_limit=limit, per_language_limit=per_language_limit)
    rows = []
    correct = 0
    group_correct = 0
    by_category = defaultdict(lambda: {"samples": 0, "correct": 0, "group_correct": 0})
    by_language = defaultdict(lambda: {"samples": 0, "correct": 0})

    for sample in samples:
        result = smart_detect_details(sample["text"], top_k=1, record_unknown=False)
        prediction = result.get("language", "unknown")
        is_correct = prediction == sample["expected"]
        is_group_correct = is_correct or same_related_group(sample["expected"], prediction)
        
        correct += int(is_correct)
        group_correct += int(is_group_correct)
        
        by_category[sample["category"]]["samples"] += 1
        by_category[sample["category"]]["correct"] += int(is_correct)
        by_category[sample["category"]]["group_correct"] += int(is_group_correct)
        
        by_language[sample["expected"]]["samples"] += 1
        by_language[sample["expected"]]["correct"] += int(is_correct)
        
        rows.append({
            "text": sample["text"],
            "expected": sample["expected"],
            "predicted": prediction,
            "category": sample["category"],
            "correct": is_correct,
            "group_correct": is_group_correct,
            "confidence": result.get("confidence", 0),
            "source": result.get("source", ""),
            "reason": result.get("reason", "")
        })

    total = len(samples)
    accuracy = correct / total if total else 0
    group_accuracy = group_correct / total if total else 0
    
    per_language = {}
    for lang, stats in by_language.items():
        lang_acc = stats["correct"] / stats["samples"] if stats["samples"] else 0
        per_language[lang] = {
            "correct": stats["correct"],
            "total": stats["samples"],
            "accuracy": round(lang_acc, 4)
        }

    return {
        "samples": total,
        "total_tests": total,
        "correct": correct,
        "group_correct": group_correct,
        "accuracy": round(accuracy, 4),
        "group_accuracy": round(group_accuracy, 4),
        "categories": dict(by_category),
        "per_language": per_language,
        "rows": rows
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run detector benchmark.")
    parser.add_argument("--full", action="store_true", help="Run on full dataset (50 samples per lang).")
    parser.add_argument("--total", type=int, default=None, help="Total samples to test.")
    args = parser.parse_args()
    
    if args.full:
        report = run_benchmark(limit=None, per_language_limit=50)
    else:
        limit = args.total if args.total else 500
        report = run_benchmark(limit=limit)
    
    print(f"Benchmark: {report['samples']} samples, Accuracy: {report['accuracy']*100:.2f}%")
