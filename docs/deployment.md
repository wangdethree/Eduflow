# 部署与运维

## 环境要求

- Docker Engine 24+ 与 Docker Compose v2
- 建议 2 核 CPU、4 GB 内存作为开发/演示环境起点
- 生产环境需要域名、HTTPS 证书和独立备份位置

## Docker Compose 部署

```bash
git clone git@github.com:wangdethree/Eduflow.git
cd Eduflow
cp .env.example .env
```

至少替换以下值：`SECRET_KEY`、`MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`、`MINIO_SECRET_KEY`、`INITIAL_ADMIN_PASSWORD`。`SECRET_KEY` 建议使用密码学安全随机值且不少于 32 字节。

```bash
docker compose config -q
docker compose up -d --build
docker compose ps
docker compose exec backend python scripts/init_data.py
curl http://localhost/api/v1/health
```

后端容器启动时自动执行 `alembic upgrade head`；数据初始化脚本可重复运行，不会重复创建系统角色、权限和管理员。

## 服务说明

| 服务 | 作用 | 默认对外入口 |
|---|---|---|
| nginx | 统一网关 | `80` |
| frontend | Vue 静态站点 | 仅 Compose 内网 |
| backend | FastAPI | 通过 Nginx `/api`、`/docs` |
| mysql | 主数据 | 不对宿主机开放 |
| redis | 缓存、锁、Broker | 不对宿主机开放 |
| minio | 对象存储 | 当前未映射宿主端口 |
| celery-worker | 异步任务执行 | 无 HTTP 入口 |
| celery-beat | 定时调度 | 无 HTTP 入口 |

若演示环境需要 MinIO 控制台，可为 `minio` 添加 `9000:9000` 和 `9001:9001` 端口映射；生产环境优先通过受控内网或独立域名访问。

## 可观测性与告警

项目提供独立的 Compose 叠加层，不会增加普通开发启动的常驻服务。先在 `.env` 中设置强密码 `GRAFANA_ADMIN_PASSWORD`，再启动完整监控栈：

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.observability.yml config -q
docker compose -f docker-compose.yml -f deploy/docker-compose.observability.yml up -d --build
```

- Grafana：`http://127.0.0.1:3000`，预置“EduFlow 运行概览”仪表盘和 Prometheus、Tempo 数据源。
- Prometheus：`http://127.0.0.1:9090`，每 15 秒抓取后端 `/metrics`。
- Tempo：`http://127.0.0.1:3200`，接收 FastAPI、SQLAlchemy、Redis 和 Celery 的 OTLP HTTP 链路。
- Sentry：在 `.env` 配置 `SENTRY_DSN` 后启用；未配置时不会发起外部请求。

预置告警包含后端不可用、依赖不可用、5xx 错误率、P95 延迟、Celery 默认队列积压和 MySQL 慢查询增长。Prometheus 页面可以直接查看告警状态；生产环境应在 Prometheus 或 Grafana 中继续配置邮件、飞书、钉钉等真实通知渠道。

MySQL 默认启用慢查询日志，阈值由 `MYSQL_LONG_QUERY_TIME` 控制；应用同时记录超过 `SLOW_QUERY_THRESHOLD_SECONDS` 的结构化日志，但不会写入 SQL 参数。常用排查命令：

```bash
docker compose exec mysql mysql -uroot -p -e "SELECT start_time,query_time,sql_text FROM mysql.slow_log ORDER BY start_time DESC LIMIT 20"
docker compose exec redis redis-cli -n 1 LLEN celery
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode()[:1000])"
```

## 更新发布

```bash
git pull --ff-only
docker compose build backend frontend celery-worker celery-beat
docker compose up -d
docker compose exec backend alembic current
curl --fail http://localhost/api/v1/health
```

涉及迁移时先备份数据库。应用与迁移不兼容的变更应采用“先兼容字段、再切应用、最后清理旧字段”的多阶段发布方式。

## 常用运维命令

```bash
docker compose logs -f --tail=200 backend
docker compose logs -f --tail=200 celery-worker celery-beat
docker compose exec backend alembic current
docker compose exec redis redis-cli INFO memory
docker compose exec mysql mysqladmin ping -uroot -p
```

## 备份建议

- MySQL：每日全量备份，重要环境开启 binlog 并定期执行恢复演练。
- MinIO：使用版本控制或跨存储复制，数据库和对象备份保持同一恢复点。
- Redis：学习进度采用 AOF；Redis 仍不是唯一长期数据源，Worker 会持续落库。
- `.env`：放入机密管理系统，不进入 Git，不与备份明文打包。

## 生产加固清单

- Nginx 开启 HTTPS、HSTS、合理的请求体和超时限制。
- 仅暴露 80/443；MySQL、Redis、MinIO 使用内部网络和强凭据。
- `APP_ENV=production`、`DEBUG=false`，CORS 改为真实前端域名。
- 使用独立非 root 运行用户和只读文件系统，设置容器 CPU/内存限制。
- 将结构化日志接入长期存储，并补充磁盘容量、证书过期和通知渠道巡检。
- 执行镜像漏洞扫描、依赖审计、迁移演练、备份恢复演练和压力测试。

## 回滚

应用回滚优先重新部署上一版本镜像。数据库回滚只有在迁移明确可逆且确认不会丢失新数据时才执行 `alembic downgrade`；否则应使用前向修复迁移。任何回滚前都先保存现场日志和数据库备份。
