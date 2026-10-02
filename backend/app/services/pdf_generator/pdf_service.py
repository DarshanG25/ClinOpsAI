"""Prescription PDF rendering (ReportLab), with a Unicode/Devanagari-capable
font bundled under app/assets/fonts so Hindi/Marathi text renders correctly.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.config.settings import settings

ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"
FONT_REGULAR = ASSETS_DIR / "NotoSansDevanagari-Regular.ttf"
FONT_BOLD = ASSETS_DIR / "NotoSansDevanagari-Bold.ttf"

DISCLAIMER = (
    "ClinOps-AI is an academic prototype and clinical decision-support demonstration. "
    "AI-generated recommendations are not medical advice and must be independently "
    "reviewed and approved by a qualified doctor before use."
)

_FONTS_REGISTERED = False


def _register_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    try:
        if FONT_REGULAR.exists():
            pdfmetrics.registerFont(TTFont("Noto", str(FONT_REGULAR)))
        if FONT_BOLD.exists():
            pdfmetrics.registerFont(TTFont("Noto-Bold", str(FONT_BOLD)))
    except Exception:
        pass  # fall back to core Helvetica fonts below if registration fails
    _FONTS_REGISTERED = True


def _font(bold: bool = False) -> str:
    _register_fonts()
    name = "Noto-Bold" if bold else "Noto"
    return name if name in pdfmetrics.getRegisteredFontNames() else ("Helvetica-Bold" if bold else "Helvetica")


def generate_prescription_pdf(
    *,
    output_path: str,
    doctor_name: str,
    doctor_reg_no: str,
    patient_name: str,
    patient_age: Optional[int],
    patient_gender: Optional[str],
    consultation_id: str,
    diagnosis_summary: str,
    items: List[dict],
    precautions: List[str],
    approval_status: str,
) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    margin = 18 * mm
    y = height - margin

    def line(text, size=10, bold=False, color=colors.black, dy=6 * mm):
        nonlocal y
        c.setFont(_font(bold), size)
        c.setFillColor(color)
        c.drawString(margin, y, text)
        y -= dy

    # Header
    line("ClinOps-AI — Prescription", size=16, bold=True, dy=8 * mm)
    c.setStrokeColor(colors.HexColor("#334155"))
    c.line(margin, y, width - margin, y)
    y -= 6 * mm

    line(f"Doctor: {doctor_name}  (Reg. No: {doctor_reg_no})", size=10, bold=True)
    line(f"Patient: {patient_name}" + (f", {patient_age} yrs" if patient_age else "") + (f", {patient_gender}" if patient_gender else ""))
    line(f"Consultation ID: {consultation_id}")
    line(f"Date: {datetime.now().strftime('%d-%b-%Y %H:%M')}")
    line(f"Approval status: {approval_status}", bold=True,
         color=colors.HexColor("#15803d") if approval_status == "APPROVED" else colors.HexColor("#b91c1c"))
    y -= 2 * mm

    line("Diagnosis / Summary:", bold=True)
    line(diagnosis_summary or "-", dy=8 * mm)

    line("Medicines:", bold=True, dy=7 * mm)
    c.setFont(_font(True), 9)
    headers = ["Medicine", "Dosage", "Frequency", "Duration", "Route"]
    col_x = [margin, margin + 55 * mm, margin + 90 * mm, margin + 130 * mm, margin + 160 * mm]
    for h, x in zip(headers, col_x):
        c.drawString(x, y, h)
    y -= 5 * mm
    c.setFont(_font(False), 9)
    if not items:
        line("(No approved medicines)", dy=5 * mm)
    for it in items:
        if y < 40 * mm:
            c.showPage()
            y = height - margin
        row = [it.get("medicine", "-"), it.get("dosage") or "-", it.get("frequency") or "-",
               it.get("duration") or "-", it.get("route") or "-"]
        for val, x in zip(row, col_x):
            c.drawString(x, y, str(val)[:28])
        y -= 6 * mm

    y -= 3 * mm
    line("Precautions:", bold=True)
    if precautions:
        for p in precautions:
            line(f"- {p}", dy=5 * mm)
    else:
        line("- None specified", dy=5 * mm)

    y -= 4 * mm
    c.setFont(_font(False), 8)
    c.setFillColor(colors.HexColor("#64748b"))
    text_obj = c.beginText(margin, y)
    text_obj.setLeading(4 * mm)
    import textwrap
    for wline in textwrap.wrap(DISCLAIMER, 100):
        text_obj.textLine(wline)
    c.drawText(text_obj)

    c.showPage()
    c.save()
    return output_path
