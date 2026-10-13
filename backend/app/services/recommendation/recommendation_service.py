"""Candidate medicine recommendation engine.

Transparent MVP method (no black-box ML): for each diagnosed condition /
symptom set extracted from the transcript, we score every medicine in the
knowledge base (data/medicines.json) by:

  1. Indication overlap  — does the medicine's `indications` list contain a
     matched symptom/diagnosis term (exact + simple substring match)?
  2. Direct-mention bonus — if the doctor already named this medicine in the
     transcript (i.e. it's already a ClinicalEntity of type "medication"),
     boost its score and reuse the dosage/frequency/duration that was
     actually extracted from what the doctor said.
  3. Rule filtering — obviously irrelevant medicines (zero overlap) are
     dropped rather than padded in with a fake score.

The output "score" is explicitly a *Recommendation Relevance Score*
(0.0-1.0), never described as a diagnostic probability. Doctor review is
always required before anything is used.
"""
import json
from pathlib import Path
from typing import List, Dict

from app.config.settings import settings

DATA_DIR = Path(settings.data_dir)
MEDICINES_PATH = DATA_DIR / "medicines.json"


def _load_medicines() -> List[dict]:
    if not MEDICINES_PATH.exists():
        return []
    with open(MEDICINES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


MEDICINES = _load_medicines()

DEFAULT_FREQUENCY_BY_FORM = {
    "tablet": "twice daily", "capsule": "twice daily", "syrup": "twice daily",
    "sachet": "once daily", "inhaler": "as needed", "gel": "twice daily", "powder": "once daily",
}
DEFAULT_DURATION = "3-5 days (doctor to confirm)"


def _term_overlap_score(condition_terms: List[str], indications: List[str]) -> float:
    if not condition_terms or not indications:
        return 0.0
    hits = 0
    for term in condition_terms:
        for ind in indications:
            if term == ind or term in ind or ind in term:
                hits += 1
                break
    return hits / max(len(condition_terms), 1)


def _recommender_safe_status(entity: dict) -> bool:
    status = str(entity.get("status") or "positive").lower()
    if status in {"negated", "historical", "family_history", "uncertain", "unknown", "patient_reported", "hypothetical", "ambiguous"}:
        return False
    text = (entity.get("text") or "").lower()
    if any(marker in text for marker in ("i take", "currently taking", "used to take", "stopped taking", "patient says")):
        return False
    return True


def generate_recommendations(clinical_entities: List[dict]) -> List[dict]:
    """Generate medication recommendations only from explicit clinician-matched
    medication records in the transcript. Never invent missing dosage, frequency,
    or duration, and never infer a prescription from symptoms alone.
    """
    explicit_meds = [
        e for e in clinical_entities
        if e.get("entity_type") == "medication" and _recommender_safe_status(e)
    ]
    if not explicit_meds:
        return []

    scored: List[dict] = []
    for entity in explicit_meds:
        name = entity.get("normalized") or entity.get("text")
        if not name:
            continue
        status = str(entity.get("status") or "positive").lower()
        dosage = entity.get("dosage")
        frequency = entity.get("frequency")
        duration = entity.get("duration")
        route = entity.get("route")
        reason = "Explicit medication details recorded in the consultation; clinician review required before prescription."
        if status == "doctor_ordered":
            reason = "Medication appears to be explicitly ordered or prescribed during the consultation."
        elif status == "patient_reported":
            continue
        if not dosage and not frequency and not duration:
            reason = "Medication name is present but dose/frequency/duration are not explicit; clinician review required."

        score = 0.85 if dosage and frequency and duration else 0.65
        candidate = {
            "medicine": name,
            "dosage": dosage,
            "frequency": frequency,
            "duration": duration,
            "route": route,
            "score": round(score, 2),
            "reason": reason,
        }
        if any(value is None for value in (dosage, frequency, duration)):
            candidate["reason"] = "Medication details are incomplete; do not fabricate a prescription-ready dose/frequency/duration."
        scored.append(candidate)

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:8]
