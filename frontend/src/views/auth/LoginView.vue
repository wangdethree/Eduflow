<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const loading = ref(false)
const form = reactive({ account: '', password: '' })

async function submit() {
  if (!form.account || !form.password) return ElMessage.warning('请输入账号和密码')
  loading.value = true
  try {
    await auth.login(form.account, form.password)
    ElMessage.success('欢迎回来')
    await router.replace((route.query.redirect as string) || '/app')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-brand"><b>EduFlow</b><h2>每一次学习，都有迹可循。</h2><p>课程、进度、考试和数据，汇聚于一个清晰的学习空间。</p></section>
    <el-card class="auth-card">
      <p class="eyebrow">WELCOME BACK</p><h1>登录学习平台</h1>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名或邮箱"><el-input v-model="form.account" size="large" autofocus /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" size="large" show-password @keyup.enter="submit" /></el-form-item>
        <el-button type="primary" size="large" :loading="loading" style="width: 100%" @click="submit">进入 EduFlow</el-button>
      </el-form>
      <el-button link style="margin-top: 18px" @click="$router.push('/')">返回首页</el-button>
    </el-card>
  </main>
</template>
