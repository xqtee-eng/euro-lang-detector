from pathlib import Path

def check_file(filename):
    try:
        path = Path(filename)
        if not path.exists():
            print(f"File {filename} not found.")
            return
        text = path.read_text(encoding='utf-8')
        non_cyr = []
        for c in text:
            if not (0x0400 <= ord(c) <= 0x04FF or c.isspace() or c in ',.?!:;\"\'\'-'):
                non_cyr.append(c)
        print(f"File: {filename}")
        print(f"Non-Cyrillic characters: {set(non_cyr)}")
        print("-" * 20)
    except Exception as e:
        print(f"Error checking {filename}: {e}")

check_file("data/raw/be.txt")
check_file("data/raw/uk.txt")
check_file("data/raw/ru.txt")
check_file("data/raw/bg.txt")
check_file("data/raw/mk.txt")
check_file("data/raw/sr.txt")
