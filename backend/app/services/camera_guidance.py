"""Transient positioning guidance, separate from identity/access decisions."""
import math


def camera_guidance(feature, width, height):
    def response(accepted, message):
        return {"accepted": accepted, "message": message}
    if feature is None:
        return response(False, "Nenhum rosto encontrado. Posicione-se dentro da marcação.")
    x1, y1, x2, y2 = feature.bbox
    if width <= 0 or height <= 0 or not all(math.isfinite(v) for v in feature.bbox) or x2 <= x1 or y2 <= y1:
        return response(False, "Não foi possível avaliar a posição. Tente novamente.")
    center_x, center_y = (x1+x2)/(2*width), (y1+y2)/(2*height)
    face_height = (y2-y1)/height
    if face_height < .32:
        return response(False, "Aproxime-se um pouco da câmera.")
    if face_height > .78 or x1 < 0 or y1 < 0 or x2 > width or y2 > height:
        return response(False, "Afaste-se um pouco para manter o rosto inteiro na imagem.")
    if not (.38 <= center_x <= .62 and .32 <= center_y <= .62):
        return response(False, "Centralize o rosto dentro da marcação.")
    if not feature.quality.passed:
        return response(False, " ".join(feature.quality.errors) or "Ajuste a iluminação e olhe para a câmera.")
    if not feature.liveness or not feature.liveness.is_real:
        return response(False, "Vivacidade não confirmada. Olhe diretamente para a câmera.")
    return response(True, "Posição e qualidade aprovadas. Mantenha o rosto parado.")
