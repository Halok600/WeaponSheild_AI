import { useState, useRef, useEffect } from 'react'
import api from '../api/axiosClient'
import AlertBadge from './AlertBadge'
import DetectionLog from './DetectionLog'
import { IconVideo, IconUpload, IconPlay, IconCheck, IconAlert, IconSend, IconSettings, IconZap } from './Icons'

const POLL_MS = 1500

export default function VideoDetection() {
  const [file, setFile]             = useState(null)
  const [jobId, setJobId]           = useState(null)
  const [job, setJob]               = useState(null)
  const [uploading, setUploading]   = useState(false)
  const [uploadPct, setUploadPct]   = useState(0)
  const [error, setError]           = useState(null)
  const [dragOver, setDragOver]     = useState(false)
  const pollRef = useRef(null)
  const inputRef = useRef()

  const [stopOnFirst, setStopOnFirst]         = useState(false)
  const [frameSkip, setFrameSkip]             = useState(0)
  const [addNoise, setAddNoise]               = useState(false)
  const [blurStrength, setBlurStrength]       = useState(0)
  const [lowRes, setLowRes]                   = useState(false)
  const [confThreshold, setConfThreshold]     = useState(0.15)
  const [usedConfThreshold, setUsedConfThreshold] = useState(null)
  const [thresholdChanged, setThresholdChanged]   = useState(false)

  useEffect(() => {
    if (!jobId) return
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.get(`/detect/video/${jobId}`)
        setJob(data)
        if (data.status === 'done' || data.status === 'error') clearInterval(pollRef.current)
      } catch { /* ignore */ }
    }, POLL_MS)
    return () => clearInterval(pollRef.current)
  }, [jobId])

  const handleFile = (f) => { if (!f) return; setFile(f); setJob(null); setJobId(null); setError(null) }
  const handleDrop = (e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]) }

  const handleSubmit = async () => {
    if (!file) return
    setUploading(true); setUploadPct(0); setError(null); setJob(null); setJobId(null); setThresholdChanged(false)
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
        onUploadProgress: (e) => { if (e.total) setUploadPct(Math.round((e.loaded / e.total) * 100)) }
      })
      setJobId(data.job_id)
      setJob({ status: 'queued', processed_frames: 0, total_frames: 0, detection_log: [] })
    } catch (err) {
      setError(err?.response?.data?.detail || 'Upload failed.')
    } finally { setUploading(false) }
  }

  const isProcessing = job?.status === 'processing' || job?.status === 'queued'
  const isDone       = job?.status === 'done'
  const isError      = job?.status === 'error'
  const progress     = job?.total_frames ? Math.round((job.processed_frames / job.total_frames) * 100) : 0
  const detectionLog = job?.detection_log ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', paddingTop: '1rem' }}>
      <AlertBadge active={isDone && job?.weapon_detected} message={`First detection at ${detectionLog[0]?.timestamp ?? '—'}`} />

      {/* ── Upload + Options ── */}
      <div className="card card-hover">
        <div className="flex items-center gap-3 mb-4">
          <div style={{
            width: 36, height: 36, background: 'hsla(0,76%,55%,0.1)',
            borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <IconVideo size={18} style={{ color: 'var(--accent)' }} />
          </div>
          <div>
            <h2>CCTV Video Detection</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2 }}>Upload surveillance footage for weapon analysis</p>
          </div>
        </div>

        {/* Dropzone */}
        <div
          className={`dropzone ${dragOver ? 'drag-over' : ''}`}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current.click()}
        >
          <input ref={inputRef} type="file" accept="video/*" style={{ display: 'none' }} onChange={e => handleFile(e.target.files[0])} />
          <div className="dropzone-icon"><IconUpload size={32} /></div>
          <div className="dropzone-text">{file ? file.name : 'Drop a video file or click to browse'}</div>
          <div className="dropzone-hint">MP4 · AVI · MOV · MKV</div>
        </div>

        {/* Options */}
        <div style={{ marginTop: '1.25rem' }}>
          <div className="flex items-center gap-2 mb-3">
            <IconSettings size={13} style={{ color: 'var(--text-muted)' }} />
            <div className="section-label" style={{ marginBottom: 0 }}>Processing Options</div>
          </div>
          <div className="options-panel">
            {[
              { label: 'Stop on First Detection', desc: 'Halt processing when a weapon is found', val: stopOnFirst, set: setStopOnFirst },
              { label: 'CCTV Noise Simulation', desc: 'Add realistic noise to test robustness', val: addNoise, set: setAddNoise },
              { label: 'Low-Res (Pixelate)', desc: 'Simulate low-quality camera footage', val: lowRes, set: setLowRes },
            ].map(({ label, desc, val, set }) => (
              <div key={label} className="toggle-row">
                <div className="toggle-info">
                  <div className="toggle-title">{label}</div>
                  <div className="toggle-desc">{desc}</div>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={val} onChange={e => set(e.target.checked)} />
                  <div className="toggle-track" />
                  <div className="toggle-thumb" />
                </label>
              </div>
            ))}
          </div>

          <div className="sliders-row">
            <div className="slider-wrap">
              <div className="slider-label">
                <span className="slider-name">Frame Skip</span>
                <span className="slider-val">{frameSkip}</span>
              </div>
              <input type="range" min={0} max={10} value={frameSkip} onChange={e => setFrameSkip(Number(e.target.value))} />
              <div className="text-xs text-muted mt-1">Frames to skip between inferences</div>
            </div>
            <div className="slider-wrap">
              <div className="slider-label">
                <span className="slider-name">Blur</span>
                <span className="slider-val">{blurStrength}px</span>
              </div>
              <input type="range" min={0} max={21} step={2} value={blurStrength} onChange={e => setBlurStrength(Number(e.target.value))} />
            </div>
            <div className="slider-wrap">
              <div className="slider-label">
                <span className="slider-name">Confidence</span>
                <span className="slider-val">{(confThreshold * 100).toFixed(0)}%</span>
              </div>
              <input type="range" min={1} max={90} value={Math.round(confThreshold * 100)} onChange={e => { setConfThreshold(Number(e.target.value) / 100); if (isDone) setThresholdChanged(true) }} />
              <div className="text-xs text-muted mt-1">Lower = more sensitive (5–15% for video)</div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 mt-4" style={{ flexWrap: 'wrap' }}>
          <button id="video-detect-btn" className="btn btn-primary" onClick={handleSubmit} disabled={!file || uploading || isProcessing}>
            {uploading ? <><span className="spinner" /> Uploading {uploadPct}%…</>
              : isProcessing ? <><span className="spinner" /> Processing…</>
              : <><IconPlay size={15} /> Start Detection</>}
          </button>
          {file && !isProcessing && !uploading && (
            <button className="btn btn-secondary" onClick={() => { setFile(null); setJob(null); setJobId(null) }}>Clear</button>
          )}
          {isDone && (
            <span className={`badge ${job.weapon_detected ? 'badge-danger' : 'badge-success'}`}>
              {job.weapon_detected ? <><IconAlert size={11} /> {detectionLog.length} detection(s)</> : <><IconCheck size={11} /> No Weapon Found</>}
            </span>
          )}
        </div>

        {thresholdChanged && isDone && (
          <div className="warn-box mt-3">
            <IconZap size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>Confidence changed to {(confThreshold * 100).toFixed(0)}% — re-run to apply. Current results used {usedConfThreshold !== null ? (usedConfThreshold * 100).toFixed(0) : '?'}%.</span>
          </div>
        )}
        {error && <div className="error-box mt-3"><span>⚠</span><span>{error}</span></div>}
      </div>

      {/* ── Progress ── */}
      {(isProcessing || isDone) && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3>{isProcessing ? `Processing… Frame ${job.processed_frames} / ${job.total_frames || '?'}` : `✓ Complete — ${job.processed_frames} frames`}</h3>
            <span className="font-mono text-sm text-accent" style={{ fontWeight: 700 }}>{isDone ? 100 : progress}%</span>
          </div>
          <div className="progress-wrap">
            <div className="progress-bar" style={{ width: `${isDone ? 100 : progress}%` }} />
          </div>
          {job.stopped_early && <div className="text-xs text-amber mt-2">⚡ Stopped after first detection</div>}
        </div>
      )}

      {/* ── Video output + Stats ── */}
      {isDone && (
        <div className="two-col">
          {job.output_url && (
            <div className="card" style={{ padding: '1rem' }}>
              <div className="section-label mb-3">Processed Output</div>
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <video key={job.output_url} controls style={{ width: '100%', borderRadius: 'var(--radius-lg)', background: '#000' }}>
                <source src={job.output_url} type="video/mp4" />
              </video>
            </div>
          )}
          <div className="flex flex-col gap-3">
            {[
              { label: 'Frames Processed', value: job.processed_frames, color: 'var(--cyan)' },
              { label: 'Detections Found', value: detectionLog.length, color: detectionLog.length > 0 ? 'var(--danger)' : 'var(--accent-green)' },
              { label: 'SMS Alert', value: job.alert?.sent ? '✓ Sent' : '— Not Sent', color: job.alert?.sent ? 'var(--accent-green)' : 'var(--text-muted)' },
            ].map(s => (
              <div key={s.label} className="kpi-card">
                <div className="kpi-num" style={{ color: s.color }}>{s.value}</div>
                <div className="kpi-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {isError && (
        <div className="card card-danger">⚠ Processing error: {job.error}</div>
      )}

      <DetectionLog entries={detectionLog} title="Video Detection Timeline" maxHeight="380px" />
    </div>
  )
}
