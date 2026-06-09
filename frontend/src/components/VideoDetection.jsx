import { useState, useRef, useEffect } from 'react'
import api from '../api/axiosClient'
import AlertBadge from './AlertBadge'
import DetectionLog from './DetectionLog'

const POLL_MS = 1500

export default function VideoDetection() {
  const [file, setFile] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadPct, setUploadPct] = useState(0)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const pollRef = useRef(null)
  const inputRef = useRef()

  // Options
  const [stopOnFirst, setStopOnFirst] = useState(false)
  const [frameSkip, setFrameSkip] = useState(0)
  const [addNoise, setAddNoise] = useState(false)
  const [blurStrength, setBlurStrength] = useState(0)
  const [lowRes, setLowRes] = useState(false)
  const [confThreshold, setConfThreshold] = useState(0.15)
  // Track what threshold was actually sent for the current job result
  const [usedConfThreshold, setUsedConfThreshold] = useState(null)
  const [thresholdChanged, setThresholdChanged] = useState(false)

  /* ── Poll job status ───────────────────────────────────────────────── */
  useEffect(() => {
    if (!jobId) return
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.get(`/detect/video/${jobId}`)
        setJob(data)
        if (data.status === 'done' || data.status === 'error') {
          clearInterval(pollRef.current)
        }
      } catch { /* ignore transient errors */ }
    }, POLL_MS)
    return () => clearInterval(pollRef.current)
  }, [jobId])

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    setJob(null)
    setJobId(null)
    setError(null)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer.files[0])
  }

  const handleSubmit = async () => {
    if (!file) return
    setUploading(true)
    setUploadPct(0)
    setError(null)
    setJob(null)
    setJobId(null)
    setThresholdChanged(false)

    // Snapshot the threshold at submission time so results show what was actually used
    const submittedConf = confThreshold
    setUsedConfThreshold(submittedConf)

    try {
      const form = new FormData()
      form.append('file', file)
      form.append('stop_on_detection', stopOnFirst)
      form.append('frame_skip', frameSkip)
      form.append('add_noise', addNoise)
      form.append('blur_strength', blurStrength)
      form.append('low_res', lowRes)
      form.append('conf_threshold', submittedConf)

      const { data } = await api.post('/detect/video', form, {
        onUploadProgress: (e) => {
          if (e.total) setUploadPct(Math.round((e.loaded / e.total) * 100))
        },
      })
      setJobId(data.job_id)
      setJob({ status: 'queued', processed_frames: 0, total_frames: 0, detection_log: [] })
    } catch (err) {
      setError(err?.response?.data?.detail || 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  /* ── Derived state ─────────────────────────────────────────────────── */
  const isProcessing = job?.status === 'processing' || job?.status === 'queued'
  const isDone       = job?.status === 'done'
  const isError      = job?.status === 'error'
  const progress = job?.total_frames
    ? Math.round((job.processed_frames / job.total_frames) * 100)
    : 0
  const detectionLog = job?.detection_log ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <AlertBadge
        active={isDone && job?.weapon_detected}
        message={`First detection at ${detectionLog[0]?.timestamp ?? '—'}`}
      />

      {/* Upload + options */}
      <div className="card">
        <h2 style={{ marginBottom: '1rem' }}>📹 CCTV Video Detection</h2>

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
            accept="video/*"
            style={{ display: 'none' }}
            onChange={e => handleFile(e.target.files[0])}
          />
          <div className="dropzone-icon">🎞️</div>
          <div className="dropzone-text">
            {file ? file.name : 'Drop a video file or click to browse'}
          </div>
          <div className="dropzone-hint">MP4 • AVI • MOV • MKV</div>
        </div>

        {/* Options */}
        <div style={{ marginTop: '1rem' }}>
          <div className="section-label">Processing Options</div>
          <div className="options-grid" style={{ marginTop: '0.5rem' }}>
            <label className="toggle-label">
              <input type="checkbox" checked={stopOnFirst} onChange={e => setStopOnFirst(e.target.checked)} />
              Stop on first detection
            </label>
            <label className="toggle-label">
              <input type="checkbox" checked={addNoise} onChange={e => setAddNoise(e.target.checked)} />
              CCTV noise simulation
            </label>
            <label className="toggle-label">
              <input type="checkbox" checked={lowRes} onChange={e => setLowRes(e.target.checked)} />
              Low-res (pixelate)
            </label>
          </div>

          <div style={{ marginTop: '0.85rem', display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <div style={{ minWidth: 180 }}>
              <div className="section-label">Frame Skip: {frameSkip}</div>
              <input
                type="range" min={0} max={10} value={frameSkip}
                onChange={e => setFrameSkip(Number(e.target.value))}
              />
              <div className="text-xs text-muted">Skip {frameSkip} frame(s) between inferences</div>
            </div>
            <div style={{ minWidth: 180 }}>
              <div className="section-label">Blur: {blurStrength}px</div>
              <input
                type="range" min={0} max={21} step={2} value={blurStrength}
                onChange={e => setBlurStrength(Number(e.target.value))}
              />
            </div>
            <div style={{ minWidth: 180 }}>
              <div className="section-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                Confidence: {(confThreshold * 100).toFixed(0)}%
                {usedConfThreshold !== null && isDone && (
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 400 }}>
                    (last run: {(usedConfThreshold * 100).toFixed(0)}%)
                  </span>
                )}
              </div>
              <input
                type="range" min={1} max={90} value={Math.round(confThreshold * 100)}
                onChange={e => {
                  setConfThreshold(Number(e.target.value) / 100)
                  if (isDone) setThresholdChanged(true)
                }}
              />
              <div className="text-xs text-muted">Lower = more sensitive (try 5–15% for video)</div>
            </div>
          </div>
        </div>

        {/* Action row */}
        <div style={{ marginTop: '1rem', display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            id="video-detect-btn"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!file || uploading || isProcessing}
          >
            {uploading
              ? <><span className="spinner" /> Uploading {uploadPct}%…</>
              : isProcessing
              ? <><span className="spinner" /> Processing…</>
              : '▶ Start Detection'}
          </button>
          {file && !isProcessing && !uploading && (
            <button className="btn btn-secondary" onClick={() => { setFile(null); setJob(null); setJobId(null) }}>
              ✕ Clear
            </button>
          )}
          {isDone && (
            <span className={`badge ${job.weapon_detected ? 'badge-danger' : 'badge-success'}`}>
              {job.weapon_detected ? `⚠️ ${detectionLog.length} detection(s)` : '✅ No Weapon Found'}
            </span>
          )}
        </div>

        {thresholdChanged && isDone && (
          <div style={{
            marginTop: '0.75rem', padding: '0.75rem 1rem',
            background: 'hsla(45,95%,55%,0.1)', border: '1px solid #f5c542',
            borderRadius: 'var(--radius-md)', color: '#f5c542', fontSize: '0.875rem'
          }}>
            ⚡ Confidence threshold changed — click <strong>Start Detection</strong> to re-run with {(confThreshold * 100).toFixed(0)}%.
            The current results used {usedConfThreshold !== null ? (usedConfThreshold * 100).toFixed(0) : '?'}%.
          </div>
        )}
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

      {/* Progress */}
      {(isProcessing || isDone) && (
        <div className="card">
          <div className="flex items-center justify-between" style={{ marginBottom: '0.6rem' }}>
            <h3>
              {isProcessing
                ? `Processing… Frame ${job.processed_frames} / ${job.total_frames || '?'}`
                : `✅ Complete — ${job.processed_frames} frames processed`}
            </h3>
            <span className="font-mono text-sm text-accent">{progress}%</span>
          </div>
          <div className="progress-wrap">
            <div className="progress-bar" style={{ width: `${isDone ? 100 : progress}%` }} />
          </div>
          {job.stopped_early && (
            <div className="text-xs text-amber mt-2">⚡ Stopped after first detection</div>
          )}
        </div>
      )}

      {/* Video player */}
      {isDone && job.output_url && (
        <div className="card" style={{ padding: '0.75rem' }}>
          <div className="section-label" style={{ marginBottom: '0.5rem' }}>Processed Video Output</div>
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <video
            key={job.output_url}
            controls
            style={{ width: '100%', borderRadius: 'var(--radius-md)', background: '#000', maxHeight: 480 }}
          >
            <source src={job.output_url} type="video/mp4" />
            Your browser does not support the video tag.
          </video>
        </div>
      )}

      {/* Error panel */}
      {isError && (
        <div className="card" style={{
          borderColor: 'var(--accent)', background: 'hsla(0,80%,58%,0.07)',
          color: 'var(--accent)'
        }}>
          ⚠️ Processing error: {job.error}
        </div>
      )}

      {/* Stats */}
      {isDone && (
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {[
            { label: 'Total Frames', value: job.processed_frames },
            { label: 'Detections', value: detectionLog.length },
            { label: 'SMS Alert', value: job.alert?.sent ? '✓ Sent' : 'Not sent' },
          ].map(s => (
            <div key={s.label} className="stat-chip" style={{ flex: 1, minWidth: 120 }}>
              <div>
                <div className="stat-num">{s.value}</div>
                <div className="text-xs text-muted">{s.label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      <DetectionLog entries={detectionLog} title="Video Detection Timeline" maxHeight="380px" />
    </div>
  )
}
