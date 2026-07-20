# 测试与压测

## 自动化测试

后端测试使用 pytest、httpx ASGITransport 和独立 SQLite 数据库，覆盖：

- 注册、登录、双令牌刷新、退出和密码安全。
- RBAC 接口权限、角色分配和资源归属越权。
- 课程创建、章节课时、审核状态机、公开查询。
- MinIO 预签名、对象校验、下载和删除（存储客户端替身）。
- Redis 进度乱序、完成判定、批量落库和收藏。
- 考试自动评分、重复提交、错题本及通知接收者。
- 消息未读计数、已读、删除、广播和定时提醒幂等。
- 教师与管理员统计。
- 核心 E2E：建课、审核、选课、学习完成整条链路。

执行：

```bash
cd backend
.venv/bin/ruff check app tests locustfile.py
.venv/bin/python -m pytest --cov=app --cov-fail-under=85 --cov-report=term-missing
```

2026-07-20 本地验证基线为 `25 passed`、应用总代码覆盖率 `90.37%`。Coverage 已启用 greenlet/thread 并发追踪，避免 SQLAlchemy 异步 greenlet 切换后的代码被漏记；CI 以 `85%` 为硬门槛。测试包含考试并发重复提交、Redis 不可用时进度写入返回 503、进度读取降级数据库，以及通知缓存故障降级。

前端质量检查：

```bash
cd frontend
npm run lint
npm run build
npm audit --omit=dev
```

当前 ESLint、TypeScript/Vite 生产构建已通过，官方 npm registry 审计结果为 `0 vulnerabilities`。构建仍提示 Element Plus 主分包较大，属于后续按需导入优化项。

## CI

GitHub Actions 在 push 与 pull request 时执行：

1. Python 3.11 安装开发依赖、Ruff、pytest + coverage。
2. Node 22 使用 `npm ci` 复现锁文件依赖、ESLint 和生产构建。

## Locust 场景

`backend/locustfile.py` 包含公开课程浏览、健康检查、我的课程和通知读取。未提供账号时只压公开接口；提供单账号或账号池后加入受保护读取接口。固定基准使用 50 个独立账号，避免所有虚拟用户争抢同一用户记录而扭曲正常读取场景；真实 MySQL 集成测试另行保留 20 路同账号并发登录死锁回归。

```bash
cd backend
export LOCUST_HOST=http://127.0.0.1:8000
export LOCUST_ACCOUNT=student_account
export LOCUST_PASSWORD='student_password'
.venv/bin/locust -f locustfile.py
```

账号池模式使用 `LOCUST_ACCOUNT_PREFIX`、`LOCUST_ACCOUNT_COUNT` 和统一测试密码，账号可先由 `scripts/prepare_benchmark_users.py` 幂等准备。

访问 <http://localhost:8089> 配置用户数和爬升速率。无界面短跑示例：

```bash
.venv/bin/locust -f locustfile.py --headless \
  -u 50 -r 5 -t 2m \
  --csv reports/locust
```

## 性能验收方法

建议在与生产相近的独立环境分三轮执行，每轮预热后至少持续 10 分钟：

| 场景 | 关注指标 | 初始建议目标 |
|---|---|---|
| 课程公开列表 | P95、吞吐、MySQL 慢查询 | P95 < 300 ms，错误率 < 0.1% |
| 登录后学习数据 | P95、Redis/DB 连接池 | P95 < 500 ms，错误率 < 0.1% |
| 学习进度上报 | Redis CPU、Worker 积压、最终一致性 | 不丢进度，落库延迟 < 2 min |
| 考试集中提交 | 锁冲突、幂等、DB 事务耗时 | 不重复评分，业务错误可解释 |

这些数值是验收目标，不是已测结果。真实报告必须记录：代码提交、机器规格、数据规模、容器资源限制、并发模型、P50/P95/P99、RPS、错误率、数据库/Redis/队列指标及瓶颈结论。

## 真实依赖集成与固定基准

仓库提供独立的 `deploy/docker-compose.integration.yml`，使用 MySQL 8.0、Redis 7.4 和 MinIO，并为各容器设置固定资源上限。该环境使用独立数据库和宿主机端口，不与开发数据混用；生产 Compose 仍使用 MySQL 8.4，后续需在发布候选环境补跑一次 8.4 兼容性回归。

```bash
cp .env.integration.example .env.integration
backend/scripts/run_integration_benchmark.sh
```

脚本依次执行：启动真实依赖与应用、初始化权限数据、运行 `integration_tests` 的 MySQL/Redis/MinIO 和课程审核链路、再以 50 个并发用户、每秒 5 个用户爬升、持续 2 分钟执行 Locust。原始 CSV/HTML 写入忽略提交的 `reports/runtime/`；确认环境和数据有效后，再将摘要整理为带日期的 `docs/performance-report-*.md` 提交。

## 上线前人工检查

- 三类角色分别走通主要导航和权限边界。
- 令牌过期自动刷新与退出后的旧令牌失效。
- 课程审核、退回、再提交和下架状态转换。
- 断网重试进度不倒退，重复考试提交只产生一份成绩。
- MinIO 私有文件不可绕过授权永久访问。
- 备份恢复、迁移升级、服务重启和 Worker 任务重试。
