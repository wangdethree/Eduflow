<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import request from "@/utils/request";
import type { ApiResponse, Category, Chapter, Course, Lesson } from "@/types";

const props = defineProps<{ courses: Course[]; categories: Category[] }>();
const emit = defineEmits<{ reload: [] }>();

const createVisible = ref(false);
const drawerVisible = ref(false);
const lessonVisible = ref(false);
const saving = ref(false);
const selected = ref<Course | null>(null);
const activeChapter = ref<Chapter | null>(null);
const editingLessonId = ref<number | null>(null);
const courseForm = reactive({
  title: "",
  subtitle: "",
  description: "",
  category_id: undefined as number | undefined,
  difficulty: "beginner",
  cover_url: "",
});
const lessonForm = reactive({
  title: "",
  lesson_type: "video",
  content: "",
  duration_seconds: 0,
  is_required: true,
  is_free_preview: false,
  sort_order: 1,
});

const statusText: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审核",
  rejected: "已驳回",
  published: "已发布",
  offline: "已下架",
};

function resetCourseForm() {
  Object.assign(courseForm, {
    title: "",
    subtitle: "",
    description: "",
    category_id: undefined,
    difficulty: "beginner",
    cover_url: "",
  });
}

async function createCourse() {
  if (!courseForm.title || !courseForm.category_id)
    return ElMessage.warning("请填写课程名称并选择分类");
  saving.value = true;
  try {
    await request.post("/courses", {
      ...courseForm,
      cover_url: courseForm.cover_url || null,
    });
    createVisible.value = false;
    resetCourseForm();
    ElMessage.success("课程草稿已创建");
    emit("reload");
  } finally {
    saving.value = false;
  }
}

async function openCourse(course: Course) {
  const { data } = await request.get<ApiResponse<Course>>(
    `/teacher/courses/${course.id}`,
  );
  selected.value = data.data;
  Object.assign(courseForm, {
    title: data.data.title,
    subtitle: data.data.subtitle,
    description: data.data.description,
    category_id: data.data.category_id,
    difficulty: data.data.difficulty,
    cover_url: data.data.cover_url || "",
  });
  drawerVisible.value = true;
}

async function reloadSelected() {
  if (!selected.value) return;
  const { data } = await request.get<ApiResponse<Course>>(
    `/teacher/courses/${selected.value.id}`,
  );
  selected.value = data.data;
  emit("reload");
}

async function saveCourse() {
  if (!selected.value) return;
  saving.value = true;
  try {
    await request.patch(`/courses/${selected.value.id}`, {
      ...courseForm,
      cover_url: courseForm.cover_url || null,
    });
    ElMessage.success("课程信息已保存");
    await reloadSelected();
  } finally {
    saving.value = false;
  }
}

async function addChapter() {
  if (!selected.value) return;
  const { value } = await ElMessageBox.prompt("请输入章节名称", "新增章节", {
    inputPattern: /^.{2,150}$/,
    inputErrorMessage: "章节名称需为 2-150 个字符",
  });
  await request.post(`/courses/${selected.value.id}/chapters`, {
    title: value,
  });
  ElMessage.success("章节已新增");
  await reloadSelected();
}

async function editChapter(chapter: Chapter) {
  if (!selected.value) return;
  const { value } = await ElMessageBox.prompt(
    "请输入新的章节名称",
    "编辑章节",
    {
      inputValue: chapter.title,
      inputPattern: /^.{2,150}$/,
      inputErrorMessage: "章节名称需为 2-150 个字符",
    },
  );
  await request.patch(`/courses/${selected.value.id}/chapters/${chapter.id}`, {
    title: value,
  });
  ElMessage.success("章节已更新");
  await reloadSelected();
}

async function moveChapter(chapter: Chapter, sortOrder: number) {
  if (!selected.value || sortOrder === chapter.sort_order) return;
  await request.patch(`/courses/${selected.value.id}/chapters/${chapter.id}`, {
    sort_order: sortOrder,
  });
  await reloadSelected();
}

async function deleteChapter(chapter: Chapter) {
  if (!selected.value) return;
  await ElMessageBox.confirm(
    `删除章节“${chapter.title}”及其全部课时？`,
    "确认删除",
    { type: "warning" },
  );
  await request.delete(`/courses/${selected.value.id}/chapters/${chapter.id}`);
  ElMessage.success("章节已删除");
  await reloadSelected();
}

function openLesson(chapter: Chapter, lesson?: Lesson) {
  activeChapter.value = chapter;
  editingLessonId.value = lesson?.id || null;
  Object.assign(
    lessonForm,
    lesson
      ? {
          title: lesson.title,
          lesson_type: lesson.lesson_type,
          content: lesson.content,
          duration_seconds: lesson.duration_seconds,
          is_required: lesson.is_required,
          is_free_preview: lesson.is_free_preview,
          sort_order: lesson.sort_order,
        }
      : {
          title: "",
          lesson_type: "video",
          content: "",
          duration_seconds: 0,
          is_required: true,
          is_free_preview: false,
          sort_order: chapter.lessons.length + 1,
        },
  );
  lessonVisible.value = true;
}

async function saveLesson() {
  if (!selected.value || !activeChapter.value || !lessonForm.title) return;
  const base = `/courses/${selected.value.id}/chapters/${activeChapter.value.id}`;
  saving.value = true;
  try {
    if (editingLessonId.value) {
      await request.patch(
        `${base}/lessons/${editingLessonId.value}`,
        lessonForm,
      );
    } else {
      await request.post(`${base}/lessons`, {
        title: lessonForm.title,
        lesson_type: lessonForm.lesson_type,
        content: lessonForm.content,
        duration_seconds: lessonForm.duration_seconds,
        is_required: lessonForm.is_required,
        is_free_preview: lessonForm.is_free_preview,
      });
    }
    lessonVisible.value = false;
    ElMessage.success(editingLessonId.value ? "课时已更新" : "课时已新增");
    await reloadSelected();
  } finally {
    saving.value = false;
  }
}

async function deleteLesson(chapter: Chapter, lesson: Lesson) {
  if (!selected.value) return;
  await ElMessageBox.confirm(`确认删除课时“${lesson.title}”？`, "确认删除", {
    type: "warning",
  });
  await request.delete(
    `/courses/${selected.value.id}/chapters/${chapter.id}/lessons/${lesson.id}`,
  );
  ElMessage.success("课时已删除");
  await reloadSelected();
}

async function submitReview() {
  if (!selected.value) return;
  await ElMessageBox.confirm(
    "提交后审核完成前不能继续编辑，确认提交？",
    "提交审核",
  );
  await request.post(`/courses/${selected.value.id}/submit-review`);
  ElMessage.success("课程已提交审核");
  await reloadSelected();
}

async function deleteCourse(course: Course) {
  await ElMessageBox.confirm(`确认删除课程“${course.title}”？`, "确认删除", {
    type: "warning",
  });
  await request.delete(`/courses/${course.id}`);
  drawerVisible.value = false;
  ElMessage.success("课程已删除");
  emit("reload");
}
</script>

<template>
  <div class="panel table-panel">
    <div class="panel-title">
      <div>
        <h2>课程与内容</h2>
        <small>维护课程资料、章节和课时，并提交审核</small>
      </div>
      <el-button type="primary" @click="createVisible = true"
        >创建课程</el-button
      >
    </div>
    <el-table :data="props.courses" empty-text="还没有课程，先创建一门吧">
      <el-table-column prop="title" label="课程" min-width="220" />
      <el-table-column prop="difficulty" label="难度" width="100" />
      <el-table-column prop="total_duration" label="时长（秒）" width="120" />
      <el-table-column label="状态" width="110">
        <template #default="scope"
          ><el-tag>{{ statusText[scope.row.status] }}</el-tag></template
        >
      </el-table-column>
      <el-table-column label="操作" width="180" align="right">
        <template #default="scope">
          <el-button link type="primary" @click="openCourse(scope.row)"
            >管理内容</el-button
          >
          <el-button
            v-if="['draft', 'rejected'].includes(scope.row.status)"
            link
            type="danger"
            @click="deleteCourse(scope.row)"
            >删除</el-button
          >
        </template>
      </el-table-column>
    </el-table>
  </div>

  <el-dialog v-model="createVisible" title="创建课程" width="560px">
    <el-form label-position="top">
      <el-form-item label="课程名称"
        ><el-input v-model="courseForm.title"
      /></el-form-item>
      <el-form-item label="课程简介"
        ><el-input v-model="courseForm.description" type="textarea" :rows="4"
      /></el-form-item>
      <el-form-item label="分类">
        <el-select v-model="courseForm.category_id" style="width: 100%">
          <el-option
            v-for="item in props.categories"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="难度">
        <el-radio-group v-model="courseForm.difficulty">
          <el-radio-button value="beginner">入门</el-radio-button>
          <el-radio-button value="intermediate">进阶</el-radio-button>
          <el-radio-button value="advanced">高级</el-radio-button>
        </el-radio-group>
      </el-form-item>
    </el-form>
    <template #footer
      ><el-button @click="createVisible = false">取消</el-button
      ><el-button type="primary" :loading="saving" @click="createCourse"
        >创建草稿</el-button
      ></template
    >
  </el-dialog>

  <el-drawer
    v-model="drawerVisible"
    title="课程内容管理"
    size="min(900px, 92vw)"
  >
    <template v-if="selected">
      <el-alert
        v-if="!['draft', 'rejected'].includes(selected.status)"
        title="当前状态不可编辑章节和课时"
        type="info"
        :closable="false"
      />
      <el-form class="course-form" label-position="top">
        <el-form-item label="课程名称"
          ><el-input v-model="courseForm.title"
        /></el-form-item>
        <el-form-item label="副标题"
          ><el-input v-model="courseForm.subtitle"
        /></el-form-item>
        <el-form-item label="课程简介" class="full"
          ><el-input v-model="courseForm.description" type="textarea" :rows="3"
        /></el-form-item>
        <el-form-item label="分类">
          <el-select v-model="courseForm.category_id" style="width: 100%"
            ><el-option
              v-for="item in props.categories"
              :key="item.id"
              :label="item.name"
              :value="item.id"
          /></el-select>
        </el-form-item>
        <el-form-item label="难度"
          ><el-select v-model="courseForm.difficulty" style="width: 100%"
            ><el-option label="入门" value="beginner" /><el-option
              label="进阶"
              value="intermediate" /><el-option
              label="高级"
              value="advanced" /></el-select
        ></el-form-item>
      </el-form>
      <div class="drawer-actions">
        <el-button type="primary" :loading="saving" @click="saveCourse"
          >保存课程资料</el-button
        ><el-button
          v-if="['draft', 'rejected'].includes(selected.status)"
          @click="submitReview"
          >提交审核</el-button
        >
      </div>
      <el-divider />
      <div class="panel-title">
        <div>
          <h2>章节与课时</h2>
          <small>拖动替代方案：输入目标序号即可重排</small>
        </div>
        <el-button
          :disabled="!['draft', 'rejected'].includes(selected.status)"
          @click="addChapter"
          >新增章节</el-button
        >
      </div>
      <el-empty v-if="!selected.chapters.length" description="暂无章节" />
      <el-collapse v-else>
        <el-collapse-item
          v-for="chapter in selected.chapters"
          :key="chapter.id"
          :name="chapter.id"
        >
          <template #title
            ><b>{{ chapter.sort_order }}. {{ chapter.title }}</b
            ><el-tag size="small" class="chapter-count"
              >{{ chapter.lessons.length }} 课时</el-tag
            ></template
          >
          <div class="chapter-actions">
            <span>排序</span
            ><el-input-number
              :model-value="chapter.sort_order"
              :min="1"
              :max="selected.chapters.length"
              size="small"
              @change="
                (value: number | undefined) =>
                  value && moveChapter(chapter, value)
              "
            />
            <el-button link @click="editChapter(chapter)">重命名</el-button
            ><el-button link type="primary" @click="openLesson(chapter)"
              >新增课时</el-button
            ><el-button link type="danger" @click="deleteChapter(chapter)"
              >删除章节</el-button
            >
          </div>
          <el-table :data="chapter.lessons" size="small" empty-text="暂无课时">
            <el-table-column
              prop="sort_order"
              label="#"
              width="48"
            /><el-table-column
              prop="title"
              label="课时"
              min-width="180"
            /><el-table-column
              prop="lesson_type"
              label="类型"
              width="80"
            /><el-table-column
              prop="duration_seconds"
              label="时长/秒"
              width="90"
            /><el-table-column label="操作" width="120"
              ><template #default="scope"
                ><el-button link @click="openLesson(chapter, scope.row)"
                  >编辑</el-button
                ><el-button
                  link
                  type="danger"
                  @click="deleteLesson(chapter, scope.row)"
                  >删除</el-button
                ></template
              ></el-table-column
            >
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </template>
  </el-drawer>

  <el-dialog
    v-model="lessonVisible"
    :title="editingLessonId ? '编辑课时' : '新增课时'"
    width="620px"
  >
    <el-form label-position="top">
      <el-form-item label="课时名称"
        ><el-input v-model="lessonForm.title"
      /></el-form-item>
      <div class="two-column">
        <el-form-item label="类型"
          ><el-select v-model="lessonForm.lesson_type" style="width: 100%"
            ><el-option label="视频" value="video" /><el-option
              label="图文"
              value="article" /></el-select></el-form-item
        ><el-form-item label="时长（秒）"
          ><el-input-number
            v-model="lessonForm.duration_seconds"
            :min="0"
            :max="86400"
        /></el-form-item>
      </div>
      <el-form-item label="内容或资源地址"
        ><el-input v-model="lessonForm.content" type="textarea" :rows="5"
      /></el-form-item>
      <el-form-item v-if="editingLessonId" label="排序"
        ><el-input-number v-model="lessonForm.sort_order" :min="1"
      /></el-form-item>
      <el-checkbox v-model="lessonForm.is_required">必修课时</el-checkbox
      ><el-checkbox v-model="lessonForm.is_free_preview"
        >允许免费试看</el-checkbox
      >
    </el-form>
    <template #footer
      ><el-button @click="lessonVisible = false">取消</el-button
      ><el-button type="primary" :loading="saving" @click="saveLesson"
        >保存</el-button
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
.course-form,
.two-column {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 18px;
}
.course-form .full {
  grid-column: 1 / -1;
}
.drawer-actions {
  display: flex;
  gap: 10px;
}
.chapter-count {
  margin-left: 12px;
}
.chapter-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  color: #7b8da0;
}
@media (max-width: 680px) {
  .course-form,
  .two-column {
    grid-template-columns: 1fr;
  }
}
</style>
