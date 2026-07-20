<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'
import type { ApiResponse, Enrollment } from '@/types'

const auth = useAuthStore(); const courses = ref<Enrollment[]>([]); const unread = ref(0)
onMounted(async () => {
  const [learning, messages] = await Promise.all([
    request.get<ApiResponse<Enrollment[]>>('/learning/courses'),
    request.get<ApiResponse<{ count: number }>>('/notifications/unread-count'),
  ])
  courses.value = learning.data.data; unread.value = messages.data.data.count
})
</script>
<template>
  <section class="page">
    <header class="page-header"><div><p class="eyebrow">LEARNING OVERVIEW</p><h1>早上好，{{ auth.user?.nickname }}</h1><p>继续保持节奏，今天也向目标靠近一点。</p></div><el-button type="primary" size="large" @click="$router.push('/app/courses')">探索新课程</el-button></header>
    <div class="metric-grid"><article><span>学习中课程</span><strong>{{ courses.length }}</strong><small>持续积累</small></article><article><span>平均进度</span><strong>{{ courses.length ? Math.round(courses.reduce((n,c)=>n+c.progress,0)/courses.length) : 0 }}%</strong><small>所有课程</small></article><article><span>已完成</span><strong>{{ courses.filter(c=>c.status==='completed').length }}</strong><small>课程里程碑</small></article><article><span>未读消息</span><strong>{{ unread }}</strong><small>及时查看</small></article></div>
    <div class="panel"><div class="panel-title"><h2>最近学习</h2><el-button link @click="$router.push('/app/learning')">查看全部</el-button></div><el-empty v-if="!courses.length" description="还没有加入课程" /><div v-else class="learning-list"><div v-for="course in courses.slice(0,4)" :key="course.id"><span>课程 #{{ course.course_id }}</span><el-progress :percentage="course.progress" /><b>{{ course.status }}</b></div></div></div>
  </section>
</template>
