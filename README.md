# European Language Detector

Python CLI and Flask service for detecting European languages with a conservative
`rules + names + lexicon + Lingua + local profile fallback` pipeline.

## What This Project Does

- detects 40 configured European languages;
- handles unique scripts and language-specific characters with deterministic rules;
- detects known words through editable lexicon files;
- detects personal names through an editable name manager;
- analyzes full text word by word;
- stores unknown texts for review;
- learns only from human feedback, not from its own guesses.

## Supported Languages

`sq, hy, az, eu, be, bs, bg, ca, hr, cs, da, nl, en, et, fi, fr, ka, de, el, hu, is, ga, it, lv, lt, mk, nb, nn, pl, pt, ro, ru, sr, sk, sl, es, sv, tr, uk, cy`

See `data/languages.txt` for the code-to-name list.

## Install

```bash
python -m pip install -r requirements.txt
```

## Linux / Codespaces Quick Start

On a Linux machine or in GitHub Codespaces:

```bash
git clone https://github.com/xqtee-eng/euro-lang-detector.git
cd euro-lang-detector

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m src.db_manage init
python -m src.db_manage import-jsonl

export ELD_DEBUG=0
export ELD_ADMIN_USERNAME="admin"
export ELD_ADMIN_PASSWORD="replace-with-strong-password"
export ELD_SECRET_KEY="replace-with-random-secret-at-least-32-chars"

python serve.py
```

In GitHub Codespaces, create the codespace from the repository page and start
from the `python -m venv .venv` command because the repository is already
checked out. Open the forwarded port `5000` when Codespaces shows it. Do not
open `localhost:5000` in your local desktop browser unless you are running the
server on your own computer; for Codespaces, use the generated
`https://<codespace-name>-5000.app.github.dev/...` URL or the `Open in Browser`
button in the Codespaces `Ports` tab. When running inside Codespaces, the app
auto-detects the forwarded URL and renders sidebar navigation links with the
matching `app.github.dev` URL.

For other hosted environments, set `ELD_PUBLIC_URL` if you want local preview
navigation links to use a canonical public URL:

```bash
export ELD_PUBLIC_URL="https://your-public-domain.example"
```

For a temporary Codespaces demo with the default `admin/admin` login, use debug
mode instead of production mode:

```bash
export ELD_HOST=0.0.0.0
export ELD_PORT=5000
export ELD_DEBUG=1
export ELD_ADMIN_USERNAME="admin"
export ELD_ADMIN_PASSWORD="admin"
export ELD_SECRET_KEY="dev-only-secret-key-at-least-32-chars"
export ELD_PUBLIC_URL="https://${CODESPACE_NAME}-5000.app.github.dev"
```

Local URLs:

```text
http://127.0.0.1:5000/detect
http://127.0.0.1:5000/admin
```

The SQLite runtime database `data/app.db` is not tracked in Git. The
`src.db_manage init` command creates it locally.

If you change `ELD_ADMIN_USERNAME` or `ELD_ADMIN_PASSWORD` after the database
was already created, recreate the local database so the initial owner account is
created with the new credentials:

```bash
rm data/app.db
python -m src.db_manage init
python -m src.db_manage import-jsonl
```

## Recommended Run Order

Create starter data, build train/test files, train, and evaluate:

```bash
python -m src.seeding.seed_dataset --overwrite
python -m src.close_language_pack --mode append
python -m src.build_dataset
python -m src.train
python -m src.evaluate
```

## Real Tatoeba Data Pipeline

If `sentences.tar.bz2` from Tatoeba is in the project root, build real corpora,
an independent benchmark, and frequency TSV files:

```bash
python -m src.real_data_pipeline sentences.tar.bz2 --mode replace --raw-per-language 1000 --benchmark-per-language 15 --frequency-words-per-language 2000 --frequency-source-per-language 10000 --min-length 20
python -m src.build_dataset --max-samples-per-language 1000 --test-ratio 0.2
python -m src.train
python -m src.frequency --import-lexicon --limit-per-language 2000
python -m src.evaluate
```

This creates:

```text
data/raw/*.txt              1000 real corpus rows per configured language
data/benchmark.jsonl        600 independent benchmark rows
data/frequency/*.tsv        2000 frequency words per configured language
data/real_data_report.json  import summary
```

## Related Language Classifier

The detector has a second-stage classifier for close language groups:

```text
serbo_croatian: bs, hr, sr
norwegian: nb, nn
```

It trains automatically during:

```bash
python -m src.train
```

and writes:

```text
models/related_profiles.json
```

For these groups, `/detect` includes extra fields such as:

```json
{
  "language_group": "serbo_croatian",
  "possible_languages": ["bs", "hr", "sr"],
  "group_reliability": "ambiguous",
  "related_classifier": {
    "suggested_language": "hr",
    "applied": false
  }
}
```

The second-stage classifier is conservative: it only overrides the main language
when its margin is strong enough. Otherwise it reports the group and candidates
without pretending the exact label is certain.

The curated close-language pack is stored separately in `data/close_pack` and
is added to `train.jsonl` only. It is not mixed into `test.jsonl`, so these
extra disambiguation sentences do not distort evaluation.

The admin close-language page now also shows:

```text
/groups
  - exact accuracy vs group accuracy
  - internal confusions inside bs/hr/sr and nb/nn
  - external confusions outside the close-language family
  - learned marker hints extracted from corpus + frequency lists
```

After this, the project creates:

```text
data/app.db
data/dataset.jsonl
data/train.jsonl
data/test.jsonl
models/profiles.json
models/evaluation_report.json
```

## CLI

Interactive mode:

```bash
python run.py
```

One-shot detection:

```bash
python run.py "Bonjour tout le monde"
python run.py --details "Привіт, як справи?"
```

## Web UI

Start the Flask app:

```bash
python api/app.py
```

Open:

```text
http://127.0.0.1:5000/detect
```

The public app is intentionally small: detector, API docs, safety page, and an
admin entry point. Dataset editing, learning queues, corpus uploads, model
training, reports, and rollback live in the separate admin console:

```text
http://127.0.0.1:5000/admin
```

From Admin you can run `Rebuild dataset`, `Train`, `Retrain feedback`, and
`Evaluate` directly from the browser.

Admin pages require a password. The local default is:

```text
admin
```

For production, set:

```powershell
$env:ELD_ADMIN_PASSWORD="replace-with-strong-password"
$env:ELD_SECRET_KEY="replace-with-random-secret-at-least-32-chars"
```

Useful pages:

```text
/detect   - main detector and word analyzer
/admin    - separate admin console with model operations
/quality  - data quality score and next improvement checklist
/benchmark - AI benchmark by category
/groups - close-language report, confusion breakdown, and learned marker hints
/characters - character profiles and alphabet signatures
/model-card - model card with quality, safety, data, and limitations
/logs    - recent rotating application logs
/runs     - training history, model snapshots, and rollback
/learn    - active learning queue for uncertain examples
/review   - review unknown texts
/corpus   - upload reviewed .txt corpora, apply curated close-language train pack, and rebuild dataset/train/test
/frequency - generate/import word frequency lists
/lexicon  - add, delete, import, and search words
/names    - add, delete, and search name hints
/api-docs - OpenAPI JSON and REST examples
/safety   - human-approved learning policy
/report   - per-language evaluation report
/storage  - SQLite storage summary as JSON
/openapi.json - OpenAPI schema
/admin.json - admin dashboard data as JSON
/quality.json - data quality report as JSON
/runs.json - training runs as JSON
/learn/items - active learning queue as JSON
```

## SQLite Storage

The main application state is stored in:

```text
data/app.db
```

This SQLite file is local runtime state and is intentionally not tracked in Git.
Create it with `python -m src.db_manage init`, then import versioned JSONL,
lexicon, and name files with `python -m src.db_manage import-jsonl`.

The database contains:

```text
unknown_texts
feedback_samples
lexicon_words
name_hints
users
training_runs
```

JSONL files are still kept as backup/import/export files.

Initialize or inspect the database:

```bash
python -m src.db_manage init
python -m src.db_manage import-jsonl
python -m src.db_manage export-jsonl
python -m src.db_manage stats
```

## API Examples

Detect language:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/detect -ContentType "application/json" -Body '{"text":"Bonjour","top_k":3}'
```

Analyze words:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/analyze -ContentType "application/json" -Body '{"text":"hello привіт bonjour","top_k":3}'
```

Add a lexicon word:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/lexicon/items -ContentType "application/json" -Body '{"lang":"uk","word":"козак"}'
```

Add a name hint:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/names/items -ContentType "application/json" -Body '{"lang":"uk","name":"Остап","country":"Ukraine","confidence":0.95}'
```

## Learning Workflow

When the detector is unsure, it writes the text to `data/unknown.jsonl`.

Use `/review` to either:

- add a correct label as feedback;
- discard the item so it does not keep coming back.
- clear review files if you want to remove the previous unknown/resolved history.

Then retrain:

```bash
python -m src.retrain
python -m src.evaluate
```

## Training Runs And Rollback

Every `python -m src.train` and `python -m src.retrain` creates a model snapshot:

```text
models/snapshots/*.profiles.json
```

Open:

```text
http://127.0.0.1:5000/runs
```

From that page you can inspect train/retrain/evaluate/rollback history and restore
`models/profiles.json` from a previous model snapshot.

`src.retrain` promotes reviewed feedback into `data/dataset.jsonl` and rebuilds the
local profiles. The project intentionally avoids blind self-training because that
would teach the model its own mistakes.

## Active Learning

The detector stores uncertain or conflicting examples in SQLite:

```text
active_learning_items
```

Open the review queue:

```text
http://127.0.0.1:5000/learn
```

When you confirm an item, it is saved to `feedback_samples`. Then run:

```bash
python -m src.retrain
python -m src.evaluate
```

## Corpus Manager

Open:

```text
http://127.0.0.1:5000/corpus
```

Upload or paste reviewed `.txt` text for a selected language. Each non-empty
line becomes one reviewed corpus sample in `data/raw/<lang>.txt`.

After editing corpus files from the browser, click `Rebuild dataset/train/test`
or run:

```bash
python -m src.build_dataset
python -m src.train
python -m src.evaluate
```

## Word And Name Knowledge

The Lexicon page stores word frequency metadata and marks ambiguous words that
appear in more than one language. The Name page stores country/language hints
and labels person names separately from ordinary words.

The Frequency page creates `data/frequency/<lang>.tsv` files from reviewed
corpus text and imports those words into SQLite lexicon knowledge:

```bash
python -m src.frequency --generate --import
python -m src.seeding.seed_names
```

## Security and Roles

The system uses a 3-tier administrative hierarchy for secure management:

1. **Owner**: Full access to all data and user management.
2. **Admin (Super Admin)**: Can manage detector data and create/edit Reviewer accounts. Cannot modify other Admins or the Owner.
3. **Viewer (Reviewer)**: Read-only access to reports and status. Cannot modify any data or users.

The local default account is:

```text
Username: admin
Password: admin
```

Production mode (`ELD_DEBUG=0`) rejects the default `admin` password. Set a
non-default password and a random secret key before starting the server:

```bash
export ELD_ADMIN_USERNAME="admin"
export ELD_ADMIN_PASSWORD="replace-with-strong-password"
export ELD_SECRET_KEY="replace-with-random-secret-at-least-32-chars"
```

`ELD_ADMIN_USERNAME` is optional; if you do not set it, the username is
`admin`. If the SQLite database already exists, changing these variables does
not rename or reset the existing owner account. For a fresh demo environment,
stop the server, remove `data/app.db`, set the new owner credentials, and run
the database setup again:

```bash
rm -f data/app.db
export ELD_ADMIN_USERNAME="owner-name"
export ELD_ADMIN_PASSWORD="owner-password"
python -m src.db_manage init
python -m src.db_manage import-jsonl
```

The primary owner account cannot be deleted or demoted from the Admin Manager.
Use the Admin Manager to create additional `super_admin` or `viewer` accounts
for other people.

Other users can access the app while the server process is running. The public
detector page does not require login; admin pages require a valid account. In
Codespaces, make port `5000` public if you want people outside your GitHub
session to open the forwarded `app.github.dev` URL. The owner does not need to
stay logged in, but the terminal running `python serve.py` must stay alive.

You can add, edit, or delete users via the `/admin` console (requires Owner or Admin privileges).

You can also upload real external TSV lists from `/frequency`:

```text
word<TAB>frequency
language<TAB>1200
system<TAB>900
```

The Benchmark page checks short words, ambiguous words, names, scripts, mixed
text, and normal phrases:

```text
http://127.0.0.1:5000/benchmark
http://127.0.0.1:5000/benchmark.json
```

The Characters page generates alphabet/signature profiles from the reviewed
corpus and explains which languages a text resembles by character evidence:

```text
http://127.0.0.1:5000/characters
http://127.0.0.1:5000/characters.json
```

The Model Card and Logs pages make the project closer to a production AI app:

```text
http://127.0.0.1:5000/model-card
http://127.0.0.1:5000/model-card.json
http://127.0.0.1:5000/logs
```

Useful JSON endpoints:

```text
/frequency/files
/lexicon/entries
/words/analyze?word=hello
/names/analyze?name=Ostap
```

## Production Server

Install requirements, then run the Waitress server:

```bash
python serve.py
```

Configuration is done through environment variables:

```text
ELD_HOST=127.0.0.1
ELD_PORT=5000
ELD_DATA_DIR=data
ELD_MODELS_DIR=models
ELD_DEBUG=0
ELD_ADMIN_PASSWORD=replace-with-strong-password
ELD_SECRET_KEY=replace-with-random-secret-at-least-32-chars
```

See `deployment/README.md` and `.env.example`.

## Real External Data

Large real corpora are not included in the repo. Use the importer with external
files such as Tatoeba sentence dumps:

```powershell
python -m src.external_import D:\datasets\tatoeba\sentences.tar.bz2 --max-per-language 5000 --mode append
python -m src.build_dataset
python -m src.train
python -m src.evaluate
```

See `data_sources/REAL_DATA_SOURCES.md` for source links and required formats.

## Data Files

Raw reviewed texts:

```text
data/raw/uk.txt
data/raw/fr.txt
data/raw/de.txt
```

User lexicons:

```text
data/lexicons/uk.txt
data/lexicons/en.txt
```

User name hints:

```text
data/names/uk.jsonl
data/names/ru.jsonl
```

Each raw text file should contain one reviewed sentence per line.

Review and learning files:

```text
data/unknown.jsonl          - texts the detector could not classify
data/resolved_unknown.jsonl - discarded/resolved texts that should not reappear
data/feedback.jsonl         - reviewed labels waiting for retraining
```

On `/review`, `Clear visible unknowns` clears active unknowns and keeps those
items as resolved. `Clear review files` clears both active and resolved review
items. JSONL files are refreshed from `data/app.db`.
