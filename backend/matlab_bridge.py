"""MATLAB Integration Bridge for RetinaSense / Netra-setu.

Manages connection to MATLAB engine, invokes MATLAB screening functions,
and provides seamless fallback to Python-native modules when MATLAB is offline.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
from PIL import Image

from backend.quality_gate import RetinaQualityGate, QualityResult

logger = logging.getLogger("RetinaSenseBridge")


class MatlabScreeningBridge:
    """Bridges Flask API to MATLAB engine with high-availability fallback."""

    def __init__(self, use_matlab: bool = True):
        self._eng = None
        self._use_matlab = use_matlab
        self._fallback_gate = RetinaQualityGate()
        self.quality_dir = Path(__file__).resolve().parent.parent / "matlab-pipeline" / "quality"

    def connect_engine(self) -> bool:
        """Attempts to start or find an active shared MATLAB engine."""
        if not self._use_matlab:
            logger.info("MATLAB engine disabled via configuration; using native Python fallback.")
            return False

        try:
            # pyrefly: ignore [missing-import]
            import matlab.engine

            logger.info("Connecting to MATLAB Engine R2026a...")
            # Check for existing shared sessions first
            shared_sessions = matlab.engine.find_matlab()
            if shared_sessions:
                logger.info(f"Connecting to shared MATLAB session: {shared_sessions[0]}")
                self._eng = matlab.engine.connect_matlab(shared_sessions[0])
            else:
                logger.info("Starting new MATLAB engine instance...")
                self._eng = matlab.engine.start_matlab()

            # Add quality gate path to MATLAB path
            if self.quality_dir.exists():
                self._eng.addpath(str(self.quality_dir), nargout=0)
                logger.info(f"Added to MATLAB path: {self.quality_dir}")

            return True
        except Exception as e:
            logger.warning(f"Could not connect to MATLAB engine ({e}). Operating in native Python mode.")
            self._eng = None
            return False

    @property
    def is_engine_active(self) -> bool:
        return self._eng is not None

    def get_status(self) -> Dict[str, Any]:
        """Returns bridge operational status and diagnostic metadata."""
        status = {
            "matlab_connected": self.is_engine_active,
            "engine_backend": "MATLAB Engine R2026a" if self.is_engine_active else "Python Native (NumPy/PIL)",
            "pipeline_path": str(self.quality_dir),
        }
        if self.is_engine_active:
            try:
                status["matlab_version"] = self._eng.version()
            except Exception:
                status["matlab_version"] = "Unknown"
        return status

    def check_quality(
        self,
        image_input: Union[str, Path, bytes, Image.Image],
    ) -> QualityResult:
        """Executes Stage A Quality Gate via MATLAB engine or native Python."""
        if self.is_engine_active and isinstance(image_input, (str, Path)) and os.path.exists(str(image_input)):
            try:
                # Call checkImageQuality in MATLAB
                res_struct = self._eng.checkImageQuality(str(image_input), nargout=1)
                metrics_struct = res_struct.get("metrics", {})
                
                # Convert MATLAB struct to Python QualityResult
                from backend.quality_gate import QualityMetrics
                metrics = QualityMetrics(
                    blur_score=float(metrics_struct.get("blur_score", 0.0)),
                    tenengrad_score=float(metrics_struct.get("tenengrad_score", 0.0)),
                    mean_luminance=float(metrics_struct.get("mean_luminance", 0.0)),
                    underexposure_pct=float(metrics_struct.get("underexposure_pct", 0.0)),
                    overexposure_pct=float(metrics_struct.get("overexposure_pct", 0.0)),
                    fov_ratio=float(metrics_struct.get("fov_ratio", 0.0)),
                )
                
                # Fetch enhanced preview from fallback gate
                _, enhanced_preview = self._fallback_gate.evaluate(image_input)
                b64 = self._fallback_gate._to_base64_jpeg(enhanced_preview) if enhanced_preview else None

                return QualityResult(
                    passed=bool(res_struct.get("passed", False)),
                    reason=str(res_struct.get("reason", "")),
                    recapture_instructions=str(res_struct.get("recapture_instructions", "")),
                    metrics=metrics,
                    enhanced_image_base64=b64,
                )
            except Exception as e:
                logger.error(f"MATLAB engine execution error ({e}). Falling back to native Python.")

        # Fallback native evaluation
        result, _ = self._fallback_gate.evaluate(image_input)
        return result


# Global singleton bridge instance
bridge = MatlabScreeningBridge()
