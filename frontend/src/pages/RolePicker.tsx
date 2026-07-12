interface Props {
  onPick: (role: string, data?: any) => void;
}

export function RolePicker({ onPick }: Props) {
  return (
    <div className="landing landing-dual">
      <div className="landing-hero dual-hero">
        <div className="hero-wave" aria-hidden="true">
          <svg viewBox="0 0 1440 220" preserveAspectRatio="none" width="100%" height="220">
            <defs>
              <linearGradient id="hg" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#4f6ef7" stopOpacity="0.9" />
                <stop offset="50%" stopColor="#a78bfa" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#10b981" stopOpacity="0.85" />
              </linearGradient>
            </defs>
            <path fill="url(#hg)" d="M0,160 C240,80 480,200 720,160 C960,120 1200,40 1440,120 L1440,220 L0,220 Z" opacity="0.55" />
            <path fill="none" stroke="url(#hg)" strokeWidth="2" d="M0,120 C240,40 480,160 720,120 C960,80 1200,0 1440,80" opacity="0.7" />
          </svg>
        </div>
        <div className="landing-logo-big">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
          </svg>
        </div>
        <h2>MedVault</h2>
        <p>Upload your lab reports and let your doctor run the AI clinical pipeline. Two roles, one connected workflow.</p>
      </div>

      <div className="hero-grid">
        <div className="hero-card neu" onClick={() => onPick("patient")}>
          <div className="hero-card-glow" aria-hidden="true" />
          <div className="hero-card-icon patient">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <h3>Patient Portal</h3>
          <p>Upload your lab reports</p>
          <span className="hero-card-sub">Share reports with your doctor and track analysis status in real time.</span>
          <div className="hero-card-cta">Enter as Patient →</div>
        </div>

        <div className="hero-card neu" onClick={() => onPick("doctor")}>
          <div className="hero-card-glow" aria-hidden="true" />
          <div className="hero-card-icon doctor">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4.8 2.62A2 2 0 0 1 6.6 2h.89a2 2 0 0 1 1.82.62l.73.82a2 2 0 0 0 1.49.67H13a2 2 0 0 0 1.49-.67l.73-.82A2 2 0 0 1 17 2h.89" />
              <path d="M4 7v3a8 8 0 0 0 8 8 8 8 0 0 0 8-8V7" />
              <circle cx="19" cy="14" r="2" />
              <path d="M19 16v3a3 3 0 0 1-3 3h-1a3 3 0 0 1-3-3v-1" />
            </svg>
          </div>
          <h3>Doctor Portal</h3>
          <p>Review &amp; Analyze</p>
          <span className="hero-card-sub">Browse patient reports, run the AI pipeline, and view OCR + diagnosis results.</span>
          <div className="hero-card-cta">Enter as Doctor →</div>
        </div>
      </div>

      <div className="landing-features">
        <div className="landing-feature">
          <div className="feature-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </div>
          <span>HIPAA-ready</span>
        </div>
        <div className="landing-feature">
          <div className="feature-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          </div>
          <span>Vitals Tracking</span>
        </div>
        <div className="landing-feature">
          <div className="feature-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <span>AI Analysis</span>
        </div>
        <div className="landing-feature">
          <div className="feature-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>
          </div>
          <span>Prescriptions</span>
        </div>
        <div className="landing-feature">
          <div className="feature-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          </div>
          <span>Appointments</span>
        </div>
        <div className="landing-feature">
          <div className="feature-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4"/></svg>
          </div>
          <span>Plug & Play</span>
        </div>
      </div>

      <button className="neu-btn ghost" onClick={() => onPick("settings")} style={{ marginTop: 8 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4"/></svg>
        Configure Providers
      </button>
    </div>
  );
}
