"""Builds the structured prescription payload from doctor-approved
recommendations. Pure data shaping — no persistence here (that's the
repository layer) and no PDF rendering here (see services/pdf_generator).
"""
from typing import List, Dict

DISCLAIMER = (
    "ClinOps-AI is an academic prototype and clinical decision-support "
    "demonstration. AI-generated recommendations are not medical advice and "
    "must be independently reviewed and approved by a qualified doctor "
    "before use."
)


def build_prescription_items(recommendations: List[dict]) -> List[Dict]:
    """recommendations: Recommendation rows (as dicts) that the doctor has
    approved. Converts them into PrescriptionItem-shaped dicts.
    """
    items = []
    for rec in recommendations:
        items.append({
            "medicine": rec["medicine"],
            "dosage": rec.get("dosage"),
            "frequency": rec.get("frequency"),
            "duration": rec.get("duration"),
            "route": rec.get("route"),
            "instructions": rec.get("reason"),
        })
    return items


def summarize_diagnosis(clinical_entities: List[dict]) -> str:
    diagnoses = [e["normalized"] for e in clinical_entities if e.get("entity_type") == "diagnosis"]
    symptoms = [e["normalized"] for e in clinical_entities if e.get("entity_type") == "symptom"]
    if diagnoses:
        summary = ", ".join(sorted(set(diagnoses))).title()
    elif symptoms:
        summary = "Symptomatic treatment for: " + ", ".join(sorted(set(symptoms)))
    else:
        summary = "General consultation (no structured diagnosis extracted)"
    return summary


def default_precautions(clinical_entities: List[dict]) -> List[str]:
    return [e["normalized"] for e in clinical_entities if e.get("entity_type") == "precaution"]
