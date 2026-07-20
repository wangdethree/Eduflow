# EduFlow 真实依赖固定规格性能报告

## 报告结论

2026-07-20 在真实 MySQL、Redis、MinIO 容器环境中完成 50 用户固定规格 Locust 基准。以生成的最终 CSV 为准，共完成 3,687 次请求，失败 0 次，错误率 0%，平均吞吐 30.41 RPS；总体 P50 为 20 ms、P95 为 230 ms、P99 为 870 ms。

本轮满足当前读取场景的初始验收目标：课程列表 P95 小于 300 ms，登录后的学习数据接口 P95 小于 500 ms，整体错误率小于 0.1%。本报告是小数据量、单后端实例的开发机基准，不能替代发布候选环境的容量测试。

## 可复现信息

| 项目 | 规格 |
|---|---|
| 测试日期 | 2026-07-20 12:21:33 至 12:23:35（Asia/Shanghai） |
| 被测代码 | `7eb982d`，并发登录修复为 `c7714d3` |
| 主机 | MacBook Pro，Intel Core i5 2.3 GHz，4 核，8 GB 内存 |
| 操作系统 | macOS 15.7.7 |
| 容器引擎 | Docker Engine 29.5.3 |
| 后端 | Python 3.12、单 Uvicorn 进程，2 CPU / 1 GB 上限 |
| MySQL | 8.0.46，2 CPU / 2 GB 上限 |
| Redis | 7.4.9，1 CPU / 512 MB 上限 |
| MinIO | `RELEASE.2025-04-22T22-12-26Z`，1 CPU / 512 MB 上限 |
| 压测端 | Locust 2.46.0，独立容器，2 CPU / 1 GB 上限 |
| 网络 | 同一 Docker bridge 网络，未经过公网或 TLS |

环境由 `.env.integration.example`、`docker-compose.yml` 和 `deploy/docker-compose.integration.yml` 共同定义。验证脚本在压测前直接执行 MySQL 查询、Redis 读写、MinIO 对象上传下载删除，以及注册、角色分配、课程章节、提交审核、审核发布完整链路。

## 负载模型

- 50 个独立测试账号，每个虚拟用户登录一次，避免共享账号热点扭曲常规读取结果。
- 以每秒 5 个用户爬升，约 10 秒到达 50 用户，持续时间参数为 2 分钟，停止等待 10 秒。
- 用户思考时间在 1 至 3 秒之间。
- 任务权重为课程列表 5、健康检查 2、登录后学习数据 3；每次学习数据任务分别请求“我的课程”和“通知列表”。
- 压测前额外执行 20 路同账号并发登录回归，确认真实 MySQL 下无 HTTP 500。

复现命令：

```bash
cp .env.integration.example .env.integration
backend/scripts/run_integration_benchmark.sh
```

## 最终结果

| 接口 | 请求数 | 失败数 | 平均耗时 | P50 | P95 | P99 | RPS |
|---|---:|---:|---:|---:|---:|---:|---:|
| `GET /courses` | 1,394 | 0 | 57.74 ms | 26 ms | 150 ms | 770 ms | 11.50 |
| `GET /health` | 533 | 0 | 32.57 ms | 6 ms | 110 ms | 510 ms | 4.40 |
| `GET /learning/courses` | 860 | 0 | 61.92 ms | 16 ms | 250 ms | 1,600 ms | 7.09 |
| `GET /notifications` | 850 | 0 | 28.09 ms | 14 ms | 85 ms | 290 ms | 7.01 |
| `POST /auth/login` | 50 | 0 | 852.91 ms | 810 ms | 1,100 ms | 1,800 ms | 0.41 |
| **汇总** | **3,687** | **0** | **59.03 ms** | **20 ms** | **230 ms** | **870 ms** | **30.41** |

登录耗时明显高于读取接口，主要来自有意采用的 Argon2 密码哈希计算；登录仅在虚拟用户启动时执行一次。读取接口在稳定阶段的大多数响应低于 30 ms，但 P99 存在 0.5 至 1.6 秒长尾，说明单进程在爬升和停止阶段仍有调度抖动。

## 压测发现与修复

第一次诊断性运行让 50 个虚拟用户共享管理员账号，27 次登录返回 HTTP 500，整体错误率为 1.71%。MySQL `SHOW ENGINE INNODB STATUS` 和后端异常栈均指向错误码 1213：登录事务同时写入带用户外键的登录日志、刷新令牌，并更新同一用户的最后登录时间，引发共享锁向排他锁升级死锁。

修复后，核心登录记录和刷新令牌先提交，最后登录时间在独立事务更新；仅当辅助更新时间遇到 MySQL 1213 死锁或 1205 锁等待超时时回滚该辅助更新并输出结构化告警，不再把已成功签发令牌的登录响应变成 HTTP 500。真实环境 20 路同账号并发回归和后续固定规格压测均为 0 失败。

## 原始数据与限制

原始结果随报告提交：

- `reports/benchmark/2026-07-20/locust-success_stats.csv`
- `reports/benchmark/2026-07-20/locust-success_stats_history.csv`
- `reports/benchmark/2026-07-20/locust-success_failures.csv`
- `reports/benchmark/2026-07-20/locust-success_exceptions.csv`

本轮没有连续采集容器 CPU、内存、MySQL 慢查询和 Redis 指标，因此不对资源峰值或容量上限作结论。数据规模也较小，且未覆盖进度写入、考试集中提交、文件上传和 Celery 积压。下一轮容量验收应在发布候选硬件上使用生产级数据量，预热后至少持续 10 分钟，并由 Prometheus/Grafana 同步记录资源、连接池、慢查询与队列指标。
