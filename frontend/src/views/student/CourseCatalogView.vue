<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import type { ApiResponse, Course, PageData } from '@/types'
const courses = ref<Course[]>([]); const keyword = ref(''); const loading = ref(false)
async function load() { loading.value=true; try { const {data}=await request.get<ApiResponse<PageData<Course>>>('/courses',{params:{keyword:keyword.value||undefined}}); courses.value=data.data.items } finally { loading.value=false } }
async function enroll(id:number) { await request.post(`/learning/courses/${id}/enroll`); ElMessage.success('已加入课程') }
onMounted(load)
</script>
<template><section class="page"><header class="page-header"><div><p class="eyebrow">COURSE CATALOG</p><h1>课程广场</h1><p>找到下一项值得投入的技能。</p></div><el-input v-model="keyword" placeholder="搜索课程" clearable style="width:300px" @keyup.enter="load"><template #append><el-button @click="load">搜索</el-button></template></el-input></header><div v-loading="loading" class="course-grid"><article v-for="course in courses" :key="course.id" class="course-card"><div class="course-cover" :style="course.cover_url?{backgroundImage:`url(${course.cover_url})`}:{}"><span>{{ course.difficulty }}</span></div><div><small>{{ course.student_count }} 人学习</small><h3>{{ course.title }}</h3><p>{{ course.subtitle || course.description || '精心设计的体系化课程' }}</p><footer><span>{{ Math.round(course.total_duration/60) }} 分钟</span><el-button type="primary" @click="enroll(course.id)">加入学习</el-button></footer></div></article></div><el-empty v-if="!loading&&!courses.length" description="暂无匹配课程" /></section></template>
