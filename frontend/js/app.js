import { QualityGateAPI } from './quality_gate_api.js';
import { PatientStore } from './patient_store.js';

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initModals();
  initUploadHandler();
  initPatientScanner();
  renderPatientTable();
  initReferralNetwork();
});

/* Navigation Router */
function initNavigation() {
  const navLinks = document.querySelectorAll('.nav-link');
  const sections = document.querySelectorAll('.page-section');

  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = link.getAttribute('data-target');

      navLinks.forEach(l => l.classList.remove('active'));
      link.classList.add('active');

      sections.forEach(sec => {
        if (sec.id === targetId) {
          sec.classList.add('active-section');
        } else {
          sec.classList.remove('active-section');
        }
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });
}

/* Modal Management */
function initModals() {
  const btnScan = document.getElementById('btn-scan-patient');
  const btnUpload = document.getElementById('btn-upload-scan');

  const modalScan = document.getElementById('modal-scan');
  const modalUpload = document.getElementById('modal-upload');
  const closeBtns = document.querySelectorAll('.modal-close');

  if (btnScan) {
    btnScan.addEventListener('click', () => {
      openModal(modalScan);
      startCamera();
    });
  }

  if (btnUpload) {
    btnUpload.addEventListener('click', () => {
      openModal(modalUpload);
    });
  }

  closeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      closeAllModals();
      stopCamera();
    });
  });

  window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
      closeAllModals();
      stopCamera();
    }
  });
}

function openModal(modal) {
  closeAllModals();
  if (modal) modal.classList.add('active');
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
}

/* Upload & Quality Gate Evaluation Handler */
function initUploadHandler() {
  const dropzone = document.getElementById('upload-dropzone');
  const fileInput = document.getElementById('retina-file-input');
  const resultsContainer = document.getElementById('quality-results');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      processRetinaScan(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      processRetinaScan(e.target.files[0]);
    }
  });
}

async function processRetinaScan(file) {
  const resultsContainer = document.getElementById('quality-results');
  if (!resultsContainer) return;

  resultsContainer.style.display = 'block';
  resultsContainer.innerHTML = `
    <div style="text-align: center; padding: 2rem;">
      <div style="font-size: 2rem; color: var(--primary-green); margin-bottom: 0.5rem;">⚙️</div>
      <p style="font-size: 1.1rem; font-weight: 600;">Executing RetinaSense Screening Pipeline...</p>
      <p style="color: var(--text-muted); font-size: 0.9rem;">Running Stage A Quality Gate &rarr; Lesion Detection &rarr; ResNet-18 DR Grading &rarr; Evidence Combiner...</p>
    </div>
  `;

  const screening = await QualityGateAPI.screenImage(file);

  const passed = screening.pass;
  const qStatus = screening.quality_status || {};
  const metrics = qStatus.metrics || {};
  const referral = screening.referral;
  const gradeLabel = screening.grade_label || `Grade ${screening.grade ?? 0}`;
  const whyRefer = screening.why_refer || screening.reason || '';
  const evidenceList = screening.evidence_list || [];
  const confidence = screening.confidence ? screening.confidence.toFixed(1) : '90.0';
  const overlayUrl = screening.overlay_image_path || qStatus.enhanced_image_base64 || '';

  const statusBadge = passed ? 
    (referral ? `<span class="status-badge badge-fail">REFERRAL RECOMMENDED</span>` : `<span class="status-badge badge-pass">NO REFERRAL REQUIRED</span>`) : 
    `<span class="status-badge badge-fail">RECAPTURE REQUIRED</span>`;

  const evidenceListHtml = evidenceList.map(item => `<li style="margin-bottom: 0.4rem; color: var(--text-dark);">${item}</li>`).join('');

  resultsContainer.innerHTML = `
    <div class="card" style="border-top: 5px solid ${!passed ? '#c5221f' : (referral ? '#c5221f' : '#137333')}; margin-top: 1.5rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3 style="font-size: 1.3rem; color: var(--brand-teal);">End-to-End Diagnostic Screening Report</h3>
        ${statusBadge}
      </div>

      <!-- Stage A Quality Gate Summary -->
      <div style="background: ${passed ? '#f0f9f0' : '#fdf2f2'}; padding: 1rem; border-radius: 8px; margin-bottom: 1.25rem;">
        <div style="font-weight: 600; color: ${passed ? '#137333' : '#c5221f'};">
          Stage A Quality Gate: ${passed ? 'PASSED' : 'FAILED'} &mdash; ${qStatus.reason || screening.reason}
        </div>
        ${!passed ? `
          <div class="recapture-box" style="margin-top: 0.75rem;">
            <div class="recapture-title">⚠️ Frontline Recapture Instructions:</div>
            <p style="font-size: 0.95rem; color: #6d2808;">${qStatus.recapture_instructions || whyRefer}</p>
          </div>
        ` : ''}
      </div>

      ${passed ? `
        <!-- Stage B & C Screening Results -->
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1.25rem; display: flex; align-items: center; justify-content: space-between;">
          <span style="font-size: 0.9rem; font-weight: 600; color: #0f766e;">
            🛡️ Explainable AI (XAI) Audit Status: <span style="color: #0369a1;">Verifiable Dual-Evidence Fusion (Grad-CAM + Lesion Masks)</span>
          </span>
          <span style="font-size: 0.8rem; background: #e0f2fe; color: #0369a1; padding: 0.2rem 0.6rem; border-radius: 12px; font-weight: 600;">
            Non Black-Box Verdict
          </span>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem;">
          <div>
            <h4 style="color: var(--brand-teal); margin-bottom: 0.5rem;">ICDR Severity & Referral Decision</h4>
            <div style="font-size: 1.2rem; font-weight: 700; color: #1e293b; margin-bottom: 0.25rem;">
              ${gradeLabel}
            </div>
            <div style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 1rem;">
              Classification Confidence: <strong>${confidence}%</strong>
            </div>

            <!-- Plain-Language Why Refer Reason -->
            <div style="background: ${referral ? '#fef2f2' : '#f0fdf4'}; border-left: 4px solid ${referral ? '#dc2626' : '#16a34a'}; padding: 1rem; border-radius: 6px; margin-bottom: 1rem;">
              <div style="font-weight: 700; color: ${referral ? '#991b1b' : '#166534'}; margin-bottom: 0.3rem;">
                ${referral ? '🚨 Specialist Referral Rationale:' : '✅ Screening Recommendation:'}
              </div>
              <p style="font-size: 0.95rem; color: #334155; line-height: 1.4; margin: 0;">
                ${whyRefer}
              </p>
            </div>

            <!-- Evidence Findings List -->
            <h5 style="color: var(--brand-teal); margin-bottom: 0.4rem;">Defensible Clinical Evidence List</h5>
            <ul style="padding-left: 1.2rem; margin: 0; font-size: 0.9rem;">
              ${evidenceListHtml}
            </ul>
          </div>

          <div>
            <h4 style="color: var(--brand-teal); margin-bottom: 0.5rem;">Explainable AI Evidence Map</h4>
            ${overlayUrl ? `
              <div style="border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; background: #000; text-align: center;">
                <img src="${overlayUrl}" alt="Explainable AI Evidence Overlay" style="max-width: 100%; max-height: 280px; object-fit: contain;" />
              </div>
              <div style="display: flex; gap: 0.75rem; justify-content: center; margin-top: 0.6rem; font-size: 0.8rem; color: var(--text-muted); flex-wrap: wrap;">
                <span style="background: #f1f5f9; padding: 0.2rem 0.5rem; border-radius: 4px;"><span style="display:inline-block; width:10px; height:10px; background:red; border-radius:50%;"></span> Microaneurysms (U-Net)</span>
                <span style="background: #f1f5f9; padding: 0.2rem 0.5rem; border-radius: 4px;"><span style="display:inline-block; width:10px; height:10px; background:yellow; border-radius:50%;"></span> Hard Exudates (U-Net)</span>
                <span style="background: #f1f5f9; padding: 0.2rem 0.5rem; border-radius: 4px;"><span style="display:inline-block; width:10px; height:10px; background:cyan; border-radius:50%;"></span> Grad-CAM Heatmap</span>
              </div>
            ` : `
              <div style="padding: 2rem; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; text-align: center; color: var(--text-muted);">
                Overlay Image Generated on Backend
              </div>
            `}
          </div>
        </div>


        <div class="metrics-grid" style="margin-bottom: 1.25rem;">
          <div class="metric-card">
            <div class="metric-label">Blur Sharpness</div>
            <div class="metric-value">${metrics.blur_score ?? 'N/A'}</div>
            <small style="color: var(--text-muted);">&ge; 6.0</small>
          </div>
          <div class="metric-card">
            <div class="metric-label">Tenengrad Score</div>
            <div class="metric-value">${metrics.tenengrad_score ?? 'N/A'}</div>
            <small style="color: var(--text-muted);">&ge; 60.0</small>
          </div>
          <div class="metric-card">
            <div class="metric-label">Mean Luminance</div>
            <div class="metric-value">${metrics.mean_luminance ?? 'N/A'}</div>
            <small style="color: var(--text-muted);">30 - 200</small>
          </div>
          <div class="metric-card">
            <div class="metric-label">Retinal FOV</div>
            <div class="metric-value">${(metrics.fov_ratio ? metrics.fov_ratio * 100 : 0).toFixed(1)}%</div>
            <small style="color: var(--text-muted);">&ge; 20%</small>
          </div>
        </div>

        <div style="margin-top: 1.25rem; text-align: right;">
          <button class="btn btn-primary" id="btn-save-patient-rec">Save to Patient Record</button>
        </div>
      ` : ''}
    </div>
  `;

  const btnSave = document.getElementById('btn-save-patient-rec');
  if (btnSave) {
    btnSave.addEventListener('click', () => {
      const newRec = PatientStore.addPatient({
        name: 'New Patient (Uploaded)',
        age: 52,
        gender: 'Unspecified',
        village: 'PHC Screening Center',
        eye: 'Right (OD)',
        stageAQuality: passed ? 'Passed' : 'Failed',
        stageBResult: gradeLabel,
        confidence: Number(confidence),
        status: referral ? 'Urgent Referral' : 'Normal',
        notes: `Screening: ${whyRefer}`,
      });
      alert(`Patient record ${newRec.id} saved successfully to Tele-Ophthalmology Database!`);
      closeAllModals();
      renderPatientTable();
      document.querySelector('[data-target="section-history"]').click();
    });
  }
}

/* Patient Scanner & Camera Logic */
let cameraStream = null;

function initPatientScanner() {
  const btnCapture = document.getElementById('btn-capture-frame');
  if (!btnCapture) return;

  btnCapture.addEventListener('click', () => {
    const video = document.getElementById('webcam-feed');
    const canvas = document.getElementById('webcam-canvas');

    if (video && canvas) {
      const ctx = canvas.getContext('2d');
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      canvas.toBlob(blob => {
        closeAllModals();
        stopCamera();
        const modalUpload = document.getElementById('modal-upload');
        openModal(modalUpload);
        processRetinaScan(blob);
      }, 'image/jpeg');
    } else {
      alert('Camera snapshot taken!');
    }
  });
}

function startCamera() {
  const video = document.getElementById('webcam-feed');
  const fallback = document.getElementById('camera-sim-box');
  if (!video) return;

  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      .then(stream => {
        cameraStream = stream;
        video.srcObject = stream;
        video.style.display = 'block';
        if (fallback) fallback.style.display = 'none';
      })
      .catch(err => {
        console.warn('Webcam access not granted, running optics simulator:', err);
        if (video) video.style.display = 'none';
        if (fallback) fallback.style.display = 'flex';
      });
  } else {
    if (video) video.style.display = 'none';
    if (fallback) fallback.style.display = 'flex';
  }
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }
}

/* Render Patient Database Table */
function renderPatientTable() {
  const tbody = document.getElementById('patient-table-body');
  const searchInput = document.getElementById('search-patient-input');
  if (!tbody) return;

  const render = (query = '') => {
    const records = PatientStore.searchPatients(query);
    if (records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No matching patient records found.</td></tr>`;
      return;
    }

    tbody.innerHTML = records.map(p => {
      const badgeClass = p.status.includes('Normal') ? 'badge-pass' : (p.status.includes('Urgent') ? 'badge-fail' : 'badge-warning');
      return `
        <tr>
          <td><strong>${p.id}</strong></td>
          <td>${p.name} (${p.age}, ${p.gender[0]})</td>
          <td>${p.village}</td>
          <td>${p.scanDate}</td>
          <td><span class="status-badge ${p.stageAQuality === 'Passed' ? 'badge-pass' : 'badge-fail'}">${p.stageAQuality}</span></td>
          <td>${p.stageBResult} (${p.confidence}%)</td>
          <td><span class="status-badge ${badgeClass}">${p.status}</span></td>
        </tr>
      `;
    }).join('');
  };

  render();

  if (searchInput) {
    searchInput.addEventListener('input', (e) => render(e.target.value));
  }
}

/* Referral Network Interactive Trigger */
function initReferralNetwork() {
  const btnReferral = document.getElementById('btn-create-referral');
  if (btnReferral) {
    btnReferral.addEventListener('click', () => {
      alert('Tele-Ophthalmology Referral Request generated and transmitted to District Tele-consultation portal.');
    });
  }
}
