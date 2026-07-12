import { useState, useEffect, useCallback } from "react";
import * as api from "../api";

/**
 * GPU Status Panel — shows which heavy models (classifier CNN, PaddleOCR,
 * Qwen-VL) are loaded on the NVIDIA GPU and offers a "Preload Models" button
 * to eagerly warm them up before the first OCR request.
 *
 * Polls /api/gpu/status every 3s while a preload is in progress.
 */
export function GpuStatusPanel() {
  const [status, setStatus] = useState<api.GpuStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await api.gpuStatus();
      setStatus(s);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  // Poll faster while a preload is in progress
  useEffect(() => {
    if (status && status.preload_started && !status.preload_done) {
      const id = setInterval(refresh, 1500);
      return () => clearInterval(id);
    }
  }, [status?.preload_started, status?.preload_done, refresh]);

  const handlePreload = useCallback(async () => {
    setLoading(true);
    try {
      await api.gpuPreload();
      refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [refresh]);

  if (!status && !error) {
    return (
      <div className="gpu-panel neu">
        <div className="gpu-header"><span className="gpu-icon">🖥️</span><h4>GPU Status</h4></div>
        <p className="gpu-loading">Checking GPU…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="gpu-panel neu">
        <div className="gpu-header"><span className="gpu-icon">🖥️</span><h4>GPU Status</h4></div>
        <p className="gpu-error">⚠️ {error}</p>
      </div>
    );
  }

  const s = status!;
  const preloading = s.preload_started && !s.preload_done;

  const modelRow = (label: string, loaded: boolean, errMsg: string | null, extra?: string) => (
    <div className={`gpu-model-row ${loaded ? "loaded" : errMsg ? "error" : "idle"}`}>
      <span className="gpu-model-name">{label}</span>
      <span className="gpu-model-state">
        {loaded ? "✅ Loaded" : errMsg ? `❌ ${errMsg.slice(0, 60)}` : "⏳ Idle"}
        {extra && <span className="gpu-extra"> ({extra})</span>}
      </span>
    </div>
  );

  return (
    <div className="gpu-panel neu">
      <div className="gpu-header">
        <span className="gpu-icon">🖥️</span>
        <h4>GPU Status</h4>
        <button className="neu-btn sm gpu-refresh" onClick={refresh} title="Refresh">↻</button>
      </div>

      <div className={`gpu-cuda-row ${s.cuda_available ? "ok" : "warn"}`}>
        <span className="gpu-cuda-label">CUDA</span>
        <span className="gpu-cuda-value">
          {s.cuda_available ? `✅ ${s.cuda_device_name}` : "❌ Not available"}
        </span>
        {s.torch_version && <span className="gpu-torch">torch {s.torch_version}</span>}
      </div>

      <div className="gpu-models">
        {modelRow("Classifier CNN", s.classifier_loaded, s.classifier_error)}
        {modelRow("PaddleOCR", s.paddle_loaded, s.paddle_error, s.paddle_using_gpu ? "GPU" : "CPU")}
        {modelRow("Qwen2.5-VL", s.qwen_loaded, s.qwen_error)}
      </div>

      {s.preload_error && (
        <div className="gpu-preload-error">⚠️ Preload error: {s.preload_error}</div>
      )}

      <div className="gpu-actions">
        <button
          className="neu-btn gpu-preload-btn"
          onClick={handlePreload}
          disabled={loading || preloading}
        >
          {preloading ? "⏳ Loading models…" : loading ? "Starting…" : "🔥 Preload Models to GPU"}
        </button>
        {preloading && <span className="gpu-hint">Warming up the GPU — this takes 30-90s for Qwen-VL.</span>}
      </div>
    </div>
  );
}
