"""Production Biometric Engine using UniFace official models and ONNX Runtime.

Models employed:
- Detector: RetinaFace MobileNetV2 (MIT)
- Recognizer: AdaFace IR-18 (MIT)
- Anti-Spoofing: MiniFASNet V2 (Apache-2.0)
- Quality Assessment: eDifFIQA-T (MIT) + OpenCV photometric checks
"""
from __future__ import annotations

import logging
import threading
from typing import Any

import cv2
import numpy as np
from uniface import AdaFace, EDifFIQA, MiniFASNet, RetinaFace, compute_similarity
from uniface.constants import (
    AdaFaceWeights,
    EDifFIQAWeights,
    MiniFASNetWeights,
    RetinaFaceWeights,
)

from app.biometrics.base import (
    BiometricEngine,
    FaceFeature,
    LivenessAssessment,
    QualityAssessment,
)
from app.core.config import get_settings
from app.core.errors import ServiceUnavailable
from app.biometrics.model_catalog import REQUIRED_MODELS, model_file_path, model_sha256
from uniface.model_store import verify_file_hash
import os

log = logging.getLogger("faceaccess.biometrics")


class UniFaceEngine(BiometricEngine):
    def __init__(self):
        s = get_settings()
        self._providers = s.biometric_providers
        self._lock = threading.Lock()

        # Installation prepares models. Never download weights inside a user's capture.
        for spec in REQUIRED_MODELS:
            path = model_file_path(spec.weight)
            if not os.path.isfile(path) or not verify_file_hash(path, model_sha256(spec.weight)):
                raise ServiceUnavailable(
                    "Os modelos de reconhecimento facial precisam ser preparados no servidor. "
                    "Execute scripts/download_models.py antes de iniciar o cadastro."
                )

        log.info("Initializing UniFaceEngine with providers=%s", self._providers)
        self.detector = RetinaFace(
            model_name=RetinaFaceWeights.MNET_V2,
            confidence_threshold=0.6,
            providers=self._providers,
        )
        self.recognizer = AdaFace(
            model_name=AdaFaceWeights.IR_18,
            providers=self._providers,
        )
        self.anti_spoof = MiniFASNet(
            model_name=MiniFASNetWeights.V2,
            providers=self._providers,
        )
        self.quality_model = EDifFIQA(
            model_name=EDifFIQAWeights.T,
            providers=self._providers,
        )

    @property
    def name(self) -> str:
        return "uniface"

    @property
    def version(self) -> str:
        return (
            "uniface:4.3.0/retinaface_mnet_v2+adaface_ir18+minifasnet_v2+ediffiqa_t"
        )

    def assess_frame(self, image_bgr: np.ndarray) -> tuple[float, float]:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return brightness, sharpness

    def process_face(
        self,
        image_bgr: np.ndarray,
        *,
        check_liveness: bool = True,
        include_embedding: bool = True,
    ) -> FaceFeature | None:
        s = get_settings()
        h, w = image_bgr.shape[:2]
        brightness, sharpness = self.assess_frame(image_bgr)

        with self._lock:
            # 1. Detection
            faces = self.detector.detect(image_bgr, max_num=2)
            if not faces:
                return None

            # Enforce single-face check
            if len(faces) > 1:
                log.warning("Multiple faces detected in capture frame (%d faces)", len(faces))
                # Still select the primary dominant one, but mark potential quality failure
            dominant = faces[0]

            # 2. Geometry & Framing check
            bbox = dominant.bbox.astype(int).tolist()
            x1, y1, x2, y2 = bbox
            face_w = x2 - x1
            face_h = y2 - y1
            face_ratio = (face_w * face_h) / (w * h)

            quality_errors = []
            if len(faces) > 1:
                quality_errors.append("Apenas uma pessoa deve aparecer na câmera")
            if brightness < s.min_brightness:
                quality_errors.append(f"Iluminação muito baixa ({brightness:.1f})")
            elif brightness > s.max_brightness:
                quality_errors.append(f"Iluminação excessiva ({brightness:.1f})")

            if sharpness < s.min_sharpness:
                quality_errors.append(f"Imagem desfocada ({sharpness:.1f})")

            if face_ratio < s.min_face_size_ratio:
                quality_errors.append(f"Aproxime-se mais da câmera (rosto pequeno)")

            # Check centering
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            if abs(cx - w / 2.0) > (w * 0.25) or abs(cy - h / 2.0) > (h * 0.25):
                quality_errors.append("Centralize seu rosto no enquadramento")

            # 3. Model-based Quality Assessment
            q_res = self.quality_model.predict(image_bgr, dominant.landmarks)
            quality_score = float(q_res.score)
            if quality_score < s.quality_min_score:
                quality_errors.append(f"Qualidade da captura insuficiente ({quality_score:.2f})")

            quality = QualityAssessment(
                passed=len(quality_errors) == 0,
                score=quality_score,
                brightness=brightness,
                sharpness=sharpness,
                face_ratio=face_ratio,
                errors=quality_errors,
            )

            # 4. Anti-spoofing / Liveness
            liveness: LivenessAssessment | None = None
            if check_liveness and s.liveness_enabled:
                sp_res = self.anti_spoof.predict(image_bgr, dominant.bbox)
                liveness = LivenessAssessment(
                    is_real=bool(sp_res.is_real and sp_res.confidence >= s.liveness_threshold),
                    confidence=float(sp_res.confidence),
                    method="minifasnet_v2",
                )

            # 5. Feature extraction
            embedding = (
                self.recognizer.get_normalized_embedding(image_bgr, dominant.landmarks)
                if include_embedding and quality.passed and (not check_liveness or (liveness and liveness.is_real))
                else np.empty(0, dtype=np.float32)
            )

            return FaceFeature(
                bbox=bbox,
                confidence=float(dominant.confidence),
                landmarks=dominant.landmarks,
                embedding=embedding,
                quality=quality,
                liveness=liveness,
            )

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        return float(compute_similarity(embedding1, embedding2, normalized=True))


class FakeBiometricEngine(BiometricEngine):
    """Engine mock for synthetic isolated unit tests without ONNX models."""

    @property
    def name(self) -> str:
        return "fake"

    @property
    def version(self) -> str:
        return "fake:1.0.0"

    def assess_frame(self, image_bgr: np.ndarray) -> tuple[float, float]:
        return 120.0, 100.0

    def process_face(
        self,
        image_bgr: np.ndarray,
        *,
        check_liveness: bool = True,
        include_embedding: bool = True,
    ) -> FaceFeature | None:
        # Deterministic synthetic embedding for consistent unit test matching
        emb = np.ones(512, dtype=np.float32)
        emb /= np.linalg.norm(emb)
        return FaceFeature(
            bbox=[100, 100, 300, 300],
            confidence=0.99,
            landmarks=np.zeros((5, 2), dtype=np.float32),
            embedding=emb,
            quality=QualityAssessment(True, 0.85, 120.0, 100.0, 0.25, []),
            liveness=LivenessAssessment(True, 0.98, "fake") if check_liveness else None,
        )

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        return float(np.dot(embedding1.ravel(), embedding2.ravel()))


_engine_instance: BiometricEngine | None = None
_engine_init_lock = threading.Lock()


def get_biometric_engine() -> BiometricEngine:
    global _engine_instance
    if _engine_instance is None:
        if not _engine_init_lock.acquire(timeout=2):
            raise ServiceUnavailable("O motor facial está inicializando. Aguarde alguns segundos e tente novamente.")
        try:
            if _engine_instance is None:
                s = get_settings()
                _engine_instance = FakeBiometricEngine() if s.biometric_engine == "fake" else UniFaceEngine()
        finally:
            _engine_init_lock.release()
    return _engine_instance
