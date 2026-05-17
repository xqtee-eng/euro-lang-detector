import os
import json
import random
import argparse
from pathlib import Path

from src.european_languages import EUROPEAN_LANGUAGE_SPECS
from src.close_language_pack import CLOSE_LANGUAGE_PACK
from src.storage import bulk_upsert_lexicon_words, bulk_upsert_name_hints, wipe_table

# MEGA SEED 8.0: THE DATA-DRIVEN ARCHITECTURE
# Clean, modular, and DB-integrated.

DATA_ROOT = Path("data")
DEFAULTS_ROOT = DATA_ROOT / "defaults"

def load_json(path):
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_sentence(vocab):
    length = random.randint(6, 12)
    sentence = []
    last_word = None
    for _ in range(length):
        word = random.choice([w for w in vocab if w != last_word])
        sentence.append(word)
        last_word = word
    return " ".join(sentence).capitalize() + "."

def mega_seed(populate_db=False):
    print("--- MEGA SEED 8.0: SYSTEM INITIALIZATION ---")
    
    vocab_master = load_json(DEFAULTS_ROOT / "vocab_master.json")
    names_master = load_json(DEFAULTS_ROOT / "names_master.json")
    
    if not vocab_master or not names_master:
        print("[ERROR] Defaults missing. Please ensure vocab_master.json and names_master.json exist.")
        return

    # 1. Directory Setup & Cleanup
    for d in ["raw", "frequency", "lexicons", "names", "close_pack"]:
        dir_path = DATA_ROOT / d
        dir_path.mkdir(parents=True, exist_ok=True)
        for f in dir_path.glob("*.*"): f.unlink()

    # 2. Database Reset (optional)
    if populate_db:
        print("[*] Wiping DB tables for fresh start...")
        wipe_table("lexicon_words")
        wipe_table("name_hints")

    all_lexicon_rows = []
    all_name_rows = []

    # 3. Generate Files & Collect DB Rows
    for spec in EUROPEAN_LANGUAGE_SPECS:
        code = spec['code']
        name = spec['name']
        print(f"[*] Processing {name} ({code})...")
        
        vocab = vocab_master.get(code, [])
        names = names_master.get(code, [])
        
        if not vocab:
            print(f"  [WARN] No vocab for {code}")
            continue

        # A. Raw Text
        with open(DATA_ROOT / "raw" / f"{code}.txt", "w", encoding="utf-8") as f:
            unique_sentences = set()
            while len(unique_sentences) < 500: # Reduced for speed, increased if needed
                s = generate_sentence(vocab)
                if s not in unique_sentences:
                    unique_sentences.add(s)
                    f.write(s + "\n")

        # B. Lexicons
        with open(DATA_ROOT / "lexicons" / f"{code}.txt", "w", encoding="utf-8") as f:
            for w in sorted(set(vocab)): 
                f.write(w + "\n")
                all_lexicon_rows.append({
                    "language": code,
                    "word": w,
                    "source": "seed",
                    "enabled": 1
                })

        # C. Names
        with open(DATA_ROOT / "names" / f"{code}.jsonl", "w", encoding="utf-8") as f:
            for n in names:
                f.write(json.dumps({"name": n, "language": code}, ensure_ascii=False) + "\n")
                all_name_rows.append({
                    "name": n,
                    "language": code,
                    "source": "seed",
                    "enabled": 1,
                    "confidence": 0.95
                })

        # D. Frequency (Dummy)
        with open(DATA_ROOT / "frequency" / f"{code}.tsv", "w", encoding="utf-8") as f:
            for i, w in enumerate(vocab):
                f.write(f"{w}\t{int(30000 / (i + 1))}\n")

    # 4. Bulk Database Import
    if populate_db:
        print(f"[*] Importing {len(all_lexicon_rows)} words to DB...")
        bulk_upsert_lexicon_words(all_lexicon_rows)
        print(f"[*] Importing {len(all_name_rows)} names to DB...")
        bulk_upsert_name_hints(all_name_rows)

    print("\n[SUCCESS] System Initialization Complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", action="store_true", help="Populate database directly")
    args = parser.parse_args()
    mega_seed(populate_db=args.db)
