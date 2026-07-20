<script setup lang="ts">
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init, type ECharts, use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import AuditLogManager from "@/components/admin/AuditLogManager.vue";
import CourseAuditManager from "@/components/admin/CourseAuditManager.vue";
import UserRoleManager from "@/components/admin/UserRoleManager.vue";
import request from "@/utils/request";
import type { ApiResponse } from "@/types";

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

const activeTab = ref("overview");
const stats = ref<any>({});
const chartEl = ref<HTMLElement>();
let chart: ECharts | undefined;

onMounted(async () => {
  const { data } = await request.get<ApiResponse<any>>(
    "/statistics/admin/overview",
  );
  stats.value = data.data;
  await nextTick();
  if (chartEl.value) {
    chart = init(chartEl.value);
    chart.setOption({
      grid: { left: 36, right: 20, top: 20, bottom: 30 },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: ["用户", "课程", "已发布", "考试"] },
      yAxis: { type: "value" },
      series: [
        {
          type: "bar",
          barWidth: 34,
          data: [
            stats.value.user_total,
            stats.value.course_total,
            stats.value.published_courses,
            stats.value.exam_total,
          ],
          itemStyle: { color: "#2f87ff", borderRadius: [8, 8, 0, 0] },
        },
      ],
    });
  }
});

onBeforeUnmount(() => chart?.dispose());
</script>

<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="eyebrow">PLATFORM CONTROL</p>
        <h1>管理中心</h1>
        <p>课程审核、账号权限与关键管理操作集中处理。</p>
      </div>
      <el-tag type="success" size="large">系统运行正常</el-tag>
    </header>
    <div class="metric-grid">
      <article>
        <span>用户总数</span><strong>{{ stats.user_total || 0 }}</strong
        ><small>{{ stats.active_users || 0 }} 位正常用户</small>
      </article>
      <article>
        <span>课程总数</span><strong>{{ stats.course_total || 0 }}</strong
        ><small>{{ stats.published_courses || 0 }} 门已发布</small>
      </article>
      <article>
        <span>考试总数</span><strong>{{ stats.exam_total || 0 }}</strong
        ><small>平台测评</small>
      </article>
      <article>
        <span>学习时长</span
        ><strong>{{ Math.round((stats.learning_seconds || 0) / 3600) }}h</strong
        ><small>累计有效时长</small>
      </article>
    </div>
    <el-tabs v-model="activeTab" class="admin-tabs"
      ><el-tab-pane label="平台概览" name="overview"
        ><div class="panel">
          <div class="panel-title">
            <h2>平台资源概览</h2>
            <span>实时数据</span>
          </div>
          <div ref="chartEl" style="height: 300px" /></div></el-tab-pane
      ><el-tab-pane label="课程审核" name="courses"
        ><CourseAuditManager /></el-tab-pane
      ><el-tab-pane label="用户与角色" name="users"
        ><UserRoleManager /></el-tab-pane
      ><el-tab-pane label="审计日志" name="logs"
        ><AuditLogManager /></el-tab-pane
    ></el-tabs>
  </section>
</template>

<style scoped>
.admin-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}
.admin-tabs :deep(.el-tabs__item) {
  height: 48px;
  font-size: 16px;
}
</style>
