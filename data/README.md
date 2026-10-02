# Data

**SYNTHETIC DEMONSTRATION DATA — NOT REAL PATIENT DATA.**

This folder holds prototype data used to run and demo ClinOps-AI. None of it
comes from real patients or real clinical encounters.

## Folders

- `raw/` — placeholder for unmodified third-party samples (empty by default;
  see "External datasets" below for what *could* go here).
- `processed/` — placeholder for any cleaned/derived version of the above.
- `samples/` — a few short example transcripts used by the NLP unit tests.
- `demo/` — synthetic, fully scripted consultations (English, Hindi, Marathi,
  and code-mixed) used to drive the end-to-end demo without needing a
  microphone or real audio file.
- `medicines.json` — a small, hand-curated medicine reference table used by
  the clinical-NLP normalizer and the recommendation engine.

## `medicines.json`

Each entry has: `generic_name`, `aliases` (brand names / common misspellings
used for matching), `common_strengths`, `forms`, `indications` (used only for
MVP-level symptom→medicine matching) and `default_route`.

This is **terminology/prototype data for a student project, not a clinical
authority**. Strengths and indications were compiled by hand from widely
published, non-proprietary drug-information summaries (e.g. national
essential-medicines lists and manufacturer package inserts) for teaching
purposes only. Do not use it to make real prescribing decisions.

## External datasets (not bundled)

The brief mentions two possible sources for a future, larger version of this
project. Neither is downloaded automatically (to respect the "no large
automatic downloads" constraint and access restrictions):

- **AI4Bharat IndicVoices** (https://ai4bharat.iitm.ac.in/indicvoices/) — a
  multilingual Indian speech corpus that could supply real Hindi/Marathi
  audio for ASR fine-tuning/evaluation. CC-BY-4.0-style licensing per
  AI4Bharat's terms — check current terms before use.
- **n2c2 (National NLP Clinical Challenges) datasets** — US clinical-NLP
  corpora that require a signed Data Use Agreement through the n2c2 portal.
  **Not included here** and must never be scraped or accessed without going
  through that official, restricted process.

If you want to extend this project with either dataset, request access
through the official channel above and drop the files under `raw/`.

## Disclaimer

All consultation content in `demo/` is invented for demonstration purposes.
ClinOps-AI is an academic prototype; nothing in this repository should be
used for real patient care.
