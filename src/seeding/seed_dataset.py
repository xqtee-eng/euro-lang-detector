import argparse

from src.config import DATA_DIR
from src.european_languages import SUPPORTED_LANGUAGE_CODES

RAW_DATA_DIR = DATA_DIR / "raw"

SEED_TEXTS = {
    "sq": [
        "Pershendetje, si jeni sot?",
        "Ky eshte nje tekst i shkurter ne gjuhen shqipe.",
        "Ne po testojme zbulimin e gjuhes.",
    ],
    "hy": [
        "Բարեւ, ինչպես եք այսօր։",
        "Սա կարճ նախադասություն է հայերեն լեզվով։",
        "Մենք փորձարկում ենք լեզվի ճանաչումը։",
    ],
    "az": [
        "Salam, bu gün necəsiniz?",
        "Bu Azərbaycan dilində qısa bir cümlədir.",
        "Biz dil tanıma sistemini yoxlayırıq.",
    ],
    "eu": [
        "Kaixo, zer moduz zaude gaur?",
        "Hau euskaraz idatzitako esaldi laburra da.",
        "Hizkuntza detektatzeko sistema probatzen ari gara.",
    ],
    "be": [
        "Добры дзень, як вашы справы?",
        "Гэта кароткі тэкст на беларускай мове.",
        "Мы правяраем сістэму вызначэння мовы.",
        "Беларуская мова — гэта мова беларускага народа.",
        "Я вельмі люблю сваю краіну і сваю культуру.",
        "Сёння выдатнае надвор'е для прагулкі ў парку.",
        "Дзякуй за вашу дапамогу і падтрымку.",
        "Калі ласка, размаўляйце са мной па-беларуску.",
        "У кожнага чалавека ёсць права на свабоду і шчасце.",
        "Жыццё — гэта вялікая таямніца, якую трэба разгадаць.",
        "Распаўсюджвайце эсперанта ва ўсім свеце!",
        "Я прачнуўся і ўбачыў у пакоі прыгожую кветку.",
    ],
    "bs": [
        "Dobar dan, kako ste danas?",
        "Ovo je kratka recenica na bosanskom jeziku.",
        "Testiramo sistem za prepoznavanje jezika.",
    ],
    "bg": [
        "Здравейте, как сте днес?",
        "Това е кратък текст на български език.",
        "Тестваме системата за разпознаване на език.",
    ],
    "ca": [
        "Hola, com estas avui?",
        "Aquest es un text curt en catala.",
        "Estem provant el sistema de deteccio de llengua.",
    ],
    "hr": [
        "Bok, kako ste danas?",
        "Ovo je kratka recenica na hrvatskom jeziku.",
        "Testiramo sustav za prepoznavanje jezika.",
    ],
    "cs": [
        "Dobrý den, jak se dnes máte?",
        "Toto je krátká věta v češtině.",
        "Testujeme systém pro rozpoznávání jazyka.",
    ],
    "da": [
        "Goddag, hvordan har du det i dag?",
        "Dette er en kort sætning på dansk.",
        "Vi tester systemet til sproggenkendelse.",
    ],
    "nl": [
        "Hallo, hoe gaat het vandaag?",
        "Dit is een korte zin in het Nederlands.",
        "We testen het systeem voor taalherkenning.",
    ],
    "en": [
        "Hello, how are you today?",
        "This is a short sentence in English.",
        "We are testing the language detection system.",
    ],
    "et": [
        "Tere, kuidas teil täna läheb?",
        "See on lühike lause eesti keeles.",
        "Me testime keele tuvastamise süsteemi.",
    ],
    "fi": [
        "Hei, miten voit tänään?",
        "Tämä on lyhyt lause suomen kielellä.",
        "Testaamme kielen tunnistusjärjestelmää.",
    ],
    "fr": [
        "Bonjour, comment allez-vous aujourd'hui?",
        "Ceci est une courte phrase en français.",
        "Nous testons le systeme de detection de langue.",
    ],
    "ka": [
        "გამარჯობა, როგორ ხართ დღეს?",
        "ეს არის მოკლე წინადადება ქართულ ენაზე.",
        "ჩვენ ვამოწმებთ ენის ამოცნობის სისტემას.",
    ],
    "de": [
        "Guten Tag, wie geht es Ihnen heute?",
        "Dies ist ein kurzer Satz auf Deutsch.",
        "Wir testen das System zur Spracherkennung.",
    ],
    "el": [
        "Καλημέρα, πώς είστε σήμερα;",
        "Αυτή είναι μια σύντομη πρόταση στα ελληνικά.",
        "Δοκιμάζουμε το σύστημα αναγνώρισης γλώσσας.",
    ],
    "hu": [
        "Jó napot, hogy van ma?",
        "Ez egy rövid mondat magyar nyelven.",
        "Teszteljük a nyelvfelismerő rendszert.",
    ],
    "is": [
        "Góðan dag, hvernig hefur þú það í dag?",
        "Þetta er stutt setning á íslensku.",
        "Við prófum tungumála greiningarkerfið.",
    ],
    "ga": [
        "Dia duit, conas ata tu inniu?",
        "Seo abairt ghearr i nGaeilge.",
        "Ta muid ag tástáil an chórais aitheanta teanga.",
    ],
    "it": [
        "Buongiorno, come stai oggi?",
        "Questa è una breve frase in italiano.",
        "Stiamo testando il sistema di rilevamento della lingua.",
    ],
    "lv": [
        "Labdien, kā jums šodien klājas?",
        "Šis ir īss teikums latviešu valodā.",
        "Mēs testējam valodas noteikšanas sistēmu.",
    ],
    "lt": [
        "Laba diena, kaip šiandien laikotės?",
        "Tai trumpas sakinys lietuvių kalba.",
        "Mes tikriname kalbos atpažinimo sistemą.",
    ],
    "mk": [
        "Добар ден, како сте денес?",
        "Ова е кратка реченица на македонски јазик.",
        "Го тестираме системот за препознавање јазик.",
    ],
    "nb": [
        "Hei, hvordan går det med deg i dag?",
        "Dette er en kort setning på norsk bokmål.",
        "Vi tester bokmål i systemet for språkgjenkjenning.",
    ],
    "nn": [
        "God dag, korleis har du det i dag?",
        "Dette er ei kort setning på nynorsk.",
        "Vi testar systemet for språkgjenkjenning.",
    ],
    "pl": [
        "Dzień dobry, jak się dzisiaj masz?",
        "To jest krótkie zdanie w języku polskim.",
        "Testujemy system rozpoznawania języka.",
    ],
    "pt": [
        "Bom dia, como você está hoje?",
        "Esta é uma frase curta em português.",
        "Estamos testando o sistema de detecção de idioma.",
    ],
    "ro": [
        "Bună ziua, cum sunteți astăzi?",
        "Aceasta este o propoziție scurtă în limba română.",
        "Testam sistemul de detectare a limbii.",
    ],
    "ru": [
        "Здравствуйте, как ваши дела сегодня?",
        "Это короткое предложение на русском языке.",
        "Мы проверяем систему определения языка.",
        "Русский язык является одним из самых распространенных в мире.",
        "Я очень люблю читать книги в свободное время.",
        "Сегодня на улице светит яркое солнце и поют птицы.",
        "Большое спасибо за ваше гостеприимство и доброту.",
        "Пожалуйста, закройте дверь, когда будете уходить.",
        "Жизнь полна неожиданностей и удивительных открытий.",
        "Каждый человек стремится к счастью и благополучию.",
        "Эта книга содержит много полезной информации для студентов.",
    ],
    "sr": [
        "Добар дан, како сте данас?",
        "Ово је кратка реченица на српском језику.",
        "Тестирамо систем за препознавање језика.",
    ],
    "sk": [
        "Dobrý deň, ako sa dnes máte?",
        "Toto je krátka veta v slovenčine.",
        "Testujeme systém na rozpoznávanie jazyka.",
    ],
    "sl": [
        "Dober dan, kako ste danes?",
        "To je kratek stavek v slovenskem jeziku.",
        "Preizkušamo sistem za prepoznavanje jezika.",
    ],
    "es": [
        "Buenos días, cómo estás hoy?",
        "Esta es una frase corta en español.",
        "Estamos probando el sistema de detección de idioma.",
    ],
    "sv": [
        "God dag, hur mår du idag?",
        "Detta är en kort mening på svenska.",
        "Vi testar systemet för språkidentifiering.",
    ],
    "tr": [
        "Merhaba, bugün nasılsınız?",
        "Bu Türkçe kısa bir cümledir.",
        "Dil algılama sistemini test ediyoruz.",
    ],
    "uk": [
        "Привіт, як твої справи сьогодні?",
        "Це коротке речення українською мовою.",
        "Ми перевіряємо систему визначення мови.",
        "Українська мова — одна з наймилозвучніших мов світу.",
        "Я щиро люблю свою батьківщину та її славну історію.",
        "Сьогодні чудовий день для відпочинку на природі.",
        "Дуже дякую за вашу щиру допомогу та корисні поради.",
        "Будь ласка, говоріть зі мною українською мовою.",
        "Життя — це неоціненний скарб, який даровано кожному.",
        "Кожна людина має право на вільний розвиток своєї особистості.",
        "У нас сьогодні відбудеться важлива зустріч у центрі міста.",
        "Ми повинні берегти природу для майбутніх поколінь.",
    ],
    "cy": [
        "Helo, sut ydych chi heddiw?",
        "Dyma frawddeg fer yn Gymraeg.",
        "Rydym yn profi'r system adnabod iaith.",
    ],
}


def expand_seed_texts(texts):
    expanded = []

    def add(value):
        value = " ".join(str(value or "").split())
        if value and value not in expanded:
            expanded.append(value)

    for text in texts:
        add(text)

    for left_index, left in enumerate(texts):
        for right_index, right in enumerate(texts):
            if left_index != right_index:
                add(f"{left} {right}")

    for first_index, first in enumerate(texts):
        for second_index, second in enumerate(texts):
            for third_index, third in enumerate(texts):
                if len({first_index, second_index, third_index}) == 3:
                    add(f"{first} {second} {third}")

    for left_index, left in enumerate(texts):
        for right_index, right in enumerate(texts):
            if left_index != right_index:
                add(f"{left} {right} {left}")
                add(f"{right} {left} {right}")
                add(f"{left} {left} {right}")
                add(f"{left} {right} {right}")

    for text in texts:
        add(f"{text} {text}")
        add(f"{text} {text} {text}")

    return expanded


def seed_raw_dataset(overwrite=False):
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    skipped = 0

    for language in SUPPORTED_LANGUAGE_CODES:
        texts = SEED_TEXTS.get(language)
        if not texts:
            continue

        path = RAW_DATA_DIR / f"{language}.txt"
        if path.exists() and not overwrite:
            skipped += 1
            continue

        expanded_texts = expand_seed_texts(texts)

        path.write_text("\n".join(expanded_texts) + "\n", encoding="utf-8")
        created += 1

    print(f"Seed files created: {created}")
    print(f"Seed files skipped: {skipped}")
    print(f"Raw data directory: {RAW_DATA_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create starter raw language files.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing seed files.")
    args = parser.parse_args()
    seed_raw_dataset(overwrite=args.overwrite)
