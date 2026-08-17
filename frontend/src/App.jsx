import { useState, useEffect } from 'react'
import './index.css'
import ImageDetection from './components/ImageDetection'
import VideoDetection from './components/VideoDetection'
import WebcamDetection from './components/WebcamDetection'
import { IconVideo, IconImage, IconCamera } from './components/Icons'
import api from './api/axiosClient'

const TABS = [
  { id: 'video',  label: 'CCTV Video',  Icon: IconVideo,  desc: 'Upload & analyse surveillance footage' },
  { id: 'image',  label: 'Image Scan',  Icon: IconImage,  desc: 'Detect weapons in a single image' },
  { id: 'webcam', label: 'Live Webcam', Icon: IconCamera, desc: 'Real-time webcam stream detection' },
]

export default function App() {
  const [tab, setTab] = useState('video')
  const [backendOk, setBackendOk] = useState(null)

  useEffect(() => {
    api.get('/health')
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false))
  }, [])

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
            {tab === 'video'  && <VideoDetection />}
            {tab === 'image'  && <ImageDetection />}
            {tab === 'webcam' && <WebcamDetection />}
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
