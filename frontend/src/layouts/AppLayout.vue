<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'
import type { ApiResponse } from '@/types'

const auth = useAuthStore(); const route = useRoute(); const router = useRouter(); const unread = ref(0)
const menus = computed(() => {
  const base = [
    { path: '/app', label: '总览', icon: 'House' }, { path: '/app/courses', label: '课程广场', icon: 'Collection' },
    { path: '/app/learning', label: '我的学习', icon: 'Reading' }, { path: '/app/exams', label: '考试中心', icon: 'EditPen' },
    { path: '/app/notifications', label: '消息中心', icon: 'Bell' },
  ]
  if (auth.user?.roles.includes('teacher')) base.push({ path: '/app/teacher', label: '教师工作台', icon: 'DataAnalysis' })
  if (auth.user?.roles.includes('admin')) base.push({ path: '/app/admin', label: '管理中心', icon: 'Setting' })
  return base
})
onMounted(async () => {
  if (!auth.user) await auth.loadCurrentUser().catch(() => undefined)
  const { data } = await request.get<ApiResponse<{ count: number }>>('/notifications/unread-count').catch(() => ({ data: { data: { count: 0 } } } as any))
  unread.value = data.data.count
})
async function logout() { await auth.logout(); await router.replace('/login') }
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="logo"><span>E</span><b>EduFlow</b></div>
      <nav>
        <router-link v-for="item in menus" :key="item.path" :to="item.path" :class="{ active: route.path === item.path }">
          <el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span><em v-if="item.path.includes('notifications') && unread">{{ unread }}</em>
        </router-link>
      </nav>
      <div class="profile"><el-avatar>{{ auth.user?.nickname?.slice(0, 1) || 'E' }}</el-avatar><div><b>{{ auth.user?.nickname || 'EduFlow 用户' }}</b><small>{{ auth.primaryRole }}</small></div><el-button link @click="logout">退出</el-button></div>
    </aside>
    <main class="app-main"><router-view /></main>
  </div>
</template>
