import { IconDownload, IconActivity } from './Icons'

export default function DetectionLog({ entries = [], title = 'Detection Log', maxHeight = '340px' }) {
  const handleExport = () => {
    if (!entries.length) return
    const header = 'Frame,Timestamp,Label,Confidence\n'
    const rows = entries.map(e => `${e.frame ?? '-'},${e.timestamp},${e.label},${(e.confidence * 100).toFixed(1)}%`).join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'detection_log.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <IconActivity size={16} style={{ color: 'var(--accent)' }} />
          <h3>{title}</h3>
          {entries.length > 0 && <span className="badge badge-danger">{entries.length}</span>}
        </div>
        {entries.length > 0 && (
          <button className="btn btn-secondary btn-sm" onClick={handleExport} title="Export as CSV">
            <IconDownload size={13} /> Export CSV
          </button>
        )}
      </div>

      {entries.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '2.5rem 1rem', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem', opacity: 0.4 }}>◎</div>
          <div style={{ fontSize: '0.875rem' }}>No detections recorded yet</div>
          <div style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>Results will appear here after analysis</div>
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
                  <td className="font-mono" style={{ color: 'var(--accent)', fontSize: '0.8rem' }}>{e.timestamp}</td>
                  <td style={{ color: 'var(--text-muted)' }}>{e.frame ?? '—'}</td>
                  <td><span className="badge badge-danger" style={{ fontSize: '0.68rem' }}>{e.label}</span></td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="conf-bar-wrap" style={{ width: 64 }}>
                        <div className="conf-bar" style={{ width: `${(e.confidence * 100).toFixed(0)}%` }} />
                      </div>
                      <span className="font-mono" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
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
