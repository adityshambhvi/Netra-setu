"""End-to-end integration verification script for Netra-setu screening pipeline."""

import io
import sys
from pathlib import Path
from PIL import Image

from backend.app import app
from backend.matlab_bridge import bridge


def run_integration_tests():
    print("=" * 60)
    print("NETRA-SETU END-TO-END PIPELINE INTEGRATION TEST SUITE")
    print("=" * 60)

    client = app.test_client()

    # 1. Health check
    print("\n--- [Test 1] GET /health Endpoint ---")
    resp_h = client.get("/health")
    assert resp_h.status_code == 200, f"Expected 200, got {resp_h.status_code}"
    data_h = resp_h.get_json()
    print("Health Status:", data_h)
    assert data_h["status"] == "healthy"
    print("Status: [PASS]")

    # 2. Benchmark clean image test
    sample_img_path = Path("Dataset/IEEE diabetic retinopathy/A. Segmentation/A. Segmentation/1. Original Images/a. Training Set/IDRiD_01.jpg")
    if not sample_img_path.exists():
        print(f"[WARN] Benchmark sample image not found at {sample_img_path}, creating synthetic clean fundus image...")
        img = Image.new("RGB", (512, 512), color=(180, 50, 20))
        img_bytes_io = io.BytesIO()
        img.save(img_bytes_io, format="JPEG")
        img_bytes = img_bytes_io.getvalue()
        img_filename = "synthetic_clean.jpg"
    else:
        with open(sample_img_path, "rb") as f:
            img_bytes = f.read()
        img_filename = sample_img_path.name

    print(f"\n--- [Test 2] POST /screen with Benchmark Image ({img_filename}) ---")
    data_screen = {
        "image": (io.BytesIO(img_bytes), img_filename),
    }
    resp_s = client.post("/screen", data=data_screen, content_type="multipart/form-data")
    assert resp_s.status_code == 200, f"Expected 200, got {resp_s.status_code}"
    res_s = resp_s.get_json()
    assert res_s["success"] is True, "Screening API returned success=False"
    screening = res_s["screening"]
    print("Screening Output:")
    print("  Pass Status:      ", screening["pass"])
    print("  DR Grade:         ", screening["grade"], f"({screening['grade_label']})")
    print("  Referral Decision:", screening["referral"])
    print("  Why Refer Reason: ", screening["why_refer"])
    print("  Evidence List:    ", screening["evidence_list"])
    print("  Confidence:       ", screening["confidence"], "%")
    print("  Overlay Web Path: ", screening["overlay_image_path"])

    assert screening["pass"] is True, "Expected clean image to pass screening!"
    assert "grade" in screening
    assert "referral" in screening
    assert "why_refer" in screening
    assert isinstance(screening["evidence_list"], list)
    print("Status: [PASS]")

    # 3. Blurred image quality failure test
    print("\n--- [Test 3] POST /screen with Severely Blurred Image (Must Fail Quality Gate) ---")
    clean_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    from PIL import ImageFilter
    blurred_pil = clean_pil.filter(ImageFilter.GaussianBlur(radius=10))
    blur_buf = io.BytesIO()
    blurred_pil.save(blur_buf, format="JPEG")
    
    data_blur = {
        "image": (io.BytesIO(blur_buf.getvalue()), "blurred_test.jpg"),
    }
    resp_b = client.post("/screen", data=data_blur, content_type="multipart/form-data")
    assert resp_b.status_code == 200
    res_b = resp_b.get_json()
    screening_b = res_b["screening"]
    print("Blurred Image Screening Output:")
    print("  Pass Status:      ", screening_b["pass"])
    print("  Reason:           ", screening_b["reason"])
    print("  Why Refer / Action:", screening_b["why_refer"])

    assert screening_b["pass"] is False, "Expected blurred image to fail quality gate!"
    assert "Quality Gate" in screening_b["reason"] or "blur" in screening_b["reason"].lower()
    print("Status: [PASS]")

    print("=" * 60)
    print("ALL PIPELINE INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
