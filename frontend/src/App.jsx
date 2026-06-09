import { useState, useEffect } from 'react'
import './index.css'
import ImageDetection from './components/ImageDetection'
import VideoDetection from './components/VideoDetection'
import WebcamDetection from './components/WebcamDetection'
import api from './api/axiosClient'

const TABS = [
  { id: 'video',  label: 'CCTV Video',   icon: '📹', desc: 'Upload & analyse surveillance video' },
  { id: 'image',  label: 'Image',         icon: '🖼️',  desc: 'Detect weapons in a single image' },
  { id: 'webcam', label: 'Live Webcam',   icon: '📷', desc: 'Real-time webcam stream detection' },
]

export default function App() {
  const [tab, setTab] = useState('video')
  const [backendOk, setBackendOk] = useState(null) // null=loading, true=ok, false=down

  /* ── Backend health probe ─────────────────────────────────────────── */
  useEffect(() => {
    api.get('/health')
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false))
  }, [])

  return (
    <div className="app-shell">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="header">
        <div className="container">
          <div className="header-inner">
            <a href="/" className="logo" aria-label="WeaponShield AI home">
              <div className="logo-icon" aria-hidden="true">🛡️</div>
              <div>
                <div className="logo-text">WeaponShield AI</div>
                <div className="logo-sub">Surveillance Detection System</div>
              </div>
            </a>

            <div className="flex items-center gap-3">
              {/* Backend status indicator */}
              <div className="stat-chip">
                <div
                  style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: backendOk === null
                      ? 'var(--text-muted)'
                      : backendOk
                      ? 'var(--accent-green)'
                      : 'var(--accent)',
                  }}
                />
                <span className="text-xs text-secondary">
                  {backendOk === null ? 'Connecting…' : backendOk ? 'API Online' : 'API Offline'}
                </span>
              </div>

              {/* Current mode */}
              <span className="badge badge-info">
                {TABS.find(t => t.id === tab)?.icon} {TABS.find(t => t.id === tab)?.label}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Main ──────────────────────────────────────────────────── */}
      <main className="main-content" id="main-content">
        <div className="container">

          {/* Backend down warning */}
          {backendOk === false && (
            <div style={{
              marginTop: '1.5rem',
              padding: '1rem 1.25rem',
              background: 'hsla(0,80%,58%,0.1)',
              border: '1px solid var(--accent)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--accent)',
              fontSize: '0.875rem'
            }}>
              ⚠️ <strong>Backend is offline.</strong>{' '}
              Start the FastAPI server with{' '}
              <code style={{ fontFamily: 'var(--font-mono)', background: 'hsla(0,0%,0%,0.3)', padding: '0 0.4em', borderRadius: 4 }}>
                uvicorn main:app --reload
              </code>{' '}
              in the <code style={{ fontFamily: 'var(--font-mono)', background: 'hsla(0,0%,0%,0.3)', padding: '0 0.4em', borderRadius: 4 }}>backend/</code> directory.
            </div>
          )}

          {/* ── Tabs ─────────────────────────────────────────────── */}
          <nav className="tabs" aria-label="Detection mode">
            {TABS.map(t => (
              <button
                key={t.id}
                id={`tab-${t.id}`}
                className={`tab-btn ${tab === t.id ? 'active' : ''}`}
                onClick={() => setTab(t.id)}
                aria-selected={tab === t.id}
                role="tab"
                title={t.desc}
              >
                <span aria-hidden="true">{t.icon}</span>
                {t.label}
              </button>
            ))}
          </nav>

          {/* ── Panel ────────────────────────────────────────────── */}
          <div role="tabpanel" aria-labelledby={`tab-${tab}`}>
            {tab === 'video'  && <VideoDetection />}
            {tab === 'image'  && <ImageDetection />}
            {tab === 'webcam' && <WebcamDetection />}
          </div>
        </div>
      </main>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <footer className="footer">
        <div className="container">
          WeaponShield AI — Final Year Engineering Project &nbsp;·&nbsp; YOLOv8 + FastAPI + React
        </div>
      </footer>
    </div>
  )
}
