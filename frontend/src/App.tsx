import { useState, useCallback, useEffect } from "react";
import { RolePicker } from "./pages/RolePicker";
import { PatientPortal } from "./pages/PatientPortal";
import { DoctorPortal } from "./pages/DoctorPortal";
import { Settings } from "./pages/Settings";
import { Dashboard } from "./pages/Dashboard";
import { PatientChart } from "./pages/PatientChart";
import { DrugInteractions } from "./pages/DrugInteractions";
import { Messages } from "./pages/Messages";
import { AuditLog } from "./pages/AuditLog";
import { AdvancedAnalytics } from "./pages/AdvancedAnalytics";
import { ConsentForms } from "./pages/ConsentForms";
import { PatientEducation } from "./pages/PatientEducation";
import { MedicalImaging } from "./pages/MedicalImaging";
import { Telemedicine } from "./pages/Telemedicine";
import { PrescriptionRefills } from "./pages/PrescriptionRefills";
import { Genomics } from "./pages/Genomics";
import { ClinicalTrials } from "./pages/ClinicalTrials";
import { VitalsMonitor } from "./pages/VitalsMonitor";
import { LabInterpretation } from "./pages/LabInterpretation";
import { ResearchPipeline } from "./pages/ResearchPipeline";
import { OCRWorkbench } from "./pages/OCRWorkbench";

type View = "pick" | "patient" | "doctor" | "settings" | "dashboard" | "patient-chart" | "drug-interactions" | "messages" | "audit-log" | "analytics" | "consent-forms" | "education" | "imaging" | "telemedicine" | "rx-refills" | "genomics" | "clinical-trials" | "vitals-monitor" | "lab-interpret" | "research" | "ocr-workbench";

interface Toast {
  id: number;
  msg: string;
  type: "success" | "error";
  exiting?: boolean;
}

let toastId = 0;

export function App() {
  const [view, setView] = useState<View>("pick");
  const [viewData, setViewData] = useState<any>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [dark, setDark] = useState(() => localStorage.getItem("medvault_theme") === "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    localStorage.setItem("medvault_theme", dark ? "dark" : "light");
  }, [dark]);

  const notify = useCallback((msg: string, type: "success" | "error" = "success") => {
    const id = ++toastId;
    setToasts(prev => [...prev, { id, msg, type }]);
    setTimeout(() => {
      setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t));
      setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 300);
    }, 2800);
  }, []);

  const navigate = (v: string, data?: any) => {
    if (v === "patient-detail" && data?.id) {
      setViewData(data);
      setView("patient-chart");
    } else {
      setView(v as View);
      setViewData(data);
    }
  };

  return (
    <div className="app-shell" role="application" aria-label="MedVault Medical Platform">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <nav className="topbar" role="navigation" aria-label="Main navigation">
        <div className="logo" onClick={() => setView("pick")} style={{ cursor: "pointer" }}>
          <div className="mark">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
            </svg>
          </div>
          <span>MedVault</span>
        </div>
        <div className="topbar-actions">
          {view !== "pick" && (
            <>
              <button className="neu-btn sm ghost" onClick={() => setView("pick")}>Home</button>
              <button className="neu-btn sm ghost" onClick={() => setView("dashboard")}>Analytics</button>
            </>
          )}
          <button className="neu-btn sm ghost" onClick={() => setView("settings")} title="Settings">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
          </button>
          <button
            className="neu-btn sm icon-only"
            onClick={() => setDark(d => !d)}
            title={dark ? "Light mode" : "Dark mode"}
          >
            {dark ? "☀️" : "🌙"}
          </button>
        </div>

      </nav>
      <main className="main-content" id="main-content" role="main">
        <div key={view + (viewData?.id || "")} className="page-enter">
          {view === "pick" && <RolePicker onPick={navigate} />}
          {view === "patient" && <PatientPortal onBack={() => setView("pick")} notify={notify} />}
          {view === "doctor" && <DoctorPortal onBack={() => setView("pick")} notify={notify} onOpenChart={(id: string) => navigate("patient-detail", { id })} />}
          {view === "settings" && <Settings onBack={() => setView("pick")} notify={notify} />}
          {view === "dashboard" && <Dashboard onBack={() => setView("pick")} onNavigate={navigate} notify={notify} />}
          {view === "drug-interactions" && <DrugInteractions onBack={() => setView("pick")} notify={notify} />}
          {view === "messages" && <Messages onBack={() => setView("pick")} notify={notify} />}
          {view === "audit-log" && <AuditLog onBack={() => setView("pick")} />}
          {view === "analytics" && <AdvancedAnalytics onBack={() => setView("pick")} onNavigate={navigate} />}
          {view === "consent-forms" && <ConsentForms onBack={() => setView("pick")} notify={notify} />}
          {view === "education" && <PatientEducation onBack={() => setView("pick")} />}
          {view === "imaging" && <MedicalImaging onBack={() => setView("pick")} notify={notify} />}
          {view === "telemedicine" && <Telemedicine onBack={() => setView("pick")} notify={notify} />}
          {view === "rx-refills" && <PrescriptionRefills onBack={() => setView("pick")} notify={notify} />}
          {view === "genomics" && <Genomics onBack={() => setView("pick")} notify={notify} />}
          {view === "clinical-trials" && <ClinicalTrials onBack={() => setView("pick")} notify={notify} />}
          {view === "vitals-monitor" && <VitalsMonitor onBack={() => setView("pick")} notify={notify} />}
          {view === "lab-interpret" && <LabInterpretation onBack={() => setView("pick")} notify={notify} />}
          {view === "research" && <ResearchPipeline onBack={() => setView("pick")} notify={notify} />}
          {view === "ocr-workbench" && <OCRWorkbench onBack={() => setView("pick")} notify={notify} />}
          {view === "patient-chart" && viewData?.id && (
            <PatientChart patientId={viewData.id} onBack={() => setView("doctor")} notify={notify} />
          )}
        </div>
      </main>

      <div className="toast-container" role="status" aria-live="polite">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type}${t.exiting ? " exiting" : ""}`}>
            {t.type === "success" ? "✓" : "✕"} {t.msg}
          </div>
        ))}
      </div>
    </div>
  );
}
