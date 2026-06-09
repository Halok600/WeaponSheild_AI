import axios from 'axios'

const api = axios.create({
  baseURL: '/',          // Vite proxy forwards to http://localhost:8000
  timeout: 300_000,      // 5-minute timeout for large video uploads
})

export default api
