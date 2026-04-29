# Roadmap

Ideas for turning the detector into a fuller AI-style application:

1. SQLite storage - done
   - Store unknown texts, feedback, lexicon words, names, users, and training runs in one database.
   - Keep JSONL export/import for backup.

2. Admin dashboard - done
   - Show unknown rate, accuracy by language, last feedback items, retrain status, and dataset size.

3. Active learning - done
   - Ask the user to label only uncertain or conflicting examples.
   - Prioritize items that would improve the model most.

4. Training runs - done
   - Save each retrain event with date, sample count, accuracy, and report path.
   - Allow rollback to a previous model profile.

5. Corpus manager - done
   - Upload reviewed `.txt` files per language from the browser.
   - Rebuild dataset/train/test from the browser.

6. Better word knowledge - done
   - Add word frequency lists per language.
   - Mark ambiguous words and show all possible languages.

7. Name knowledge - done
   - Expand names by country and language.
   - Distinguish person names from ordinary words.

8. Production server - done
   - Run Flask behind Waitress or Gunicorn.
   - Add configuration for host, port, data directory, and model directory.

9. API clients - done
   - Add simple REST examples and a small frontend client.
   - Add OpenAPI documentation.

10. Safety controls - done
    - Keep human-approved learning only.
    - Never automatically train on low-confidence guesses.

## Project Status

As of April 2026, the European Language Detector MVP is **100% COMPLETE**. 
All original objectives have been met:
- Successfully supports **40 configured European languages**.
- High performance achieved using hybrid N-gram profiles and dynamic unique character rules (bypassing heavy Lingua engine when confident).
- Self-learning loop is fully functional, capable of rebuilding models from scratch.
- Modern Web UI built with Flask, featuring a robust Admin Dashboard.
