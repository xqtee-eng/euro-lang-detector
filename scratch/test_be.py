from src.detector import detect
from src.european_languages import SUPPORTED_LANGUAGE_CODES

sentences = [
    "Добры дзень, як вашы справы?",
    "Гэта кароткі тэкст на беларускай мове.",
    "Мы правяраем сістэму вызначэння мовы.",
    "Я вельмі сумую па табе.",
    "Распаўсюджвайце эсперанта!"
]

for s in sentences:
    lang, conf = detect(s)
    print(f"Text: {s}")
    print(f"Detected: {lang} ({conf:.4f})")
    print("-" * 20)
