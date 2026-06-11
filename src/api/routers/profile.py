"""Patient profile endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_profile_service
from src.api.schemas import PatchProfileRequest, ProfileDTO
from src.common.patient import PatientInfo
from src.services.profile import ProfileService

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def _to_dto(patient: PatientInfo) -> ProfileDTO:
    return ProfileDTO(
        name=patient.name,
        age=patient.age,
        sex=patient.sex,
        date_of_birth=str(patient.date_of_birth),
        chronic_conditions=patient.chronic_conditions,
        current_medications=patient.current_medications,
        allergies=patient.allergies,
        is_complete=ProfileService.is_complete(patient),
    )


@router.get("", response_model=ProfileDTO)
async def get_profile(
    service: ProfileService = Depends(get_profile_service),
) -> ProfileDTO:
    patient = await service.get_profile()
    return _to_dto(patient)


@router.patch("", response_model=ProfileDTO)
async def patch_profile(
    body: PatchProfileRequest,
    service: ProfileService = Depends(get_profile_service),
) -> ProfileDTO:
    patient = PatientInfo(
        name=body.name,
        age=body.age,
        sex=body.sex,
        date_of_birth=body.date_of_birth,
        chronic_conditions=body.chronic_conditions,
        current_medications=body.current_medications,
        allergies=body.allergies,
    )
    updated = await service.update_profile(patient)
    return _to_dto(updated)
