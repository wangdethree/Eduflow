<script setup lang="ts">
const features = ['课程管理', '学习进度', '在线考试', '教学统计']
</script>

<template>
  <main class="home">
    <nav><strong>EduFlow</strong><el-button type="primary" @click="$router.push('/login')">登录</el-button></nav>
    <section class="hero">
      <p class="eyebrow">智慧学习 · 持续成长</p>
      <h1>让教学与学习，<span>自然流动</span></h1>
      <p>面向高校与职业培训场景的一体化在线学习平台。</p>
      <el-button size="large" type="primary" @click="$router.push('/login')">开始使用</el-button>
    </section>
    <section class="features">
      <article v-for="item in features" :key="item"><h3>{{ item }}</h3><p>清晰、可靠、可追踪的学习体验</p></article>
    </section>
  </main>
</template>
