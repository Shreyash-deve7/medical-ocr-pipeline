const BASE = "/api";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

const jsonPost = (path: string, data: any) =>
  request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const jsonPut = (path: string, data: any) =>
  request(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
const del = (path: string) => request(path, { method: "DELETE" });

// ── Patient Auth ────────────────────────────────────────────
export const register = (phone: string, password: string, name: string) =>
  jsonPost("/patient/register", { phone, password, name }) as Promise<{ token: string; patient_id: string }>;
export const login = (phone: string, password: string) =>
  jsonPost("/patient/login", { phone, password }) as Promise<{ token: string; patient_id: string }>;
export const uploadReport = (token: string, file: File) => {
  const fd = new FormData();
  fd.append("token", token);
  fd.append("file", file);
  return request<{ report_id: string; filename: string }>("/patient/upload", { method: "POST", body: fd });
};
export const patientReports = (token: string) =>
  request<any[]>(`/patient/reports?token=${token}`);
export const getPatientProfile = (token: string) =>
  request<any>(`/patient/profile?token=${token}`);
export const updatePatientProfile = (token: string, data: any) =>
  jsonPut(`/patient/profile?token=${token}`, data);

// ── No-auth test endpoints (test-only version, no login required) ───────────
// These hit /api/test/* which operate on a seeded default patient on the backend.
export const testUploadReport = (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return request<{ report_id: string; filename: string }>("/test/upload", { method: "POST", body: fd });
};
export const testReports = () => request<any[]>("/test/reports");

// ── GPU status & preload (no auth) ───────────────────────────
export interface GpuStatus {
  cuda_available: boolean;
  cuda_device_name: string;
  torch_version: string;
  preload_started: boolean;
  preload_done: boolean;
  preload_error: string | null;
  classifier_loaded: boolean;
  classifier_error: string | null;
  paddle_loaded: boolean;
  paddle_using_gpu: boolean;
  paddle_error: string | null;
  qwen_loaded: boolean;
  qwen_error: string | null;
}
export const gpuStatus = () => request<GpuStatus>("/gpu/status");
export const gpuPreload = () =>
  request<{ status: string; message: string }>("/gpu/preload", { method: "POST" });

// ── Doctor Auth ─────────────────────────────────────────────
export const doctorRegister = (data: any) => jsonPost("/doctor/register", data) as Promise<{ token: string; doctor_id: string }>;
export const doctorLogin = (phone: string, password: string) =>
  jsonPost("/doctor/login", { phone, password }) as Promise<{ token: string; doctor_id: string }>;

// ── Doctor Endpoints ────────────────────────────────────────
export const listPatients = () => request<any[]>("/doctor/patients");
export const getPatientDetail = (id: string) => request<any>(`/doctor/patient/${id}`);
export const patientReportList = (id: string) => request<any[]>(`/doctor/patient/${id}/reports`);
export const fileUrl = (id: string) => `${BASE}/file/${id}`;

// ── Analysis ────────────────────────────────────────────────
export const analyzeReport = (reportId: string, opts: { apiKey?: string; aiProviderId?: string } = {}) =>
  jsonPost("/doctor/analyze", { report_id: reportId, api_key: opts.apiKey || "", ai_provider_id: opts.aiProviderId || "" }) as Promise<{ analysis: string; ocr_text: string; doc_type: string; structured_results: any[]; ocr_engine: string; report_id: string; status: string }>;

// ── Pipeline (Session 8 endpoint) ───────────────────────────
export const runPipeline = async (
  fileBlob: Blob,
  filename: string,
  opts: { summary?: boolean; evaluate?: boolean } = {}
) => {
  const fd = new FormData();
  fd.append("file", fileBlob, filename);
  if (opts.summary) fd.append("summary", "true");
  if (opts.evaluate) fd.append("evaluate", "true");
  return request<PipelineResult>("/pipeline/run", { method: "POST", body: fd });
};

export interface PipelineResult {
  preprocessing: { transformations_applied: string[]; quality_metrics_before: any; quality_metrics_after?: any } | null;
  classification: { class: string; confidence: number; fallback_triggered: boolean } | null;
  ocr: { raw_output: any; engine: string; confidence: number; processing_time_seconds: number } | null;
  lab_report: { lab_results: LabResult[] } | null;
  diagnosis: {
    clinical_patterns: any[];
    abnormal_values: any[];
    urgent_flags: string[];
    suggested_followup: string[];
    summary_for_doctor: string;
    llm_narrative?: string | null;
  } | null;
  summary: { summary: string; flags: any[]; critical_alerts: string[]; discussion_points: string[] } | null;
  evaluation: any | null;
  metadata: {
    use_graph: boolean;
    evaluate: boolean;
    summary: boolean;
    duration_ms: number;
    started_at: string;
    completed_at: string;
    errors?: Record<string, string>;
  };
}

export interface LabResult {
  test_name: string;
  test_abbreviation?: string | null;
  value: number | null;
  unit: string;
  flag: "HIGH" | "LOW" | "CRITICAL_HIGH" | "CRITICAL_LOW" | "NORMAL" | "UNKNOWN";
  reference_range: { low: number | null; high: number | null; unit: string } | null;
  clinical_significance: string | null;
}

// ── Medical Records ─────────────────────────────────────────
export const listAllergies = (pid: string) => request<any[]>(`/patient/${pid}/allergies`);
export const addAllergy = (pid: string, data: any) => jsonPost(`/patient/${pid}/allergies`, data);
export const deleteAllergy = (id: string) => del(`/allergies/${id}`);

export const listConditions = (pid: string) => request<any[]>(`/patient/${pid}/conditions`);
export const addCondition = (pid: string, data: any) => jsonPost(`/patient/${pid}/conditions`, data);
export const deleteCondition = (id: string) => del(`/conditions/${id}`);

export const listMedications = (pid: string) => request<any[]>(`/patient/${pid}/medications`);
export const addMedication = (pid: string, data: any) => jsonPost(`/patient/${pid}/medications`, data);
export const deleteMedication = (id: string) => del(`/medications/${id}`);

// ── Vitals ──────────────────────────────────────────────────
export const listVitals = (pid: string, limit = 50) => request<any[]>(`/patient/${pid}/vitals?limit=${limit}`);
export const recordVital = (data: any) => jsonPost("/vitals", data);

// ── Prescriptions ───────────────────────────────────────────
export const listPrescriptions = (pid: string) => request<any[]>(`/patient/${pid}/prescriptions`);
export const createPrescription = (data: any) => jsonPost("/prescriptions", data);

// ── Clinical Notes ──────────────────────────────────────────
export const listClinicalNotes = (pid: string) => request<any[]>(`/patient/${pid}/notes`);
export const createClinicalNote = (data: any) => jsonPost("/notes", data);

// ── Appointments ────────────────────────────────────────────
export const listAppointments = (params?: { patient_id?: string; status?: string }) => {
  const qs = new URLSearchParams();
  if (params?.patient_id) qs.set("patient_id", params.patient_id);
  if (params?.status) qs.set("status", params.status);
  return request<any[]>(`/appointments?${qs}`);
};
export const createAppointment = (data: any) => jsonPost("/appointments", data);
export const updateAppointment = (id: string, data: any) => jsonPut(`/appointments/${id}`, data);

// ── Lab Results ─────────────────────────────────────────────
export const listLabResults = (pid: string) => request<any[]>(`/patient/${pid}/labs`);
export const addLabResult = (data: any) => jsonPost("/labs", data);

// ── Analytics ───────────────────────────────────────────────
export const getAnalytics = () => request<any>("/analytics");

// ── Messages ───────────────────────────────────────────────
export const listMessages = (userType: string, userId: string) =>
  request<any[]>(`/messages?user_type=${userType}&user_id=${userId}`);
export const sendMessage = (data: any, senderType = "doctor", senderId = "") =>
  jsonPost(`/messages?sender_type=${senderType}&sender_id=${senderId}`, data);
export const markMessageRead = (id: string) => jsonPut(`/messages/${id}/read`, {});

// ── Notifications ──────────────────────────────────────────
export const listNotifications = (userType: string, userId: string, unreadOnly = false) =>
  request<any[]>(`/notifications?user_type=${userType}&user_id=${userId}&unread_only=${unreadOnly}`);
export const markNotificationRead = (id: string) => jsonPut(`/notifications/${id}/read`, {});
export const markAllNotificationsRead = (userType: string, userId: string) =>
  jsonPut(`/notifications/read-all?user_type=${userType}&user_id=${userId}`, {});

// ── Drug Interactions ──────────────────────────────────────
export const listDrugInteractions = () => request<any[]>("/drug-interactions");
export const checkDrugInteractions = (drugs: string[]) =>
  request<{ interactions: any[]; checked: string[] }>(`/drug-interactions/check?drugs=${drugs.join(",")}`);

// ── ICD-10 ─────────────────────────────────────────────────
export const searchICD10 = (q = "") => request<any[]>(`/icd10?q=${encodeURIComponent(q)}`);
export const listDiagnoses = (pid: string) => request<any[]>(`/patient/${pid}/diagnoses`);
export const addDiagnosis = (pid: string, data: any) => jsonPost(`/patient/${pid}/diagnoses`, data);
export const deleteDiagnosis = (id: string) => del(`/diagnoses/${id}`);

// ── Referrals ──────────────────────────────────────────────
export const listReferrals = (pid: string) => request<any[]>(`/patient/${pid}/referrals`);
export const createReferral = (data: any) => jsonPost("/referrals", data);
export const updateReferralStatus = (id: string, status: string) =>
  jsonPut(`/referrals/${id}/status?status=${status}`, {});

// ── Templates ──────────────────────────────────────────────
export const listTemplates = (type?: string) => request<any[]>(`/templates${type ? `?template_type=${type}` : ""}`);
export const createTemplate = (data: any) => jsonPost("/templates", data);
export const deleteTemplate = (id: string) => del(`/templates/${id}`);

// ── Invoices / Billing ─────────────────────────────────────
export const listInvoices = (pid: string) => request<any[]>(`/patient/${pid}/invoices`);
export const createInvoice = (data: any) => jsonPost("/invoices", data);
export const updateInvoiceStatus = (id: string, status: string) =>
  jsonPut(`/invoices/${id}/status?status=${status}`, {});

// ── Insurance ──────────────────────────────────────────────
export const listInsurance = (pid: string) => request<any[]>(`/patient/${pid}/insurance`);
export const addInsurance = (pid: string, data: any) => jsonPost(`/patient/${pid}/insurance`, data);
export const deleteInsurance = (id: string) => del(`/insurance/${id}`);

// ── Doctor Profile ─────────────────────────────────────────
export const getDoctorProfile = (id: string) => request<any>(`/doctor/profile?doctor_id=${id}`);
export const updateDoctorProfile = (id: string, data: any) => jsonPut(`/doctor/profile?doctor_id=${id}`, data);

// ── Audit Log ──────────────────────────────────────────────
export const getAuditLog = (limit = 100) => request<any[]>(`/audit-log?limit=${limit}`);

// ── Export ──────────────────────────────────────────────────
export const exportPatientData = (pid: string) => request<any>(`/patient/${pid}/export`);
export const exportFHIR = (pid: string) => request<any>(`/patient/${pid}/fhir`);

// ── Providers ───────────────────────────────────────────────
export interface ProviderField { key: string; label: string; placeholder: string; required: boolean; secret?: boolean; }
export interface EngineInfo { id: string; name: string; fields: ProviderField[]; }
export interface Provider { id: string; kind: string; name: string; engine: string; config: Record<string, string>; is_default: number; created_at: string; }

export const listProviders = () => request<Provider[]>("/providers");
export const listEngines = () => request<{ ocr: EngineInfo[]; ai: EngineInfo[] }>("/providers/engines");
export const createProvider = (data: any) => jsonPost("/providers", data);
export const updateProvider = (id: string, data: any) => jsonPut(`/providers/${id}`, data);
export const deleteProvider = (id: string) => del(`/providers/${id}`);
