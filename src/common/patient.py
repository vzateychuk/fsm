"""Shared patient domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class PatientInfo:
    """Patient demographic and clinical information.
    Loaded from config/patient.yaml.
    Used to populate Patient Info section in consultation prompts.
    """

    name: str
    """Full patient name."""
    age: int
    """Patient age in years."""
    sex: str
    """Patient sex/gender."""
    date_of_birth: str
    """Patient date of birth (ISO format YYYY-MM-DD)."""
    chronic_conditions: list[str] = field(default_factory=list)
    """Known chronic conditions or diagnoses."""
    current_medications: list[str] = field(default_factory=list)
    """Current medications and dosages."""
    allergies: list[str] = field(default_factory=list)
    """Known allergies and adverse reactions."""

    @classmethod
    def load(cls, config_path: Path) -> "PatientInfo":
        """Load patient information from YAML file.

        Args:
            config_path: Path to config/patient.yaml

        Returns:
            PatientInfo instance with patient demographic and clinical data.
        """
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        patient_data = data.get("patient", {})
        return cls(**patient_data)
