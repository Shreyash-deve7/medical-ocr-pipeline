import { useState, useRef, useCallback } from "react";
import * as api from "../api";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Props {
  onBack: () => void;
  notify: (msg: string, type?: "success" | "error") => void;
}

type Tab =
  | "upload"
  | "pipeline"
  | "results"
  | "templates"
  | "export";

interface MockFile {
  name: string;
  size: string;
  progress: number;
  status: "uploading" | "done" | "queued";
}

interface OCREngine {
  id: string;
  name: string;
  accuracy: number;
  languages: string[];
  capabilities: string[];
}

interface PipelineStep {
  id: string;
  label: string;
  group: "pre" | "ocr" | "post";
  enabled: boolean;
}

interface Template {
  id: string;
  name: string;
  category: string;
  fields: string[];
}

interface WordResult {
  text: string;
  confidence: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

/* ------------------------------------------------------------------ */
/*  Static data                                                        */
/* ------------------------------------------------------------------ */

const TABS: { key: Tab; label: string }[] = [
  { key: "upload", label: "Upload" },
  { key: "pipeline", label: "Pipeline" },
  { key: "results", label: "Results" },
  { key: "templates", label: "Templates" },
  { key: "export", label: "Export" },
];

const FORMATS = ["PDF", "JPEG", "PNG", "TIFF", "DICOM"];

const MOCK_FILES: MockFile[] = [
  { name: "lab_report_2026.pdf", size: "2.4 MB", progress: 100, status: "done" },
  { name: "prescription_scan.png", size: "1.1 MB", progress: 62, status: "uploading" },
  { name: "discharge_summary.tiff", size: "4.8 MB", progress: 0, status: "queued" },
];

const ENGINES: OCREngine[] = [
  { id: "paddleocr", name: "PaddleOCR", accuracy: 91, languages: ["en", "zh", "ja", "ko", "de", "fr"], capabilities: ["Table recognition", "Layout analysis", "Lightweight", "Printed (GPU)"] },
  { id: "qwen_vl", name: "Qwen2.5-VL", accuracy: 93, languages: ["Multimodal"], capabilities: ["Handwritten", "Vision-Language", "GPU"] },
  { id: "pipeline", name: "MedVault Dual Pipeline", accuracy: 0, languages: ["Auto"], capabilities: ["Printed→PaddleOCR", "Handwritten→Qwen-VL", "Document classifier"] },
];

const INITIAL_PIPELINE: PipelineStep[] = [
  { id: "deskew", label: "Deskew", group: "pre", enabled: true },
  { id: "denoise", label: "Denoise", group: "pre", enabled: true },
  { id: "binarize", label: "Binarize", group: "pre", enabled: false },
  { id: "contrast", label: "Contrast", group: "pre", enabled: false },
  { id: "ocr", label: "OCR Engine", group: "ocr", enabled: true },
  { id: "spell", label: "Spell Check", group: "post", enabled: true },
  { id: "entity", label: "Entity Extraction", group: "post", enabled: false },
  { id: "table", label: "Table Detection", group: "post", enabled: true },
  { id: "layout", label: "Layout Analysis", group: "post", enabled: false },
];

const TEMPLATES: Template[] = [
  { id: "lab", name: "Lab Report", category: "Diagnostics", fields: ["Patient Name", "MRN", "Test Name", "Result", "Reference Range", "Units", "Flag"] },
  { id: "rx", name: "Prescription", category: "Pharmacy", fields: ["Patient", "Provider", "Drug", "Dosage", "Frequency", "Refills", "Date"] },
  { id: "discharge", name: "Discharge Summary", category: "Inpatient", fields: ["Admission Date", "Discharge Date", "Diagnosis", "Procedures", "Medications", "Follow-up"] },
  { id: "insurance", name: "Insurance Claim", category: "Billing", fields: ["Claim ID", "CPT Code", "ICD-10", "Billed Amount", "Allowed", "Provider NPI"] },
  { id: "pathology", name: "Pathology Report", category: "Diagnostics", fields: ["Specimen", "Gross Description", "Microscopic", "Diagnosis", "Stage", "Margins"] },
];

const MOCK_WORDS: WordResult[] = [
  { text: "Patient:", confidence: 97, x: 30, y: 40, w: 80, h: 18 },
  { text: "John", confidence: 94, x: 115, y: 40, w: 45, h: 18 },
  { text: "Doe", confidence: 92, x: 165, y: 40, w: 35, h: 18 },
  { text: "DOB:", confidence: 96, x: 30, y: 70, w: 45, h: 18 },
  { text: "03/15/1985", confidence: 88, x: 80, y: 70, w: 100, h: 18 },
  { text: "Hemoglobin", confidence: 78, x: 30, y: 110, w: 105, h: 18 },
  { text: "14.2", confidence: 85, x: 200, y: 110, w: 40, h: 18 },
  { text: "g/dL", confidence: 91, x: 245, y: 110, w: 40, h: 18 },
  { text: "WBC", confidence: 65, x: 30, y: 140, w: 40, h: 18 },
  { text: "7.5", confidence: 72, x: 200, y: 140, w: 30, h: 18 },
  { text: "x10^3/uL", confidence: 60, x: 235, y: 140, w: 80, h: 18 },
];

/* ------------------------------------------------------------------ */
/*  Inline SVG icons                                                   */
/* ------------------------------------------------------------------ */

const Icon = {
  upload: (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  ),
  engine: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  back: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
    </svg>
  ),
  check: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  doc: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  ),
  download: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  ),
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function confidenceColor(c: number): string {
  if (c >= 90) return "#22c55e";
  if (c >= 70) return "#eab308";
  return "#ef4444";
}

function accuracyBadge(a: number) {
  if (a === 0) return { label: "N/A", color: "#94a3b8" };
  if (a >= 93) return { label: `${a}%`, color: "#22c55e" };
  if (a >= 85) return { label: `${a}%`, color: "#eab308" };
  return { label: `${a}%`, color: "#ef4444" };
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function OCRWorkbench({ onBack, notify }: Props) {
  const [tab, setTab] = useState<Tab>("upload");
  const [pipeline, setPipeline] = useState<PipelineStep[]>(INITIAL_PIPELINE);
  const [activeTemplate, setActiveTemplate] = useState<string | null>(null);

  const toggleStep = (id: string) => {
    setPipeline((prev) =>
      prev.map((s) => (s.id === id ? { ...s, enabled: !s.enabled } : s))
    );
  };

  /* ---- Tab renderers ---- */

  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleRealUpload = async (file: File, docType: string) => {
    setUploading(true);
    setPendingFile(null);
    try {
      const res = await api.testUploadReport(file, docType);
      notify(`Uploaded ${file.name} as ${docType.toUpperCase()} (ID: ${res.report_id.slice(0, 8)})`, "success");
    } catch (e: any) {
      notify(e.message || "Upload failed", "error");
    } finally {
      setUploading(false);
    }
  };

  const renderUpload = () => (
    <div>
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.webp"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) setPendingFile(f);
          e.target.value = "";
        }}
      />

      {uploading ? (
        <div className="neu" style={{ padding: 40, textAlign: "center", marginBottom: 20 }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>⏳</div>
          <h4 style={{ margin: 0 }}>Uploading to Medical AI Pipeline…</h4>
          <p style={{ fontSize: 13, opacity: 0.7, marginTop: 4 }}>Processing document and queueing OCR extraction</p>
        </div>
      ) : pendingFile ? (
        <div className="neu" style={{ padding: 40, cursor: "default", borderStyle: "dashed", borderWidth: 2, marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={{ fontWeight: 600 }}>📄 {pendingFile.name}</div>
            <button className="neu-btn sm" onClick={(e) => { e.stopPropagation(); setPendingFile(null); }}>✕ Cancel</button>
          </div>
          <h4 style={{ textAlign: "center" }}>What type of document is this?</h4>
          <p style={{ textAlign: "center", marginBottom: 20 }}>Select the format to route it to the best AI model.</p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <button className="neu-btn" style={{ padding: "12px 24px" }} onClick={(e) => { e.stopPropagation(); handleRealUpload(pendingFile, "printed"); }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>🖨️</div>
              <div style={{ fontWeight: 600 }}>Printed</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>Typed text (PaddleOCR)</div>
            </button>
            <button className="neu-btn" style={{ padding: "12px 24px" }} onClick={(e) => { e.stopPropagation(); handleRealUpload(pendingFile, "tabular"); }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>📊</div>
              <div style={{ fontWeight: 600 }}>Tabular</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>Tables / lab panels (PaddleOCR)</div>
            </button>
            <button className="neu-btn" style={{ padding: "12px 24px" }} onClick={(e) => { e.stopPropagation(); handleRealUpload(pendingFile, "handwritten"); }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>✍️</div>
              <div style={{ fontWeight: 600 }}>Handwritten</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>Doctor notes (Qwen2.5-VL)</div>
            </button>
          </div>
        </div>
      ) : (
        <div
          className={`neu${dragging ? " dragging" : ""}`}
          style={{ padding: 40, textAlign: "center", cursor: "pointer", borderStyle: "dashed", borderWidth: 2, marginBottom: 20 }}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files[0];
            if (f) setPendingFile(f);
          }}
        >
          {Icon.upload}
          <p style={{ margin: "12px 0 4px", fontWeight: 600 }}>Click to upload documents</p>
          <p style={{ fontSize: 13, opacity: 0.6 }}>Drag and drop or click to browse</p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 12, flexWrap: "wrap" }}>
            {FORMATS.map((f) => (
              <span key={f} style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, background: "var(--neu-bg, #e8e8e8)" }}>{f}</span>
            ))}
          </div>
        </div>
      )}

      <h4 className="section-header">Batch Queue</h4>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {MOCK_FILES.map((f) => (
          <div key={f.name} className="neu" style={{ padding: 14, display: "flex", alignItems: "center", gap: 12 }}>
            {Icon.doc}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 500, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</div>
              <div style={{ fontSize: 12, opacity: 0.6 }}>{f.size} &mdash; {f.status}</div>
              <div style={{ height: 6, borderRadius: 3, background: "var(--neu-bg, #ddd)", marginTop: 6 }}>
                <div style={{ height: "100%", borderRadius: 3, width: `${f.progress}%`, background: f.status === "done" ? "#22c55e" : "#3b82f6", transition: "width .3s" }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderEngines = () => (
    <div>
      <div className="neu" style={{ padding: 20, textAlign: "center", marginBottom: 16 }}>
        <h4 className="section-header" style={{ marginTop: 0 }}>MedVault OCR Pipeline</h4>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 16, flexWrap: "wrap", marginTop: 16 }}>
          <div className="neu" style={{ padding: "12px 20px", borderRadius: 8, background: "#dbeafe" }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>User Selection</div>
            <div style={{ fontSize: 11, opacity: 0.6 }}>Routing Decision</div>
          </div>
          <span style={{ fontSize: 20, opacity: 0.4 }}>→</span>
          <div className="neu" style={{ padding: "12px 20px", borderRadius: 8, borderLeft: "4px solid #22c55e" }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Printed → PaddleOCR</div>
            <div style={{ fontSize: 11, opacity: 0.6 }}>GPU · Table/ Layout aware</div>
          </div>
          <span style={{ fontSize: 14, opacity: 0.3 }}>OR</span>
          <div className="neu" style={{ padding: "12px 20px", borderRadius: 8, borderLeft: "4px solid #a78bfa" }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Handwritten → Qwen2.5-VL</div>
            <div style={{ fontSize: 11, opacity: 0.6 }}>3B · 4-bit GPU · Vision-Language</div>
          </div>
        </div>
        <div style={{ fontSize: 12, opacity: 0.5, marginTop: 16 }}>
          Explicit user selection at upload · Routing documents to the optimal backend
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 }}>
        {ENGINES.map((e) => {
          const badge = accuracyBadge(e.accuracy);
          return (
            <div key={e.id} className="neu" style={{ padding: 16, borderRadius: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontWeight: 600 }}>{Icon.engine} {e.name}</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: badge.color, padding: "2px 8px", borderRadius: 6, background: `${badge.color}22` }}>{badge.label}</span>
              </div>
              <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 6 }}>Languages: {e.languages.join(", ")}</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {e.capabilities.map((c) => (
                  <span key={c} style={{ fontSize: 11, padding: "2px 7px", borderRadius: 4, background: "var(--neu-bg, #e8e8e8)" }}>{c}</span>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  const renderPipeline = () => {
    const groups: { key: PipelineStep["group"]; label: string }[] = [
      { key: "pre", label: "Pre-processing" },
      { key: "ocr", label: "OCR Engine" },
      { key: "post", label: "Post-processing" },
    ];
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {groups.map((g) => (
          <div key={g.key}>
            <h4 className="section-header">{g.label}</h4>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {pipeline.filter((s) => s.group === g.key).map((s) => (
                <div
                  key={s.id}
                  className="neu"
                  style={{ padding: "10px 16px", cursor: s.id === "ocr" ? "default" : "pointer", opacity: s.enabled ? 1 : 0.45, minWidth: 120, textAlign: "center" }}
                  onClick={() => toggleStep(s.id)}
                >
                  <div style={{ fontWeight: 500, fontSize: 14 }}>{s.label}</div>
                  <div style={{ fontSize: 11, marginTop: 4, color: s.enabled ? "#22c55e" : "#94a3b8" }}>{s.enabled ? "Enabled" : "Disabled"}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
        <button className="neu-btn" style={{ alignSelf: "flex-start" }} onClick={() => notify("Pipeline saved", "success")}>
          Save Pipeline
        </button>
      </div>
    );
  };

  const renderResults = () => (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      {/* Document side */}
      <div className="neu" style={{ padding: 12, position: "relative", minHeight: 280 }}>
        <h4 className="section-header" style={{ marginTop: 0 }}>Original Document</h4>
        <svg viewBox="0 0 320 220" style={{ width: "100%", background: "#f8f8f8", borderRadius: 6 }}>
          <rect width="320" height="220" fill="#f1f5f9" />
          <text x="160" y="20" textAnchor="middle" fontSize="11" fill="#64748b">Lab Report — Mock Preview</text>
          {MOCK_WORDS.map((w, i) => (
            <g key={i}>
              <rect x={w.x} y={w.y} width={w.w} height={w.h} fill="none" stroke={confidenceColor(w.confidence)} strokeWidth="1.5" rx="2" opacity="0.7" />
              <text x={w.x + 2} y={w.y + 13} fontSize="11" fill="#1e293b">{w.text}</text>
            </g>
          ))}
        </svg>
      </div>

      {/* Extracted text side */}
      <div className="neu" style={{ padding: 12 }}>
        <h4 className="section-header" style={{ marginTop: 0 }}>Extracted Text</h4>
        <div style={{ fontFamily: "monospace", fontSize: 13, lineHeight: 1.8 }}>
          {MOCK_WORDS.map((w, i) => (
            <span key={i} style={{ background: `${confidenceColor(w.confidence)}22`, color: confidenceColor(w.confidence), padding: "1px 4px", borderRadius: 3, marginRight: 4 }} title={`${w.confidence}%`}>
              {w.text}
            </span>
          ))}
        </div>
        <div style={{ marginTop: 16, display: "flex", gap: 12, fontSize: 12 }}>
          <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#22c55e", marginRight: 4 }} />&ge;90%</span>
          <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#eab308", marginRight: 4 }} />70-90%</span>
          <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#ef4444", marginRight: 4 }} />&lt;70%</span>
        </div>
      </div>
    </div>
  );



  const renderTemplates = () => (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
      {TEMPLATES.map((t) => {
        const active = activeTemplate === t.id;
        return (
          <div
            key={t.id}
            className="neu"
            style={{ padding: 16, cursor: "pointer", outline: active ? "2px solid #3b82f6" : "none", borderRadius: 10 }}
            onClick={() => { setActiveTemplate(active ? null : t.id); notify(active ? "Template deselected" : `Template "${t.name}" selected`, "success"); }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontWeight: 600 }}>{t.name}</span>
              <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, background: "var(--neu-bg, #e8e8e8)" }}>{t.category}</span>
            </div>
            <div style={{ fontSize: 12, marginTop: 10, opacity: 0.7 }}>Fields:</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
              {t.fields.map((f) => (
                <span key={f} style={{ fontSize: 11, padding: "2px 7px", borderRadius: 4, background: active ? "#3b82f622" : "var(--neu-bg, #e8e8e8)" }}>{f}</span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );

  const renderExport = () => {
    const formats = [
      { id: "json", label: "JSON", desc: "Structured extraction with confidence scores" },
      { id: "csv", label: "CSV", desc: "Tabular data, one row per recognized field" },
      { id: "fhir", label: "FHIR R4", desc: "HL7 FHIR DiagnosticReport / DocumentReference" },
      { id: "txt", label: "Plain Text", desc: "Raw extracted text without metadata" },
    ];
    return (
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 14 }}>
        {formats.map((f) => (
          <div key={f.id} className="neu" style={{ padding: 18, textAlign: "center" }}>
            {Icon.download}
            <div style={{ fontWeight: 600, marginTop: 8 }}>{f.label}</div>
            <div style={{ fontSize: 12, opacity: 0.6, marginTop: 4, marginBottom: 12 }}>{f.desc}</div>
            <button className="neu-btn" onClick={() => notify(`Exported as ${f.label} (mock)`, "success")}>Export</button>
          </div>
        ))}
      </div>
    );
  };

  const RENDERERS: Record<Tab, () => JSX.Element> = {
    upload: renderUpload,
    pipeline: renderPipeline,
    results: renderResults,
    templates: renderTemplates,
    export: renderExport,
  };

  /* ---- Main render ---- */

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: 20 }}>
      {/* Breadcrumb */}
      <div className="breadcrumb" style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16, fontSize: 13 }}>
        <span style={{ cursor: "pointer", opacity: 0.6 }} onClick={onBack}>{Icon.back}</span>
        <span style={{ opacity: 0.4 }}>/</span>
        <span style={{ opacity: 0.6, cursor: "pointer" }} onClick={onBack}>Home</span>
        <span style={{ opacity: 0.4 }}>/</span>
        <span style={{ fontWeight: 600 }}>OCR Workbench</span>
      </div>

      <h2 style={{ marginBottom: 4 }}>OCR Workbench</h2>
      <p style={{ fontSize: 14, opacity: 0.6, marginBottom: 20 }}>Upload, process, and compare OCR results across engines</p>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 20 }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`chart-tab${tab === t.key ? " active" : ""}`}
            style={{
              padding: "6px 14px",
              borderRadius: 6,
              border: "none",
              cursor: "pointer",
              fontWeight: tab === t.key ? 600 : 400,
              background: tab === t.key ? "#3b82f6" : "var(--neu-bg, #e8e8e8)",
              color: tab === t.key ? "#fff" : "inherit",
            }}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Active tab content */}
      {RENDERERS[tab]()}
    </div>
  );
}
