from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance


@dataclass(frozen=True)
class DetectionResult:
    tamper_score: float
    authentic_confidence: float
    ela_signal: float
    texture_signal: float


class DocumentTamperDetector:
    """Lightweight forensic baseline with a stable production-facing interface.

    This is intentionally not presented as a trained fraud model. It combines
    Error Level Analysis (ELA) and local texture inconsistency into a bounded
    score so the complete API/SQL analytics pipeline is runnable without large
    model weights. Replace `score()` with calibrated ViT/CLIP inference while
    preserving the returned contract.
    """

    def __init__(self, jpeg_quality: int = 90) -> None:
        self.jpeg_quality = jpeg_quality

    @staticmethod
    def _open_rgb(payload: bytes) -> Image.Image:
        image = Image.open(io.BytesIO(payload)).convert("RGB")
        if image.width < 64 or image.height < 64:
            raise ValueError("document image is too small; minimum size is 64x64")
        return image

    def _ela_signal(self, image: Image.Image) -> float:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=self.jpeg_quality)
        buffer.seek(0)
        recompressed = Image.open(buffer).convert("RGB")
        diff = ImageChops.difference(image, recompressed)
        extrema = diff.getextrema()
        max_diff = max(channel_max for _, channel_max in extrema) or 1
        enhanced = ImageEnhance.Brightness(diff).enhance(255.0 / max_diff)
        arr = np.asarray(enhanced, dtype=np.float32)
        # Robust upper-tail difference avoids a few isolated pixels dominating.
        return float(np.percentile(arr, 95) / 255.0)

    @staticmethod
    def _texture_signal(image: Image.Image) -> float:
        gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
        gray = cv2.resize(gray, (512, 512), interpolation=cv2.INTER_AREA)
        laplacian = cv2.Laplacian(gray, cv2.CV_32F)
        magnitude = np.abs(laplacian)
        # Compare local block edge energy; edited patches often produce uneven
        # compression/edge statistics. Normalize to a bounded coefficient.
        block = 64
        energies = []
        for y in range(0, magnitude.shape[0], block):
            for x in range(0, magnitude.shape[1], block):
                patch = magnitude[y : y + block, x : x + block]
                energies.append(float(np.mean(patch)))
        mean_energy = float(np.mean(energies)) + 1e-6
        cv = float(np.std(energies) / mean_energy)
        return float(np.clip(cv / 2.0, 0.0, 1.0))

    def score(self, payload: bytes) -> DetectionResult:
        image = self._open_rgb(payload)
        ela = self._ela_signal(image)
        texture = self._texture_signal(image)

        # Heuristic baseline only: weighted forensic signals mapped to 0-100.
        raw = 0.65 * ela + 0.35 * texture
        tamper_score = round(float(np.clip(raw * 100.0, 0.0, 100.0)), 2)
        authentic_confidence = round(100.0 - tamper_score, 2)

        return DetectionResult(
            tamper_score=tamper_score,
            authentic_confidence=authentic_confidence,
            ela_signal=round(ela, 4),
            texture_signal=round(texture, 4),
        )
