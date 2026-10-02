# Implementation Status

This documents what actually works, verified by running the app, not just
what files exist. Last verified: full pytest suite (18/18) + fresh
`npm install && npm run build` both green.

## ✅ Completed (verified working end-to-end)

| Area | Status |
|---|---|
| Backend boots (`uvicorn app.main:app`) | ✅ verified with a real running server + curl |
| `/health` | ✅ |
| Patient creation | ✅ |
| Consultation creation | ✅ |
| Audio upload (WAV/MP3/M4A, size/format validation) | ✅ |
| ASR (`/process`) | ✅ with explicit DEMO mode; real-ASR failures are reported |
| Transcript retrieval | ✅ |
| Clinical entity extraction (symptoms/diagnoses/medications/precautions) | ✅ |
| Dosage/frequency/duration parsing (EN + transliterated HI/MR) | ✅ (regression-tested) |
| Recommendation generation (indication-matching, transparent scoring) | ✅ |
| Doctor review/edit (`PUT recommendations`) | ✅ |
| Approval → prescription generation | ✅ |
| Rejection flow | ✅ |
| Prescription PDF (Unicode/Devanagari font) | ✅ |
| Database persistence (SQLite via SQLAlchemy) | ✅ |
| Full consultation state machine | ✅ |
| pytest suite (18 tests incl. one full end-to-end run) | ✅ all passing |
| Frontend: patient/consultation creation, audio upload/record,
  processing status, transcript view, clinical-data + recommendation
  display, doctor edit UI, approve/reject, prescription preview, PDF
  download | ✅ implemented and TypeScript build passes |
| Frontend production build (`npm run build`) | ✅ verified clean |
| Medicine knowledge base (`data/medicines.json`, 21 entries) | ✅ |
| Synthetic demo consultations (EN/HI/MR/code-mixed, labelled) | ✅ |
| Docker Compose (SQLite-based, no Mongo dependency) | ✅ config fixed, not built/run in this sandbox (no Docker daemon available here) |

## ⚠️ Partially completed / known limitations

- **Real Whisper transcription was not verifiable in this environment.**
  `faster-whisper` is wired up correctly and will download/run a real model
  on a machine with normal internet access (Hugging Face reachable). This
  sandbox's network allowlist does **not** include Hugging Face, so tests use
  explicit `ASR_MODE=demo`; real-ASR mode reports an actionable failure
  instead of returning a repeated synthetic transcript. You should
  re-verify with `ASR_MODE=whisper` and
  a real audio file once you have full internet access.
- **Clinical NLP** is a hybrid regex + 21-medicine dictionary approach, not
  a trained clinical NER model. It handles the demo transcripts and
  similar phrasing well; unusual phrasing, abbreviations, or medicines
  outside the KB will not be extracted. This is explicitly disclosed in
  the UI/README, not hidden.
- **Translation service** is a small fixed phrasebook for known UI/PDF
  strings (disclaimer, status labels), not general machine translation of
  arbitrary transcript text.
- **Recommendation scoring** is a transparent indication-overlap heuristic
  labelled "Recommendation Relevance Score" — not a trained/validated
  clinical model. This is by design per the brief.
- **`feedback_learning/feedback_updater.py`** remains a stub (as in the
  original scaffold). It is not called anywhere in the pipeline yet.

## ❌ Not implemented (explicitly out of scope for this MVP)

- Authentication / authorization (single implicit "demo doctor" is
  auto-created and used).
- Live/streaming ASR (architecture supports adding it later — ASR is
  already an isolated service).
- Automated frontend tests (manual/build verification only).
- Multi-doctor / multi-clinic workflows.

## Exact files changed

### Removed (stale/unused MongoDB-era code)
- `backend/app/db/mongodb.py`
- `backend/app/services/recommendation/similarity_engine.py`
- `backend/app/services/recommendation/confidence_scorer.py`
- `backend/app/services/recommendation/case_repository.py`
- `backend/app/services/prescription/json_formatter.py`
- `backend/app/services/pdf_generator/reportlab_pdf.py`
- `backend/app/api/routes/{recommendation,extract,prescription,transcription,feedback}.py`
  (superseded by `consultations.py`, which implements the full spec'd
  endpoint set in one cohesive module)
- `frontend/src/store/prescriptionStore.ts` (empty stub; state now lives in
  `hooks/useConversation.ts`)

### Added
- `backend/app/db/database.py` — SQLAlchemy engine/session/init_db
- `backend/app/models/domain.py` — all 8 ORM entities + state-machine enums
- `backend/app/repositories/repository.py` — data-access layer
- `backend/app/api/routes/consultations.py` — full workflow endpoints
- `backend/app/services/pdf_generator/pdf_service.py`
- `backend/app/services/prescription/prescription_service.py`
- `backend/app/assets/fonts/NotoSansDevanagari-{Regular,Bold}.ttf`
- `backend/pytest.ini`
- `data/medicines.json`, `data/README.md`, `data/demo/*.json`,
  `data/samples/sample_transcript_en.txt`
- `frontend/src/vite-env.d.ts` (missing from the original scaffold —
  `import.meta.env` did not typecheck without it)
- `IMPLEMENTATION_STATUS.md` (this file)

### Rewritten (were stubs of a few lines; now working implementations)
- `backend/requirements.txt`
- `backend/Dockerfile`, `docker-compose.yml` (Mongo → SQLite)
- `.env.example`, `frontend/.env.example`
- `backend/app/main.py`
- `backend/app/config/settings.py`
- `backend/app/schemas/api_models.py`
- `backend/app/api/routes/patients.py`
- `backend/app/services/speech/whisper_service.py`
- `backend/app/services/nlp/entity_extractor.py`
- `backend/app/services/recommendation/recommendation_service.py`
- `backend/app/services/translation/multilingual_service.py`
- `tests/backend/test_api.py`
- `frontend/src/App.tsx`
- `frontend/src/types/index.ts`
- `frontend/src/services/api.ts`
- `frontend/src/hooks/useConversation.ts`
- `frontend/src/layouts/AppLayout.tsx`
- `frontend/src/pages/HomePage.tsx`
- `frontend/src/components/{ConversationInput,TranscriptViewer,RecommendationPanel,DoctorApprovalPanel,PrescriptionPreview,PdfDownloadButton,LanguageSelector}.tsx`
- `README.md`
- `.gitignore`

## Next 5 tasks

1. Re-verify real Whisper transcription (`ASR_MODE=whisper`) on a machine
   with internet access to Hugging Face; confirm GPU/CPU auto-detection.
2. Replace the regex/dictionary clinical NLP with a fine-tuned or
   off-the-shelf clinical NER model for better recall on varied phrasing.
3. Add doctor authentication and per-doctor consultation ownership.
4. Wire `feedback_learning/feedback_updater.py` into the approval flow so
   doctor edits actually influence future recommendation ranking.
5. Add automated frontend component/integration tests (e.g. Vitest +
   Testing Library) alongside the existing backend pytest suite.
