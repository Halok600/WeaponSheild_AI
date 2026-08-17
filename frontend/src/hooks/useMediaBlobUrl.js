import { useEffect, useState } from 'react'
import api from '../api/axiosClient'

// Fetches a backend-served media file (annotated image/video output) through
// axios so custom headers apply — specifically ngrok's browser-warning
// bypass header, which a plain <img src="..."> / <video><source src="...">
// can't carry, causing ngrok to serve its HTML warning page instead of the
// actual file. Exposes the result as a local blob URL those tags can use.
export default function useMediaBlobUrl(path) {
  const [blobUrl, setBlobUrl] = useState(null)

  useEffect(() => {
    if (!path) { setBlobUrl(null); return }
    let objectUrl
    let cancelled = false

    api.get(path, { responseType: 'blob' })
      .then(res => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(res.data)
        setBlobUrl(objectUrl)
      })
      .catch(() => { if (!cancelled) setBlobUrl(null) })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [path])

  return blobUrl
}
