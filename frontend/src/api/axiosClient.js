import axios from 'axios'

// In production (Vercel), the frontend and backend live on different domains,
// so API calls need an absolute URL. Locally, Vite's dev-server proxy handles
// it via relative paths, so this stays empty.
export const API_BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: API_BASE || '/',   // Vite proxy forwards to http://localhost:8000 when empty
  timeout: 300_000,           // 5-minute timeout for large video uploads
})

export default api
