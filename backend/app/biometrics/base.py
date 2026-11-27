"""Biometric engine abstraction interface.

Allows decoupling business logic from UniFace or replacing the biometric
pipeline seamlessly in the future.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class QualityAssessment:
    passed: bool
    score: float
    brightness: float
    sharpness: float
    face_ratio: float
    errors: list[str]


@dataclass(frozen=True)
class LivenessAssessment:
    is_real: bool
    confidence: float
    method: str


@dataclass(frozen=True)
class FaceFeature:
    bbox: list[int]  # [x1, y1, x2, y2]
    confidence: float
    landmarks: np.ndarray  # (5, 2)
    embedding: np.ndarray  # (512,)
    quality: QualityAssessment
    liveness: LivenessAssessment | None


class BiometricEngine(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the engine (e.g. uniface)."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Version string including model details."""
        pass

    @abstractmethod
    def assess_frame(self, image_bgr: np.ndarray) -> tuple[float, float]:
        """Assess overall frame brightness and sharpness (Laplacian variance)."""
        pass

    @abstractmethod
    def process_face(
        self,
        image_bgr: np.ndarray,
        *,
        check_liveness: bool = True,
        include_embedding: bool = True,
    ) -> FaceFeature | None:
        """Detect dominant face, check framing, quality, anti-spoofing and extract embedding."""
        pass

    @abstractmethod
    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        """Compute cosine similarity score between two normalized embeddings."""
        pass
