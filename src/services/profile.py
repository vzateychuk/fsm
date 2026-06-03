"""ProfileService — read-only patient profile from configuration."""
from __future__ import annotations

from src.common.patient import PatientInfo


class ProfileService:
    """Application service for read-only patient profile access."""

    def __init__(self, patient: PatientInfo) -> None:
        self._patient = patient

    def get_profile(self) -> PatientInfo:
        """Return the patient profile loaded from configuration.

        Returns:
            PatientInfo instance.
        """
        return self._patient
