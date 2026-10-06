# ClinOps-AI

**Multilingual AI-Assisted Prescription & Clinical Recommendation System**


> 

## Overview

ClinOps-AI turns a recorded doctor-patient consultation into a structured,
doctor-approved prescription:

```
audio upload/record → ASR (speech-to-text) → transcript
  → speaker diarization → clinical relevance detection
  → extractive clinical condensation → clinical entity extraction
    (symptoms/diagnoses/medications/precautions)
  → candidate medicine recommendations
  → doctor review & edit
  → doctor approval / rejection
  → prescription → PDF → persisted in the database
```

Every recommendation is machine-generated but **nothing reaches a patient
without explicit doctor approval** (see the `DRAFT → AI_SUGGESTED →
DOCTOR_EDITED → APPROVED/REJECTED` state machine below).

## Architecture

```
backend/app/
  main.py                     FastAPI app, router wiring, /health
  config/settings.py          Pydantic-settings config (.env-driven)
  db/database.py              SQLAlchemy engine/session (SQLite by default)
  models/domain.py            ORM: Doctor, Patient, Consultation, Transcript,
                               ClinicalEntity, Recommendation, Prescription,
                               PrescriptionItem, ClinicalSummary
  schemas/api_models.py       Pydantic request/response schemas
  repositories/repository.py  Data-access layer (CRUD)
  api/routes/
    patients.py                POST/GET /api/patients
    consultations.py           full consultation workflow endpoints
  services/
    speech/whisper_service.py         faster-whisper ASR + explicit DEMO mode
    speech/speaker_diarization.py     pyannote speaker turns + cautious role inference
    nlp/clinical_summary.py           explainable relevance scoring + extractive condensation
    nlp/entity_extractor.py           hybrid regex+dictionary clinical NLP
    recommendation/recommendation_service.py   transparent candidate scoring
    prescription/prescription_service.py       builds prescription payload
    pdf_generator/pdf_service.py               ReportLab PDF (Unicode/Devanagari)
    translation/multilingual_service.py        local EN/HI/MR phrasebook
    feedback_learning/feedback_updater.py       stub for future adaptive learning

frontend/src/
  App.tsx, layouts/AppLayout.tsx      shell + disclaimer banner
  pages/HomePage.tsx                  dashboard / new consultation / workspace
  components/                         audio input, transcript viewer,
                                       clinical summary, clinical-data + recommendation panel,
                                       doctor review/edit, prescription
                                       preview, PDF download, language picker
  hooks/useConversation.ts            drives the consultation state machine
  services/api.ts                     typed REST client (axios)
  types/index.ts                      types mirroring the backend schemas

data/
  medicines.json               small curated medicine knowledge base
  demo/, samples/               synthetic (labelled) demo consultations
  README.md                     data sourcing/licensing notes
```

## Tech stack

- **Backend:** FastAPI, SQLAlchemy + SQLite, Pydantic v2, faster-whisper,
  pyannote.audio, ReportLab, pytest
- **Frontend:** React 18 + TypeScript, Vite, Tailwind CSS, axios
- **No paid APIs required.** Translation is a small local phrasebook;
  everything else runs offline.

## Setup & run commands

### Audio preprocessing / long recordings

For real consultation recordings, install FFmpeg before running the ASR pipeline:

```bash
# Windows (winget)
winget install Gyan.Dev.FFmpeg

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg
```

The backend's preprocessing step converts uploaded recordings to a mono 16 kHz WAV, normalizes loudness, and keeps the original file untouched. This is compatible with the current long-recording workflow and avoids assuming every consultation is only a few seconds long.

### Speaker diarization model access

Speaker diarization uses the open-source `pyannote/speaker-diarization-community-1` model. Hugging Face access is gated: create an account, accept the model's conditions, create a read token, then set `HF_TOKEN` in the backend environment. The first diarization run downloads model weights and requires internet; later runs use the local Hugging Face cache. Keep the token private and do not commit it. FFmpeg is required by pyannote's audio decoding stack.

On Windows PowerShell, set the token for the current session before starting the backend:

```powershell
$env:HF_TOKEN = "hf_your_read_token"
```

For Docker Compose, provide `HF_TOKEN` in the environment used to run `docker compose`. Set `DIARIZATION_ENABLED=false` to turn the optional feature off. If model access is not configured or inference fails, the app retains and displays the complete Whisper transcript without assigning fabricated speaker labels.

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp ../.env.example .env   # then edit values if needed
uvicorn app.main:app --reload --port 8000
```

- Health check: `GET http://localhost:8000/health`
- Interactive API docs: `http://localhost:8000/docs`
- Tests: `cd backend && pytest -q` (includes offline diarization/role tests; real model inference needs HF access)

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000/api
npm run dev             # dev server, http://localhost:5173
npm run build            # production build -> frontend/dist
```

### Docker (optional)

```bash
docker compose up --build
```

## Datasets / licenses

See [`data/README.md`](data/README.md) for full details. In short:

- `data/medicines.json` is a small, hand-compiled prototype terminology
  table (generic names, aliases, strengths, forms, indications) — **not a
  clinical authority**.
- `data/demo/*.json` are entirely **synthetic** consultations
  (English/Hindi/Marathi/code-mixed), clearly labelled
  `SYNTHETIC DEMONSTRATION DATA — NOT REAL PATIENT DATA`.
- No large datasets (e.g. AI4Bharat IndicVoices, n2c2) are downloaded
  automatically; the data README documents how you could add them later
  through their official, access-controlled channels.

## Demo workflow

1. `POST /api/patients` → create a patient.
2. `POST /api/consultations` → create a consultation for that patient.
3. `POST /api/consultations/{id}/audio` → upload a WAV/MP3/M4A file (any
   audio works in `ASR_MODE=demo`; a labelled demo transcript is returned).
4. `POST /api/consultations/{id}/process` → runs ASR → speaker diarization →
   clinical relevance detection → clinical condensation → clinical extraction
   → recommendation generation in one call. The source transcript/audio is
   retained unchanged.
5. `GET /api/consultations/{id}/transcript`, `/clinical-summary`, `/clinical-data` and
   `/recommendations` → inspect the pipeline output.
    Older consultations without a stored summary can use
    `POST /api/consultations/{id}/clinical-summary/generate` after transcription.
6. `PUT /api/consultations/{id}/recommendations` → doctor edits the
   candidate list (or skip straight to step 7 to approve as-is).
7. `POST /api/consultations/{id}/approve` (`approved: true`) → generates the
   prescription record.
8. `GET /api/consultations/{id}/prescription/pdf` → downloads the signed-off
   PDF.

The same flow is available end-to-end from the React UI (`New Consultation`
→ upload/record audio → review → approve → download PDF).

## APIs

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/patients` | Create patient |
| GET | `/api/patients/{id}` | Get patient |
| POST | `/api/consultations` | Create consultation |
| GET | `/api/consultations/{id}` | Get consultation (+ status) |
| POST | `/api/consultations/{id}/audio` | Upload audio |
| POST | `/api/consultations/{id}/process` | Run ASR + clinical extraction + recommendations |
| GET | `/api/consultations/{id}/transcript` | Get transcript |
| GET | `/api/consultations/{id}/clinical-summary` | Get condensed clinical content and scored source segments |
| POST | `/api/consultations/{id}/clinical-summary/generate` | Generate or refresh summary from an existing transcript |
| PUT | `/api/consultations/{id}/speaker-roles` | Correct speaker roles without reprocessing audio |
| GET | `/api/consultations/{id}/clinical-data` | Get extracted entities |
| GET / POST / PUT | `/api/consultations/{id}/recommendations` | List / regenerate / doctor-edit candidates |
| POST | `/api/consultations/{id}/approve` | Approve or reject → prescription |
| GET | `/api/consultations/{id}/prescription` | Get prescription JSON |
| GET | `/api/consultations/{id}/prescription/pdf` | Download prescription PDF (APPROVED only) |

## State machine

```
CREATED → AUDIO_UPLOADED → PROCESSING → TRANSCRIBED → CLINICAL_EXTRACTED
  → RECOMMENDATIONS_GENERATED → DOCTOR_REVIEW → APPROVED/REJECTED
  → PRESCRIPTION_GENERATED   (FAILED on unrecoverable errors)
```

Recommendation-level states: `DRAFT → AI_SUGGESTED → DOCTOR_EDITED →
APPROVED/REJECTED`.

## Limitations (read before demoing)

- **ASR**: this sandbox/CI environment cannot download Whisper model
  weights (no Hugging Face network access), so `ASR_MODE=auto` reports a
  clear error instead of returning synthetic clinical content. Set
  `ASR_MODE=demo` only for offline synthetic tests. On a machine with
  normal internet access, `faster-whisper` will download and use a real
  `small` (or configured) model automatically — no code changes needed.
- **Speaker diarization**: requires `pyannote.audio==4.0.7`, FFmpeg,
  internet on first use, an HF read token, and acceptance of the
  `community-1` model conditions. Speaker boundaries are estimates, and role
  inference uses transcript wording; ambiguous speakers remain
  `Other/Unknown`. Roles can be corrected without changing speaker IDs or
  rerunning transcription. A real multi-speaker validation requires an
  authorized token and audio containing at least two audible speakers.
- **Long-form audio**: the ASR service accepts multi-minute files but still
  depends on the available machine resources and the model size. For 15–30
  minute recordings, expect slower processing and rely on the explicit status
  transitions in the consultation workflow rather than a fake instant result.
- **Clinical NLP** is rule/dictionary-based (regex + a 21-medicine KB), not
  a trained medical NER model. It works well on the demo transcripts and
  similarly-phrased input but will miss unfamiliar phrasing.
- **Clinical relevance and condensation** use explainable keyword/category
  rules and select source excerpts by clinical-category priority, duplicate
  removal, and a roughly three-minute source-speech budget. The output quotes
  selected transcript segments with their timestamps; it does not generate
  new clinical facts. `ClinicalSummary` stores this derived content, selected
  segments, source references, method/version, and generation time separately
  from the original `Transcript`. SQLite creates the additive table on startup.
  This implementation is an academic, explainable prototype—not a validated
  clinical summarization model. It can miss relevant phrasing or classify
  segments incorrectly, and every AI-generated summary requires doctor
  verification. If generation fails, the full transcript is preserved and
  processing continues using that transcript for entity extraction.


- **Translation** is a small fixed phrasebook for UI/PDF labels, not
  general-purpose machine translation of free text.
- **Recommendation scoring** is a transparent indication-overlap heuristic
  ("Recommendation Relevance Score"), not a trained or validated clinical
  model, and is explicitly not represented as one.
- No authentication/authorization layer (out of scope for this MVP).
- `feedback_learning/feedback_updater.py` is a stub for future adaptive
  learning from approved cases; not wired into the pipeline yet.

## Future work

- Real-time/streaming ASR (architecture already separates ASR as its own
  service, so this is additive).
- Replace the rule-based NLP with a fine-tuned clinical NER model.
- Authentication (doctor login) and multi-doctor/multi-clinic support.
- Expand the medicine KB and validate it against a maintained formulary.
- Wire up `feedback_learning` to actually improve recommendation ranking
  over time from doctor edits/approvals.
