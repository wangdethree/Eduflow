<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import request from "@/utils/request";
import type { ApiResponse, Question } from "@/types";

const questions = ref<Question[]>([]);
const keyword = ref("");
const dialogVisible = ref(false);
const saving = ref(false);
const editingId = ref<number | null>(null);
const singleAnswer = ref("A");
const multipleAnswers = ref<string[]>([]);
const form = reactive({
  stem: "",
  question_type: "single" as Question["question_type"],
  difficulty: "medium",
  analysis: "",
  options: { A: "", B: "", C: "", D: "" } as Record<string, string>,
});
const filtered = computed(() =>
  questions.value.filter(
    (item) =>
      !keyword.value ||
      item.stem.toLowerCase().includes(keyword.value.toLowerCase()),
  ),
);
const typeText = { single: "单选题", multiple: "多选题", boolean: "判断题" };
const difficultyText = { easy: "简单", medium: "中等", hard: "困难" };

async function load() {
  const { data } = await request.get<ApiResponse<Question[]>>("/questions");
  questions.value = data.data;
}

function resetForm() {
  Object.assign(form, {
    stem: "",
    question_type: "single",
    difficulty: "medium",
    analysis: "",
  });
  Object.assign(form.options, { A: "", B: "", C: "", D: "" });
  singleAnswer.value = "A";
  multipleAnswers.value = [];
  editingId.value = null;
}

function openCreate() {
  resetForm();
  dialogVisible.value = true;
}

function openEdit(question: Question) {
  resetForm();
  editingId.value = question.id;
  Object.assign(form, {
    stem: question.stem,
    question_type: question.question_type,
    difficulty: question.difficulty,
    analysis: question.analysis,
  });
  Object.assign(form.options, question.options);
  singleAnswer.value = question.correct_answers[0] || "A";
  multipleAnswers.value = [...question.correct_answers];
  dialogVisible.value = true;
}

watch(
  () => form.question_type,
  (type) => {
    if (type === "boolean") singleAnswer.value = "true";
    else if (!["A", "B", "C", "D"].includes(singleAnswer.value))
      singleAnswer.value = "A";
  },
);

async function save() {
  const options =
    form.question_type === "boolean"
      ? {}
      : Object.fromEntries(
          Object.entries(form.options).filter(([, value]) => value.trim()),
        );
  const correctAnswers =
    form.question_type === "multiple"
      ? multipleAnswers.value
      : [singleAnswer.value];
  if (
    !form.stem ||
    (form.question_type !== "boolean" && Object.keys(options).length < 2)
  ) {
    return ElMessage.warning("请填写题干和至少两个选项");
  }
  if (form.question_type === "multiple" && correctAnswers.length < 2) {
    return ElMessage.warning("多选题至少选择两个正确答案");
  }
  const payload = {
    stem: form.stem,
    question_type: form.question_type,
    difficulty: form.difficulty,
    analysis: form.analysis,
    options,
    correct_answers: correctAnswers,
  };
  saving.value = true;
  try {
    if (editingId.value)
      await request.put(`/questions/${editingId.value}`, payload);
    else await request.post("/questions", payload);
    dialogVisible.value = false;
    ElMessage.success(editingId.value ? "题目已更新" : "题目已创建");
    await load();
  } finally {
    saving.value = false;
  }
}

async function remove(question: Question) {
  await ElMessageBox.confirm(
    `确认删除题目“${question.stem.slice(0, 30)}”？`,
    "确认删除",
    { type: "warning" },
  );
  await request.delete(`/questions/${question.id}`);
  ElMessage.success("题目已删除");
  await load();
}

onMounted(load);
</script>

<template>
  <div class="panel table-panel">
    <div class="panel-title">
      <div>
        <h2>我的题库</h2>
        <small>题型、答案与解析统一维护，已组卷题目需先从试卷移除</small>
      </div>
      <div class="toolbar">
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索题干"
        /><el-button type="primary" @click="openCreate">新增题目</el-button>
      </div>
    </div>
    <el-table :data="filtered" empty-text="题库为空">
      <el-table-column label="题干" min-width="320"
        ><template #default="scope"
          ><div class="question-stem">{{ scope.row.stem }}</div>
          <small>{{ scope.row.analysis || "暂无解析" }}</small></template
        ></el-table-column
      >
      <el-table-column label="题型" width="100"
        ><template #default="scope"
          ><el-tag effect="plain">{{
            typeText[scope.row.question_type as keyof typeof typeText]
          }}</el-tag></template
        ></el-table-column
      >
      <el-table-column label="难度" width="90"
        ><template #default="scope">{{
          difficultyText[scope.row.difficulty as keyof typeof difficultyText]
        }}</template></el-table-column
      >
      <el-table-column label="答案" width="120"
        ><template #default="scope">{{
          scope.row.correct_answers.join("、")
        }}</template></el-table-column
      >
      <el-table-column label="操作" width="130"
        ><template #default="scope"
          ><el-button link @click="openEdit(scope.row)">编辑</el-button
          ><el-button link type="danger" @click="remove(scope.row)"
            >删除</el-button
          ></template
        ></el-table-column
      >
    </el-table>
  </div>

  <el-dialog
    v-model="dialogVisible"
    :title="editingId ? '编辑题目' : '新增题目'"
    width="680px"
  >
    <el-form label-position="top">
      <div class="two-column">
        <el-form-item label="题型"
          ><el-select v-model="form.question_type" style="width: 100%"
            ><el-option label="单选题" value="single" /><el-option
              label="多选题"
              value="multiple" /><el-option
              label="判断题"
              value="boolean" /></el-select></el-form-item
        ><el-form-item label="难度"
          ><el-select v-model="form.difficulty" style="width: 100%"
            ><el-option label="简单" value="easy" /><el-option
              label="中等"
              value="medium" /><el-option
              label="困难"
              value="hard" /></el-select
        ></el-form-item>
      </div>
      <el-form-item label="题干"
        ><el-input v-model="form.stem" type="textarea" :rows="3"
      /></el-form-item>
      <template v-if="form.question_type !== 'boolean'">
        <el-form-item
          v-for="key in ['A', 'B', 'C', 'D']"
          :key="key"
          :label="`选项 ${key}`"
          ><el-input v-model="form.options[key]"
        /></el-form-item>
        <el-form-item label="正确答案">
          <el-radio-group
            v-if="form.question_type === 'single'"
            v-model="singleAnswer"
            ><el-radio
              v-for="key in ['A', 'B', 'C', 'D']"
              :key="key"
              :value="key"
              :disabled="!form.options[key]"
              >{{ key }}</el-radio
            ></el-radio-group
          >
          <el-checkbox-group v-else v-model="multipleAnswers"
            ><el-checkbox
              v-for="key in ['A', 'B', 'C', 'D']"
              :key="key"
              :value="key"
              :disabled="!form.options[key]"
              >{{ key }}</el-checkbox
            ></el-checkbox-group
          >
        </el-form-item>
      </template>
      <el-form-item v-else label="正确答案"
        ><el-radio-group v-model="singleAnswer"
          ><el-radio value="true">正确</el-radio
          ><el-radio value="false">错误</el-radio></el-radio-group
        ></el-form-item
      >
      <el-form-item label="答案解析"
        ><el-input v-model="form.analysis" type="textarea" :rows="3"
      /></el-form-item>
    </el-form>
    <template #footer
      ><el-button @click="dialogVisible = false">取消</el-button
      ><el-button type="primary" :loading="saving" @click="save"
        >保存题目</el-button
      ></template
    >
  </el-dialog>
</template>

<style scoped>
.panel-title small,
td small {
  display: block;
  margin-top: 6px;
  color: #8192a3;
}
.toolbar,
.two-column {
  display: flex;
  gap: 12px;
}
.toolbar .el-input {
  width: 220px;
}
.two-column > * {
  flex: 1;
}
.question-stem {
  line-height: 1.5;
}
@media (max-width: 680px) {
  .panel-title,
  .toolbar,
  .two-column {
    align-items: stretch;
    flex-direction: column;
  }
  .toolbar .el-input {
    width: 100%;
  }
}
</style>
