/**
 * DetectionLog – Scrollable log table of timestamped weapon detections.
 *
 * Props:
 *   entries  {Array}   – [{frame, timestamp, label, confidence, bbox}]
 *   title    {string}
 *   maxHeight{string}  – CSS max-height (default '320px')
 */
export default function DetectionLog({ entries = [], title = 'Detection Log', maxHeight = '320px' }) {
  const handleExport = () => {
    if (!entries.length) return
    const header = 'Frame,Timestamp,Label,Confidence\n'
    const rows = entries
      .map(e => `${e.frame ?? '-'},${e.timestamp},${e.label},${(e.confidence * 100).toFixed(1)}%`)
      .join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'detection_log.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="card" style={{ padding: '1rem' }}>
      <div className="flex items-center justify-between" style={{ marginBottom: '0.75rem' }}>
        <div className="flex items-center gap-3">
          <h3>{title}</h3>
          {entries.length > 0 && (
            <span className="badge badge-danger">{entries.length}</span>
          )}
        </div>
        {entries.length > 0 && (
          <button
            className="btn btn-secondary"
            style={{ padding: '0.35rem 0.85rem', fontSize: '0.78rem' }}
            onClick={handleExport}
            title="Export as CSV"
          >
            ↓ CSV
          </button>
        )}
      </div>

      {entries.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '2rem 1rem',
          color: 'var(--text-muted)',
          fontSize: '0.875rem'
        }}>
          No detections yet
        </div>
      ) : (
        <div style={{ overflowY: 'auto', maxHeight, borderRadius: 'var(--radius-md)' }}>
          <table className="log-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Frame</th>
                <th>Label</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <tr key={i}>
                  <td className="font-mono text-accent">{e.timestamp}</td>
                  <td>{e.frame ?? '—'}</td>
                  <td>
                    <span className="badge badge-danger" style={{ fontSize: '0.7rem' }}>
                      {e.label}
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="conf-bar-wrap" style={{ width: 60 }}>
                        <div
                          className="conf-bar"
                          style={{ width: `${(e.confidence * 100).toFixed(0)}%` }}
                        />
                      </div>
                      <span className="font-mono" style={{ fontSize: '0.78rem' }}>
                        {(e.confidence * 100).toFixed(1)}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
