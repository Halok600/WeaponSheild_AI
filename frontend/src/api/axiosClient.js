import axios from 'axios'

// In production (Vercel), the frontend and backend live on different domains,
// so API calls need an absolute URL. Locally, Vite's dev-server proxy handles
// it via relative paths, so this stays empty.
export const API_BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: API_BASE || '/',   // Vite proxy forwards to http://localhost:8000 when empty
  timeout: 300_000,           // 5-minute timeout for large video uploads
  headers: {
    // Bypasses ngrok's free-tier browser-warning interstitial page, which
    // otherwise returns an HTML page instead of JSON for real browser
    // requests. No-op against any backend that isn't behind ngrok.
    'ngrok-skip-browser-warning': 'true',
  },
})

export default api
