"""Automated test suite for Stage A: Image Quality Gate (RetinaSense).

Validates:
1. Baseline clean retinal images from IDRiD benchmark dataset.
2. Deliberately degraded images (severe blur, underexposure, glare, invalid FOV).
3. Actionable frontline worker recapture instructions.
4. CLAHE and illumination enhancement outputs.
"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from backend.quality_gate import RetinaQualityGate, check_image_quality


def run_tests() -> bool:
    print("=" * 60)
    print("STAGE A: RETINASENSE QUALITY GATE VERIFICATION SUITE")
    print("=" * 60)

    # Locate sample test images from IDRiD dataset
    dataset_dir = Path(
        "Dataset/IEEE diabetic retinopathy/A. Segmentation/A. Segmentation/1. Original Images/a. Training Set"
    )

    if not dataset_dir.exists():
        print(f"[ERROR] Dataset directory not found at: {dataset_dir}")
        return False

    sample_files = sorted(list(dataset_dir.glob("*.jpg")))[:3]
    if not sample_files:
        print(f"[ERROR] No JPG images found in {dataset_dir}")
        return False

    print(f"Found {len(sample_files)} benchmark images for baseline testing.")

    # 1. Test Baseline Authentic Images
    print("\n--- [Test Group 1] Baseline Benchmark Images (Must PASS) ---")
    for img_path in sample_files:
        result, enhanced = check_image_quality(img_path)
        print(f"Image: {img_path.name}")
        print(f"  Passed:             {result.passed}")
        print(f"  Blur Score:         {result.metrics.blur_score:.2f}")
        print(f"  Tenengrad Score:    {result.metrics.tenengrad_score:.2f}")
        print(f"  Mean Luminance:     {result.metrics.mean_luminance:.2f}")
        print(f"  FOV Ratio:          {result.metrics.fov_ratio:.2%}")
        print(f"  Reason:             {result.reason}")

        assert result.passed is True, f"Expected {img_path.name} to pass, but failed: {result.reason}"
        assert enhanced is not None, "Enhanced image was not generated"
        assert result.enhanced_image_base64.startswith("data:image/jpeg;base64,"), "Invalid base64 payload"
        print("  Status: [PASS]\n")

    # Load first sample for synthetic degradation tests
    base_img = Image.open(sample_files[0]).convert("RGB")
    w, h = base_img.size

    # 2. Test Severe Blur
    print("--- [Test Group 2] Synthetic Defocus / Motion Blur (Must FAIL) ---")
    blurred_img = base_img.filter(ImageFilter.GaussianBlur(radius=9))
    result_blur, _ = check_image_quality(blurred_img)
    print(f"Blur Score: {result_blur.metrics.blur_score:.2f} (Threshold: 35.0)")
    print(f"Passed:     {result_blur.passed}")
    print(f"Reason:     {result_blur.reason}")
    print(f"Recapture:  {result_blur.recapture_instructions}")

    assert result_blur.passed is False, "Blur test should have failed quality gate!"
    assert "blur" in result_blur.reason.lower(), "Diagnostic reason missing 'blur'"
    assert "focus" in result_blur.recapture_instructions.lower() or "stabilize" in result_blur.recapture_instructions.lower()
    print("Status: [PASS] Blur caught accurately with clinical recapture instructions.\n")

    # 3. Test Underexposure (Severe Darkness)
    print("--- [Test Group 3] Synthetic Underexposure / Low Light (Must FAIL) ---")
    dark_arr = (np.array(base_img, dtype=np.float32) * 0.15).astype(np.uint8)
    dark_img = Image.fromarray(dark_arr)
    result_dark, _ = check_image_quality(dark_img)
    print(f"Mean Luminance:    {result_dark.metrics.mean_luminance:.2f}")
    print(f"Underexposure Pct: {result_dark.metrics.underexposure_pct:.2f}%")
    print(f"Passed:            {result_dark.passed}")
    print(f"Reason:            {result_dark.reason}")
    print(f"Recapture:         {result_dark.recapture_instructions}")

    assert result_dark.passed is False, "Dark test should have failed quality gate!"
    assert "underexposed" in result_dark.reason.lower(), "Reason missing 'underexposed'"
    assert "illumination" in result_dark.recapture_instructions.lower() or "dilate" in result_dark.recapture_instructions.lower()
    print("Status: [PASS] Low illumination caught accurately with lighting/dilation guidance.\n")

    # 4. Test Flash Glare / Overexposure
    print("--- [Test Group 4] Synthetic Corneal Glare / Reflection (Must FAIL) ---")
    glare_img = base_img.copy()
    draw = ImageDraw.Draw(glare_img)
    center_x, center_y = w // 2, h // 2
    radius = int(min(w, h) * 0.22)
    draw.ellipse(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        fill=(255, 255, 255),
    )
    result_glare, _ = check_image_quality(glare_img)
    print(f"Overexposure Pct:  {result_glare.metrics.overexposure_pct:.2f}% (Threshold: 12.0%)")
    print(f"Passed:            {result_glare.passed}")
    print(f"Reason:            {result_glare.reason}")
    print(f"Recapture:         {result_glare.recapture_instructions}")

    assert result_glare.passed is False, "Glare test should have failed quality gate!"
    assert "overexposure" in result_glare.reason.lower() or "glare" in result_glare.reason.lower()
    assert "angle" in result_glare.recapture_instructions.lower() or "reflection" in result_glare.recapture_instructions.lower()
    print("Status: [PASS] Glare caught accurately with angle adjustment prompt.\n")

    # 5. Test Invalid Field-of-View (Misaligned / Blank Crop)
    print("--- [Test Group 5] Misaligned Camera / Small FOV (Must FAIL) ---")
    blank_img = Image.new("RGB", (w, h), color=(0, 0, 0))
    # Paste only a tiny corner (10% of frame)
    corner = base_img.crop((0, 0, int(w * 0.3), int(h * 0.3)))
    blank_img.paste(corner, (0, 0))
    result_fov, _ = check_image_quality(blank_img)
    print(f"FOV Ratio:  {result_fov.metrics.fov_ratio:.2%} (Minimum: 20.0%)")
    print(f"Passed:     {result_fov.passed}")
    print(f"Reason:     {result_fov.reason}")
    print(f"Recapture:  {result_fov.recapture_instructions}")

    assert result_fov.passed is False, "FOV test should have failed quality gate!"
    assert "field-of-view" in result_fov.reason.lower() or "fov" in result_fov.reason.lower()
    assert "center" in result_fov.recapture_instructions.lower() or "pupil" in result_fov.recapture_instructions.lower()
    print("Status: [PASS] Misaligned FOV caught accurately with centering instructions.\n")

    print("=" * 60)
    print("ALL QUALITY GATE CHECKS VERIFIED AND PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
