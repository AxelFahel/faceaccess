"""Shared capture validation; subject authorization stays in domain policies."""
import base64
from dataclasses import dataclass

import cv2
import numpy as np

from app.core.errors import ValidationFailed


def decode_image(value):
    try:
        data = base64.b64decode(value.split(',', 1)[-1], validate=True)
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError()
        return image
    except Exception:
        raise ValidationFailed('Imagem inválida. Capture novamente pela câmera.')


def capture_feedback(feature, required):
    reasons = []
    if feature is None:
        reasons.append('Posicione seu rosto na marcação e olhe para a câmera.')
    else:
        if not feature.quality.passed:
            reasons.extend(feature.quality.errors or ['Ajuste o enquadramento e a iluminação.'])
        if not feature.liveness or not feature.liveness.is_real:
            reasons.append('Vivacidade não confirmada. Use a câmera ao vivo.')
    return {'accepted': not reasons, 'message': reasons[0] if reasons else 'Captura aprovada.',
            'reasons': reasons, 'required_captures': required}


@dataclass
class EnrollmentResult:
    template: np.ndarray
    quality: float
    liveness: float
    capture_count: int


def build_enrollment(images, engine, settings):
    if len(images) != settings.enrollment_captures:
        raise ValidationFailed(f'Envie {settings.enrollment_captures} capturas aprovadas para concluir o cadastro.')
    features = []
    for index, image in enumerate(images):
        feature = engine.process_face(decode_image(image), check_liveness=True)
        feedback = capture_feedback(feature, settings.enrollment_captures)
        if not feedback['accepted']:
            raise ValidationFailed(f"Captura #{index + 1}: {feedback['message']}")
        vector = np.asarray(feature.embedding)
        if vector.ndim != 1 or not vector.size or not np.isfinite(vector).all() or np.linalg.norm(vector) <= 0:
            raise ValidationFailed('Representação facial inválida. Repita o cadastro.')
        if features and vector.shape != features[0].embedding.shape:
            raise ValidationFailed('Capturas incompatíveis. Repita o cadastro.')
        features.append(feature)
    for i, first in enumerate(features):
        for second in features[i + 1:]:
            score = engine.compute_similarity(first.embedding, second.embedding)
            if not np.isfinite(score) or score < settings.enrollment_min_consistency:
                raise ValidationFailed('Inconsistência entre as capturas. Use fotos da mesma pessoa.')
    template = np.mean([f.embedding for f in features], axis=0)
    norm = np.linalg.norm(template)
    if not np.isfinite(norm) or norm <= 0:
        raise ValidationFailed('Representação facial inválida. Repita o cadastro.')
    return EnrollmentResult(template / norm, float(np.mean([f.quality.score for f in features])),
                            float(np.mean([f.liveness.confidence for f in features])), len(features))
