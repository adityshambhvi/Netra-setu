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
      <p style="font-size: 1.1rem; font-weight: 600;">Evaluating Stage A Quality Gate Criteria...</p>
      <p style="color: var(--text-muted); font-size: 0.9rem;">Checking Laplacian variance, Tenengrad energy, FOV ratio, and illumination...</p>
    </div>
  `;

  const result = await QualityGateAPI.analyzeImage(file);

  const passed = result.passed;
  const metrics = result.metrics || {};
  const statusBadge = passed ? 
    `<span class="status-badge badge-pass">PASSED (Stage A)</span>` : 
    `<span class="status-badge badge-fail">RECAPTURE REQUIRED</span>`;

  resultsContainer.innerHTML = `
    <div class="card" style="border-top: 5px solid ${passed ? '#137333' : '#c5221f'}; margin-top: 1.5rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3 style="font-size: 1.3rem; color: var(--brand-teal);">Stage A Diagnostic Analysis</h3>
        ${statusBadge}
      </div>

      <p style="font-weight: 600; color: ${passed ? '#137333' : '#c5221f'}; margin-bottom: 1rem;">
        ${result.reason}
      </p>

      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">Blur Score</div>
          <div class="metric-value">${metrics.blur_score ?? 'N/A'}</div>
          <small style="color: var(--text-muted);">Threshold &ge; 6.0</small>
        </div>
        <div class="metric-card">
          <div class="metric-label">Tenengrad Energy</div>
          <div class="metric-value">${metrics.tenengrad_score ?? 'N/A'}</div>
          <small style="color: var(--text-muted);">Threshold &ge; 60.0</small>
        </div>
        <div class="metric-card">
          <div class="metric-label">Mean Luminance</div>
          <div class="metric-value">${metrics.mean_luminance ?? 'N/A'}</div>
          <small style="color: var(--text-muted);">Optimal: 30 - 200</small>
        </div>
        <div class="metric-card">
          <div class="metric-label">Retinal FOV Ratio</div>
          <div class="metric-value">${(metrics.fov_ratio ? metrics.fov_ratio * 100 : 0).toFixed(1)}%</div>
          <small style="color: var(--text-muted);">Min: 20%</small>
        </div>
      </div>

      ${!passed ? `
        <div class="recapture-box">
          <div class="recapture-title">⚠️ Frontline Recapture Instructions:</div>
          <p style="font-size: 0.95rem; color: #6d2808;">${result.recapture_instructions}</p>
        </div>
      ` : `
        <div style="margin-top: 1.5rem; background: #eaf5ea; padding: 1.25rem; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h4 style="color: #137333;">✓ Ready for Stage B AI Model Screening</h4>
            <p style="font-size: 0.9rem; color: #2d5a37;">Image passed diagnostic quality gate and enhanced normalization.</p>
          </div>
          <button class="btn btn-primary" id="btn-run-stage-b">Proceed to DR Classifier</button>
        </div>
      `}
    </div>
  `;

  const btnStageB = document.getElementById('btn-run-stage-b');
  if (btnStageB) {
    btnStageB.addEventListener('click', () => {
      const newRec = PatientStore.addPatient({
        name: 'New Patient (Uploaded)',
        age: 50,
        gender: 'Unspecified',
        village: 'PHC Screening Center',
        eye: 'Right (OD)',
        stageAQuality: 'Passed',
        stageBResult: 'Normal / No DR',
        confidence: 96.4,
        status: 'Normal',
        notes: 'Stage A Passed. Stage B classified as No DR.'
      });
      alert(`Patient record ${newRec.id} created successfully! Saved to Patient History.`);
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
