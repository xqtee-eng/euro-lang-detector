import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.storage import upsert_name_hint, bulk_upsert_lexicon_words
from src.name_detector import clear_name_cache
from src.word_lexicon import clear_lexicon_cache

PREMIUM_NAMES = {
    "en": ["John", "Mary", "James", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen"],
    "uk": ["Олександр", "Тетяна", "Сергій", "Наталія", "Андрій", "Олена", "Володимир", "Марія", "Ігор", "Ольга", "Микола", "Світлана", "Віктор", "Людмила", "Юрій", "Ганна", "Анатолій", "Надія", "Василь", "Катерина"],
    "fr": ["Jean", "Marie", "Michel", "Isabelle", "Philippe", "Sylvie", "Alain", "Catherine", "Pierre", "Françoise", "Nicolas", "Sandrine", "Christophe", "Nathalie", "Christian", "Monique", "Marc", "Anne", "Patrick", "Dominique"],
    "de": ["Hans", "Maria", "Thomas", "Karin", "Andreas", "Petra", "Michael", "Sabine", "Klaus", "Monika", "Christian", "Ursula", "Stefan", "Renate", "Wolfgang", "Helga", "Uwe", "Gisela", "Jürgen", "Ingrid"],
    "it": ["Giuseppe", "Maria", "Giovanni", "Anna", "Antonio", "Rosa", "Roberto", "Angela", "Mario", "Giovanna", "Franco", "Francesca", "Pietro", "Lucia", "Vincenzo", "Carmela", "Giorgio", "Caterina", "Luigi", "Antonella"],
    "es": ["José", "María", "Manuel", "Carmen", "Juan", "Ana", "Antonio", "Isabel", "Francisco", "Dolores", "Javier", "Pilar", "Rafael", "Teresa", "Carlos", "Josefa", "Luis", "Concepción", "Miguel", "Lucía"],
    "ru": ["Александр", "Елена", "Сергей", "Татьяна", "Владимир", "Наталья", "Андрей", "Ольга", "Николай", "Светлана", "Юрий", "Марина", "Виктор", "Ирина", "Дмитрий", "Галина", "Игорь", "Анна", "Анатолий", "Валентина"],
    "pl": ["Jan", "Maria", "Andrzej", "Anna", "Stanisław", "Krystyna", "Krzysztof", "Barbara", "Józef", "Teresa", "Marian", "Elżbieta", "Piotr", "Zofia", "Zbigniew", "Danuta", "Jerzy", "Halina", "Henryk", "Irena"],
    "be": ["Аляксандр", "Таццяна", "Сяргей", "Алена", "Уладзімір", "Наталля", "Андрэй", "Марыя", "Мікалай", "Вольга", "Юрый", "Святлана", "Віктар", "Ганна", "Анатоль", "Людміла", "Ігар", "Надзея", "Васіль", "Галіна"],
    "tr": ["Mustafa", "Fatma", "Mehmet", "Ayşe", "Ahmet", "Emine", "Ali", "Hatice", "Hüseyin", "Zeynep", "Hasan", "Özlem", "İbrahim", "Elif", "İsmail", "Merve", "Osman", "Canan", "Yusuf", "Sibel"],
    "pl": ["Krzysztof", "Piotr", "Andrzej", "Tomasz", "Paweł", "Michał", "Marcin", "Stanisław", "Jan", "Marek"],
    "cs": ["Jiří", "Jan", "Petr", "Josef", "Pavel", "Jaroslav", "Martin", "Miroslav", "Tomáš", "František"],
    "sk": ["Ján", "Jozef", "Peter", "Štefan", "Miroslav", "Milan", "Ladislav", "Martin", "Dušan", "Ivan"],
    "hu": ["László", "István", "József", "János", "Zoltán", "Sándor", "Gábor", "Ferenc", "Attila", "Lajos"],
    "ro": ["Gheorghe", "Ioan", "Vasile", "Constantin", "Ion", "Dumitru", "Alexandru", "Ștefan", "Nicolae", "Mihai"],
    "bg": ["Георги", "Иван", "Димитър", "Николай", "Петър", "Христо", "Йордан", "Стефан", "Васил", "Тодор"],
    "sr": ["Dragan", "Milan", "Nikola", "Zoran", "Marko", "Aleksandar", "Dušan", "Slobodan", "Miodrag", "Goran"],
    "hr": ["Ivan", "Josip", "Stjepan", "Marko", "Ante", "Ivica", "Tomislav", "Željko", "Damir", "Mario"],
    "sl": ["Janez", "Anton", "Marija", "Ivan", "Jožef", "Andrej", "Marko", "Peter", "Franc", "Stanislav"],
    "sq": ["Arben", "Agim", "Alban", "Ilir", "Fatmir", "Lulzim", "Bujar", "Genci", "Dritan", "Besnik"],
    "el": ["Georgios", "Ioannis", "Konstantinos", "Dimitrios", "Nikolaos", "Panagiotis", "Vasileios", "Christos", "Athanasios", "Michail"],
    "hy": ["Armen", "Karen", "Artur", "Samvel", "Tigran", "Hrayr", "Vardan", "Gevorg", "Hayk", "Aram"],
    "ka": ["Giorgi", "Davit", "Zurab", "Levan", "Irakli", "Mikheil", "Archil", "Tamaz", "Gela", "Avtandil"],
    "fi": ["Matti", "Juhani", "Johannes", "Olavi", "Antero", "Tapani", "Kalevi", "Tapio", "mika", "antti"],
    "sv": ["Erik", "Lars", "Karl", "Anders", "Johan", "Per", "Nils", "Jan", "Lennart", "Olof"],
    "da": ["Erik", "Peter", "Jens", "Hans", "Christian", "Jørgen", "Morten", "Niels", "Anders", "Søren"],
    "nb": ["Jan", "Per", "Bjørn", "Ole", "Lars", "Kjell", "Knut", "Svein", "Thomas", "Arne"],
    "nl": ["Johannes", "Jan", "Cornelis", "Willem", "Hendrik", "Gerrit", "Pieter", "Adriaan", "Jacobus", "Petrus"],
    "ca": ["Jordi", "Joan", "Josep", "Marc", "Antoni", "Francesc", "Pere", "Lluis", "Albert", "David"],
    "eu": ["Iñaki", "Xabier", "Mikel", "Jon", "Aitor", "Asier", "Andoni", "Unai", "Iker", "Joseba"],
    "ga": ["Seán", "Patrick", "Liam", "Conor", "Cian", "Oisín", "Darragh", "Eoin", "Finn", "Tadhg"],
    "is": ["Guðmundur", "Sigurður", "Jón", "Magnús", "Ólafur", "Einar", "Gunnar", "Kristján", "Stefán", "Helgi"],
    "lv": ["Jānis", "Andris", "Juris", "Māris", "Edgars", "Kaspars", "Aivars", "Mārtiņš", "Viesturs", "Ingars"],
    "lt": ["Vytautas", "Jonas", "Antanas", "Tomas", "Marius", "Andrius", "Darius", "Linas", "Mantvydas", "Gintaras"],
    "et": ["Rein", "Jüri", "Toomas", "Margus", "Andres", "Urmas", "Peeter", "Indrek", "Tiit", "Tarmo"],
    "az": ["Anar", "Elnur", "Rəşad", "Vüsal", "Samir", "Zaur", "Tural", "İlham", "Emin", "Orxan"],
    "mk": ["Aleksandar", "Zoran", "Dragan", "Nikola", "Igor", "Goran", "Dejan", "Petar", "Vlatko", "Stefan"],
    "cy": ["Gareth", "Dafydd", "Rhys", "Llywelyn", "Iwan", "Owain", "Sion", "Gethin", "Dylan", "Steffan"],
}

PREMIUM_WORDS = {
    "en": ["the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not", "on", "with", "he", "as", "you", "do", "at"],
    "fr": ["le", "de", "un", "être", "et", "à", "il", "avoir", "ne", "je", "son", "que", "se", "qui", "ce", "dans", "en", "pas", "pour", "sur"],
    "de": ["der", "die", "das", "und", "sein", "in", "ein", "zu", "haben", "ich", "werden", "sie", "von", "nicht", "mit", "es", "auf", "an", "als", "auch"],
    "it": ["il", "di", "essere", "e", "a", "un", "in", "che", "non", "avere", "si", "per", "lo", "con", "ma", "come", "su", "mi", "anche", "questo"],
    "es": ["el", "de", "que", "y", "en", "un", "ser", "a", "él", "lo", "no", "su", "haber", "con", "por", "para", "mí", "como", "estar", "tener"],
    "uk": ["та", "і", "що", "це", "на", "не", "він", "як", "до", "бути", "про", "вона", "за", "але", "ми", "все", "його", "який", "вони", "й"],
    "ru": ["и", "в", "не", "на", "я", "быть", "он", "с", "что", "а", "по", "это", "она", "этот", "из", "у", "который", "весь", "за", "свой"],
    "pl": ["w", "i", "z", "na", "do", "że", "o", "się", "nie", "a", "być", "jest", "za", "po", "dla", "od", "który", "mieć", "tak", "ten"],
    "be": ["і", "ў", "на", "не", "я", "быць", "ён", "з", "што", "а", "па", "гэта", "яна", "гэты", "з", "у", "які", "увесь", "за", "свой"],
    "tr": ["bir", "bu", "ve", "de", "için", "ne", "o", "da", "ama", "çok", "gibi", "en", "her", "kadar", "biraz", "sonra", "ki", "daha", "ile", "şimdi"],
}

def seed_premium_data():
    names_imported = 0
    words_imported = 0
    
    # Import Names
    for lang, names in PREMIUM_NAMES.items():
        for name in names:
            upsert_name_hint(
                name, lang, 
                country="", 
                confidence=0.9, 
                enabled=True, 
                source="premium_seed",
                notes="Premium starter name hint."
            )
            names_imported += 1
            
    # Import Words
    lexicon_rows = []
    for lang, words in PREMIUM_WORDS.items():
        for word in words:
            lexicon_rows.append({
                "language": lang,
                "word": word,
                "enabled": True,
                "source": "premium_seed",
                "frequency": 100,
                "notes": "Premium common word hint."
            })
            words_imported += 1
            
    if lexicon_rows:
        bulk_upsert_lexicon_words(lexicon_rows)
        
    clear_name_cache()
    clear_lexicon_cache()
    
    return {
        "names_imported": names_imported,
        "words_imported": words_imported
    }

if __name__ == "__main__":
    print("Seeding premium data boost...")
    result = seed_premium_data()
    print(f"Success: {result}")
