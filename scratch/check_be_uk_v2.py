from pathlib import Path

def check_file_for_chars(filename, char_specs):
    try:
        path = Path(filename)
        if not path.exists():
            return
        text = path.read_text(encoding='utf-8')
        found = {name: text.count(char) for name, char in char_specs.items()}
        print(f"File: {filename}")
        for name, count in found.items():
            print(f"  {name}: {count}")
        print("-" * 20)
    except Exception as e:
        print(f"Error checking {filename}: {e}")

specs = {
    "ў (be)": "\u045e",
    "і (be/uk)": "\u0456",
    "и (ru/bg/sr)": "\u0438",
    "ы (ru/be)": "\u044b",
    "ї (uk)": "\u0457",
    "є (uk)": "\u0454",
    "ґ (uk)": "\u0491"
}

check_file_for_chars("data/raw/be.txt", specs)
check_file_for_chars("data/raw/uk.txt", specs)
check_file_for_chars("data/raw/ru.txt", specs)
