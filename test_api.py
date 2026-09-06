"""Integration tests for Flask API endpoints."""

import io
from pathlib import Path
from PIL import Image

from backend.app import app


def test_api():
    print("Testing RetinaSense Flask API...")
    client = app.test_client()

    # 1. Test /health
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health_data = health_resp.get_json()
    print("Health response:", health_data)
    assert health_data["status"] == "healthy"

    # 2. Test /api/quality-check with IDRiD image
    img_path = Path("Dataset/IEEE diabetic retinopathy/A. Segmentation/A. Segmentation/1. Original Images/a. Training Set/IDRiD_01.jpg")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    data = {
        "image": (io.BytesIO(img_bytes), "IDRiD_01.jpg"),
    }
    resp = client.post("/api/quality-check", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    result = resp.get_json()
    print("Quality check result for IDRiD_01.jpg:")
    print("  Success:", result["success"])
    print("  Passed:", result["quality_gate"]["passed"])
    print("  Blur Score:", result["quality_gate"]["metrics"]["blur_score"])
    print("  Reason:", result["quality_gate"]["reason"])
    assert result["quality_gate"]["passed"] is True
    assert result["quality_gate"]["enhanced_image_base64"] is not None

    print("\nAPI Integration Tests PASSED successfully!")


if __name__ == "__main__":
    test_api()
