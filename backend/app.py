"""Flask API server for RetinaSense / Netra-setu screening system.

Endpoints:
  GET  /health              - System health & MATLAB engine status
  POST /api/quality-check   - Stage A Image Quality Gate evaluation
"""

import io
import logging
from flask import Flask, jsonify, request
from PIL import Image

from backend.matlab_bridge import bridge
from backend.quality_gate import check_image_quality

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RetinaSenseAPI")

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint reporting bridge connectivity."""
    status = bridge.get_status()
    return jsonify({
        "status": "healthy",
        "service": "RetinaSense Screening API",
        "bridge": status,
    }), 200


@app.route("/api/quality-check", methods=["POST"])
def quality_check_endpoint():
    """Evaluates uploaded fundus image against Stage A Quality Gate criteria."""
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "error": "No image file provided. Please upload an image under the 'image' field.",
        }), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({
            "success": False,
            "error": "Empty filename provided.",
        }), 400

    try:
        img_bytes = file.read()
        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # Run quality gate
        result = bridge.check_quality(pil_img)

        return jsonify({
            "success": True,
            "quality_gate": result.to_dict(),
        }), 200
    except Exception as e:
        logger.exception("Error processing image quality check")
        return jsonify({
            "success": False,
            "error": f"Failed to process image: {str(e)}",
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
