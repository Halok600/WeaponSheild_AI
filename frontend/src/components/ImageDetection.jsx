import { useState, useRef } from 'react'
import api from '../api/axiosClient'
import AlertBadge from './AlertBadge'
import DetectionLog from './DetectionLog'

export default function ImageDetection() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)      // original image
  const [result, setResult] = useState(null)         // API response
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef()

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setResult(null)
    setError(null)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleSubmit = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const form = new FormData()
      form.append('file', file)
      const { data } = await api.post('/detect/image', form)
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Detection failed. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const detections = result?.detections ?? []
  const logEntries = detections.map((d, i) => ({
    frame: null,
    timestamp: 'N/A',
    label: d.label,
    confidence: d.confidence,
    bbox: d.bbox,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <AlertBadge active={result?.weapon_detected} message="Weapon found in uploaded image" />

      {/* Upload zone */}
      <div className="card">
        <h2 style={{ marginBottom: '1rem' }}>📷 Image Detection</h2>
        <div
          className={`dropzone ${dragOver ? 'drag-over' : ''}`}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={e => handleFile(e.target.files[0])}
          />
          <div className="dropzone-icon">🖼️</div>
          <div className="dropzone-text">
            {file ? file.name : 'Drop an image here or click to browse'}
          </div>
          <div className="dropzone-hint">JPEG • PNG • BMP • WebP</div>
        </div>

        {/* Submit */}
        <div style={{ marginTop: '1rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button
            id="image-detect-btn"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!file || loading}
          >
            {loading ? <><span className="spinner" /> Analysing…</> : '🔍 Detect Weapons'}
          </button>
          {file && (
            <button className="btn btn-secondary" onClick={() => { setFile(null); setPreview(null); setResult(null) }}>
              ✕ Clear
            </button>
          )}
          {result && (
            <span className={`badge ${result.weapon_detected ? 'badge-danger' : 'badge-success'}`}>
              {result.weapon_detected ? '⚠️ Weapon Detected' : '✅ No Weapon'}
            </span>
          )}
        </div>

        {error && (
          <div style={{
            marginTop: '0.75rem', padding: '0.75rem 1rem',
            background: 'hsla(0,80%,58%,0.1)', border: '1px solid var(--accent)',
            borderRadius: 'var(--radius-md)', color: 'var(--accent)', fontSize: '0.875rem'
          }}>
            ⚠️ {error}
          </div>
        )}
      </div>

      {/* Image comparison */}
      {(preview || result) && (
        <div className="two-col" style={{ gap: '1rem' }}>
          {preview && (
            <div className="card" style={{ padding: '0.75rem' }}>
              <div className="section-label">Original</div>
              <img src={preview} alt="Original upload" className="img-preview" />
            </div>
          )}
          {result?.output_url && (
            <div className="card" style={{ padding: '0.75rem' }}>
              <div className="section-label">Annotated Output</div>
              <img
                src={result.output_url}
                alt="Annotated detection result"
                className="img-preview"
              />
            </div>
          )}
        </div>
      )}

      {/* Confidence scores */}
      {detections.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>Detection Results</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {detections.map((d, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '1rem',
                padding: '0.65rem 1rem',
                background: 'var(--bg-surface)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border)'
              }}>
                <span className="badge badge-danger">{d.label}</span>
                <div className="conf-bar-wrap" style={{ flex: 1 }}>
                  <div className="conf-bar" style={{ width: `${(d.confidence * 100).toFixed(0)}%` }} />
                </div>
                <span className="font-mono text-sm" style={{ color: 'var(--accent)', minWidth: 48, textAlign: 'right' }}>
                  {(d.confidence * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alert info */}
      {result?.alert && (
        <div className="card" style={{ padding: '0.85rem 1rem' }}>
          <div className="flex items-center gap-3">
            <span style={{ fontSize: '1.2rem' }}>📲</span>
            <div>
              <div className="text-sm" style={{ fontWeight: 600 }}>SMS Alert</div>
              <div className="text-xs text-muted">
                {result.alert.sent
                  ? `Sent ✓  SID: ${result.alert.sid}`
                  : `Not sent — ${result.alert.reason}`}
              </div>
            </div>
          </div>
        </div>
      )}

      <DetectionLog entries={logEntries} title="Image Detection Log" />
    </div>
  )
}
