# API 使用说明

## 基本约定

- 基础路径：`/api/v1`
- 认证方式：`Authorization: Bearer <access_token>`
- 在线文档：`/docs`；OpenAPI：`/openapi.json`
- 列表默认使用 `page`、`page_size`，并按模块支持 `keyword`、`status` 等筛选。

成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "request_id": "req_xxx"
}
```

业务异常保持相同结构，并使用合适的 HTTP 状态码；参数校验失败固定为 HTTP 422、业务码 `10001`。排障时应同时记录 HTTP 状态、业务码和 `request_id`。

## 认证示例

登录：

```bash
curl -X POST http://localhost/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"account":"admin","password":"你的密码"}'
```

调用受保护接口：

```bash
curl http://localhost/api/v1/auth/me \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

刷新接口接收 Refresh Token，成功后会返回一对新令牌并撤销旧 Refresh Token；客户端必须原子替换本地令牌。

## 接口清单

### 用户与权限

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/register` | 注册 |
| POST | `/auth/login` | 登录并记录日志 |
| POST | `/auth/refresh` | 轮换双令牌 |
| POST | `/auth/logout` | 撤销当前会话 |
| GET/PATCH | `/auth/me` | 查询/修改资料 |
| POST | `/auth/change-password` | 修改密码并使旧会话失效 |
| GET/POST | `/roles` | 角色列表/创建 |
| DELETE | `/roles/{role_id}` | 删除非系统角色 |
| PUT | `/roles/{role_id}/permissions` | 分配权限 |
| GET/POST | `/permissions` | 权限列表/创建 |
| GET | `/users` | 用户分页 |
| PUT | `/users/{user_id}/roles` | 分配角色 |
| PATCH | `/users/{user_id}/status` | 启用或禁用用户 |

### 课程与文件

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/course-categories` | 分类列表/创建 |
| GET/POST | `/courses` | 公开课程分页/教师建课 |
| GET/PATCH/DELETE | `/courses/{course_id}` | 详情/编辑/删除草稿 |
| GET | `/teacher/courses` | 当前教师课程 |
| POST | `/courses/{course_id}/chapters` | 创建章节 |
| POST | `/courses/{course_id}/chapters/{chapter_id}/lessons` | 创建课时 |
| POST | `/courses/{course_id}/submit-review` | 提交审核 |
| POST | `/courses/{course_id}/audit` | 管理员审核 |
| POST | `/courses/{course_id}/offline` | 下架 |
| POST | `/files/presigned-upload` | 申请预签名上传 |
| POST | `/files/{file_id}/complete` | 确认上传 |
| GET | `/files/{file_id}/download` | 临时下载地址 |
| DELETE | `/files/{file_id}` | 删除文件 |

### 学习、考试、消息与统计

| 方法 | 路径 | 说明 |
|---|---|---|
| POST/DELETE | `/learning/courses/{course_id}/enroll` | 加入/退出课程 |
| GET | `/learning/courses` | 我的课程 |
| POST | `/learning/courses/{course_id}/progress` | 高频进度上报 |
| GET | `/learning/lessons/{lesson_id}/progress` | 恢复学习位置 |
| POST | `/learning/courses/{course_id}/favorite` | 收藏切换 |
| POST | `/questions` | 创建题目 |
| POST | `/papers` | 创建试卷 |
| POST | `/papers/{paper_id}/questions` | 试卷加题 |
| POST | `/exams` | 发布考试 |
| POST | `/exams/{exam_id}/start` | 开始考试 |
| POST | `/exams/{exam_id}/submit` | 幂等提交与自动评分 |
| GET | `/exam-attempts/{attempt_id}` | 查询成绩 |
| GET | `/wrong-questions` | 错题本 |
| GET | `/notifications` | 消息分页 |
| GET | `/notifications/unread-count` | 未读数 |
| POST | `/notifications/{message_id}/read` | 单条已读 |
| POST | `/notifications/read-all` | 全部已读 |
| DELETE | `/notifications/{message_id}` | 删除消息 |
| POST | `/notifications/broadcast` | 管理员广播 |
| GET | `/statistics/teacher/courses/{course_id}` | 教师课程统计 |
| GET | `/statistics/admin/overview` | 平台总览 |

## 文件上传流程

1. 调用 `/files/presigned-upload`，提交文件名、内容类型、字节数、用途和公开性。
2. 使用返回的 URL 直接 `PUT` 到 MinIO，请求的 `Content-Type` 与申请值保持一致。
3. 调用 `/files/{file_id}/complete`；服务端检查对象元数据后把状态改为 `ready`。
4. 私有文件通过 `/download` 获取短期有效 URL，不在数据库中保存永久签名。

## 进度上报规则

`learned_seconds_delta` 单次最大 60 秒，`client_updated_at` 必须单调递增。服务端拒绝旧时间戳，`position_seconds` 不倒退，并按“位置达到 90% 且有效学习时长达到 80%”判断完成。

## 考试提交规则

客户端为一次提交生成稳定、足够长的 `idempotency_key`。网络超时后应使用同一 key 重试；服务端会返回已评分结果，不会重复生成答案或错题记录。
