"""Catalog of UniFace model weights used by FaceAccess.

Only weights whose upstream licence permits commercial use are selected by
default (see docs: https://yakhyo.github.io/uniface/license-attribution/):

* RetinaFace MobileNetV2 (detection + 5 landmarks)  — MIT
* AdaFace IR-18 (512-D embeddings)                   — MIT
* MiniFASNet V2 (passive anti-spoofing / liveness)   — Apache-2.0
* eDifFIQA-T (face image quality assessment)         — MIT

InsightFace ArcFace / SCRFD are deliberately NOT used (non-commercial weights).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from uniface.constants import (
    MODEL_REGISTRY,
    AdaFaceWeights,
    EDifFIQAWeights,
    MiniFASNetWeights,
    RetinaFaceWeights,
)
from uniface.model_store import get_cache_dir


@dataclass(frozen=True)
class ModelSpec:
    role: str
    weight: Enum
    license: str


DETECTOR = ModelSpec("detector", RetinaFaceWeights.MNET_V2, "MIT")
RECOGNIZER = ModelSpec("recognizer", AdaFaceWeights.IR_18, "MIT")
LIVENESS = ModelSpec("liveness", MiniFASNetWeights.V2, "Apache-2.0")
QUALITY = ModelSpec("quality", EDifFIQAWeights.T, "MIT")

REQUIRED_MODELS: tuple[ModelSpec, ...] = (DETECTOR, RECOGNIZER, LIVENESS, QUALITY)


def model_file_path(weight: Enum) -> str:
    """Mirror of uniface.model_store.verify_model_weights path resolution."""
    info = MODEL_REGISTRY[weight]
    ext = os.path.splitext(info.url)[1]
    return os.path.normpath(os.path.join(get_cache_dir(), f"{weight.value}{ext}"))


def missing_models() -> list[str]:
    return [m.weight.value for m in REQUIRED_MODELS if not os.path.exists(model_file_path(m.weight))]


def model_sha256(weight: Enum) -> str:
    return MODEL_REGISTRY[weight].sha256
