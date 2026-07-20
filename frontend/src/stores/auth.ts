import { defineStore } from 'pinia'
import request from '@/utils/request'
import type { ApiResponse, TokenData, User } from '@/types'

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: JSON.parse(localStorage.getItem('user') || 'null') as User | null }),
  getters: { isAuthenticated: () => Boolean(localStorage.getItem('access_token')), primaryRole: (state) => state.user?.roles?.[0] || 'student' },
  actions: {
    async login(account: string, password: string) {
      const { data } = await request.post<ApiResponse<TokenData>>('/auth/login', { account, password })
      localStorage.setItem('access_token', data.data.access_token)
      localStorage.setItem('refresh_token', data.data.refresh_token)
      localStorage.setItem('user', JSON.stringify(data.data.user))
      this.user = data.data.user
    },
    async loadCurrentUser() {
      const { data } = await request.get<ApiResponse<User>>('/auth/me')
      this.user = data.data
      localStorage.setItem('user', JSON.stringify(this.user))
    },
    async logout() {
      const refresh_token = localStorage.getItem('refresh_token')
      if (refresh_token) await request.post('/auth/logout', { refresh_token }).catch(() => undefined)
      localStorage.removeItem('access_token'); localStorage.removeItem('refresh_token'); localStorage.removeItem('user'); this.user = null
    },
  },
})
