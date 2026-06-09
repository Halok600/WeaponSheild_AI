import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api/axiosClient'
import AlertBadge from './AlertBadge'

const STREAM_URL = '/detect/webcam/stream'
const STATUS_URL = '/detect/webcam/status'
const POLL_MS = 600

export default function WebcamDetection() {
  const [active, setActive] = useState(false)
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [cameraIdx, setCameraIdx] = useState(0)
  const [alertVisible, setAlertVisible] = useState(false)
  const [alertDismissed, setAlertDismissed] = useState(false)
  const [alertInfo, setAlertInfo] = useState(null)
  const pollRef = useRef(null)
  const imgRef = useRef()
  const audioCtxRef = useRef(null)
  const prevConfirmedRef = useRef(false)

  /* ── Alarm beep via Web Audio API ────────────────────────────────────── */
  const playAlarm = useCallback(() => {
    try {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)()
      }
      const ctx = audioCtxRef.current
      const playBeep = (startTime, freq, dur) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.type = 'square'
        osc.frequency.setValueAtTime(freq, startTime)
        gain.gain.setValueAtTime(0.4, startTime)
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + dur)
        osc.start(startTime)
        osc.stop(startTime + dur)
      }
      // Three urgent beeps
      const now = ctx.currentTime
      playBeep(now + 0.0, 880, 0.18)
      playBeep(now + 0.22, 880, 0.18)
      playBeep(now + 0.44, 1100, 0.35)
    } catch { /* audio blocked — silent */ }
  }, [])

  /* ── Poll detection status ──────────────────────────────────────────── */
  useEffect(() => {
    if (!active) { clearInterval(pollRef.current); return }

    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.get(STATUS_URL)
        setStatus(data)

        // ── Trigger alert on FIRST confirmation ─────────────────────────
        const confirmed = data.threat_confirmed || data.weapon_detected
        if (confirmed && !prevConfirmedRef.current && !alertDismissed) {
          const topDet = data.detections?.[0]
          setAlertInfo({
            label:      topDet?.label ?? 'Weapon',
            confidence: topDet?.confidence ?? data.avg_confidence ?? 0,
            time:       new Date().toLocaleTimeString(),
          })
          setAlertVisible(true)
          playAlarm()
        }
        prevConfirmedRef.current = confirmed

        // Re-arm alert when threat clears (buffer fully empty)
        if (!confirmed && (data.positive_frames ?? 0) === 0) {
          prevConfirmedRef.current = false
          setAlertDismissed(false)
        }
      } catch { /* ignore transient */ }
    }, POLL_MS)

    return () => clearInterval(pollRef.current)
  }, [active, alertDismissed, playAlarm])

  const handleStart = () => {
    setError(null)
    setStatus(null)
    setActive(true)
    setAlertVisible(false)
    setAlertDismissed(false)
    prevConfirmedRef.current = false
  }

  const handleStop = async () => {
    setActive(false)
    setAlertVisible(false)
    try { await api.post('/detect/webcam/stop') } catch { /* ignore */ }
  }

  const dismissAlert = () => {
    setAlertVisible(false)
    setAlertDismissed(true)
  }

  const detections = status?.detections ?? []
  const fps = status?.fps ?? 0
  const threatConfirmed = status?.threat_confirmed || status?.weapon_detected || false
  const posFrames = status?.positive_frames ?? 0
  const winSize   = status?.window_size ?? 0
  const avgConf   = status?.avg_confidence ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

      {/* ── Fullscreen-style alert modal ──────────────────────────────── */}
      {alertVisible && alertInfo && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(6px)',
          animation: 'fadeIn 0.2s ease',
        }}>
          <div style={{
            background: 'hsl(222,18%,14%)',
            border: '2px solid var(--accent)',
            borderRadius: 'var(--radius-lg)',
            padding: '2.5rem 3rem',
            textAlign: 'center',
            maxWidth: 420,
            boxShadow: '0 0 60px hsla(0,80%,58%,0.4)',
            animation: 'slideUp 0.3s ease',
          }}>
            <div style={{ fontSize: '3.5rem', marginBottom: '0.5rem' }}>🚨</div>
            <div style={{
              fontSize: '1.6rem', fontWeight: 800,
              color: 'var(--accent)', marginBottom: '0.5rem',
              letterSpacing: '-0.02em',
            }}>
              WEAPON DETECTED
            </div>
            <div style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
              <div><strong style={{ color: 'var(--text-primary)' }}>{alertInfo.label}</strong> detected in live feed</div>
              <div style={{ marginTop: '0.25rem' }}>
                Confidence: <strong style={{ color: 'var(--accent)' }}>{(alertInfo.confidence * 100).toFixed(1)}%</strong>
                &nbsp;·&nbsp; Time: <strong>{alertInfo.time}</strong>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button
                className="btn btn-primary"
                onClick={dismissAlert}
                style={{ padding: '0.65rem 1.75rem', fontSize: '0.9rem' }}
              >
                ✓ Acknowledge
              </button>
              <button
                className="btn btn-secondary"
                onClick={handleStop}
              >
                ⏹ Stop Feed
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Persistent top toast (visible after dismissing modal) ─────── */}
      <AlertBadge
        active={active && threatConfirmed && !alertVisible}
        message="⚠️ Threat confirmed — weapon detected in live feed"
      />

      {/* Controls */}
      <div className="card">
        <div className="flex items-center justify-between" style={{ marginBottom: '1rem' }}>
          <h2>📷 Live Webcam Detection</h2>
          {active && (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <div className="pulse-dot" style={{ background: threatConfirmed ? 'var(--accent)' : 'var(--accent-green)' }} />
                <span className={`text-sm font-mono ${threatConfirmed ? 'text-accent' : 'text-green'}`}>
                  {threatConfirmed ? '⚠️ THREAT' : 'LIVE'}
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

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <div className="section-label">Camera Index</div>
            <select value={cameraIdx} onChange={e => setCameraIdx(Number(e.target.value))} disabled={active}>
              <option value={0}>Camera 0 (default)</option>
              <option value={1}>Camera 1</option>
              <option value={2}>Camera 2</option>
            </select>
          </div>

          {!active ? (
            <button
              id="webcam-start-btn"
              className="btn btn-primary"
              onClick={handleStart}
              style={{ marginTop: '1.25rem' }}
            >
              ▶ Start Live Feed
            </button>
          ) : (
            <button
              className="btn btn-secondary"
              onClick={handleStop}
              style={{ marginTop: '1.25rem' }}
            >
              ⏹ Stop
            </button>
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

      {/* Stream */}
      <div className="card" style={{ padding: '0.75rem', position: 'relative' }}>
        {/* Threat overlay border flash */}
        {active && threatConfirmed && (
          <div style={{
            position: 'absolute', inset: 6, borderRadius: 'var(--radius-md)',
            border: '3px solid var(--accent)',
            boxShadow: '0 0 24px var(--accent-glow)',
            pointerEvents: 'none', zIndex: 2,
            animation: 'pulse 1s ease-out infinite',
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
            <span style={{ fontSize: '3rem' }}>📷</span>
            <span>Start the live feed to see the MJPEG stream</span>
            <span className="text-xs text-muted">Requires webcam access on the server machine</span>
          </div>
        )}
      </div>

      {/* Threat status bar */}
      {active && (
        <div className="card" style={{
          background: threatConfirmed ? 'hsla(0,80%,58%,0.08)' : 'hsla(145,65%,48%,0.05)',
          borderColor: threatConfirmed ? 'var(--accent)' : 'hsla(145,65%,48%,0.3)',
          padding: '0.85rem 1.25rem',
        }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="pulse-dot" style={{
                background: threatConfirmed ? 'var(--accent)' : 'var(--accent-green)',
              }} />
              <span style={{
                fontWeight: 700, fontSize: '0.9rem',
                color: threatConfirmed ? 'var(--accent)' : 'var(--accent-green)',
              }}>
                {threatConfirmed ? '⚠️ THREAT CONFIRMED' : '✅ SCANNING — Area Clear'}
              </span>
            </div>
            {avgConf > 0 && (
              <span className="badge badge-info font-mono" style={{ fontSize: '0.72rem' }}>
                avg conf {(avgConf * 100).toFixed(1)}%
              </span>
            )}
          </div>
        </div>
      )}

      {/* Live detections */}
      {active && detections.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: '0.85rem' }}>Live Detections</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {detections.map((d, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '1rem',
                padding: '0.5rem 0.85rem',
                background: 'hsla(0,80%,58%,0.07)',
                border: '1px solid var(--accent)',
                borderRadius: 'var(--radius-md)',
              }}>
                <div className="pulse-dot" />
                <span className="badge badge-danger">{d.label}</span>
                <div className="conf-bar-wrap">
                  <div className="conf-bar" style={{ width: `${(d.confidence * 100).toFixed(0)}%` }} />
                </div>
                <span className="font-mono text-sm text-accent">
                  {(d.confidence * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tips */}
      {!active && (
        <div className="card" style={{ background: 'hsla(210,90%,60%,0.05)', borderColor: 'hsla(210,90%,60%,0.3)' }}>
          <h3 style={{ color: 'var(--accent-blue)', marginBottom: '0.75rem' }}>ℹ️ Webcam Mode Notes</h3>
          <ul style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', paddingLeft: '1.25rem', lineHeight: 2 }}>
            <li>The MJPEG stream is served directly by the FastAPI backend.</li>
            <li>The backend machine must have a camera connected at the given index.</li>
            <li>FPS depends on hardware — typically 10–25 fps on CPU.</li>
            <li>An alarm sounds and a modal appears immediately when a weapon is confirmed.</li>
            <li>SMS alerts are rate-limited to one per 60 seconds.</li>
          </ul>
        </div>
      )}

      <style>{`
        @keyframes fadeIn { from { opacity:0 } to { opacity:1 } }
        @keyframes slideUp { from { opacity:0; transform:translateY(30px) } to { opacity:1; transform:translateY(0) } }
      `}</style>
    </div>
  )
}
