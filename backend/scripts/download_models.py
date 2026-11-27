"""Download the UniFace model weights used by FaceAccess into UNIFACE_CACHE_DIR.

This is the ONLY step that requires internet access for the biometric engine.
It downloads public model weights (no personal data is transmitted) and verifies
their SHA-256 using UniFace's own registry. Run it once during installation:

    docker compose --profile setup run --rm model-fetch
"""
from __future__ import annotations

import os
import sys

# Allow running standalone (python scripts/download_models.py) or as a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.biometrics.model_catalog import REQUIRED_MODELS, model_file_path  # noqa: E402


def main() -> int:
    cache = os.environ.get("UNIFACE_CACHE_DIR")
    if not cache:
        print("UNIFACE_CACHE_DIR must be set", file=sys.stderr)
        return 2
    os.makedirs(cache, exist_ok=True)
    from uniface import download_models

    paths = download_models([m.weight for m in REQUIRED_MODELS])
    for m in REQUIRED_MODELS:
        p = model_file_path(m.weight)
        ok = os.path.exists(p)
        print(f"[{'OK' if ok else 'MISSING'}] {m.role:<12} {m.weight.value:<20} license={m.license}  -> {p}")
    return 0 if len(paths) == len(REQUIRED_MODELS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
