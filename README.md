# EduFlow 智慧学习平台

EduFlow 是面向高校和职业培训场景的前后端分离在线学习平台，覆盖课程发布、在线学习、考试测评、消息通知和教学数据分析。

## 技术栈

- 后端：FastAPI、SQLAlchemy 2.0、MySQL、Redis、Celery、MinIO
- 前端：Vue 3、TypeScript、Pinia、Element Plus、ECharts
- 工程：Alembic、pytest、Ruff、MyPy、Docker Compose、GitHub Actions

## 本地开发

```bash
cp .env.example .env
cd backend && python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload
```

另开终端：

```bash
cd frontend && npm install && npm run dev
```

访问 API 文档：<http://localhost:8000/docs>，前端：<http://localhost:5173>。

完整容器化部署与账号说明将在后续模块中补充。
