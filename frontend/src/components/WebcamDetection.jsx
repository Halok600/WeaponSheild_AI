import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api/axiosClient'
import AlertBadge from './AlertBadge'
import { IconCamera, IconPlay, IconStop, IconCheck, IconAlert, IconInfo, IconEye, IconActivity } from './Icons'

const STREAM_URL = '/detect/webcam/stream'
const STATUS_URL = '/detect/webcam/status'
const POLL_MS    = 600

export default function WebcamDetection() {
  const [active, setActive]             = useState(false)
  const [status, setStatus]             = useState(null)
  const [error, setError]               = useState(null)
  const [cameraIdx, setCameraIdx]       = useState(0)
  const [alertVisible, setAlertVisible] = useState(false)
  const [alertDismissed, setAlertDismissed] = useState(false)
  const [alertInfo, setAlertInfo]       = useState(null)
  const pollRef    = useRef(null)
  const imgRef     = useRef()
  const audioCtxRef = useRef(null)
  const prevConfirmedRef = useRef(false)

  const playAlarm = useCallback(() => {
    try {
      if (!audioCtxRef.current) audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)()
      const ctx = audioCtxRef.current
      const playBeep = (t, f, d) => {
        const osc = ctx.createOscillator(), gain = ctx.createGain()
        osc.connect(gain); gain.connect(ctx.destination)
        osc.type = 'square'; osc.frequency.setValueAtTime(f, t)
        gain.gain.setValueAtTime(0.4, t); gain.gain.exponentialRampToValueAtTime(0.001, t + d)
        osc.start(t); osc.stop(t + d)
      }
      const now = ctx.currentTime
      playBeep(now + 0.0, 880, 0.18); playBeep(now + 0.22, 880, 0.18); playBeep(now + 0.44, 1100, 0.35)
    } catch { /* audio blocked */ }
  }, [])

  useEffect(() => {
    if (!active) { clearInterval(pollRef.current); return }
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.get(STATUS_URL)
        setStatus(data)
        const confirmed = data.threat_confirmed || data.weapon_detected
        if (confirmed && !prevConfirmedRef.current && !alertDismissed) {
          const top = data.detections?.[0]
          setAlertInfo({ label: top?.label ?? 'Weapon', confidence: top?.confidence ?? data.avg_confidence ?? 0, time: new Date().toLocaleTimeString() })
          setAlertVisible(true); playAlarm()
        }
        prevConfirmedRef.current = confirmed
        if (!confirmed && (data.positive_frames ?? 0) === 0) { prevConfirmedRef.current = false; setAlertDismissed(false) }
      } catch { /* ignore */ }
    }, POLL_MS)
    return () => clearInterval(pollRef.current)
  }, [active, alertDismissed, playAlarm])

  const handleStart = () => { setError(null); setStatus(null); setActive(true); setAlertVisible(false); setAlertDismissed(false); prevConfirmedRef.current = false }
  const handleStop  = async () => { setActive(false); setAlertVisible(false); try { await api.post('/detect/webcam/stop') } catch { /* ignore */ } }
  const dismissAlert = () => { setAlertVisible(false); setAlertDismissed(true) }

  const detections    = status?.detections ?? []
  const fps           = status?.fps ?? 0
  const threatConfirmed = status?.threat_confirmed || status?.weapon_detected || false
  const posFrames     = status?.positive_frames ?? 0
  const winSize       = status?.window_size ?? 0
  const avgConf       = status?.avg_confidence ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', paddingTop: '1rem' }}>

      {/* ── Threat modal ── */}
      {alertVisible && alertInfo && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && dismissAlert()}>
          <div className="modal-box">
            <div style={{ fontSize: '3rem', marginBottom: '0.75rem', lineHeight: 1 }}>🚨</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--accent)', letterSpacing: '-0.02em', marginBottom: '0.5rem' }}>
              WEAPON DETECTED
            </div>
            <div style={{ color: 'var(--text-secondary)', marginBottom: '1.75rem', fontSize: '0.9rem', lineHeight: 1.7 }}>
              <strong style={{ color: 'var(--text-primary)' }}>{alertInfo.label}</strong> detected in live feed<br />
              Confidence: <strong style={{ color: 'var(--accent)' }}>{(alertInfo.confidence * 100).toFixed(1)}%</strong>
              &nbsp;·&nbsp; Time: <strong>{alertInfo.time}</strong>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button className="btn btn-primary" onClick={dismissAlert} style={{ padding: '0.7rem 2rem' }}>
                <IconCheck size={15} /> Acknowledge
              </button>
              <button className="btn btn-secondary" onClick={handleStop}>
                <IconStop size={15} /> Stop Feed
              </button>
            </div>
          </div>
        </div>
      )}

      <AlertBadge active={active && threatConfirmed && !alertVisible} message="⚠ Threat confirmed — weapon detected in live feed" />

      {/* ── Controls ── */}
      <div className="card card-hover">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div style={{
              width: 36, height: 36, background: 'hsla(0,76%,55%,0.1)',
              borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <IconCamera size={18} style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <h2>Live Webcam Detection</h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2 }}>Real-time MJPEG stream with weapon detection overlay</p>
            </div>
          </div>

          {active && (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <div className="pulse-dot" style={{ background: threatConfirmed ? 'var(--accent)' : 'var(--accent-green)' }} />
                <span className={`text-sm font-mono ${threatConfirmed ? 'text-accent' : 'text-green'}`} style={{ fontWeight: 700 }}>
                  {threatConfirmed ? 'THREAT' : 'LIVE'}
                </span>
              </div>
              <span className="badge badge-info font-mono">{fps} FPS</span>
              {winSize > 0 && (
                <span className={`badge ${threatConfirmed ? 'badge-danger' : 'badge-warning'}`}>
                  {posFrames}/{winSize} frames
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-4" style={{ flexWrap: 'wrap' }}>
          <div>
            <div className="section-label">Camera Source</div>
            <select value={cameraIdx} onChange={e => setCameraIdx(Number(e.target.value))} disabled={active}>
              <option value={0}>Camera 0 (default)</option>
              <option value={1}>Camera 1</option>
              <option value={2}>Camera 2</option>
            </select>
          </div>
          {!active ? (
            <button id="webcam-start-btn" className="btn btn-primary" onClick={handleStart} style={{ marginTop: '1.2rem' }}>
              <IconPlay size={15} /> Start Live Feed
            </button>
          ) : (
            <button className="btn btn-danger" onClick={handleStop} style={{ marginTop: '1.2rem' }}>
              <IconStop size={15} /> Stop Feed
            </button>
          )}
        </div>

        {error && <div className="error-box mt-3"><span>⚠</span><span>{error}</span></div>}
      </div>

      {/* ── Stream + status ── */}
      <div className="two-col" style={{ alignItems: 'start' }}>
        {/* Left: video frame */}
        <div className="card" style={{ padding: '0.75rem', position: 'relative' }}>
          {active && threatConfirmed && (
            <div style={{
              position: 'absolute', inset: 6, borderRadius: 'var(--radius-lg)',
              border: '2px solid var(--accent)', boxShadow: '0 0 24px var(--accent-glow)',
              pointerEvents: 'none', zIndex: 2, animation: 'pulse 1s ease-out infinite',
            }} />
          )}
          {active ? (
            <img
              ref={imgRef}
              src={`${STREAM_URL}?camera=${cameraIdx}&t=${Date.now()}`}
              alt="Live webcam MJPEG stream with weapon detection overlay"
              className="webcam-frame"
              onError={() => setError('Stream connection failed. Check camera access and backend.')}
            />
          ) : (
            <div className="webcam-placeholder">
              <IconCamera size={40} style={{ opacity: 0.3 }} />
              <span style={{ fontSize: '0.9rem' }}>Start the live feed to see the stream</span>
              <span className="text-xs text-muted">Requires webcam on the server machine</span>
            </div>
          )}
        </div>

        {/* Right: status + detections */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          {/* Threat status */}
          {active && (
            <div className={`card ${threatConfirmed ? 'card-danger' : 'card-success'}`} style={{ padding: '1rem 1.25rem' }}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="pulse-dot" style={{ background: threatConfirmed ? 'var(--accent)' : 'var(--accent-green)' }} />
                  <span style={{ fontWeight: 700, fontSize: '0.9rem', color: threatConfirmed ? 'var(--accent)' : 'var(--accent-green)' }}>
                    {threatConfirmed ? '⚠ THREAT CONFIRMED' : '✓ SCANNING — Clear'}
                  </span>
                </div>
                {avgConf > 0 && (
                  <span className="badge badge-info font-mono" style={{ fontSize: '0.7rem' }}>
                    avg {(avgConf * 100).toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Live detections */}
          {active && detections.length > 0 && (
            <div className="card">
              <div className="flex items-center gap-2 mb-3">
                <IconActivity size={14} style={{ color: 'var(--accent)' }} />
                <h3>Live Detections</h3>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {detections.map((d, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: '0.85rem',
                    padding: '0.6rem 0.85rem',
                    background: 'hsla(0,76%,55%,0.07)',
                    border: '1px solid hsla(0,76%,55%,0.2)',
                    borderRadius: 'var(--radius-md)',
                  }}>
                    <div className="pulse-dot" />
                    <span className="badge badge-danger">{d.label}</span>
                    <div className="conf-bar-wrap" style={{ flex: 1 }}>
                      <div className="conf-bar" style={{ width: `${(d.confidence * 100).toFixed(0)}%` }} />
                    </div>
                    <span className="font-mono text-sm text-accent" style={{ fontWeight: 700 }}>
                      {(d.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Info card (when idle) */}
          {!active && (
            <div className="card card-info">
              <div className="flex items-center gap-2 mb-3">
                <IconInfo size={15} style={{ color: 'var(--accent-blue)' }} />
                <h3 style={{ color: 'var(--accent-blue)' }}>Webcam Mode Notes</h3>
              </div>
              <ul style={{ color: 'var(--text-secondary)', fontSize: '0.83rem', paddingLeft: '1.1rem', lineHeight: 2.1 }}>
                <li>MJPEG stream is served directly by the FastAPI backend.</li>
                <li>Backend machine must have a camera at the given index.</li>
                <li>FPS typically 10–25 on CPU hardware.</li>
                <li>Alarm sounds and modal appears on weapon confirmation.</li>
                <li>SMS alerts are rate-limited to one per 60 seconds.</li>
              </ul>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity:0 } to { opacity:1 } }
      `}</style>
    </div>
  )
}
