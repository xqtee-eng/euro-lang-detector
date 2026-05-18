import shutil
import unittest
from pathlib import Path

import api.utils as api_utils
from api.app import app
from src.analyzer import analyze_words
from src.benchmark import run_benchmark
from src.build_dataset import split_rows
from src.character_profiles import character_candidates, generate_character_profiles
from src.close_language_pack import apply_close_language_pack
from src.frequency import generate_frequency_lists, list_frequency_files
from src.hybrid import smart_detect, smart_detect_details
from src.name_detector import list_name_hints, add_name_hint
from src.related_classifier import train_related_classifiers

from src.word_lexicon import list_lexicon_words, add_lexicon_word, load_lexicons
from src.name_detector import load_name_hints
from src.storage import add_user, connect, init_db, list_feedback, verify_user
import src.storage

UKRAINIAN_GREETING = "\u041f\u0440\u0438\u0432\u0456\u0442, \u044f\u043a \u0442\u0432\u043e\u0457 \u0441\u043f\u0440\u0430\u0432\u0438?"
BELARUSIAN_GREETING = "\u0414\u043e\u0431\u0440\u044b \u0434\u0437\u0435\u043d\u044c"
MIXED_TEXT = "hello \u0441\u0432\u0435\u0442"
AMBIGUOUS_CYRILLIC = "\u0432\u0430\u043d\u044f"
AMBIGUOUS_NAME = "\u0410\u043d\u0430\u0441\u0442\u0430\u0441\u0456\u044f"
KNOWN_NAME = "\u041e\u0441\u0442\u0430\u043f"
KNOWN_WORD = "\u043a\u043e\u0437\u0430\u043a"
AMBIGUOUS_WORD = "\u043a\u043e\u0437\u0430"
GREEK_TEXT = "\u039a\u03b1\u03bb\u03b7\u03bc\u03ad\u03c1\u03b1 \u03c3\u03b1\u03c2"
GEORGIAN_TEXT = "\u10e5\u10d0\u10e0\u10d7\u10e3\u10da\u10d8 \u10d4\u10dc\u10d0"
ARMENIAN_TEXT = (
    "\u0540\u0561\u0575\u0565\u0580\u0565\u0576 \u056c\u0565\u0566\u0578\u0582"
)
KNOWN_UKRAINIAN_NAME_QUERY = "\u043e\u0441\u0442\u0430\u043f"
KNOWN_WORD_QUERY = "\u043a\u043e\u0437\u0430\u043a"
BROKEN_NAME_ENDPOINT_QUERY = "\u041e\u0441\u0442\u0430\u043f"


class DetectorSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Isolate tests from the production database
        cls.test_db_path = Path("tests_tmp_db.sqlite")
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()
            
        cls.original_db_path = src.storage.DATABASE_PATH
        cls.original_unknown_path = src.storage.UNKNOWN_PATH
        cls.original_feedback_path = src.storage.FEEDBACK_PATH
        cls.original_resolved_unknown_path = src.storage.RESOLVED_UNKNOWN_PATH
        src.storage.DATABASE_PATH = cls.test_db_path

        cls.test_storage_dir = Path("tests_tmp_storage")
        if cls.test_storage_dir.exists():
            shutil.rmtree(cls.test_storage_dir)
        cls.test_storage_dir.mkdir()
        src.storage.UNKNOWN_PATH = cls.test_storage_dir / "unknown.jsonl"
        src.storage.FEEDBACK_PATH = cls.test_storage_dir / "feedback.jsonl"
        src.storage.RESOLVED_UNKNOWN_PATH = (
            cls.test_storage_dir / "resolved_unknown.jsonl"
        )
        
        # Initialize isolated DB and wipe caches
        init_db()
        load_lexicons.cache_clear()
        load_name_hints.cache_clear()
        
        # Insert mock data required by the tests so they don't fail
        add_name_hint("Остап", "uk", name_type="person_name")
        add_lexicon_word("uk", "козак")

    @classmethod
    def tearDownClass(cls):
        src.storage.DATABASE_PATH = cls.original_db_path
        src.storage.UNKNOWN_PATH = cls.original_unknown_path
        src.storage.FEEDBACK_PATH = cls.original_feedback_path
        src.storage.RESOLVED_UNKNOWN_PATH = cls.original_resolved_unknown_path
        load_lexicons.cache_clear()
        load_name_hints.cache_clear()
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()
        if cls.test_storage_dir.exists():
            shutil.rmtree(cls.test_storage_dir)
            
    def test_empty_text_returns_unknown(self):
        self.assertEqual(smart_detect(""), "unknown")

    def test_ukrainian_unique_chars_are_caught_by_rules(self):
        self.assertEqual(smart_detect(UKRAINIAN_GREETING), "uk")

    def test_greek_script_is_detected_by_rules(self):
        result = smart_detect_details(GREEK_TEXT)
        self.assertEqual(result["language"], "el")
        self.assertEqual(result["source"], "rule")

    def test_belarusian_lexical_hint(self):
        result = smart_detect_details(BELARUSIAN_GREETING)
        self.assertEqual(result["language"], "be")
        self.assertEqual(result["reason"], "lexical_hint")

    def test_mixed_latin_cyrillic_is_allowed(self):
        result = smart_detect_details(MIXED_TEXT, record_unknown=False)
        self.assertNotEqual(result["language"], "unknown")

    def test_command_like_text_returns_unknown(self):
        result = smart_detect_details("python api/app.py")
        self.assertEqual(result["language"], "unknown")
        self.assertEqual(result["reason"], "command_like_text")

    def test_short_ambiguous_cyrillic_returns_unknown(self):
        result = smart_detect_details(AMBIGUOUS_CYRILLIC, record_unknown=False)
        self.assertEqual(result["language"], "unknown")
        self.assertEqual(result["reason"], "short_ambiguous_cyrillic")

    def test_single_cyrillic_proper_name_returns_unknown(self):
        result = smart_detect_details(AMBIGUOUS_NAME, record_unknown=False)
        self.assertEqual(result["language"], "unknown")
        self.assertIn(result["reason"], ["single_cyrillic_proper_name", "ambiguous_name"])

    def test_known_ukrainian_name_returns_name_entity(self):
        result = smart_detect_details(KNOWN_NAME)
        self.assertEqual(result["language"], "uk")
        self.assertEqual(result.get("entity_type"), "person_name")
        self.assertIn("reliability", result)

    def test_short_single_word_has_reliability(self):
        result = smart_detect_details("friend")
        self.assertEqual(result["language"], "en")
        self.assertEqual(result["reason"], "exact_phrase_hint")

    def test_common_short_greetings_use_exact_hints(self):
        cases = {
            "hello": "en",
            "bonjour": "fr",
            "ciao": "it",
            "hola": "es",
            "merhaba": "tr",
        }
        for text, language in cases.items():
            with self.subTest(text=text):
                result = smart_detect_details(text)
                self.assertEqual(result["language"], language)
                self.assertEqual(result["reason"], "exact_phrase_hint")

    def test_high_confidence_detection_does_not_create_feedback(self):
        before = len(list_feedback())
        result = smart_detect_details(
            "This is an official announcement for all citizens."
        )
        self.assertNotEqual(result["language"], "unknown")
        self.assertEqual(len(list_feedback()), before)

    def test_feedback_endpoint_records_manual_feedback(self):
        response = app.test_client().post(
            "/feedback",
            json={"text": "This is a reviewed correction.", "lang": "en"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(row["source"] == "manual" for row in list_feedback())
        )

    def test_public_href_uses_public_base_url_for_relative_paths(self):
        original_public_base_url = api_utils.PUBLIC_BASE_URL
        api_utils.PUBLIC_BASE_URL = "https://demo-5000.app.github.dev"
        try:
            self.assertEqual(
                api_utils.public_href("/admin"),
                "https://demo-5000.app.github.dev/admin",
            )
            self.assertEqual(
                api_utils.public_href("https://example.com/admin"),
                "https://example.com/admin",
            )
        finally:
            api_utils.PUBLIC_BASE_URL = original_public_base_url

    def test_login_returns_public_next_url_when_configured(self):
        original_public_base_url = api_utils.PUBLIC_BASE_URL
        api_utils.PUBLIC_BASE_URL = "https://demo-5000.app.github.dev"
        try:
            response = app.test_client().post(
                "/admin/login",
                data={"username": "admin", "password": "admin", "next": "/admin"},
                headers={"Accept": "application/json"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json["next"],
                "https://demo-5000.app.github.dev/admin",
            )
        finally:
            api_utils.PUBLIC_BASE_URL = original_public_base_url

    def test_login_returns_current_codespaces_host_when_public_url_is_missing(self):
        original_public_base_url = api_utils.PUBLIC_BASE_URL
        api_utils.PUBLIC_BASE_URL = ""
        try:
            response = app.test_client().post(
                "/admin/login",
                base_url="https://demo-5000.app.github.dev",
                data={"username": "admin", "password": "admin", "next": "/admin"},
                headers={"Accept": "application/json"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json["next"],
                "https://demo-5000.app.github.dev/admin",
            )
        finally:
            api_utils.PUBLIC_BASE_URL = original_public_base_url

    def test_login_page_uses_versioned_static_assets(self):
        response = app.test_client().get("/admin/login")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("/static/js/app.js?v=", html)
        self.assertIn("/static/css/main.css?v=", html)
        self.assertIn("window.handleLogin = async function", html)

    def test_login_rejects_absolute_next_url(self):
        original_public_base_url = api_utils.PUBLIC_BASE_URL
        api_utils.PUBLIC_BASE_URL = "https://demo-5000.app.github.dev"
        try:
            response = app.test_client().post(
                "/admin/login",
                data={
                    "username": "admin",
                    "password": "admin",
                    "next": "http://localhost:5000/admin",
                },
                headers={"Accept": "application/json"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json["next"],
                "https://demo-5000.app.github.dev/admin",
            )
        finally:
            api_utils.PUBLIC_BASE_URL = original_public_base_url

    def test_user_passwords_are_hashed_and_verified(self):
        add_user("TestUser", "Strong1!", role="viewer")
        with connect() as db:
            row = db.execute(
                "SELECT password FROM users WHERE username = ?",
                ("TestUser",),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertNotEqual(row["password"], "Strong1!")
        self.assertTrue(str(row["password"]).startswith("pbkdf2_sha256$"))
        self.assertTrue(verify_user("TestUser", "Strong1!"))

    def test_related_language_group_is_reported_for_close_languages(self):
        result = smart_detect_details(
            "Ovo je jednostavna recenica za testiranje jezika.",
            top_k=5,
            record_unknown=False,
        )
        self.assertIn(result["language"], {"bs", "hr", "sr"})
        self.assertEqual(result["language_group"], "serbo_croatian")
        self.assertEqual(result["group_reliability"], "ambiguous")
        self.assertTrue(result["ambiguous_group"])
        self.assertEqual(result["possible_languages"], ["bs", "hr", "sr"])
        self.assertLessEqual(result["confidence"], 1.0)

    def test_ambiguous_multiword_lexicon_falls_through_to_models(self):
        for word in ("zajednica", "kultura"):
            add_lexicon_word("bs", word)
            add_lexicon_word("hr", word)

        result = smart_detect_details("zajednica kultura", record_unknown=False)
        self.assertFalse(
            result["source"] == "lexicon" and result["language"] == "unknown"
        )

    def test_word_analyzer_detects_mixed_tokens(self):
        result = analyze_words("hello \u043f\u0440\u0438\u0432\u0456\u0442 bonjour")
        self.assertEqual(result["language"], "mixed")
        self.assertEqual(result["token_count"], 3)
        self.assertEqual(result["known_token_count"], 3)

    def test_word_analyzer_marks_unknown_tokens(self):
        result = analyze_words("qwertyzz")
        self.assertEqual(result["token_count"], 1)
        self.assertIn("tokens", result)

    def test_split_rows_keeps_each_language_in_train_and_test(self):
        rows = [
            {"text": f"sample {language} {index}", "lang": language}
            for language in ("uk", "fr")
            for index in range(5)
        ]
        train_rows, test_rows = split_rows(rows, test_ratio=0.2, seed=1)
        self.assertEqual(len(train_rows), 8)
        self.assertEqual(len(test_rows), 2)
        self.assertEqual({row["lang"] for row in train_rows}, {"uk", "fr"})
        self.assertEqual({row["lang"] for row in test_rows}, {"uk", "fr"})


    def test_frequency_files_are_available(self):
        existing = list_frequency_files()
        if not any(item["entries"] > 0 for item in existing):
            result = generate_frequency_lists(max_words_per_language=1000)
            self.assertGreaterEqual(result["files"], 40)
            existing = list_frequency_files()
        self.assertGreaterEqual(len(existing), 40)
        self.assertTrue(any(item["entries"] > 0 for item in existing))

    def test_ai_benchmark_is_strong_enough_for_mvp(self):
        report = run_benchmark()
        self.assertGreaterEqual(report["accuracy"], 0.85)
        self.assertGreater(report["samples"], 10)

    def test_character_profiles_explain_script_languages(self):
        profiles = generate_character_profiles(save=False)
        self.assertIn("uk", profiles)
        self.assertTrue(character_candidates(GEORGIAN_TEXT))

    def test_close_language_pack_writes_curated_rows(self):
        temp_dir = Path("tests_tmp_close_pack")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            result = apply_close_language_pack(
                mode="replace",
                output_dir=temp_dir,
                languages=["bs", "hr", "sr", "nb", "nn"],
            )
            self.assertEqual(set(result["languages"]), {"bs", "hr", "sr", "nb", "nn"})
            self.assertGreaterEqual(result["languages"]["bs"]["total_lines"], 10)
            self.assertTrue((temp_dir / "bs.txt").exists())
            self.assertTrue((temp_dir / "nn.txt").exists())
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_related_classifier_trains_distinctive_markers(self):
        temp_dir = Path("tests_tmp_related_classifier")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            temp_dir.mkdir()
            dataset_path = temp_dir / "train.jsonl"
            dataset_path.write_text(
                "\n".join(
                    [
                        '{"lang":"hr","text":"Ovdje govorimo hrvatski i uvijek koristimo lijep svijet."}',
                        '{"lang":"hr","text":"Rijec i djevojka su cesti primjeri za hrvatski tekst."}',
                        '{"lang":"sr","text":"Ovde govorimo srpski i uvek koristimo lep svet."}',
                        '{"lang":"sr","text":"Rec i devojka su cesti primeri za srpski tekst."}',
                        '{"lang":"bs","text":"Ovdje govorimo bosanski i sada treba znati gdje."}',
                        '{"lang":"bs","text":"Hvala i molim su cesti primjeri za bosanski tekst."}',
                        '{"lang":"nb","text":"Jeg vet ikke hva dere vil gjore i dag."}',
                        '{"lang":"nb","text":"Dette er noe vi har i vanlig bokmal tekst."}',
                        '{"lang":"nn","text":"Eg veit ikkje kva dei vil gjere i dag."}',
                        '{"lang":"nn","text":"Dette er noko me har i vanleg nynorsk tekst."}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            profiles = train_related_classifiers(
                dataset_path=dataset_path,
                save_path=temp_dir / "related_profiles.json",
            )
            self.assertIn("serbo_croatian", profiles)
            self.assertIn("norwegian", profiles)
            self.assertTrue(profiles["serbo_croatian"]["hr"]["markers"])
            self.assertTrue(profiles["norwegian"]["nn"]["markers"])
            self.assertEqual(
                profiles["serbo_croatian"]["hr"]["markers"][0]["source"], "manual"
            )
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_lexicon_search_lists_known_word(self):
        lexicons = list_lexicon_words(query=KNOWN_WORD_QUERY, language="uk")
        self.assertIn("uk", lexicons)
        self.assertIn(KNOWN_WORD_QUERY, lexicons["uk"])

    def test_name_search_lists_known_name(self):
        names = list_name_hints(query=KNOWN_UKRAINIAN_NAME_QUERY, language="uk")
        self.assertTrue(
            any(item["name"] == KNOWN_UKRAINIAN_NAME_QUERY for item in names)
        )


if __name__ == "__main__":
    unittest.main()
