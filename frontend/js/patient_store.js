/**
 * Patient Store & Local Records Database for Netra-setu
 */

const STORAGE_KEY = 'netra_setu_patients_v1';

const MOCK_INITIAL_PATIENTS = [
  {
    id: 'NS-2026-081',
    name: 'Ramesh Patel',
    age: 58,
    gender: 'Male',
    village: 'Anand, Gujarat',
    scanDate: '2026-09-07',
    eye: 'Right (OD)',
    stageAQuality: 'Passed',
    stageBResult: 'Mild Diabetic Retinopathy',
    confidence: 94.2,
    status: 'Routine Followup',
    notes: 'Microaneurysms detected in nasal quadrant. Schedule 6-month check.'
  },
  {
    id: 'NS-2026-082',
    name: 'Sunita Devi',
    age: 49,
    gender: 'Female',
    village: 'Chittoor, AP',
    scanDate: '2026-09-07',
    eye: 'Left (OS)',
    stageAQuality: 'Passed',
    stageBResult: 'Normal / No DR',
    confidence: 98.8,
    status: 'Normal',
    notes: 'Healthy macula and optic disc clear. Annual screening advised.'
  },
  {
    id: 'NS-2026-083',
    name: 'Vikram Singh',
    age: 63,
    gender: 'Male',
    village: 'Barmer, Rajasthan',
    scanDate: '2026-09-08',
    eye: 'Both (OU)',
    stageAQuality: 'Recapture Needed',
    stageBResult: 'Quality Gate Fail',
    confidence: 0.0,
    status: 'Recapture Required',
    notes: 'Corneal glare occlusion on left eye scan. Recapture requested by operator.'
  },
  {
    id: 'NS-2026-084',
    name: 'Meena Sharma',
    age: 52,
    gender: 'Female',
    village: 'Sehore, MP',
    scanDate: '2026-09-08',
    eye: 'Right (OD)',
    stageAQuality: 'Passed',
    stageBResult: 'Severe Non-proliferative DR',
    confidence: 91.5,
    status: 'Urgent Tele-Referral',
    notes: 'Cotton wool spots and venous bleeding observed. Referral initiated to District Eye Hospital.'
  }
];

export class PatientStore {
  static getPatients() {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(MOCK_INITIAL_PATIENTS));
      return MOCK_INITIAL_PATIENTS;
    }
    try {
      return JSON.parse(raw);
    } catch {
      return MOCK_INITIAL_PATIENTS;
    }
  }

  static addPatient(patientData) {
    const list = this.getPatients();
    const newRecord = {
      id: `NS-2026-${Math.floor(100 + Math.random() * 900)}`,
      scanDate: new Date().toISOString().split('T')[0],
      ...patientData
    };
    list.unshift(newRecord);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    return newRecord;
  }

  static searchPatients(query) {
    const list = this.getPatients();
    if (!query) return list;
    const q = query.toLowerCase();
    return list.filter(p => 
      p.name.toLowerCase().includes(q) || 
      p.id.toLowerCase().includes(q) || 
      p.village.toLowerCase().includes(q) ||
      p.stageBResult.toLowerCase().includes(q)
    );
  }
}
