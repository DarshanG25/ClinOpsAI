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


def generate_recommendations(clinical_entities: List[dict]) -> List[dict]:
    """clinical_entities: list of dicts with keys entity_type/text/normalized/
    dosage/frequency/duration/route (as produced by the NLP extractor /
    ClinicalEntity rows). Returns a list of recommendation dicts ready for
    the Recommendation repository.
    """
    symptoms = [e["normalized"].lower() for e in clinical_entities if e.get("entity_type") == "symptom"]
    diagnoses = [e["normalized"].lower() for e in clinical_entities if e.get("entity_type") == "diagnosis"]
    condition_terms = list({*symptoms, *diagnoses})

    mentioned_meds = {
        e["normalized"]: e for e in clinical_entities if e.get("entity_type") == "medication"
    }

    scored: List[dict] = []

    # 1. Medicines already mentioned by the doctor -> highest-confidence candidates
    for name, entity in mentioned_meds.items():
        med_kb = next((m for m in MEDICINES if m["generic_name"].lower() == name.lower()), None)
        overlap = _term_overlap_score(condition_terms, [i.lower() for i in med_kb["indications"]]) if med_kb else 0.0
        score = round(min(1.0, 0.75 + 0.25 * overlap), 2)
        reasons = ["Explicitly mentioned in the doctor-patient transcript"]
        if overlap > 0:
            reasons.append("Indication matches extracted symptoms/diagnosis")
        scored.append({
            "medicine": name,
            "dosage": entity.get("dosage") or (med_kb["common_strengths"][0] if med_kb else None),
            "frequency": entity.get("frequency") or DEFAULT_FREQUENCY_BY_FORM.get(
                (med_kb["forms"][0] if med_kb else "tablet"), "twice daily"),
            "duration": entity.get("duration") or DEFAULT_DURATION,
            "route": entity.get("route") or (med_kb["default_route"] if med_kb else "oral"),
            "score": score,
            "reason": "; ".join(reasons),
        })

    # 2. Indication-matched candidates from the KB that weren't already mentioned
    if condition_terms:
        for med in MEDICINES:
            if med["generic_name"] in mentioned_meds:
                continue
            overlap = _term_overlap_score(condition_terms, [i.lower() for i in med["indications"]])
            if overlap <= 0:
                continue
            score = round(0.35 + 0.55 * overlap, 2)
            matched = [t for t in condition_terms if any(t in i.lower() or i.lower() in t for i in med["indications"])]
            scored.append({
                "medicine": med["generic_name"],
                "dosage": med["common_strengths"][0] if med["common_strengths"] else None,
                "frequency": DEFAULT_FREQUENCY_BY_FORM.get(med["forms"][0] if med["forms"] else "tablet", "twice daily"),
                "duration": DEFAULT_DURATION,
                "route": med.get("default_route", "oral"),
                "score": score,
                "reason": f"Indication match for: {', '.join(matched)}",
            })

    scored.sort(key=lambda r: r["score"], reverse=True)

    # Cap to a manageable candidate list for doctor review (top 8)
    return scored[:8]
