# Real Data Sources

The project can import real external corpus and frequency files, but large data
files are not vendored into this repository. Download them separately, then use
the import commands below.

## Sentence Corpora

### Tatoeba

Source: https://tatoeba.org/en/downloads

Useful file:

```text
sentences.tar.bz2
```

Format:

```text
sentence_id<TAB>iso_639_3_language<TAB>text
```

Import:

```powershell
python -m src.external_import D:\datasets\tatoeba\sentences.tar.bz2 --max-per-language 5000 --mode append
python -m src.build_dataset
python -m src.train
python -m src.evaluate
```

### OPUS / OpenSubtitles

Source: https://opus.nlpl.eu/OpenSubtitles/

Use OPUS for larger parallel corpora. Convert selected language files into one
sentence per line, then upload through `/corpus` or save to:

```text
data/raw/<lang>.txt
```

### Leipzig Corpora Collection

Source: https://wortschatz.uni-leipzig.de/

Leipzig corpora include sentence files and word frequency files. Convert word
frequency exports into:

```text
word<TAB>frequency
```

Then upload on `/frequency` or save as:

```text
data/frequency/<lang>.tsv
```

## Frequency Lists

### wordfreq

Source: https://pypi.org/project/wordfreq/

`wordfreq` provides frequency estimates for many languages. If installed, export
words into the same TSV format:

```text
word<TAB>frequency
```

Then import:

```powershell
python -m src.frequency --import-lexicon --limit-per-language 5000
```

## Minimum Target For 9/10 Data Readiness

Recommended minimum:

```text
1000+ corpus sentences per language
500+ independent benchmark rows
500-2000 frequency words for each core language
100+ editable name hints
```
