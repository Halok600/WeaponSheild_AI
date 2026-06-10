import { IconAlert, IconX } from './Icons'

export default function AlertBadge({ active, message }) {
  if (!active) return null
  return (
    <div className="alert-banner" role="alert" aria-live="assertive">
      <div className="flex items-center gap-3">
        <div className="pulse-dot" style={{ background: 'var(--accent)', width: 10, height: 10 }} />
        <div>
          <div style={{ fontWeight: 800, fontSize: '0.9rem', letterSpacing: '0.04em' }}>
            ⚠ WEAPON DETECTED
          </div>
          {message && (
            <div style={{ fontSize: '0.78rem', color: 'hsla(0,0%,100%,0.7)', marginTop: 2 }}>{message}</div>
          )}
        </div>
      </div>
    </div>
  )
}
