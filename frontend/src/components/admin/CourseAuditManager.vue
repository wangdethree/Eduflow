<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import request from "@/utils/request";
import type { ApiResponse, Course, PageData } from "@/types";

const courses = ref<Course[]>([]);
const total = ref(0);
const page = ref(1);
const status = ref("pending_review");
const keyword = ref("");
const dialogVisible = ref(false);
const selected = ref<Course | null>(null);
const saving = ref(false);
const form = reactive({ approved: true, opinion: "" });
const statusText: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审核",
  rejected: "已驳回",
  published: "已发布",
  offline: "已下架",
};

async function load() {
  const { data } = await request.get<ApiResponse<PageData<Course>>>(
    "/admin/courses",
    {
      params: {
        page: page.value,
        page_size: 10,
        status: status.value || undefined,
        keyword: keyword.value || undefined,
      },
    },
  );
  courses.value = data.data.items;
  total.value = data.data.total;
}

function openAudit(course: Course) {
  selected.value = course;
  Object.assign(form, { approved: true, opinion: "" });
  dialogVisible.value = true;
}

async function submitAudit() {
  if (!selected.value) return;
  if (!form.approved && !form.opinion.trim())
    return ElMessage.warning("驳回课程时请填写审核意见");
  saving.value = true;
  try {
    await request.post(`/courses/${selected.value.id}/audit`, form);
    dialogVisible.value = false;
    ElMessage.success(form.approved ? "课程已审核通过" : "课程已驳回");
    await load();
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="panel table-panel">
    <div class="panel-title">
      <div>
        <h2>课程审核</h2>
        <small>审阅课程资料、章节和课时后给出审核结论</small>
      </div>
      <div class="toolbar">
        <el-input
          v-model="keyword"
          clearable
          placeholder="课程名称"
          @keyup.enter="load"
        /><el-select v-model="status" style="width: 130px" @change="load"
          ><el-option label="待审核" value="pending_review" /><el-option
            label="已发布"
            value="published" /><el-option
            label="已驳回"
            value="rejected" /><el-option label="全部" value="" /></el-select
        ><el-button @click="load">查询</el-button>
      </div>
    </div>
    <el-table :data="courses" empty-text="暂无符合条件的课程">
      <el-table-column
        prop="title"
        label="课程"
        min-width="220"
      /><el-table-column
        prop="teacher_id"
        label="教师 ID"
        width="100"
      /><el-table-column label="内容" width="140"
        ><template #default="scope"
          >{{ scope.row.chapters.length }} 章 /
          {{
            scope.row.chapters.reduce(
              (sum: number, chapter: any) => sum + chapter.lessons.length,
              0,
            )
          }}
          课时</template
        ></el-table-column
      ><el-table-column label="状态" width="100"
        ><template #default="scope"
          ><el-tag>{{ statusText[scope.row.status] }}</el-tag></template
        ></el-table-column
      ><el-table-column label="操作" width="120"
        ><template #default="scope"
          ><el-button
            v-if="scope.row.status === 'pending_review'"
            type="primary"
            link
            @click="openAudit(scope.row)"
            >开始审核</el-button
          ><el-button v-else link @click="openAudit(scope.row)"
            >查看内容</el-button
          ></template
        ></el-table-column
      >
    </el-table>
    <el-pagination
      v-if="total > 10"
      v-model:current-page="page"
      class="pagination"
      layout="prev, pager, next, total"
      :total="total"
      :page-size="10"
      @current-change="load"
    />
  </div>

  <el-dialog
    v-model="dialogVisible"
    :title="selected?.status === 'pending_review' ? '审核课程' : '课程内容'"
    width="760px"
  >
    <template v-if="selected">
      <el-descriptions :column="2" border
        ><el-descriptions-item label="课程">{{
          selected.title
        }}</el-descriptions-item
        ><el-descriptions-item label="教师 ID">{{
          selected.teacher_id
        }}</el-descriptions-item
        ><el-descriptions-item label="难度">{{
          selected.difficulty
        }}</el-descriptions-item
        ><el-descriptions-item label="总时长"
          >{{ selected.total_duration }} 秒</el-descriptions-item
        ><el-descriptions-item label="简介" :span="2">{{
          selected.description || "暂无简介"
        }}</el-descriptions-item></el-descriptions
      >
      <el-divider content-position="left">章节与课时</el-divider>
      <el-collapse
        ><el-collapse-item
          v-for="chapter in selected.chapters"
          :key="chapter.id"
          :title="`${chapter.sort_order}. ${chapter.title}`"
          :name="chapter.id"
          ><ul class="lesson-list">
            <li v-for="lesson in chapter.lessons" :key="lesson.id">
              <span>{{ lesson.sort_order }}. {{ lesson.title }}</span
              ><small
                >{{ lesson.lesson_type }} ·
                {{ lesson.duration_seconds }} 秒</small
              >
            </li>
          </ul></el-collapse-item
        ></el-collapse
      >
      <el-form
        v-if="selected.status === 'pending_review'"
        label-position="top"
        class="audit-form"
        ><el-form-item label="审核结论"
          ><el-radio-group v-model="form.approved"
            ><el-radio-button :value="true">通过并发布</el-radio-button
            ><el-radio-button :value="false"
              >驳回修改</el-radio-button
            ></el-radio-group
          ></el-form-item
        ><el-form-item label="审核意见"
          ><el-input
            v-model="form.opinion"
            type="textarea"
            :rows="3"
            placeholder="请说明内容质量或需要修改的问题" /></el-form-item
      ></el-form>
    </template>
    <template #footer
      ><el-button @click="dialogVisible = false">关闭</el-button
      ><el-button
        v-if="selected?.status === 'pending_review'"
        type="primary"
        :loading="saving"
        @click="submitAudit"
        >确认审核</el-button
      ></template
    >
  </el-dialog>
</template>

<style scoped>
.panel-title small {
  display: block;
  margin-top: 6px;
  color: #8192a3;
}
.toolbar {
  display: flex;
  gap: 10px;
}
.toolbar .el-input {
  width: 200px;
}
.pagination {
  justify-content: flex-end;
  margin-top: 20px;
}
.lesson-list {
  display: grid;
  gap: 10px;
  padding: 0;
  list-style: none;
}
.lesson-list li {
  display: flex;
  justify-content: space-between;
}
.lesson-list small {
  color: #8192a3;
}
.audit-form {
  margin-top: 22px;
}
@media (max-width: 700px) {
  .panel-title,
  .toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .toolbar .el-input {
    width: 100%;
  }
}
</style>
