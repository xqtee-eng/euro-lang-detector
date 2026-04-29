import shutil
import tarfile
import unittest
from pathlib import Path

from api.app import app
from src.analyzer import analyze_words
from src.benchmark import run_benchmark
from src.build_dataset import split_rows
from src.character_profiles import character_candidates, generate_character_profiles
from src.close_language_pack import apply_close_language_pack
from src.legacy.external_import import import_tatoeba_sentences
from src.frequency import generate_frequency_lists, list_frequency_files
from src.hybrid import smart_detect, smart_detect_details
from src.name_detector import list_name_hints
from src.legacy.real_data_pipeline import build_real_data_resources
from src.related_classifier import train_related_classifiers
from src.seeding.seed_dataset import expand_seed_texts
from src.word_lexicon import list_lexicon_words

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

    def test_known_ukrainian_word_returns_word_entity(self):
        result = smart_detect_details(KNOWN_WORD)
        self.assertEqual(result["language"], "uk")
        self.assertEqual(result.get("entity_type"), "word")

    def test_ambiguous_word_returns_candidates(self):
        result = smart_detect_details(AMBIGUOUS_WORD, record_unknown=False)
        self.assertEqual(result["language"], "unknown")
        self.assertEqual(result["reason"], "ambiguous_word")
        self.assertEqual(result.get("entity_type"), "word")

    def test_details_response_has_candidates(self):
        result = smart_detect_details("Bonjour tout le monde")
        self.assertIn("language", result)
        self.assertIn("confidence", result)
        self.assertIn("candidates", result)
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

    def test_seed_expansion_creates_more_training_text(self):
        rows = expand_seed_texts(["one", "two", "three"])
        self.assertGreaterEqual(len(rows), 30)
        self.assertEqual(len(rows), len(set(rows)))

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

    def test_external_tatoeba_importer_maps_languages(self):
        temp_dir = Path("tests_tmp_external_import")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            temp_dir.mkdir()
            input_path = temp_dir / "sentences.tsv"
            output_dir = temp_dir / "raw"
            input_path.write_text(
                "1\teng\tThis is a real English sentence.\n"
                "2\tukr\t\u0426\u0435 \u0440\u0435\u0430\u043b\u044c\u043d\u0435 \u0443\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u0435 \u0440\u0435\u0447\u0435\u043d\u043d\u044f.\n"
                "3\tzzz\tIgnored language.\n",
                encoding="utf-8",
            )
            result = import_tatoeba_sentences(
                input_path, output_dir=output_dir, mode="replace"
            )
            self.assertEqual(result["by_language"]["en"], 1)
            self.assertEqual(result["by_language"]["uk"], 1)
            self.assertTrue((output_dir / "en.txt").exists())
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_external_tatoeba_importer_reads_tar_bz2(self):
        temp_dir = Path("tests_tmp_external_import_tar")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            temp_dir.mkdir()
            source_path = temp_dir / "sentences.tsv"
            archive_path = temp_dir / "sentences.tar.bz2"
            output_dir = temp_dir / "raw"
            source_path.write_text(
                "1\teng\tThis is a real English sentence.\n"
                "2\tfra\tCeci est une phrase francaise reelle.\n",
                encoding="utf-8",
            )
            with tarfile.open(archive_path, "w:bz2") as archive:
                archive.add(source_path, arcname="sentences.tsv")
            result = import_tatoeba_sentences(
                archive_path, output_dir=output_dir, mode="replace"
            )
            self.assertEqual(result["by_language"]["en"], 1)
            self.assertEqual(result["by_language"]["fr"], 1)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_real_data_pipeline_creates_benchmark_and_frequency(self):
        temp_dir = Path("tests_tmp_real_pipeline")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            temp_dir.mkdir()
            input_path = temp_dir / "sentences.tsv"
            input_path.write_text(
                "\n".join(
                    [
                        "1\teng\tThis is an independent English benchmark sentence.",
                        "2\teng\tThis English training sentence adds useful words.",
                        "3\teng\tAnother English training sentence expands frequency.",
                        "4\tfra\tCeci est une phrase francaise pour le benchmark.",
                        "5\tfra\tCette phrase francaise ajoute des mots utiles.",
                        "6\tfra\tEncore une phrase francaise pour la frequence.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            report = build_real_data_resources(
                input_path,
                raw_per_language=2,
                benchmark_per_language=1,
                frequency_words_per_language=10,
                frequency_source_per_language=2,
                min_length=10,
                mode="replace",
                run_model_steps=False,
                raw_dir=temp_dir / "raw",
                benchmark_path=temp_dir / "benchmark.jsonl",
                frequency_dir=temp_dir / "frequency",
                report_path=temp_dir / "report.json",
            )
            self.assertGreaterEqual(report["benchmark"]["rows"], 2)
            self.assertGreaterEqual(report["frequency"]["by_language"]["en"], 1)
            self.assertGreaterEqual(report["frequency"]["by_language"]["fr"], 1)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def test_character_profiles_explain_script_languages(self):
        profiles = generate_character_profiles()
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

    def test_api_pages_and_json_endpoints_work(self):
        client = app.test_client()
        client.post("/admin/login", data={"password": "admin"})
        for path in (
            "/detect",
            "/admin",
            "/admin.json",
            "/quality",
            "/quality.json",
            "/benchmark",
            "/benchmark.json",
            "/groups",
            "/groups.json",
            "/characters",
            "/characters.json",
            "/model-card",
            "/model-card.json",
            "/logs",
            "/logs.json",
            "/runs",
            "/runs.json",
            "/learn",
            "/learn/items",
            "/review",
            "/corpus",
            "/corpus/files",
            "/frequency",
            "/frequency/files",
            "/lexicon",
            "/lexicon/entries",
            "/names",
            "/api-docs",
            "/openapi.json",
            "/safety",
            "/safety.json",
            "/report",
            "/health",
            "/storage",
            "/review/storage",
            "/words/analyze?word=hello",
            f"/names/analyze?name={BROKEN_NAME_ENDPOINT_QUERY}",
        ):
            with self.subTest(path=path):
                self.assertLess(client.get(path).status_code, 400)

        detect_response = client.post("/detect", json={"text": "Bonjour", "top_k": 3})
        self.assertEqual(detect_response.status_code, 200)
        self.assertEqual(detect_response.get_json()["language"], "fr")

        analyze_response = client.post(
            "/analyze",
            json={
                "text": "hello \u043f\u0440\u0438\u0432\u0456\u0442 bonjour",
                "top_k": 3,
            },
        )
        self.assertEqual(analyze_response.status_code, 200)
        self.assertEqual(analyze_response.get_json()["language"], "mixed")

        groups_response = client.get("/groups.json")
        self.assertEqual(groups_response.status_code, 200)
        groups_payload = groups_response.get_json()
        self.assertIn("groups", groups_payload)
        self.assertIn("internal_confusions", groups_payload)
        self.assertIn("external_confusions", groups_payload)
        self.assertIn("low_margin_cases", groups_payload)

        openapi_response = client.get("/openapi.json")
        self.assertEqual(openapi_response.status_code, 200)
        self.assertIn("/corpus/close-pack", openapi_response.get_json()["paths"])


if __name__ == "__main__":
    unittest.main()
