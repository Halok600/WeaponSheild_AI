/**
 * AlertBadge – Flashing animated badge shown when weapon is detected.
 * Props:
 *   active   {boolean} – whether a weapon is currently detected
 *   message  {string}  – message to show
 */
export default function AlertBadge({ active, message }) {
  if (!active) return null

  return (
    <div className="toast" role="alert" aria-live="assertive">
      <div className="pulse-dot" />
      <div>
        <div style={{ fontWeight: 700, color: 'var(--accent)', fontSize: '0.9rem' }}>
          ⚠️ WEAPON DETECTED
        </div>
        {message && (
          <div className="text-sm text-secondary mt-1">{message}</div>
        )}
      </div>
    </div>
  )
}
