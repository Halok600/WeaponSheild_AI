import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api/axiosClient'
import AlertBadge from './AlertBadge'
import { IconCamera, IconPlay, IconStop, IconCheck, IconAlert, IconInfo, IconEye, IconActivity } from './Icons'

const CAPTURE_MS   = 600   // interval between frames sent to the backend
const CAPTURE_WIDTH = 640  // frames are downscaled to this before upload

export default function WebcamDetection({ alertEmail }) {
  const [active, setActive]             = useState(false)
  const [error, setError]               = useState(null)
  const [devices, setDevices]           = useState([])
  const [deviceId, setDeviceId]         = useState('')
  const [detections, setDetections]     = useState([])
  const [threatConfirmed, setThreatConfirmed] = useState(false)
  const [avgConf, setAvgConf]           = useState(0)
  const [posFrames, setPosFrames]       = useState(0)
  const [winSize, setWinSize]           = useState(0)
  const [reqRate, setReqRate]           = useState(0)
  const [alertVisible, setAlertVisible] = useState(false)
  const [alertDismissed, setAlertDismissed] = useState(false)
  const [alertInfo, setAlertInfo]       = useState(null)

  const videoRef        = useRef()
  const overlayRef       = useRef()
  const captureCanvasRef = useRef()
  const streamRef        = useRef(null)
  const loopRef          = useRef(null)
  const sessionIdRef      = useRef(null)
  const inFlightRef       = useRef(false)
  const audioCtxRef       = useRef(null)
  const prevConfirmedRef  = useRef(false)

  // ── Enumerate available cameras (labels populate after permission granted) ──
  useEffect(() => {
    if (!navigator.mediaDevices?.enumerateDevices) return
    navigator.mediaDevices.enumerateDevices().then(list => {
      const cams = list.filter(d => d.kind === 'videoinput')
      setDevices(cams)
      if (cams.length && !deviceId) setDeviceId(cams[0].deviceId)
    }).catch(() => {})
  }, [])

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

  const drawOverlay = useCallback((dets, frameW, frameH) => {
    const canvas = overlayRef.current
    const video  = videoRef.current
    if (!canvas || !video) return
    const dw = video.clientWidth, dh = video.clientHeight
    canvas.width = dw
    canvas.height = dh
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, dw, dh)
    if (!frameW || !frameH) return
    const sx = dw / frameW, sy = dh / frameH
    dets.forEach(d => {
      const [x1, y1, x2, y2] = d.bbox
      const rx = x1 * sx, ry = y1 * sy, rw = (x2 - x1) * sx, rh = (y2 - y1) * sy
      ctx.strokeStyle = '#e63946'
      ctx.lineWidth = 2
      ctx.strokeRect(rx, ry, rw, rh)
      const text = `${d.label} ${(d.confidence * 100).toFixed(0)}%`
      ctx.font = '600 13px sans-serif'
      const tw = ctx.measureText(text).width
      const ty = Math.max(ry - 18, 0)
      ctx.fillStyle = '#e63946'
      ctx.fillRect(rx, ty, tw + 8, 18)
      ctx.fillStyle = '#fff'
      ctx.fillText(text, rx + 4, ty + 13)
    })
  }, [])

  const sendFrame = useCallback(async () => {
    const video = videoRef.current
    if (!video || video.readyState < 2 || inFlightRef.current) return
    inFlightRef.current = true
    try {
      const vw = video.videoWidth, vh = video.videoHeight
      if (!vw || !vh) return
      const scale = Math.min(1, CAPTURE_WIDTH / vw)
      const cw = Math.round(vw * scale), ch = Math.round(vh * scale)
      const canvas = captureCanvasRef.current
      canvas.width = cw
      canvas.height = ch
      canvas.getContext('2d').drawImage(video, 0, 0, cw, ch)

      const blob = await new Promise(res => canvas.toBlob(res, 'image/jpeg', 0.7))
      if (!blob) return

      const form = new FormData()
      form.append('file', blob, 'frame.jpg')
      form.append('session_id', sessionIdRef.current)
      if (alertEmail) form.append('alert_email', alertEmail)

      const t0 = performance.now()
      const { data } = await api.post('/detect/webcam/frame', form)
      setReqRate(Math.round(1000 / Math.max(performance.now() - t0, 1) * 10) / 10)

      setDetections(data.detections || [])
      setThreatConfirmed(data.threat_confirmed)
      setAvgConf(data.avg_confidence || 0)
      setPosFrames(data.positive_frames || 0)
      setWinSize(data.window_size || 0)
      drawOverlay(data.detections || [], data.frame_width, data.frame_height)

      if (data.threat_confirmed && !prevConfirmedRef.current && !alertDismissed) {
        const top = data.detections?.[0]
        setAlertInfo({ label: top?.label ?? 'Weapon', confidence: top?.confidence ?? data.avg_confidence ?? 0, time: new Date().toLocaleTimeString() })
        setAlertVisible(true); playAlarm()
      }
      prevConfirmedRef.current = data.threat_confirmed
      if (!data.threat_confirmed && (data.positive_frames ?? 0) === 0) { setAlertDismissed(false) }
    } catch {
      /* transient network error — next tick will retry */
    } finally {
      inFlightRef.current = false
    }
  }, [alertEmail, alertDismissed, playAlarm, drawOverlay])

  const handleStart = async () => {
    setError(null)
    setAlertVisible(false); setAlertDismissed(false); prevConfirmedRef.current = false
    setDetections([]); setThreatConfirmed(false); setAvgConf(0); setPosFrames(0); setWinSize(0)

    if (!navigator.mediaDevices?.getUserMedia) {
      setError('This browser does not support camera access (getUserMedia unavailable).')
      return
    }
    try {
      sessionIdRef.current = crypto.randomUUID()
      const constraints = { video: deviceId ? { deviceId: { exact: deviceId } } : true }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      streamRef.current = stream
      videoRef.current.srcObject = stream
      await videoRef.current.play()
      setActive(true)
      loopRef.current = setInterval(sendFrame, CAPTURE_MS)
    } catch (err) {
      setError(err?.message || 'Could not access the camera. Check browser permissions.')
    }
  }

  const handleStop = async () => {
    clearInterval(loopRef.current)
    loopRef.current = null
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    const canvas = overlayRef.current
    if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height)
    setActive(false); setAlertVisible(false)
    if (sessionIdRef.current) {
      try {
        const form = new FormData()
        form.append('session_id', sessionIdRef.current)
        await api.post('/detect/webcam/stop', form)
      } catch { /* ignore */ }
    }
  }

  useEffect(() => () => { // cleanup on unmount
    clearInterval(loopRef.current)
    streamRef.current?.getTracks().forEach(t => t.stop())
  }, [])

  const dismissAlert = () => { setAlertVisible(false); setAlertDismissed(true) }

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
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2 }}>Your browser captures frames locally and sends them for detection</p>
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
              <span className="badge badge-info font-mono">{reqRate} req/s</span>
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
            <select value={deviceId} onChange={e => setDeviceId(e.target.value)} disabled={active}>
              {devices.length === 0 && <option value="">Default camera</option>}
              {devices.map((d, i) => (
                <option key={d.deviceId} value={d.deviceId}>{d.label || `Camera ${i + 1}`}</option>
              ))}
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
          <div style={{ position: 'relative', display: active ? 'block' : 'none' }}>
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video ref={videoRef} muted playsInline className="webcam-frame" />
            <canvas ref={overlayRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }} />
          </div>
          {!active && (
            <div className="webcam-placeholder">
              <IconCamera size={40} style={{ opacity: 0.3 }} />
              <span style={{ fontSize: '0.9rem' }}>Start the live feed to see the stream</span>
              <span className="text-xs text-muted">Uses your browser's camera — nothing is sent until you click Start</span>
            </div>
          )}
          <canvas ref={captureCanvasRef} style={{ display: 'none' }} />
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
                <li>Captured entirely in your browser — the server never accesses a camera directly.</li>
                <li>A frame is sent for detection roughly every {(CAPTURE_MS / 1000).toFixed(1)}s.</li>
                <li>Works the same locally and once deployed to the cloud.</li>
                <li>Alarm sounds and modal appears on weapon confirmation.</li>
                <li>Email alerts are rate-limited to one per 60 seconds.</li>
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
