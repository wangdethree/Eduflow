<script setup lang="ts">
import { onMounted, ref } from 'vue'; import request from '@/utils/request'; import type { ApiResponse, Enrollment } from '@/types'
const items=ref<Enrollment[]>([]); onMounted(async()=>{items.value=(await request.get<ApiResponse<Enrollment[]>>('/learning/courses')).data.data})
</script>
<template><section class="page"><header class="page-header"><div><p class="eyebrow">MY LEARNING</p><h1>我的学习</h1><p>进度被可靠保存，随时从上次的位置继续。</p></div></header><div class="panel learning-list"><div v-for="item in items" :key="item.id"><span>课程 #{{ item.course_id }}</span><el-progress :percentage="item.progress" :status="item.progress===100?'success':''"/><b>{{ item.status }}</b></div><el-empty v-if="!items.length" description="还没有学习记录" /></div></section></template>
