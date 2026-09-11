"""Flask API server for RetinaSense / Netra-setu screening system.

Endpoints:
  GET  /                    - Frontend dashboard
  GET  /health              - System health & MATLAB engine status
  POST /api/quality-check   - Stage A Image Quality Gate evaluation
"""

import io
import logging
from pathlib import Path
# pyrefly: ignore [missing-import]
from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image

from backend.matlab_bridge import bridge
from backend.quality_gate import check_image_quality

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RetinaSenseAPI")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app, origins="*", supports_credentials=True)


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


@app.route("/screen", methods=["POST"])
@app.route("/api/screen", methods=["POST"])
def screen_endpoint():
    """Evaluates full screening pipeline (quality gate -> lesion detection -> DR grading -> combiner)."""
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "error": "No image file provided. Upload image under 'image' field.",
        }), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({
            "success": False,
            "error": "Empty filename provided.",
        }), 400

    try:
        # Save temp image for MATLAB / Python processing
        temp_dir = Path(__file__).resolve().parent / "static" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / file.filename
        file.save(str(temp_path))

        result = bridge.run_screening(temp_path)

        return jsonify({
            "success": True,
            "screening": result,
        }), 200
    except Exception as e:
        logger.exception("Error processing full screening request")
        return jsonify({
            "success": False,
            "error": f"Screening pipeline error: {str(e)}",
        }), 500


@app.route("/overlays/<path:filename>")
def serve_overlay(filename):
    """Serves generated evidence overlay images."""
    overlay_dir = Path(__file__).resolve().parent / "static" / "overlays"
    return app.send_static_file(f"../backend/static/overlays/{filename}") if (overlay_dir / filename).exists() else ("Overlay not found", 404)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """Serves the static frontend files from /frontend directory (SPA fallback)."""
    # Check overlays static path first
    if path.startswith("overlays/"):
        overlay_file = Path(__file__).resolve().parent / "static" / path
        if overlay_file.is_file():
            from flask import send_file
            return send_file(str(overlay_file))

    if path and Path(app.static_folder, path).is_file():
        return app.send_static_file(path)
    return app.send_static_file("index.html")


if __name__ == "__main__":
    bridge.connect_engine()
    app.run(host="0.0.0.0", port=5000, debug=False)

