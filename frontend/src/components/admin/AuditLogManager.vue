<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import request from "@/utils/request";
import type { ApiResponse, ManagedUser, OperationLog, PageData } from "@/types";

const logs = ref<OperationLog[]>([]);
const users = ref<ManagedUser[]>([]);
const total = ref(0);
const page = ref(1);
const filters = reactive({
  user_id: undefined as number | undefined,
  action: "",
  resource_type: "",
});

async function load() {
  const { data } = await request.get<ApiResponse<PageData<OperationLog>>>(
    "/operation-logs",
    {
      params: { page: page.value, page_size: 20, ...filters },
    },
  );
  logs.value = data.data.items;
  total.value = data.data.total;
}

function username(userId: number) {
  return (
    users.value.find((user) => user.id === userId)?.username ||
    `用户 #${userId}`
  );
}

function reset() {
  Object.assign(filters, { user_id: undefined, action: "", resource_type: "" });
  page.value = 1;
  load();
}

onMounted(async () => {
  const { data } = await request.get<ApiResponse<ManagedUser[]>>("/users");
  users.value = data.data;
  await load();
});
</script>

<template>
  <div class="panel table-panel">
    <div class="panel-title">
      <div>
        <h2>管理审计日志</h2>
        <small>追踪角色、权限、用户状态和课程审核等关键操作</small>
      </div>
    </div>
    <div class="filters">
      <el-select v-model="filters.user_id" clearable placeholder="操作用户"
        ><el-option
          v-for="user in users"
          :key="user.id"
          :label="user.username"
          :value="user.id" /></el-select
      ><el-input
        v-model="filters.action"
        clearable
        placeholder="动作，如 assign"
        @keyup.enter="load"
      /><el-select
        v-model="filters.resource_type"
        clearable
        placeholder="资源类型"
        ><el-option label="用户" value="user" /><el-option
          label="角色"
          value="role" /><el-option label="权限" value="permission" /><el-option
          label="课程"
          value="course" /></el-select
      ><el-button
        type="primary"
        @click="
          page = 1;
          load();
        "
        >查询</el-button
      ><el-button @click="reset">重置</el-button>
    </div>
    <el-table :data="logs" empty-text="暂无审计记录"
      ><el-table-column label="时间" width="180"
        ><template #default="scope">{{
          new Date(scope.row.created_at).toLocaleString("zh-CN")
        }}</template></el-table-column
      ><el-table-column label="操作人" width="130"
        ><template #default="scope">{{
          username(scope.row.user_id)
        }}</template></el-table-column
      ><el-table-column
        prop="action"
        label="动作"
        min-width="180" /><el-table-column label="资源" min-width="150"
        ><template #default="scope"
          >{{ scope.row.resource_type }} #{{ scope.row.resource_id }}</template
        ></el-table-column
      ><el-table-column
        prop="detail"
        label="详情"
        min-width="260"
        show-overflow-tooltip
    /></el-table>
    <el-pagination
      v-if="total > 20"
      v-model:current-page="page"
      class="pagination"
      layout="prev, pager, next, total"
      :total="total"
      :page-size="20"
      @current-change="load"
    />
  </div>
</template>

<style scoped>
.panel-title small {
  display: block;
  margin-top: 6px;
  color: #8192a3;
}
.filters {
  display: grid;
  grid-template-columns: 180px 1fr 160px auto auto;
  gap: 10px;
  margin-bottom: 20px;
}
.pagination {
  justify-content: flex-end;
  margin-top: 20px;
}
@media (max-width: 760px) {
  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
