"""Verify Flask, numpy, Pillow, and matlab.engine are working."""

import io
import sys


def test_numpy() -> bool:
    import numpy as np

    arr = np.array([1, 2, 3])
    assert arr.sum() == 6
    assert np.__version__
    print(f"[OK] numpy {np.__version__} — array sum = {arr.sum()}")
    return True


def test_pillow() -> bool:
    from PIL import Image

    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    assert len(buf.getvalue()) > 0
    print(f"[OK] Pillow {Image.__version__} — created and encoded 10x10 PNG")
    return True


def test_flask() -> bool:
    from flask import Flask

    app = Flask(__name__)

    @app.route("/")
    def index():
        return "ok"

    with app.test_client() as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.data == b"ok"

    from importlib.metadata import version

    print(f"[OK] Flask {version('flask')} — test client returned 200")
    return True


def test_matlab_engine() -> bool:
    try:
        import matlab.engine
    except ImportError:
        print("[SKIP] matlab.engine — not installed (MATLAB required)")
        return False

    print("[OK] matlab.engine — module imported successfully")
    print("     Note: starting an engine requires a licensed MATLAB installation.")
    return True


def main() -> int:
    results = {
        "numpy": test_numpy(),
        "Pillow": test_pillow(),
        "Flask": test_flask(),
        "matlab.engine": test_matlab_engine(),
    }

    passed = sum(results.values())
    total = len(results)
    print(f"\nResult: {passed}/{total} checks passed")

    if not results["matlab.engine"]:
        print(
            "\nTo enable matlab.engine:\n"
            "  1. Install MATLAB (R2024b or later)\n"
            "  2. Activate this venv: .venv\\Scripts\\activate\n"
            "  3. Run: pip install matlabengine"
        )

    return 0 if passed >= 3 else 1


if __name__ == "__main__":
    sys.exit(main())
