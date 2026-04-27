from pathlib import Path

def check_file_for_chars(filename, chars):
    try:
        path = Path(filename)
        if not path.exists():
            return
        text = path.read_text(encoding='utf-8')
        found = {c: text.count(c) for c in chars}
        print(f"File: {filename}")
        print(f"Character counts: {found}")
        print("-" * 20)
    except Exception as e:
        print(f"Error checking {filename}: {e}")

check_file_for_chars("data/raw/be.txt", "ўіиы")
check_file_for_chars("data/raw/uk.txt", "їєіиы")
check_file_for_chars("data/raw/ru.txt", "иы")
