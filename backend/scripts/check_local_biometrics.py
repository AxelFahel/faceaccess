"""Time real local models using synthetic pixels, without storing face images."""
import json
import os
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ.update(json.loads((root / ".runtime.env").read_text(encoding="utf-8")))

import numpy as np
from app.biometrics.engine import get_biometric_engine

start = time.perf_counter()
engine = get_biometric_engine()
print(f"Model initialization: {time.perf_counter() - start:.3f}s", flush=True)
image = np.full((480, 640, 3), 120, dtype=np.uint8)
landmarks = np.array([[250, 190], [390, 190], [320, 260], [270, 330], [370, 330]], dtype=np.float32)
for name, call in [
    ("detector", lambda: engine.detector.detect(image, max_num=2)),
    ("quality", lambda: engine.quality_model.predict(image, landmarks)),
    ("liveness", lambda: engine.anti_spoof.predict(image, np.array([180, 80, 460, 400]))),
    ("embedding", lambda: engine.recognizer.get_normalized_embedding(image, landmarks)),
]:
    start = time.perf_counter()
    call()
    print(f"{name}: {time.perf_counter() - start:.3f}s", flush=True)
print("Synthetic timing only; does not validate real-face acceptance or anti-spoofing accuracy.")
