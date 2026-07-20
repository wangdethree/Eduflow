# EduFlow 智慧学习平台

EduFlow 是面向高校与职业培训场景的前后端分离在线学习平台。项目围绕“教师建课—管理员审核—学员学习—在线考试—成绩与统计”构建完整业务闭环，同时展示认证授权、数据权限、高频进度写入、幂等提交、异步任务和容器化部署等工程能力。

## 已实现能力

- 用户与认证：注册、登录、JWT 双令牌、Refresh Token 轮换、退出、资料与密码维护、登录日志。
- RBAC：用户、角色、权限管理，接口权限与课程资源归属双重校验。
- 课程中心：分类、课程、章节、课时、审核状态机、发布/下架、搜索和分页。
- 文件中心：MinIO 预签名直传、用途/类型/大小校验、上传确认、临时下载和软删除。
- 学习中心：选课、退课、收藏、Redis Lua 进度合并、断点续学、Celery 批量落库。
- 考试中心：单选/多选/判断题、组卷、考试发布、答题、自动判分、防重复提交和错题本。
- 消息中心：站内信、未读计数、已读/删除、考试发布、开考提醒和成绩通知。
- 数据统计：教师课程指标、章节完成率、学习排行、平均分/分数分布、平台运营总览。
- 前端界面：多角色工作台、课程、学习、考试、消息、教师与管理员页面，ECharts 可视化和响应式布局。
- 工程交付：Alembic、pytest、Ruff、ESLint、Locust、GitHub Actions、Docker Compose、Nginx。

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy 2.0、Pydantic 2、Alembic |
| 数据与任务 | MySQL 8、Redis、Celery、MinIO |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、ECharts |
| 质量与部署 | pytest、Ruff、ESLint、Prettier、Locust、Docker Compose、Nginx、GitHub Actions |

## 快速启动

推荐使用容器启动完整依赖：

```bash
cp .env.example .env
# 修改 .env 中所有“请替换”项
docker compose up -d --build
docker compose exec backend python scripts/init_data.py
```

启动后访问：

- 平台首页：<http://localhost>
- OpenAPI 文档：<http://localhost/docs>
- MinIO 控制台：<http://localhost:9001>（如需从宿主机访问，请在 Compose 中映射端口）

仅开发后端时可使用 SQLite：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install --index-url https://pypi.org/simple -e '.[dev]'
cp ../.env.example .env
# 将 DATABASE_URL 改为 sqlite+aiosqlite:///./eduflow.db
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

前端开发：

```bash
cd frontend
npm ci
npm run dev
```

Vite 开发地址为 <http://localhost:5173>，接口默认通过 `/api` 访问后端。

## 初始化账号

`backend/scripts/init_data.py` 会创建 `admin`、`teacher`、`student` 三类系统角色、基础权限、课程分类和一个管理员账号。管理员用户名、邮箱和密码由 `.env` 中以下变量决定：

```dotenv
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=请设置至少8位的强密码
```

项目不会在仓库中保存真实密码。

## 质量检查

```bash
cd backend
.venv/bin/ruff check app tests locustfile.py
.venv/bin/python -m pytest --cov=app

cd ../frontend
npm run lint
npm run build
```

当前本地验证基线：后端 `20 passed`，应用代码覆盖率 `75%`；前端 ESLint 与生产构建通过；`npm audit --omit=dev` 无已知漏洞。压测脚本已通过 Locust 用户发现检查，实际容量数据需在目标部署环境运行后记录。

## 项目文档

- [系统架构](docs/architecture.md)
- [数据库设计](docs/database.md)
- [API 使用说明](docs/api.md)
- [部署与运维](docs/deployment.md)
- [测试与压测](docs/testing.md)
- [面试说明](docs/interview-guide.md)

## 目录结构

```text
Eduflow/
├── backend/            # FastAPI 应用、迁移、任务、测试与压测
├── frontend/           # Vue 3 多角色界面
├── deploy/             # Nginx 网关配置
├── docs/               # 架构、数据库、API、部署和测试文档
├── .github/workflows/  # 持续集成
└── docker-compose.yml  # 完整运行环境
```

## 安全提示

- 生产环境必须替换 `SECRET_KEY`、数据库、MinIO 和管理员初始密码。
- 生产环境应启用 HTTPS，并将 MinIO、MySQL、Redis 仅暴露在内部网络。
- CORS 只允许真实前端域名；不要使用通配来源与凭据组合。
- 上线前应执行数据库备份与 Alembic 升级演练，并为 Redis 和 MinIO 设置持久化与备份策略。

本项目采用 Conventional Commits，提交示例：`feat(course): 增加课程审核`、`fix(auth): 修复令牌轮换`。
