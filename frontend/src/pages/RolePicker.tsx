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
    </div>
  );
}
