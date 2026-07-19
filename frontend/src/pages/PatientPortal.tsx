import { useState, useRef, useCallback, useEffect } from "react";
import * as api from "../api";

interface Props {
  onBack: () => void;
  notify: (msg: string, type?: "success" | "error") => void;
}

export function PatientPortal({ onBack, notify }: Props) {
  const [reports, setReports] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadReports = useCallback(async () => {
    try {
      setReports(await api.testReports());
    } catch {}
  }, []);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handleUpload = useCallback(async (file: File, docType: string) => {
    setUploading(true);
    setProgress(0);
    setPendingFile(null);
    const timer = setInterval(() => setProgress(p => Math.min(p + 12, 92)), 110);
    try {
      await api.testUploadReport(file, docType);
      setProgress(100);
      notify(`${file.name} uploaded`);
      loadReports();
    } catch (e: any) {
      setProgress(0);
      notify(e.message, "error");
    } finally {
      clearInterval(timer);
      setTimeout(() => { setUploading(false); setProgress(0); }, 450);
    }
  }, [notify, loadReports]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) setPendingFile(file);
  }, []);

  const analyzed = reports.filter(r => r.analyzed).length;
  const pending = reports.length - analyzed;

  return (
    <div className="page-enter">
      <div className="breadcrumb">
        <button onClick={onBack}>Home</button>
        <span className="sep">/</span>
        <span>My Reports</span>
      </div>

      <div className="section-header">
        <div>
          <h1>My Reports</h1>
          <div className="subtitle">Upload and track your medical documents</div>
        </div>
      </div>

      {reports.length > 0 && (
        <div className="stat-row">
          <div className="stat-card neu">
            <div className="stat-icon blue">📄</div>
            <div className="stat-value">{reports.length}</div>
            <div className="stat-label">Total</div>
          </div>
          <div className="stat-card neu">
            <div className="stat-icon green">✓</div>
            <div className="stat-value">{analyzed}</div>
            <div className="stat-label">Analyzed</div>
          </div>
          <div className="stat-card neu">
            <div className="stat-icon orange">⏳</div>
            <div className="stat-value">{pending}</div>
            <div className="stat-label">Pending</div>
          </div>
        </div>
      )}

      <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" hidden onChange={e => {
        const f = e.target.files?.[0];
        if (f) setPendingFile(f);
        e.target.value = "";
      }} />

      {pendingFile ? (
        <div className="upload-zone hero" style={{ cursor: "default" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={{ fontWeight: 600 }}>📄 {pendingFile.name}</div>
            <button className="neu-btn sm" onClick={(e) => { e.stopPropagation(); setPendingFile(null); }}>✕ Cancel</button>
          </div>
          <h4>What type of document is this?</h4>
          <p style={{ marginBottom: 20 }}>Select the format to route it to the best AI model.</p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <button className="neu-btn" style={{ padding: "12px 24px" }} onClick={(e) => { e.stopPropagation(); handleUpload(pendingFile, "printed"); }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>🖨️</div>
              <div style={{ fontWeight: 600 }}>Printed</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>Typed text</div>
            </button>
            <button className="neu-btn" style={{ padding: "12px 24px" }} onClick={(e) => { e.stopPropagation(); handleUpload(pendingFile, "tabular"); }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>📊</div>
              <div style={{ fontWeight: 600 }}>Tabular</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>Tables / lab panels</div>
            </button>
            <button className="neu-btn" style={{ padding: "12px 24px" }} onClick={(e) => { e.stopPropagation(); handleUpload(pendingFile, "handwritten"); }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>✍️</div>
              <div style={{ fontWeight: 600 }}>Handwritten</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 4 }}>Doctor notes</div>
            </button>
          </div>
        </div>
      ) : (
        <div
          className={`upload-zone hero${dragging ? " dragging" : ""}`}
          onClick={() => fileRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          {uploading ? (
            <>
              <div className="upload-icon"><span className="spinner" /></div>
              <h4>Uploading…</h4>
              <p>Securely sending your document</p>
              <div className="upload-progress"><div className="upload-progress-bar" style={{ width: `${progress}%` }} /></div>
              <div className="upload-progress-label">{progress}%</div>
            </>
          ) : (
            <>
              <div className="upload-icon">📤</div>
              <h4>Drop your lab report image here</h4>
              <p>Drag &amp; drop or click to select — PDF, PNG, JPG, JPEG, WebP</p>
            </>
          )}
        </div>
      )}

      {reports.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h4>No reports yet</h4>
          <p>Upload your first medical document above to get started.</p>
        </div>
      ) : (
        <div className="report-list">
          {reports.map(r => (
            <div key={r.id} className="report-card neu">
              <div className="file-thumb">
                {r.filetype === "pdf" ? "📕" : "🖼️"}
              </div>
              <div className="report-body">
                <div className="report-title">{r.filename}</div>
                <div className="report-date">
                  {new Date(r.shared_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                  {" · "}
                  {new Date(r.shared_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
              <div className="report-right">
                <span className={`tag ${r.filetype}`}>{r.filetype}</span>
                {r.analyzed ? <span className="tag analyzed">Analyzed</span> : <span className="tag uploaded">Uploaded</span>}
                <a href={api.fileUrl(r.id)} target="_blank" rel="noopener">
                  <button className="neu-btn sm">View</button>
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
