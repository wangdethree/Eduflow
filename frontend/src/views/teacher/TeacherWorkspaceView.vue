<script setup lang="ts">
import { onMounted, ref } from "vue";
import CourseManager from "@/components/teacher/CourseManager.vue";
import PaperManager from "@/components/teacher/PaperManager.vue";
import QuestionBankManager from "@/components/teacher/QuestionBankManager.vue";
import request from "@/utils/request";
import type { ApiResponse, Category, Course } from "@/types";

const activeTab = ref("courses");
const courses = ref<Course[]>([]);
const categories = ref<Category[]>([]);

async function loadCourses() {
  const [courseResponse, categoryResponse] = await Promise.all([
    request.get<ApiResponse<Course[]>>("/teacher/courses"),
    request.get<ApiResponse<Category[]>>("/course-categories"),
  ]);
  courses.value = courseResponse.data.data;
  categories.value = categoryResponse.data.data;
}

onMounted(loadCourses);
</script>

<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="eyebrow">TEACHER STUDIO</p>
        <h1>教师工作台</h1>
        <p>从课程构思、内容编排、题库组卷，到发布审核的一站式工作区。</p>
      </div>
    </header>
    <div class="metric-grid">
      <article>
        <span>课程总数</span><strong>{{ courses.length }}</strong
        ><small>我的课程</small>
      </article>
      <article>
        <span>已发布</span
        ><strong>{{
          courses.filter((item) => item.status === "published").length
        }}</strong
        ><small>对学员可见</small>
      </article>
      <article>
        <span>待审核</span
        ><strong>{{
          courses.filter((item) => item.status === "pending_review").length
        }}</strong
        ><small>正在审核流转</small>
      </article>
      <article>
        <span>学员总数</span
        ><strong>{{
          courses.reduce((sum, item) => sum + item.student_count, 0)
        }}</strong
        ><small>累计加入</small>
      </article>
    </div>
    <el-tabs v-model="activeTab" class="workspace-tabs">
      <el-tab-pane label="课程与章节" name="courses"
        ><CourseManager
          :courses="courses"
          :categories="categories"
          @reload="loadCourses"
      /></el-tab-pane>
      <el-tab-pane label="题库管理" name="questions"
        ><QuestionBankManager
      /></el-tab-pane>
      <el-tab-pane label="试卷管理" name="papers"><PaperManager /></el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.workspace-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}
.workspace-tabs :deep(.el-tabs__item) {
  height: 48px;
  font-size: 16px;
}
</style>
