"""Stage A: Image Quality Gate for RetinaSense / Netra-setu.

Performs:
1. Field-of-view (FOV) and sensor occlusion checks
2. Masked Laplacian variance and Tenengrad sharpness for motion/defocus blur
3. Retinal illumination and corneal glare analysis via histogram statistics
4. Frontline recapture feedback loop with clinical operator prompts
5. Image enhancement via contrast-limited adaptive equalization & normalization
"""

import base64
import io
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


@dataclass
class QualityMetrics:
    blur_score: float
    tenengrad_score: float
    mean_luminance: float
    underexposure_pct: float
    overexposure_pct: float
    fov_ratio: float


@dataclass
class QualityResult:
    passed: bool
    reason: str
    recapture_instructions: str
    metrics: QualityMetrics
    enhanced_image_base64: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


class RetinaQualityGate:
    """Evaluates retinal fundus image suitability for DR screening."""

    def __init__(
        self,
        blur_threshold: float = 10.0,
        tenengrad_threshold: float = 80.0,
        min_fov_ratio: float = 0.20,
        max_fov_ratio: float = 0.98,
        min_mean_luminance: float = 32.0,
        max_underexposure_pct: float = 30.0,
        max_overexposure_pct: float = 12.0,
    ):
        self.blur_threshold = blur_threshold
        self.tenengrad_threshold = tenengrad_threshold
        self.min_fov_ratio = min_fov_ratio
        self.max_fov_ratio = max_fov_ratio
        self.min_mean_luminance = min_mean_luminance
        self.max_underexposure_pct = max_underexposure_pct
        self.max_overexposure_pct = max_overexposure_pct

    @staticmethod
    def _load_image(image_input: Union[str, Path, bytes, Image.Image, np.ndarray]) -> Image.Image:
        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.is_file():
                raise FileNotFoundError(f"Image not found at: {path}")
            return Image.open(path).convert("RGB")
        elif isinstance(image_input, bytes):
            return Image.open(io.BytesIO(image_input)).convert("RGB")
        elif isinstance(image_input, Image.Image):
            return image_input.convert("RGB")
        elif isinstance(image_input, np.ndarray):
            if image_input.dtype != np.uint8:
                image_input = np.clip(image_input, 0, 255).astype(np.uint8)
            if image_input.ndim == 2:
                return Image.fromarray(image_input).convert("RGB")
            return Image.fromarray(image_input)
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")

    @staticmethod
    def _compute_laplacian(channel: np.ndarray) -> np.ndarray:
        """Computes 4-connected discrete Laplacian using vectorized NumPy padding."""
        padded = np.pad(channel, 1, mode="edge")
        lap = (
            padded[:-2, 1:-1]
            + padded[2:, 1:-1]
            + padded[1:-1, :-2]
            + padded[1:-1, 2:]
            - 4.0 * padded[1:-1, 1:-1]
        )
        return lap

    @staticmethod
    def _compute_tenengrad(channel: np.ndarray) -> np.ndarray:
        """Computes Tenengrad gradient energy using 3x3 Sobel kernels."""
        padded = np.pad(channel, 1, mode="edge")
        gx = (
            padded[:-2, 2:]
            + 2.0 * padded[1:-1, 2:]
            + padded[2:, 2:]
            - padded[:-2, :-2]
            - 2.0 * padded[1:-1, :-2]
            - padded[2:, :-2]
        )
        gy = (
            padded[2:, :-2]
            + 2.0 * padded[2:, 1:-1]
            + padded[2:, 2:]
            - padded[:-2, :-2]
            - 2.0 * padded[:-2, 1:-1]
            - padded[:-2, 2:]
        )
        return gx**2 + gy**2

    def _extract_retinal_mask(self, rgb_arr: np.ndarray) -> Tuple[np.ndarray, float]:
        """Segments the circular retinal disk from the dark border frame."""
        h, w, _ = rgb_arr.shape
        red = rgb_arr[:, :, 0]
        green = rgb_arr[:, :, 1]

        # Initial intensity mask
        mask = (green > 12) | (red > 20)
        fov_ratio = float(np.sum(mask) / (h * w))
        return mask, fov_ratio

    def _enhance_fundus(self, pil_img: Image.Image) -> Image.Image:
        """Enhances microaneurysm and exudate contrast while controlling noise."""
        # 1. Mild unsharp mask for vessel & border clarity
        sharpened = pil_img.filter(ImageFilter.UnsharpMask(radius=2, percent=130, threshold=3))

        # 2. Local contrast expansion via auto-contrast on Green & Luminance
        r, g, b = sharpened.split()
        g_eq = ImageOps.autocontrast(g, cutoff=1)
        r_eq = ImageOps.autocontrast(r, cutoff=1)
        b_eq = ImageOps.autocontrast(b, cutoff=1)
        enhanced_merged = Image.merge("RGB", (r_eq, g_eq, b_eq))

        # 3. Boost color vibrancy slightly for clinical readability
        color_enhancer = ImageEnhance.Color(enhanced_merged)
        final_enh = color_enhancer.enhance(1.15)
        return final_enh

    @staticmethod
    def _to_base64_jpeg(pil_img: Image.Image, quality: int = 85) -> str:
        buffer = io.BytesIO()
        pil_img.save(buffer, format="JPEG", quality=quality)
        return f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"

    def evaluate(
        self,
        image_input: Union[str, Path, bytes, Image.Image, np.ndarray],
        return_enhanced: bool = True,
    ) -> Tuple[QualityResult, Optional[Image.Image]]:
        """Evaluates image quality against all criteria and returns diagnostic results."""
        pil_img = self._load_image(image_input)
        rgb_arr = np.array(pil_img, dtype=np.float32)
        green_chan = rgb_arr[:, :, 1]

        # 1. Field of view segmentation
        mask, fov_ratio = self._extract_retinal_mask(rgb_arr)
        mask_pixels = np.sum(mask)

        # 2. Sharpness & Blur computation inside retinal boundary
        if mask_pixels > 100:
            laplacian = self._compute_laplacian(green_chan)
            masked_lap = laplacian[mask]
            blur_score = float(np.var(masked_lap))

            tenengrad_map = self._compute_tenengrad(green_chan)
            tenengrad_score = float(np.mean(tenengrad_map[mask]))
        else:
            blur_score = 0.0
            tenengrad_score = 0.0

        # 3. Illumination & Glare statistics
        if mask_pixels > 100:
            masked_green = green_chan[mask]
            mean_luminance = float(np.mean(masked_green))
            underexposed_count = int(np.sum(masked_green < 35))
            overexposed_count = int(np.sum(masked_green > 235))
            underexposure_pct = float((underexposed_count / mask_pixels) * 100.0)
            overexposure_pct = float((overexposed_count / mask_pixels) * 100.0)
        else:
            mean_luminance = 0.0
            underexposure_pct = 100.0
            overexposure_pct = 0.0

        # 4. Clinical Decision Rules
        passed = True
        reasons = []
        instructions = []

        # FOV check
        if fov_ratio < self.min_fov_ratio:
            passed = False
            reasons.append(
                f"Field-of-view too small ({fov_ratio*100:.1f}% of frame, minimum {self.min_fov_ratio*100:.1f}%)"
            )
            instructions.append(
                "Camera alignment error: Center the camera lens directly on the patient's pupil and bring it closer to frame the full retina."
            )
        elif fov_ratio > self.max_fov_ratio and mean_luminance < 15:
            passed = False
            reasons.append("Blank or fully occluded capture detected")
            instructions.append(
                "Check for lens cap or total sensor blockage, confirm camera illumination LED is on, and recapture."
            )

        # Blur / Sharpness check: evaluate both Laplacian variance and Tenengrad energy
        if blur_score < self.blur_threshold or tenengrad_score < self.tenengrad_threshold:
            passed = False
            reasons.append(
                f"Severe blur detected (sharpness: blur={blur_score:.1f} < {self.blur_threshold:.1f}, tenengrad={tenengrad_score:.1f} < {self.tenengrad_threshold:.1f})"
            )
            instructions.append(
                "Motion or defocus blur: Stabilize camera with the forehead rest, instruct the patient to look steadily at the internal fixation target, and rotate the focus dial until retinal blood vessels appear crisp."
            )

        # Exposure checks
        if mean_luminance < self.min_mean_luminance or underexposure_pct > self.max_underexposure_pct:
            passed = False
            reasons.append(
                f"Underexposed / insufficient light (mean luminance {mean_luminance:.1f}, {underexposure_pct:.1f}% dark pixels)"
            )
            instructions.append(
                "Underexposure: Increase camera LED flash/illumination setting or allow the patient's eyes 60 seconds to naturally dilate in a darkened screening room."
            )

        if overexposure_pct > self.max_overexposure_pct:
            passed = False
            reasons.append(
                f"Corneal glare / severe overexposure detected ({overexposure_pct:.1f}% saturated pixels)"
            )
            instructions.append(
                "Corneal flash reflection: Slightly alter camera tilt or angle relative to the pupil to displace the white reflection away from the diagnostic field."
            )

        # 5. Enhancement Branch
        enhanced_img = None
        b64_str = None
        if return_enhanced:
            enhanced_img = self._enhance_fundus(pil_img)
            b64_str = self._to_base64_jpeg(enhanced_img)

        metrics = QualityMetrics(
            blur_score=round(blur_score, 2),
            tenengrad_score=round(tenengrad_score, 2),
            mean_luminance=round(mean_luminance, 2),
            underexposure_pct=round(underexposure_pct, 2),
            overexposure_pct=round(overexposure_pct, 2),
            fov_ratio=round(fov_ratio, 4),
        )

        result = QualityResult(
            passed=passed,
            reason="Pass: Image satisfies diagnostic sharpness and illumination criteria."
            if passed
            else " | ".join(reasons),
            recapture_instructions="N/A (Ready for DR screening)"
            if passed
            else " ".join(instructions),
            metrics=metrics,
            enhanced_image_base64=b64_str,
        )

        return result, enhanced_img


# Convenience functional interface
_DEFAULT_GATE = RetinaQualityGate()


def check_image_quality(
    image_input: Union[str, Path, bytes, Image.Image, np.ndarray],
    **kwargs,
) -> Tuple[QualityResult, Optional[Image.Image]]:
    """Runs Stage A quality evaluation with default clinical thresholds."""
    if kwargs:
        gate = RetinaQualityGate(**kwargs)
        return gate.evaluate(image_input)
    return _DEFAULT_GATE.evaluate(image_input)
