"""Patient profile endpoint (read-only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_profile_service
from src.api.schemas import ProfileDTO
from src.services.profile import ProfileService

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("", response_model=ProfileDTO)
async def get_profile(
    service: ProfileService = Depends(get_profile_service),
) -> ProfileDTO:
    patient = service.get_profile()
    return ProfileDTO(
        name=patient.name,
        age=patient.age,
        sex=patient.sex,
        date_of_birth=str(patient.date_of_birth),
        chronic_conditions=patient.chronic_conditions,
        current_medications=patient.current_medications,
        allergies=patient.allergies,
    )
