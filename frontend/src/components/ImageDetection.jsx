import { useState, useRef } from 'react'
import api, { API_BASE } from '../api/axiosClient'
import AlertBadge from './AlertBadge'
import DetectionLog from './DetectionLog'
import { IconImage, IconUpload, IconCrosshair, IconCheck, IconAlert, IconSend } from './Icons'

export default function ImageDetection({ alertEmail }) {
  const [file, setFile]       = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef()

  const handleFile = (f) => {
    if (!f) return
    setFile(f); setPreview(URL.createObjectURL(f)); setResult(null); setError(null)
  }
  const handleDrop = (e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]) }
  const handleSubmit = async () => {
    if (!file) return
    setLoading(true); setError(null); setResult(null)
    try {
      const form = new FormData()
      form.append('file', file)
      if (alertEmail) form.append('alert_email', alertEmail)
      const { data } = await api.post('/detect/image', form)
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Detection failed. Is the backend running?')
    } finally { setLoading(false) }
  }

  const detections = result?.detections ?? []
  const logEntries = detections.map(d => ({ frame: null, timestamp: 'N/A', label: d.label, confidence: d.confidence, bbox: d.bbox }))

  return (
    <div className="flex flex-col gap-4" style={{ gap: '1.25rem', paddingTop: '1rem' }}>
      <AlertBadge active={result?.weapon_detected} message="Weapon found in uploaded image" />

      {/* ── Upload card ── */}
      <div className="card card-hover">
        <div className="flex items-center gap-3 mb-4">
          <div style={{
            width: 36, height: 36, background: 'var(--accent-subtle)',
            borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <IconImage size={18} style={{ color: 'var(--accent)' }} />
          </div>
          <div>
            <h2>Image Scan</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2 }}>Upload an image to detect weapons using YOLOv8</p>
          </div>
        </div>

        <div
          className={`dropzone ${dragOver ? 'drag-over' : ''}`}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current.click()}
        >
          <input ref={inputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={e => handleFile(e.target.files[0])} />
          <div className="dropzone-icon"><IconUpload size={32} /></div>
          <div className="dropzone-text">
            {file ? file.name : 'Drop an image here or click to browse'}
          </div>
          <div className="dropzone-hint">JPEG · PNG · BMP · WebP</div>
        </div>

        <div className="flex items-center gap-3 mt-4" style={{ flexWrap: 'wrap' }}>
          <button id="image-detect-btn" className="btn btn-primary" onClick={handleSubmit} disabled={!file || loading}>
            {loading ? <><span className="spinner" /> Analysing…</> : <><IconCrosshair size={15} /> Detect Weapons</>}
          </button>
          {file && (
            <button className="btn btn-secondary" onClick={() => { setFile(null); setPreview(null); setResult(null) }}>
              Clear
            </button>
          )}
          {result && (
            <span className={`badge ${result.weapon_detected ? 'badge-danger' : 'badge-success'}`}>
              {result.weapon_detected ? <><IconAlert size={11} /> Weapon Detected</> : <><IconCheck size={11} /> No Weapon</>}
            </span>
          )}
        </div>

        {error && <div className="error-box mt-3"><span>⚠</span><span>{error}</span></div>}
      </div>

      {/* ── Image comparison ── */}
      {(preview || result) && (
        <div className="two-col">
          {preview && (
            <div className="card" style={{ padding: '1rem' }}>
              <div className="section-label">Original</div>
              <img src={preview} alt="Original upload" className="img-preview" />
            </div>
          )}
          {result?.output_url && (
            <div className="card" style={{ padding: '1rem', borderColor: result.weapon_detected ? 'hsla(0,72%,58%,0.35)' : undefined }}>
              <div className="section-label" style={{ color: result.weapon_detected ? 'var(--danger)' : undefined }}>
                {result.weapon_detected ? '⚠ Annotated — Weapon Found' : '✓ Annotated — Clear'}
              </div>
              <img src={`${API_BASE}${result.output_url}`} alt="Annotated detection result" className="img-preview" />
            </div>
          )}
        </div>
      )}

      {/* ── Confidence scores ── */}
      {detections.length > 0 && (
        <div className="card">
          <h3 className="mb-3">Detection Results</h3>
          <div className="flex flex-col" style={{ gap: '0.6rem' }}>
            {detections.map((d, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '1rem',
                padding: '0.7rem 1rem',
                background: 'var(--bg-surface)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid hsla(0,72%,58%,0.2)',
              }}>
                <span className="badge badge-danger">{d.label}</span>
                <div className="conf-bar-wrap" style={{ flex: 1 }}>
                  <div className="conf-bar" style={{ width: `${(d.confidence * 100).toFixed(0)}%` }} />
                </div>
                <span className="font-mono text-sm" style={{ color: 'var(--danger)', minWidth: 52, textAlign: 'right', fontWeight: 700 }}>
                  {(d.confidence * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Email alert info ── */}
      {result?.alert && (
        <div className={`card ${result.alert.sent ? 'card-success' : ''}`} style={{ padding: '1rem 1.25rem' }}>
          <div className="flex items-center gap-3">
            <IconSend size={18} style={{ color: result.alert.sent ? 'var(--accent-green)' : 'var(--text-muted)', flexShrink: 0 }} />
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Email Alert</div>
              <div className="text-xs text-muted" style={{ marginTop: 2 }}>
                {result.alert.sent ? `Sent ✓ to ${alertEmail}` : `Not sent — ${result.alert.reason}`}
              </div>
            </div>
          </div>
        </div>
      )}

      <DetectionLog entries={logEntries} title="Image Detection Log" />
    </div>
  )
}
