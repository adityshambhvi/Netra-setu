# Netra-setu-
Netra-setu is a quality-aware, explainable DR screening and referral assistant for frontline health workers using low-cost fundus cameras. It produces a defensible, evidence-backed referral decision and not a black-box verdit.

**Problem Statement 26038 — Explainable AI for Diabetic Retinopathy Screening in Rural India**
*Organization: MathWorks | Theme: MedTech / BioTech / HealthTech | Category: Software*

---
<img width="1897" height="992" alt="image" src="https://github.com/user-attachments/assets/a9187fff-9751-4f41-baf5-dda7e1f01817" />
<img width="1916" height="1052" alt="image" src="https://github.com/user-attachments/assets/d767ff9e-8c87-4d10-904f-00d743d96737" />
<img width="1913" height="1083" alt="image" src="https://github.com/user-attachments/assets/2087fde7-111f-4201-ada0-146fe6c254d4" />




## 1. Project Summary

RetinaSense is a quality-aware, explainable screening and referral assistant for diabetic
retinopathy (DR). It is **not** a diagnostic replacement for an ophthalmologist — it is a tool
that lets a minimally trained frontline health worker screen a patient's retinal image on-site
and get a defensible, evidence-backed referral recommendation.

**Core pipeline:**

```
Fundus Image
     ↓
Image Quality Gate  →  Bad → Recapture prompt
     ↓ Good
     ├─────────────────────┐
     ↓                     ↓
Lesion Detection      DR Grading CNN
(microaneurysms,        (ICDR 0–4)
 exudates)                   ↓
     ↓                  Grad-CAM attribution
     ↓                       ↓
     └───────────┬───────────┘
                 ↓
       Evidence Combiner
   (lesion map + attribution overlay)
                 ↓
    Referral Decision + Explanation
```

**MVP scope:** microaneurysm + exudate detection only. Hemorrhage and neovascularization
detection, plus full 5-level calibrated grading, are explicitly **Phase 2** — not promised in
the hackathon build.

---

## 2. Architecture Overview

Three layers, kept deliberately separate:

| Layer | Technology | Responsibility |
|---|---|---|
| **ML Pipeline (backend core)** | MATLAB | Image quality check, lesion detection, DR grading, explainability |
| **Integration Bridge** | Python + Flask + `matlab.engine` | Receives requests from frontend, calls MATLAB functions, returns JSON |
| **Frontend** | HTML/CSS/JS or React | Image upload, result dashboard, evidence display |

Separating these lets the team work in parallel and keeps MATLAB doing exactly what the
problem statement requires, without forcing the whole UI to live inside MATLAB App Designer.

---

## 3. Technology Stack

### Backend / ML Pipeline (MATLAB)
- MATLAB
- Image Processing Toolbox — CLAHE, illumination normalization, denoising, morphological ops
- Deep Learning Toolbox — CNN training, transfer learning, pretrained network import
- Computer Vision Toolbox — feature extraction, detection support
- `gradCAM` (native function) — explainability overlay

### Models & Techniques
- Pretrained CNN backbone (ResNet-50 / EfficientNet) — transfer-learned for DR grading
- U-Net-style segmentation model — microaneurysm + exudate detection
- Classical CV — Laplacian variance (blur), histogram analysis (exposure), thresholding/morphology (quality gate, vessels)

### Integration Layer
- Python
- `matlab.engine` for Python
- Flask (or FastAPI)
- Fallback: MATLAB writes result JSON + overlay image to disk; static file serving if live engine calls are unreliable

### Frontend
- HTML / CSS / JavaScript (or React for a more polished build)
- `fetch()` / Axios for API calls
- Browser file input with camera capture support for mobile/tablet use

### Datasets
- APTOS 2019 — grading (no lesion masks)
- IDRiD — lesion segmentation + grading (Indian-specific)
- DRIVE — vessel segmentation only
- Messidor-2 — external validation (grading only)

### Supporting Tools
- ONNX — model interchange, if importing externally pretrained weights
- Git / GitHub — version control
- Postman — API testing before frontend integration

### Deployment (Phase 2 roadmap, not hackathon build)
- MATLAB Compiler — standalone offline packaging for field devices

---

## 4. Detailed Build Steps

### Step 1 — Environment & Data Setup
- Install MATLAB with Image Processing, Deep Learning, and Computer Vision Toolboxes
- Set up Python environment: Flask, `matlab.engine`, `numpy`, `Pillow`
- Download datasets: APTOS 2019, IDRiD, DRIVE, Messidor-2 — keep in separate folders
- Split APTOS into train/validation; reserve Messidor-2 entirely for external testing (never train on it)
- Set up Git repo structure:
  ```
  /matlab-pipeline
  /backend
  /frontend
  /datasets   (or .gitignore if too large)
  ```

### Step 2 — Stage A: Image Quality Gate
- Blur detection via Laplacian variance
- Illumination/exposure check via histogram analysis
- Field-of-view check (circular Hough transform or vessel density heuristic)
- Enhancement branch: CLAHE (`adapthisteq`), illumination normalization, denoising (`imgaussfilt`)
- Empirically tune pass/fail thresholds against deliberately degraded sample images
- Deliverable: `checkImageQuality(image)` → `{pass/fail, reason, enhanced_image}`

### Step 3 — Stage B (Track 1): Lesion Detection
- Load IDRiD pixel-level lesion masks (microaneurysms, exudates)
- Preprocess: resize/normalize, augment (rotation, flip, brightness jitter)
- Train/fine-tune U-Net-style segmentation model (MATLAB, or prototype in PyTorch and import via ONNX)
- Validate visually against ground-truth masks
- Deliverable: `detectLesions(image)` → lesion masks + spatial coordinates

### Step 4 — Stage B (Track 2): DR Grading CNN
- Load APTOS with severity labels (0–4)
- Import pretrained CNN backbone, replace final layers for 5-class output
- Fine-tune with class-weighted loss (addresses imbalance toward mild/no-DR cases)
- Track referable-DR sensitivity (Level 2+) as the **primary** metric, not just overall accuracy
- Generate Grad-CAM maps via MATLAB's native `gradCAM`
- Deliverable: `gradeDR(image)` → `{grade, class probabilities, gradcam_heatmap}`

### Step 5 — Stage C: Evidence Combiner
- Overlay lesion masks + Grad-CAM heatmap on the original image
- Keep fusion **rule-based** (alpha-blended overlay, color-coded) — explicitly not learned, to preserve interpretability
- Generate "why refer" text: grade ≥ 2 AND lesion evidence present
- Deliverable: `combineEvidence(lesion_masks, gradcam_map, grade)` → annotated image + referral reasoning

### Step 6 — Stage D: Validation & Calibration
- Run full pipeline on held-out Messidor-2 set
- Generate confusion matrix + reliability (calibration) diagram
- Report sensitivity, specificity, F1, AUROC — referable-DR sensitivity as headline metric
- Adjust classification threshold to hit >90% sensitivity / >85% specificity target for referable DR

### Step 7 — Integration Layer
- Wrap all four stages into one MATLAB function: `runScreening(image_path)`
- Set up `matlab.engine` in Python; wrapper converts MATLAB struct output to JSON
- Build Flask API:
  - `POST /screen` — accepts image, returns JSON result
  - `GET /health` — server status check
- Test API independently with Postman before frontend integration

### Step 8 — Frontend Build
- Upload screen: file input / drag-and-drop / mobile camera capture
- Quality check state: loading indicator → pass/fail branching UI
- Result dashboard: original image, evidence overlay, grade, color-coded referral flag, evidence list, quality status
- Wire up `fetch()`/Axios calls to `/screen`
- Add error handling (network failure, bad image, backend timeout)

### Step 9 — End-to-End Testing
- Full flow test: upload → quality gate → detection → grading → combiner → display
- Test with both good and deliberately poor-quality images
- Time the pipeline; pre-load models at server startup if per-request latency is too high
- Test across all four datasets to catch resolution/format edge cases

### Step 10 — Demo Preparation
- Curate 3–5 test images spanning different severity grades, including one that fails the quality gate
- Prepare a backup screen recording of the full pipeline in case of live technical issues
- Prepare talking points on calibration and the "why refer" logic — likely judge questions

---

## 5. Suggested Team Split (parallel work from Step 3 onward)

| Track | Owns |
|---|---|
| **ML Track A** | Lesion detection (Step 3) |
| **ML Track B** | DR grading CNN + Grad-CAM (Step 4) |
| **Integration Track** | Evidence combiner, MATLAB↔Flask bridge (Steps 5, 7) |
| **Frontend Track** | Web UI, API wiring (Step 8) |

Steps 1–2 and 6–10 are shared checkpoints — the whole team should sync at these points rather
than working in silos.

---

## 6. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Cross-dataset generalization gap (APTOS → Messidor-2) | Treat Messidor-2 as explicit external validation; report honestly |
| Class imbalance (few severe/proliferative cases) | Class-weighted loss, augmentation |
| 5-lesion segmentation unrealistic in hackathon window | MVP scoped to 2 lesion types; rest is stated Phase 2 |
| `matlab.engine` integration proves unstable near deadline | Fallback: MATLAB writes result files, simple server serves them statically |
| Grad-CAM misrepresented as lesion-level detection | Architecture explicitly separates lesion detection (spatial evidence) from Grad-CAM (model attribution) — never conflate the two in the pitch |
| Overclaiming performance | Report sensitivity/specificity only after actual testing; label targets as "Target:" not "Achieves:" until measured |

---

## 7. Reference Materials

- **Datasets:** APTOS 2019 (Kaggle), IDRiD (IEEE DataPort), DRIVE (Grand Challenge), Messidor-2 (ADCIS)
- **Clinical standard:** International Clinical Diabetic Retinopathy (ICDR) Severity Scale
- **Explainability:** Selvaraju et al., *Grad-CAM*, ICCV 2017
- **Implementation reference:** MATLAB Deep Learning Toolbox documentation — `gradCAM`, pretrained network import
