
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.db.database import get_db
from app.models.domain import Consultation, Doctor, Patient, User
from app.repositories import repository as repo
from app.schemas.api_models import PatientCreate, PatientOut

router = APIRouter()


@router.post(
    "/patients",
    response_model=PatientOut,
    status_code=status.HTTP_201_CREATED,
)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor")),
):
    # A doctor must have a valid, linked clinical record.
    if not current_user.doctor_id or not db.query(Doctor).filter(
        Doctor.id == current_user.doctor_id
    ).first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor account is not linked to a valid doctor record.",
        )

    return repo.create_patient(
        db,
        name=payload.name,
        age=payload.age,
        gender=payload.gender,
        language=payload.language,
        contact=payload.contact,
    )


@router.get("/patients/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = repo.get_patient(db, patient_id)

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if current_user.role == "patient":
        # Patients can only retrieve the clinical record linked to their account.
        if not current_user.patient_id or current_user.patient_id != patient.id:
            raise HTTPException(status_code=403, detail="Access denied.")

    elif current_user.role == "doctor":
        # Doctors can retrieve only patients with whom they have a consultation.
        if not current_user.doctor_id:
            raise HTTPException(status_code=403, detail="Doctor account is not linked.")

        has_access = (
            db.query(Consultation.id)
            .filter(
                Consultation.patient_id == patient.id,
                Consultation.doctor_id == current_user.doctor_id,
            )
            .first()
        )

        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied.")

    else:
        raise HTTPException(status_code=403, detail="Access denied.")

    return patient


@router.get("/patients", response_model=list[PatientOut])
def list_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "patient":
        if not current_user.patient_id:
            raise HTTPException(
                status_code=403,
                detail="Patient account is not linked to a patient record.",
            )

        patient = repo.get_patient(db, current_user.patient_id)
        return [patient] if patient else []

    if current_user.role == "doctor":
        if not current_user.doctor_id:
            raise HTTPException(status_code=403, detail="Doctor account is not linked.")

        return (
            db.query(Patient)
            .join(Consultation, Consultation.patient_id == Patient.id)
            .filter(Consultation.doctor_id == current_user.doctor_id)
            .distinct()
            .order_by(Patient.created_at.desc())
            .all()
        )

    raise HTTPException(status_code=403, detail="Access denied.")