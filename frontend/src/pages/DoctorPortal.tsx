import { useState, useEffect, useMemo } from "react";
import * as api from "../api";

interface Props {
  onBack: () => void;
  notify: (msg: string, type?: "success" | "error") => void;
  onOpenChart?: (patientId: string) => void;
}

const PIPELINE_STAGES = ["Preprocess", "Classify", "OCR", "Extract + Diagnose"];

const flagClass = (flag?: string) =>
  ({
    CRITICAL_HIGH: "flag-critical-high",
    CRITICAL_LOW: "flag-critical-low",
    HIGH: "flag-high",
    LOW: "flag-low",
    NORMAL: "flag-normal",
    UNKNOWN: "flag-unknown",
  }[flag || "UNKNOWN"] || "flag-unknown");

const classClass = (cls?: string) =>
  ({
    TABLE: "cls-table",
    HANDWRITTEN: "cls-handwritten",
    PRINTED_TEXT: "cls-printed",
  }[cls || ""] || "cls-unknown");

export function DoctorPortal({ onBack, notify, onOpenChart }: Props) {
  const [patients, setPatients] = useState<any[]>([]);
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [selectedPatient, setSelectedPatient] = useState<any>(null);
  const [reports, setReports] = useState<any[]>([]);
  const [loadingReports, setLoadingReports] = useState(false);
  const [runningPipelineFor, setRunningPipelineFor] = useState<string | null>(null);
  const [expandedReport, setExpandedReport] = useState<string | null>(null);
  const [previewReport, setPreviewReport] = useState<string | null>(null);
  const [pipelineResult, setPipelineResult] = useState<api.PipelineResult | null>(null);
  const [pipelineReportId, setPipelineReportId] = useState<string | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.listPatients()
      .then(setPatients)
      .catch(() => {})
      .finally(() => setLoadingPatients(false));
  }, []);

  const selectPatient = async (p: any) => {
    setSelectedPatient(p);
    setExpandedReport(null);
    setPreviewReport(null);
    setPipelineResult(null);
    setPipelineReportId(null);
    setPipelineError(null);
    setLoadingReports(true);
    try {
      setReports(await api.patientReportList(p.id));
    } catch (e: any) {
      notify(e.message, "error");
    } finally {
      setLoadingReports(false);
    }
  };

  const handleRunPipeline = async (reportId: string, filename: string) => {
    setRunningPipelineFor(reportId);
    setPipelineError(null);
    setPipelineResult(null);
    setPipelineReportId(reportId);
    setExpandedReport(reportId);
    try {
      const blob = await (await fetch(api.fileUrl(reportId))).blob();
      const result = await api.runPipeline(blob, filename, { summary: true });
      setPipelineResult(result);
      setReports(prev =>
        prev.map(r => (r.id === reportId ? { ...r, analyzed: 1 } : r))
      );
      notify("Pipeline complete!");
    } catch (e: any) {
      setPipelineError(e.message || "Pipeline failed");
      notify(e.message || "Pipeline failed", "error");
    } finally {
      setRunningPipelineFor(null);
    }
  };

  const filtered = useMemo(() => {
    if (!search.trim()) return patients;
    const q = search.toLowerCase();
    return patients.filter(p =>
      (p.name || "").toLowerCase().includes(q) ||
      p.phone.includes(q)
    );
  }, [patients, search]);

  const totalReports = patients.reduce((s, p) => s + p.report_count, 0);
  const COLORS = ["#4f6ef7", "#a78bfa", "#10b981", "#f59e0b", "#ef4444", "#ec4899"];
  const avatarColor = (name: string) => COLORS[Math.abs([...name].reduce((a, c) => a + c.charCodeAt(0), 0)) % COLORS.length];
  const initials = (name: string) => name ? name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase() : "?";

  // ── Patient detail view ──────────────────────────────
  if (selectedPatient) {
    const analyzed = reports.filter(r => r.analyzed).length;
    return (
      <div className="page-enter">
        <div className="breadcrumb">
          <button onClick={onBack}>Home</button>
          <span className="sep">/</span>
          <button onClick={() => setSelectedPatient(null)}>Patients</button>
          <span className="sep">/</span>
          <span>{selectedPatient.name || selectedPatient.phone}</span>
        </div>

        <div className="section-header">
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div className="patient-avatar" style={{ background: avatarColor(selectedPatient.name || selectedPatient.phone), width: 48, height: 48, fontSize: 18 }}>
              {initials(selectedPatient.name || selectedPatient.phone)}
            </div>
            <div>
              <h1>{selectedPatient.name || "Unnamed Patient"}</h1>
              <div className="subtitle">📞 {selectedPatient.phone}</div>
            </div>
            {onOpenChart && (
              <button className="neu-btn sm primary" onClick={() => onOpenChart(selectedPatient.id)} style={{ marginLeft: "auto" }}>
                Full Patient Chart →
              </button>
            )}
          </div>
        </div>

        {reports.length > 0 && (
          <div className="stat-row">
            <div className="stat-card neu">
              <div className="stat-icon blue">📄</div>
              <div className="stat-value">{reports.length}</div>
              <div className="stat-label">Reports</div>
            </div>
            <div className="stat-card neu">
              <div className="stat-icon green">✓</div>
              <div className="stat-value">{analyzed}</div>
              <div className="stat-label">Analyzed</div>
            </div>
            <div className="stat-card neu">
              <div className="stat-icon orange">⏳</div>
              <div className="stat-value">{reports.length - analyzed}</div>
              <div className="stat-label">Pending</div>
            </div>
          </div>
        )}

        {loadingReports ? (
          <div>
            {[1, 2, 3].map(i => <div key={i} className="skeleton skeleton-card" />)}
          </div>
        ) : reports.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <h4>No reports</h4>
            <p>This patient hasn't shared any reports yet.</p>
          </div>
        ) : (
          <div className="report-list">
            {reports.map(r => {
              const running = runningPipelineFor === r.id;
              const showResult = !running && pipelineReportId === r.id && pipelineResult;
              return (
                <div key={r.id}>
                  <div className="report-card neu">
                    <div className="file-thumb">
                      {r.filetype === "pdf" ? "📕" : "🖼️"}
                    </div>
                    <div className="report-body">
                      <div className="report-title">{r.filename}</div>
                      <div className="report-date">
                        Shared {new Date(r.shared_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                        {" at "}
                        {new Date(r.shared_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                      </div>
                      <div className="report-actions">
                        <a href={api.fileUrl(r.id)} target="_blank" rel="noopener">
                          <button className="neu-btn sm">Open File</button>
                        </a>
                        <button
                          className="neu-btn sm"
                          onClick={() => setPreviewReport(previewReport === r.id ? null : r.id)}
                        >
                          {previewReport === r.id ? "Hide Preview" : "Preview"}
                        </button>
                        <button
                          className="neu-btn sm primary"
                          disabled={running}
                          onClick={() => handleRunPipeline(r.id, r.filename)}
                        >
                          {running ? <><span className="spinner white" /> Running Pipeline…</> : "Run Pipeline"}
                        </button>
                        {!!r.analyzed && (
                          <button
                            className="neu-btn sm ghost"
                            onClick={() => setExpandedReport(expandedReport === r.id ? null : r.id)}
                          >
                            {expandedReport === r.id ? "Hide Analysis" : "View Analysis"}
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="report-right">
                      <span className={`tag ${r.filetype}`}>{r.filetype}</span>
                      {r.analyzed ? <span className="tag analyzed">Analyzed</span> : <span className="tag pending">Pending</span>}
                    </div>
                  </div>

                  {previewReport === r.id && (
                    <div className="file-preview">
                      {r.filetype === "image" ? (
                        <img src={api.fileUrl(r.id)} alt={r.filename} />
                      ) : (
                        <iframe src={api.fileUrl(r.id)} title={r.filename} />
                      )}
                    </div>
                  )}

                  {expandedReport === r.id && (
                    <div className="analysis-panel neu-inset">
                      {running && <PipelineStrip running />}
                      {pipelineError && !running && (
                        <div className="pipeline-error">⚠ {pipelineError}</div>
                      )}
                      {showResult && pipelineResult && (
                        <>
                          <PipelineStrip done />
                          <PipelineAccordion result={pipelineResult} />
                        </>
                      )}
                      {!running && !showResult && !pipelineError && (
                        <div className="pipeline-empty">Run the pipeline to see classification, OCR, extracted labs, and the AI diagnosis.</div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // ── Patient list view ────────────────────────────────
  return (
    <div className="page-enter">
      <div className="breadcrumb">
        <button onClick={onBack}>Home</button>
        <span className="sep">/</span>
        <span>Doctor Dashboard</span>
      </div>

      <div className="section-header">
        <div>
          <h1>Doctor Dashboard</h1>
          <div className="subtitle">All registered patients and their reports</div>
        </div>
      </div>

      <div className="stat-row">
        <div className="stat-card neu">
          <div className="stat-icon blue">👥</div>
          <div className="stat-value">{patients.length}</div>
          <div className="stat-label">Patients</div>
        </div>
        <div className="stat-card neu">
          <div className="stat-icon green">📄</div>
          <div className="stat-value">{totalReports}</div>
          <div className="stat-label">Total Reports</div>
        </div>
      </div>

      <div className="search-bar">
        <span className="search-icon">🔍</span>
        <input
          className="neu-input"
          placeholder="Search patients by name or phone..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ paddingLeft: 42 }}
        />
      </div>

      {loadingPatients ? (
        <div>
          {[1, 2, 3, 4].map(i => <div key={i} className="skeleton skeleton-card" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">👥</div>
          <h4>{search ? "No matches" : "No patients yet"}</h4>
          <p>{search ? "Try a different search term." : "Patients will appear here once they register."}</p>
        </div>
      ) : (
        <div className="patient-grid">
          {filtered.map(p => (
            <div key={p.id} className="patient-row neu" onClick={() => selectPatient(p)}>
              <div className="patient-avatar" style={{ background: avatarColor(p.name || p.phone) }}>
                {initials(p.name || p.phone)}
              </div>
              <div className="patient-info">
                <h4>{p.name || "Unnamed Patient"}</h4>
                <p>📞 {p.phone} · Joined {new Date(p.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</p>
              </div>
              <div className="patient-meta">
                <span className="report-badge">{p.report_count} report{p.report_count !== 1 ? "s" : ""}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PipelineStrip({ running, done }: { running?: boolean; done?: boolean }) {
  return (
    <div className={`pipeline-strip${running ? " running" : ""}${done ? " done" : ""}`}>
      {PIPELINE_STAGES.map((stage, i) => (
        <div className="pipeline-stage" key={stage} style={{ ["--i" as any]: i }}>
          <div className="stage-dot">{done || (!running && i < (done ? 4 : 0)) ? "✓" : i + 1}</div>
          <span className="stage-label">{stage}</span>
        </div>
      ))}
    </div>
  );
}

function PipelineAccordion({ result }: { result: api.PipelineResult }) {
  const cls = result.classification;
  const lab = result.lab_report?.lab_results || [];
  const dx = result.diagnosis;
  const pre = result.preprocessing;

  return (
    <div className="pipeline-accordion">
      {/* Panel 1 — Classification */}
      <details className="acc-panel" open>
        <summary><span className="acc-num">1</span> Classification Result</summary>
        <div className="acc-body">
          {cls ? (
            <>
              <div className="class-row">
                <span className={`class-chip ${classClass(cls.class)}`}>{cls.class || "UNKNOWN"}</span>
                <span className="confidence">
                  <span className="confidence-label">Confidence</span>
                  <span className="confidence-track">
                    <span className="confidence-fill" style={{ width: `${Math.round((cls.confidence || 0) * 100)}%` }} />
                  </span>
                  <span className="confidence-val">{Math.round((cls.confidence || 0) * 100)}%</span>
                </span>
              </div>
              {cls.fallback_triggered && <div className="fallback-note">⚠ Classifier fallback triggered</div>}
              <div className="badge-row">
                <span className="badge-label">Preprocessing transforms:</span>
                {(pre?.transformations_applied || []).map((t: string, i: number) => (
                  <span className="transform-badge" key={i}>{t}</span>
                ))}
                {(!pre?.transformations_applied || pre.transformations_applied.length === 0) && <span className="muted">none</span>}
              </div>
            </>
          ) : (
            <div className="muted">No classification result.</div>
          )}
        </div>
      </details>

      {/* Panel 2 — OCR Text */}
      <details className="acc-panel" open>
        <summary><span className="acc-num">2</span> OCR Text</summary>
        <div className="acc-body">
          {(() => {
            const ocr = result.ocr;
            if (!ocr || (!ocr.raw_output && ocr.raw_output !== 0)) {
              return <div className="muted">No OCR text was produced for this report.</div>;
            }
            const raw = ocr.raw_output;
            const isTable = Array.isArray(raw) && raw.length > 0 && Array.isArray(raw[0]);
            const ocrText = typeof raw === "string" ? raw : isTable ? null : JSON.stringify(raw, null, 2);
            return (
              <>
                <div className="badge-row" style={{ marginBottom: 10 }}>
                  <span className="transform-badge">Engine: {ocr.engine || "unknown"}</span>
                  {ocr.confidence != null && (
                    <span className="transform-badge">Confidence: {Math.round((ocr.confidence || 0) * 100)}%</span>
                  )}
                  {ocr.processing_time_seconds != null && (
                    <span className="transform-badge">{ocr.processing_time_seconds.toFixed(2)}s</span>
                  )}
                </div>
                {isTable ? (
                  <div className="lab-table-wrap">
                    <table className="lab-table">
                      <tbody>
                        {(raw as string[][]).map((row, ri) => (
                          <tr key={ri}>
                            {row.map((cell, ci) => (
                              <td key={ci}>{cell}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <pre className="ocr-text-output">{ocrText}</pre>
                )}
              </>
            );
          })()}
        </div>
      </details>

      {/* Panel 3 — Extracted Lab Results */}
      <details className="acc-panel" open>
        <summary><span className="acc-num">3</span> Extracted Lab Results</summary>
        <div className="acc-body">
          {lab.length > 0 ? (
            <div className="lab-table-wrap">
              <table className="lab-table">
                <thead>
                  <tr>
                    <th>Test Name</th>
                    <th>Value</th>
                    <th>Unit</th>
                    <th>Reference Range</th>
                    <th>Flag</th>
                  </tr>
                </thead>
                <tbody>
                  {lab.map((lr: api.LabResult, i: number) => (
                    <tr key={i}>
                      <td>{lr.test_name}{lr.test_abbreviation ? ` (${lr.test_abbreviation})` : ""}</td>
                      <td>{lr.value ?? "—"}</td>
                      <td>{lr.unit}</td>
                      <td>
                        {lr.reference_range
                          ? `${lr.reference_range.low ?? "?"} – ${lr.reference_range.high ?? "?"} ${lr.reference_range.unit || ""}`
                          : "—"}
                      </td>
                      <td><span className={`flag-chip ${flagClass(lr.flag)}`}>{lr.flag}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="muted">No lab results were extracted from this report.</div>
          )}
        </div>
      </details>

      {/* Panel 4 — AI Diagnosis */}
      <details className="acc-panel" open>
        <summary><span className="acc-num">4</span> AI Diagnosis Summary</summary>
        <div className="acc-body">
          {dx ? (
            <>
              <p className="dx-summary">{dx.summary_for_doctor}</p>
              {dx.clinical_patterns?.length > 0 && (
                <div className="badge-row">
                  <span className="badge-label">Clinical patterns:</span>
                  {dx.clinical_patterns.map((p: any, i: number) => (
                    <span className="pattern-badge" key={i}>{p.pattern || p}</span>
                  ))}
                </div>
              )}
              {dx.urgent_flags?.length > 0 && (
                <div className="urgent-row">
                  {dx.urgent_flags.map((f: string, i: number) => (
                    <span className="urgent-chip" key={i}>🚨 {f}</span>
                  ))}
                </div>
              )}
              {dx.suggested_followup?.length > 0 && (
                <div className="followup">
                  <div className="badge-label">Suggested follow-up:</div>
                  <ul>
                    {dx.suggested_followup.map((f: string, i: number) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
              )}
              {(!dx.summary_for_doctor && !dx.clinical_patterns?.length && !dx.urgent_flags?.length && !dx.suggested_followup?.length) && (
                <div className="muted">No diagnosis output produced.</div>
              )}
            </>
          ) : (
            <div className="muted">No diagnosis result.</div>
          )}
        </div>
      </details>
    </div>
  );
}
