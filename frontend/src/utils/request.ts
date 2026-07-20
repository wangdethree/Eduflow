import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiResponse, TokenData } from '@/types'

const request = axios.create({ baseURL: '/api/v1', timeout: 15000 })
let refreshing: Promise<string> | null = null

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

request.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean }
    if (error.response?.status !== 401 || original._retried || original.url?.includes('/auth/')) {
      return Promise.reject(error)
    }
    original._retried = true
    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) return Promise.reject(error)
    refreshing ||= axios
      .post<ApiResponse<TokenData>>('/api/v1/auth/refresh', { refresh_token: refreshToken })
      .then(({ data }) => {
        localStorage.setItem('access_token', data.data.access_token)
        localStorage.setItem('refresh_token', data.data.refresh_token)
        return data.data.access_token
      })
      .finally(() => { refreshing = null })
    try {
      const token = await refreshing
      original.headers.Authorization = `Bearer ${token}`
      return request(original)
    } catch {
      localStorage.clear()
      location.href = '/login'
      return Promise.reject(error)
    }
  },
)

export default request
