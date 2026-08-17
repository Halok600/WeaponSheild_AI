import { useState, useEffect } from 'react'
import './index.css'
import ImageDetection from './components/ImageDetection'
import VideoDetection from './components/VideoDetection'
import WebcamDetection from './components/WebcamDetection'
import { IconVideo, IconImage, IconCamera, IconMail, IconCheck } from './components/Icons'
import api from './api/axiosClient'

const TABS = [
  { id: 'video',  label: 'CCTV Video',  Icon: IconVideo,  desc: 'Upload & analyse surveillance footage' },
  { id: 'image',  label: 'Image Scan',  Icon: IconImage,  desc: 'Detect weapons in a single image' },
  { id: 'webcam', label: 'Live Webcam', Icon: IconCamera, desc: 'Real-time webcam stream detection' },
]

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const ALERT_EMAIL_KEY = 'weaponshield_alert_email'

export default function App() {
  const [tab, setTab] = useState('video')
  const [backendOk, setBackendOk] = useState(null)
  const [alertEmail, setAlertEmail] = useState(() => localStorage.getItem(ALERT_EMAIL_KEY) || '')

  useEffect(() => {
    api.get('/health')
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false))
  }, [])

  const emailValid = EMAIL_RE.test(alertEmail.trim())

  const handleEmailChange = (value) => {
    setAlertEmail(value)
    if (EMAIL_RE.test(value.trim())) {
      localStorage.setItem(ALERT_EMAIL_KEY, value.trim())
    } else if (!value.trim()) {
      localStorage.removeItem(ALERT_EMAIL_KEY)
    }
  }

  return (
    <div className="app-shell">
      {/* ── Header ── */}
      <header className="header">
        <div className="container">
          <div className="header-inner">

            {/* Logo */}
            <a href="/" className="logo" aria-label="WeaponShield AI home">
              <img src="/logo.png" alt="WeaponShield AI" className="logo-img" />
              <div>
                <div className="logo-text">WeaponShield AI</div>
                <div className="logo-sub">Surveillance Detection System</div>
              </div>
            </a>

            {/* Centre: Tab nav */}
            <nav className="tabs header-tabs" aria-label="Detection mode">
              {TABS.map(({ id, label, Icon }) => (
                <button
                  key={id}
                  id={`tab-${id}`}
                  className={`tab-btn ${tab === id ? 'active' : ''}`}
                  onClick={() => setTab(id)}
                  aria-selected={tab === id}
                  role="tab"
                >
                  <Icon size={15} />
                  <span>{label}</span>
                </button>
              ))}
            </nav>

            {/* Right: status */}
            <div className="header-right">
              <div className="status-pill">
                <div className={`status-dot ${backendOk === null ? 'loading' : backendOk ? 'online' : 'offline'}`} />
                <span>{backendOk === null ? 'Connecting…' : backendOk ? 'API Online' : 'API Offline'}</span>
              </div>
            </div>

          </div>

          {/* ── Alert email bar ── */}
          <div className="alert-email-bar">
            <IconMail size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            <input
              type="email"
              placeholder="Email address for weapon-detection alerts (optional)"
              value={alertEmail}
              onChange={e => handleEmailChange(e.target.value)}
              className="alert-email-input"
              aria-label="Alert email address"
            />
            {alertEmail.trim() && (
              emailValid
                ? <span className="badge badge-success" style={{ fontSize: '0.68rem' }}><IconCheck size={11} /> Saved</span>
                : <span className="badge badge-warning" style={{ fontSize: '0.68rem' }}>Invalid email</span>
            )}
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="main-content" id="main-content">
        <div className="container">

          {/* Backend offline warning */}
          {backendOk === false && (
            <div className="error-box mt-4" role="alert">
              <span style={{ fontSize: '1rem', flexShrink: 0 }}>⚠</span>
              <div>
                <strong>Backend offline.</strong> Start the server:{' '}
                <code style={{ fontFamily: 'var(--font-mono)', background: 'rgba(0,0,0,0.3)', padding: '0 0.4em', borderRadius: 4 }}>
                  uvicorn main:app --reload
                </code>{' '}
                inside the <code style={{ fontFamily: 'var(--font-mono)', background: 'rgba(0,0,0,0.3)', padding: '0 0.4em', borderRadius: 4 }}>backend/</code> directory.
              </div>
            </div>
          )}

          {/* ── Tab panels ── */}
          <div role="tabpanel" aria-labelledby={`tab-${tab}`} className="fade-in" key={tab} style={{ marginTop: '0.25rem' }}>
            {tab === 'video'  && <VideoDetection alertEmail={emailValid ? alertEmail.trim() : ''} />}
            {tab === 'image'  && <ImageDetection alertEmail={emailValid ? alertEmail.trim() : ''} />}
            {tab === 'webcam' && <WebcamDetection alertEmail={emailValid ? alertEmail.trim() : ''} />}
          </div>

        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="footer">
        <div className="container">
          WeaponShield AI · YOLOv8 + FastAPI + React · Final Year Engineering Project
        </div>
      </footer>
    </div>
  )
}
