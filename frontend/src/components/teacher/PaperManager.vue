<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import request from "@/utils/request";
import type { ApiResponse, Paper, Question } from "@/types";

const papers = ref<Paper[]>([]);
const questions = ref<Question[]>([]);
const createVisible = ref(false);
const addVisible = ref(false);
const activePaper = ref<Paper | null>(null);
const saving = ref(false);
const paperForm = reactive({ title: "", description: "" });
const addForm = reactive({
  question_id: undefined as number | undefined,
  score: 10,
});
const availableQuestions = computed(() =>
  questions.value.filter(
    (question) =>
      !activePaper.value?.questions.some(
        (item) => item.question_id === question.id,
      ),
  ),
);

async function load() {
  const [paperResponse, questionResponse] = await Promise.all([
    request.get<ApiResponse<Paper[]>>("/papers"),
    request.get<ApiResponse<Question[]>>("/questions"),
  ]);
  papers.value = paperResponse.data.data;
  questions.value = questionResponse.data.data;
}

async function createPaper() {
  if (!paperForm.title) return ElMessage.warning("请输入试卷名称");
  saving.value = true;
  try {
    await request.post("/papers", paperForm);
    createVisible.value = false;
    Object.assign(paperForm, { title: "", description: "" });
    ElMessage.success("试卷已创建");
    await load();
  } finally {
    saving.value = false;
  }
}

async function editPaper(paper: Paper) {
  const { value } = await ElMessageBox.prompt("请输入试卷名称", "编辑试卷", {
    inputValue: paper.title,
    inputPattern: /^.{2,150}$/,
    inputErrorMessage: "名称需为 2-150 个字符",
  });
  await request.patch(`/papers/${paper.id}`, { title: value });
  ElMessage.success("试卷名称已更新");
  await load();
}

function openAdd(paper: Paper) {
  activePaper.value = paper;
  Object.assign(addForm, { question_id: undefined, score: 10 });
  addVisible.value = true;
}

async function addQuestion() {
  if (!activePaper.value || !addForm.question_id)
    return ElMessage.warning("请选择题目");
  saving.value = true;
  try {
    await request.post(`/papers/${activePaper.value.id}/questions`, addForm);
    addVisible.value = false;
    ElMessage.success("题目已加入试卷");
    await load();
  } finally {
    saving.value = false;
  }
}

async function updateScore(paper: Paper, questionId: number, score?: number) {
  if (!score) return;
  await request.patch(`/papers/${paper.id}/questions/${questionId}`, { score });
  ElMessage.success("分值已更新");
  await load();
}

async function removeQuestion(paper: Paper, questionId: number) {
  await ElMessageBox.confirm("确认从试卷中移除这道题？", "移除题目", {
    type: "warning",
  });
  await request.delete(`/papers/${paper.id}/questions/${questionId}`);
  ElMessage.success("题目已移除");
  await load();
}

async function deletePaper(paper: Paper) {
  await ElMessageBox.confirm(`确认删除试卷“${paper.title}”？`, "确认删除", {
    type: "warning",
  });
  await request.delete(`/papers/${paper.id}`);
  ElMessage.success("试卷已删除");
  await load();
}

onMounted(load);
</script>

<template>
  <div class="paper-layout">
    <div class="panel paper-summary">
      <div>
        <span>试卷数量</span><strong>{{ papers.length }}</strong>
      </div>
      <div>
        <span>题库数量</span><strong>{{ questions.length }}</strong>
      </div>
      <div>
        <span>累计组题</span
        ><strong>{{
          papers.reduce((sum, item) => sum + item.questions.length, 0)
        }}</strong>
      </div>
      <el-button type="primary" @click="createVisible = true"
        >创建试卷</el-button
      >
    </div>
    <el-empty v-if="!papers.length" description="暂无试卷" />
    <el-collapse v-else class="paper-list">
      <el-collapse-item
        v-for="paper in papers"
        :key="paper.id"
        :name="paper.id"
      >
        <template #title
          ><div class="paper-title">
            <b>{{ paper.title }}</b
            ><span
              >{{ paper.questions.length }} 题 ·
              {{ paper.total_score }} 分</span
            >
          </div></template
        >
        <div class="paper-actions">
          <p>{{ paper.description || "暂无试卷说明" }}</p>
          <div>
            <el-button link @click="editPaper(paper)">重命名</el-button
            ><el-button type="primary" plain @click="openAdd(paper)"
              >添加题目</el-button
            ><el-button link type="danger" @click="deletePaper(paper)"
              >删除试卷</el-button
            >
          </div>
        </div>
        <el-table :data="paper.questions" empty-text="试卷还没有题目">
          <el-table-column prop="sort_order" label="#" width="50" />
          <el-table-column label="题目" min-width="300"
            ><template #default="scope">{{
              scope.row.question.stem
            }}</template></el-table-column
          >
          <el-table-column label="题型" width="90"
            ><template #default="scope">{{
              scope.row.question.question_type
            }}</template></el-table-column
          >
          <el-table-column label="分值" width="150"
            ><template #default="scope"
              ><el-input-number
                :model-value="scope.row.score"
                :min="1"
                :max="100"
                size="small"
                @change="
                  (value: number | undefined) =>
                    updateScore(paper, scope.row.question_id, value)
                " /></template
          ></el-table-column>
          <el-table-column label="操作" width="90"
            ><template #default="scope"
              ><el-button
                link
                type="danger"
                @click="removeQuestion(paper, scope.row.question_id)"
                >移除</el-button
              ></template
            ></el-table-column
          >
        </el-table>
      </el-collapse-item>
    </el-collapse>
  </div>

  <el-dialog v-model="createVisible" title="创建试卷" width="520px">
    <el-form label-position="top"
      ><el-form-item label="试卷名称"
        ><el-input v-model="paperForm.title" /></el-form-item
      ><el-form-item label="试卷说明"
        ><el-input
          v-model="paperForm.description"
          type="textarea"
          :rows="3" /></el-form-item
    ></el-form>
    <template #footer
      ><el-button @click="createVisible = false">取消</el-button
      ><el-button type="primary" :loading="saving" @click="createPaper"
        >创建</el-button
      ></template
    >
  </el-dialog>

  <el-dialog v-model="addVisible" title="添加试题" width="560px">
    <el-form label-position="top"
      ><el-form-item label="选择题目"
        ><el-select
          v-model="addForm.question_id"
          filterable
          style="width: 100%"
          placeholder="搜索并选择题目"
          ><el-option
            v-for="item in availableQuestions"
            :key="item.id"
            :label="item.stem"
            :value="item.id" /></el-select></el-form-item
      ><el-form-item label="分值"
        ><el-input-number
          v-model="addForm.score"
          :min="1"
          :max="100" /></el-form-item
    ></el-form>
    <template #footer
      ><el-button @click="addVisible = false">取消</el-button
      ><el-button type="primary" :loading="saving" @click="addQuestion"
        >加入试卷</el-button
      ></template
    >
  </el-dialog>
</template>

<style scoped>
.paper-layout {
  display: grid;
  gap: 18px;
}
.paper-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr) auto;
  align-items: center;
  gap: 24px;
}
.paper-summary span {
  display: block;
  color: #8192a3;
}
.paper-summary strong {
  display: block;
  margin-top: 7px;
  font-size: 28px;
}
.paper-list {
  padding: 8px 24px;
  background: white;
  border: 1px solid #e7edf4;
  border-radius: 18px;
}
.paper-title {
  display: flex;
  align-items: center;
  gap: 14px;
}
.paper-title span,
.paper-actions p {
  color: #8192a3;
}
.paper-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
@media (max-width: 760px) {
  .paper-summary {
    grid-template-columns: 1fr 1fr;
  }
  .paper-actions {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
