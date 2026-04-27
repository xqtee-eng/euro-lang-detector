import json
from collections import defaultdict
from src.hybrid import smart_detect_details
from src.related_languages import same_related_group
from src.seed_bshrsr import BENCHMARK_PATH

def load_benchmark():
    samples = []
    if not BENCHMARK_PATH.exists():
        print(f"File not found: {BENCHMARK_PATH}")
        return samples
        
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            samples.append(json.loads(line))
    return samples

def run_bshrsr_benchmark():
    samples = load_benchmark()
    if not samples:
        return
        
    print(f"Running targeted bs/hr/sr benchmark on {len(samples)} samples...")
    
    correct = 0
    group_correct = 0
    confusion_matrix = defaultdict(lambda: defaultdict(int))
    
    for sample in samples:
        expected = sample["expected"]
        result = smart_detect_details(sample["text"], record_unknown=False)
        predicted = result.get("language", "unknown")
        
        is_correct = predicted == expected
        is_group_correct = is_correct or same_related_group(expected, predicted)
        
        correct += int(is_correct)
        group_correct += int(is_group_correct)
        
        confusion_matrix[expected][predicted] += 1
        
    total = len(samples)
    print("\n--- RESULTS ---")
    print(f"Total samples: {total}")
    print(f"Exact Accuracy: {correct/total:.4f}")
    print(f"Group Accuracy: {group_correct/total:.4f}")
    
    print("\n--- CONFUSION MATRIX ---")
    # Rows are actual, columns are predicted
    labels = ["bs", "hr", "sr"]
    print("Actual \\ Predicted | " + " | ".join(f"{l:>4}" for l in labels) + " | other")
    print("-" * 45)
    
    for actual in labels:
        row = f"{actual:>17} | "
        other_errors = 0
        for predicted in labels:
            row += f"{confusion_matrix[actual][predicted]:>4} | "
            
        for predicted, count in confusion_matrix[actual].items():
            if predicted not in labels:
                other_errors += count
        row += f"{other_errors:>5}"
        print(row)

if __name__ == "__main__":
    run_bshrsr_benchmark()
