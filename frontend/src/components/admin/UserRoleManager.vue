<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import request from "@/utils/request";
import type { ApiResponse, ManagedUser, Permission, Role } from "@/types";

const users = ref<ManagedUser[]>([]);
const roles = ref<Role[]>([]);
const permissions = ref<Permission[]>([]);
const roleDialogVisible = ref(false);
const permissionDialogVisible = ref(false);
const createRoleVisible = ref(false);
const selectedUser = ref<ManagedUser | null>(null);
const selectedRole = ref<Role | null>(null);
const selectedRoleIds = ref<number[]>([]);
const selectedPermissionIds = ref<number[]>([]);
const roleForm = reactive({ name: "", code: "", description: "" });
const saving = ref(false);

async function load() {
  const [userResponse, roleResponse, permissionResponse] = await Promise.all([
    request.get<ApiResponse<ManagedUser[]>>("/users"),
    request.get<ApiResponse<Role[]>>("/roles"),
    request.get<ApiResponse<Permission[]>>("/permissions"),
  ]);
  users.value = userResponse.data.data;
  roles.value = roleResponse.data.data;
  permissions.value = permissionResponse.data.data;
}

function openUserRoles(user: ManagedUser) {
  selectedUser.value = user;
  selectedRoleIds.value = user.roles.map((role) => role.id);
  roleDialogVisible.value = true;
}

async function saveUserRoles() {
  if (!selectedUser.value) return;
  saving.value = true;
  try {
    await request.put(`/users/${selectedUser.value.id}/roles`, {
      ids: selectedRoleIds.value,
    });
    roleDialogVisible.value = false;
    ElMessage.success("用户角色已更新，旧令牌已失效");
    await load();
  } finally {
    saving.value = false;
  }
}

async function changeStatus(user: ManagedUser) {
  const nextStatus = user.status === "active" ? "disabled" : "active";
  await ElMessageBox.confirm(
    nextStatus === "disabled"
      ? `确认禁用用户“${user.username}”？`
      : `确认启用用户“${user.username}”？`,
    "修改用户状态",
    { type: nextStatus === "disabled" ? "warning" : "info" },
  );
  await request.patch(`/users/${user.id}/status`, { status: nextStatus });
  ElMessage.success(nextStatus === "disabled" ? "用户已禁用" : "用户已启用");
  await load();
}

function openPermissions(role: Role) {
  selectedRole.value = role;
  selectedPermissionIds.value = role.permissions.map((item) => item.id);
  permissionDialogVisible.value = true;
}

async function savePermissions() {
  if (!selectedRole.value) return;
  saving.value = true;
  try {
    await request.put(`/roles/${selectedRole.value.id}/permissions`, {
      ids: selectedPermissionIds.value,
    });
    permissionDialogVisible.value = false;
    ElMessage.success("角色权限已更新");
    await load();
  } finally {
    saving.value = false;
  }
}

async function createRole() {
  if (!roleForm.name || !roleForm.code)
    return ElMessage.warning("请填写角色名称和编码");
  saving.value = true;
  try {
    await request.post("/roles", roleForm);
    createRoleVisible.value = false;
    Object.assign(roleForm, { name: "", code: "", description: "" });
    ElMessage.success("角色已创建");
    await load();
  } finally {
    saving.value = false;
  }
}

async function deleteRole(role: Role) {
  await ElMessageBox.confirm(`确认删除角色“${role.name}”？`, "删除角色", {
    type: "warning",
  });
  await request.delete(`/roles/${role.id}`);
  ElMessage.success("角色已删除");
  await load();
}

onMounted(load);
</script>

<template>
  <div class="management-grid">
    <div class="panel table-panel">
      <div class="panel-title">
        <div>
          <h2>用户与角色</h2>
          <small>分配角色或启停账号后，用户旧令牌会立即失效</small>
        </div>
        <span>共 {{ users.length }} 人</span>
      </div>
      <el-table :data="users" empty-text="暂无用户">
        <el-table-column
          prop="username"
          label="用户名"
          min-width="120"
        /><el-table-column
          prop="nickname"
          label="昵称"
          min-width="120"
        /><el-table-column
          prop="email"
          label="邮箱"
          min-width="200"
        /><el-table-column label="角色" min-width="180"
          ><template #default="scope"
            ><el-tag
              v-for="role in scope.row.roles"
              :key="role.id"
              effect="plain"
              class="role-tag"
              >{{ role.name }}</el-tag
            ></template
          ></el-table-column
        ><el-table-column label="状态" width="90"
          ><template #default="scope"
            ><el-tag
              :type="scope.row.status === 'active' ? 'success' : 'danger'"
              >{{ scope.row.status === "active" ? "正常" : "禁用" }}</el-tag
            ></template
          ></el-table-column
        ><el-table-column label="操作" width="160"
          ><template #default="scope"
            ><el-button link type="primary" @click="openUserRoles(scope.row)"
              >分配角色</el-button
            ><el-button
              link
              :type="scope.row.status === 'active' ? 'danger' : 'success'"
              @click="changeStatus(scope.row)"
              >{{ scope.row.status === "active" ? "禁用" : "启用" }}</el-button
            ></template
          ></el-table-column
        >
      </el-table>
    </div>
    <div class="panel table-panel">
      <div class="panel-title">
        <div>
          <h2>角色权限</h2>
          <small>系统角色可调整权限，但不能删除</small>
        </div>
        <el-button type="primary" plain @click="createRoleVisible = true"
          >新建角色</el-button
        >
      </div>
      <el-table :data="roles"
        ><el-table-column prop="name" label="角色" min-width="130"
          ><template #default="scope"
            >{{ scope.row.name }}
            <el-tag v-if="scope.row.is_system" size="small"
              >系统</el-tag
            ></template
          ></el-table-column
        ><el-table-column
          prop="code"
          label="编码"
          min-width="130"
        /><el-table-column label="权限数" width="90"
          ><template #default="scope">{{
            scope.row.permissions.length
          }}</template></el-table-column
        ><el-table-column label="操作" width="150"
          ><template #default="scope"
            ><el-button link @click="openPermissions(scope.row)"
              >权限配置</el-button
            ><el-button
              v-if="!scope.row.is_system"
              link
              type="danger"
              @click="deleteRole(scope.row)"
              >删除</el-button
            ></template
          ></el-table-column
        ></el-table
      >
    </div>
  </div>

  <el-dialog
    v-model="roleDialogVisible"
    :title="`为 ${selectedUser?.username || ''} 分配角色`"
    width="520px"
    ><el-checkbox-group v-model="selectedRoleIds" class="checkbox-list"
      ><el-checkbox v-for="role in roles" :key="role.id" :value="role.id"
        ><b>{{ role.name }}</b
        ><small>{{ role.description || role.code }}</small></el-checkbox
      ></el-checkbox-group
    ><template #footer
      ><el-button @click="roleDialogVisible = false">取消</el-button
      ><el-button type="primary" :loading="saving" @click="saveUserRoles"
        >保存角色</el-button
      ></template
    ></el-dialog
  >
  <el-dialog
    v-model="permissionDialogVisible"
    :title="`配置 ${selectedRole?.name || ''} 权限`"
    width="620px"
    ><el-checkbox-group v-model="selectedPermissionIds" class="permission-grid"
      ><el-checkbox v-for="item in permissions" :key="item.id" :value="item.id"
        ><b>{{ item.name }}</b
        ><small>{{ item.code }}</small></el-checkbox
      ></el-checkbox-group
    ><template #footer
      ><el-button @click="permissionDialogVisible = false">取消</el-button
      ><el-button type="primary" :loading="saving" @click="savePermissions"
        >保存权限</el-button
      ></template
    ></el-dialog
  >
  <el-dialog v-model="createRoleVisible" title="新建角色" width="520px"
    ><el-form label-position="top"
      ><el-form-item label="角色名称"
        ><el-input v-model="roleForm.name" /></el-form-item
      ><el-form-item label="角色编码"
        ><el-input
          v-model="roleForm.code"
          placeholder="例如 content_operator" /></el-form-item
      ><el-form-item label="角色说明"
        ><el-input
          v-model="roleForm.description"
          type="textarea" /></el-form-item></el-form
    ><template #footer
      ><el-button @click="createRoleVisible = false">取消</el-button
      ><el-button type="primary" :loading="saving" @click="createRole"
        >创建角色</el-button
      ></template
    ></el-dialog
  >
</template>

<style scoped>
.management-grid {
  display: grid;
  gap: 20px;
}
.panel-title small {
  display: block;
  margin-top: 6px;
  color: #8192a3;
}
.role-tag {
  margin: 2px 5px 2px 0;
}
.checkbox-list,
.permission-grid {
  display: grid;
  gap: 12px;
}
.permission-grid {
  grid-template-columns: 1fr 1fr;
}
.checkbox-list .el-checkbox,
.permission-grid .el-checkbox {
  height: auto;
  margin: 0;
  padding: 12px;
  border: 1px solid #e7edf4;
  border-radius: 10px;
}
.checkbox-list small,
.permission-grid small {
  display: block;
  color: #8192a3;
}
@media (max-width: 680px) {
  .permission-grid {
    grid-template-columns: 1fr;
  }
}
</style>
