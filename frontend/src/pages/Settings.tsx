import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import * as api from "../api";

interface Props {
  onBack: () => void;
  notify: (msg: string, type?: "success" | "error") => void;
}

export function Settings({ onBack, notify }: Props) {
  const [providers, setProviders] = useState<api.Provider[]>([]);
  const [engines, setEngines] = useState<{ ocr: api.EngineInfo[]; ai: api.EngineInfo[] }>({ ocr: [], ai: [] });
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState<"ocr" | "ai" | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formEngine, setFormEngine] = useState("");
  const [formConfig, setFormConfig] = useState<Record<string, string>>({});
  const [formDefault, setFormDefault] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const [p, e] = await Promise.all([api.listProviders(), api.listEngines()]);
      setProviders(p);
      setEngines(e);
    } catch (e: any) {
      notify(e.message, "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const ocrProviders = providers.filter(p => p.kind === "ocr");
  const aiProviders = providers.filter(p => p.kind === "ai");

  const openAdd = (kind: "ocr" | "ai") => {
    setShowForm(kind);
    setEditId(null);
    setFormName("");
    setFormEngine(kind === "ocr" ? "pipeline" : "gemini");
    setFormConfig({});
    setFormDefault(false);
  };

  const openEdit = (p: api.Provider) => {
    setShowForm(p.kind as "ocr" | "ai");
    setEditId(p.id);
    setFormName(p.name);
    setFormEngine(p.engine);
    setFormConfig({ ...p.config });
    setFormDefault(!!p.is_default);
  };

  const handleSave = async () => {
    if (!formName.trim()) return notify("Name is required", "error");
    setSaving(true);
    try {
      const data = { kind: showForm!, name: formName, engine: formEngine, config: formConfig, is_default: formDefault };
      if (editId) {
        await api.updateProvider(editId, data);
        notify("Provider updated!");
      } else {
        await api.createProvider(data);
        notify("Provider added!");
      }
      setShowForm(null);
      await load();
    } catch (e: any) {
      notify(e.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteProvider(id);
      notify("Provider removed");
      await load();
    } catch (e: any) {
      notify(e.message, "error");
    }
  };

  const currentEngineFields = () => {
    if (!showForm) return [];
    const list = showForm === "ocr" ? engines.ocr : engines.ai;
    return list.find(e => e.id === formEngine)?.fields || [];
  };

  const engineOptions = showForm === "ocr" ? engines.ocr : engines.ai;

  return (
    <div className="page-enter">
      <div className="breadcrumb">
        <button onClick={onBack}>Home</button>
        <span className="sep">/</span>
        <span>Settings</span>
      </div>

      <div className="section-header">
        <div>
          <h1>Provider Settings</h1>
          <div className="subtitle">Connect OCR engines and AI models to power your analysis pipeline</div>
        </div>
      </div>

      {loading ? (
        <div>{[1, 2].map(i => <div key={i} className="skeleton skeleton-card" />)}</div>
      ) : (
        <>
          {/* OCR Providers */}
          <div className="provider-section">
            <div className="provider-section-header">
              <div>
                <h3>OCR Engines</h3>
                <p>Text extraction from documents and images</p>
              </div>
              <button className="neu-btn sm primary" onClick={() => openAdd("ocr")}>+ Add OCR</button>
            </div>

            {ocrProviders.length === 0 ? (
              <div className="provider-empty neu-inset">
                <span>No OCR providers configured.</span>
                <span className="provider-empty-hint">The MedVault Dual Pipeline (PaddleOCR + Qwen2.5-VL) is used by default.</span>
              </div>
            ) : (
              <div className="provider-list">
                {ocrProviders.map(p => (
                  <ProviderCard key={p.id} provider={p} onEdit={() => openEdit(p)} onDelete={() => handleDelete(p.id)} />
                ))}
              </div>
            )}
          </div>

          {/* AI Providers */}
          <div className="provider-section">
            <div className="provider-section-header">
              <div>
                <h3>AI Models</h3>
                <p>Language models for medical report analysis</p>
              </div>
              <button className="neu-btn sm primary" onClick={() => openAdd("ai")}>+ Add AI Model</button>
            </div>

            {aiProviders.length === 0 ? (
              <div className="provider-empty neu-inset">
                <span>No AI providers configured.</span>
                <span className="provider-empty-hint">Add a Gemini, OpenAI, or Ollama provider to start analyzing.</span>
              </div>
            ) : (
              <div className="provider-list">
                {aiProviders.map(p => (
                  <ProviderCard key={p.id} provider={p} onEdit={() => openEdit(p)} onDelete={() => handleDelete(p.id)} />
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Add/Edit Form Modal */}
      {showForm && createPortal(
        <div className="modal-overlay" onClick={() => setShowForm(null)}>
          <div className="modal-card neu" onClick={e => e.stopPropagation()}>
            <h3>{editId ? "Edit" : "Add"} {showForm === "ocr" ? "OCR Engine" : "AI Model"}</h3>

            <div className="form-group">
              <label>Name</label>
              <input className="neu-input" placeholder="e.g. My Gemini Key" value={formName} onChange={e => setFormName(e.target.value)} />
            </div>

            <div className="form-group">
              <label>Engine</label>
              <select className="neu-input" value={formEngine} onChange={e => { setFormEngine(e.target.value); setFormConfig({}); }}>
                {engineOptions.map(eng => (
                  <option key={eng.id} value={eng.id}>{eng.name}</option>
                ))}
              </select>
            </div>

            {currentEngineFields().map(field => (
              <div className="form-group" key={field.key}>
                <label>{field.label} {field.required && <span style={{ color: "var(--danger)" }}>*</span>}</label>
                <input
                  className="neu-input"
                  type={field.secret ? "password" : "text"}
                  placeholder={field.placeholder}
                  value={formConfig[field.key] || ""}
                  onChange={e => setFormConfig(prev => ({ ...prev, [field.key]: e.target.value }))}
                />
              </div>
            ))}

            <label className="checkbox-row">
              <input type="checkbox" checked={formDefault} onChange={e => setFormDefault(e.target.checked)} />
              <span>Set as default</span>
            </label>

            <div className="form-actions">
              <button className="neu-btn ghost" onClick={() => setShowForm(null)}>Cancel</button>
              <button className="neu-btn primary" onClick={handleSave} disabled={saving}>
                {saving ? <span className="spinner white" /> : editId ? "Update" : "Add"}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

function ProviderCard({ provider, onEdit, onDelete }: { provider: api.Provider; onEdit: () => void; onDelete: () => void }) {
  const ENGINE_ICONS: Record<string, string> = {
    auto: "🔀", paddleocr: "📝", qwen_vl: "👁",
    gemini: "✦", openai: "◐", ollama: "🦙", custom_openai: "🔌", pipeline: "🔄",
  };
  return (
    <div className="provider-card neu">
      <div className="provider-card-icon">{ENGINE_ICONS[provider.engine] || "⚙"}</div>
      <div className="provider-card-body">
        <div className="provider-card-name">
          {provider.name}
          {!!provider.is_default && <span className="tag analyzed">Default</span>}
        </div>
        <div className="provider-card-engine">{provider.engine}</div>
      </div>
      <div className="provider-card-actions">
        <button className="neu-btn sm ghost" onClick={onEdit}>Edit</button>
        <button className="neu-btn sm danger" onClick={onDelete}>Remove</button>
      </div>
    </div>
  );
}
