# 临港 · 港站晨报定时分发

把昨日计划到发、延误分位数与交接班晨报串起来，由真实worker到点生成站内收件箱回执，保留冻结来源。接驳配载批次在同一口径下接续进站货量与出港班次，随晨报回执入箱生效。

## 场景与工作流

临港联运运营北站、南站和东港三个港站，每天约150条班次记录。现行工作流是值班员导出 `临港到发_20261114.xlsx`，分析员按日期筛选后手算延误，负责人再把表格转发给下一班。痛点是跨午夜班次归错日、未到发被当准点、重复转发后分不清同一口径；单班准点也可能错过接驳，人工对接不清楚哪批货上了哪班。上游为港站计划/实际到发记录；本项目替代日界归档、晨报试算、定时分发与接驳配载；下游为站内值班室交接班。

核心实体：Arrival到发记录、Subscription晨报订阅、Receipt分发回执、LoadBatch接驳配载批次（含CargoLot进站货量、OutboundOption出港候选），另有用户和审计。五页：到发台账、晨报预览、订阅计划、分发回执、接驳配载。回执支持值班复核与下载，原始记录修订不改变已分发晨报；配载批次入箱后同样冻结。

|角色|权限|典型动作|
|---|---|---|
|admin|全部；独占订阅配置/值班复核/审计|设定08:30晨报并核对回执|
|analyst|到发录入/修订、晨报试算、配载发起/修订/重算、读取计划回执、导出|补录跨午夜班次并发起接驳配载|
|viewer|业务只读与回执导出|下载冻结晨报；后端拒绝写入/计算|

## 快速启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
docker compose exec -T backend python -m scripts.seed_load_demo   # 可选：接驳配载演练数据
```

前端 [localhost:18212](http://localhost:18212)，API [localhost:19212/docs](http://localhost:19212/docs)，PostgreSQL映射17712。账号 `admin@demo.local`、`analyst@demo.local`、`viewer@demo.local`，密码均 `Demo123!`。种子为3账号、150条昨日计划到发、3条暂停订阅；不会自动对外发送。自然编号幂等，重复运行不覆盖人工修订；种子日期为首次启动的昨日，后续日需业务录入新记录。

## 一日业务剧本

1. 08:00 viewer 查看LG-001至LG-150，核对未到发为空。
2. 08:05 analyst 录入 `LG-151`，北站，计划2026-11-14 23:55，实际2026-11-15 00:05，交接说明为跨午夜。
3. 08:10 在晨报预览选择2026-11-14和北站，检查该班次仍归14日、延误10分钟。
4. 08:15 admin 创建“北站08:30值班晨报”，站内收件箱“北站值班室”，每日08:30，启用。
5. 演示时可把“首次到点”设为未来10秒；不需要任何手动发送按钮。
6. 08:30 worker每秒检查到点订阅，冻结昨日来源并写入回执。
7. 08:31 刷新分发回执，核对P50/P95、完成/未到发人数和来源checksum。
8. 08:35 admin 写入“跨日班次已核对”复核意见；viewer下载 `port-digest-<业务日>-<回执id>.json`。

## 接驳配载演练

```sh
docker compose exec -T backend python -m scripts.seed_load_demo
```

种子为北站昨日业务日造一个批次：LG-901/LG-904 跨午夜进站（计划23:50/23:55，实际次日00:12/00:24）各10吨，LG-905 未到发6吨；出港候选 LG-902（舱位10、换装5分）、LG-903（舱位10、换装40分）、LG-906（未发）。自然编号幂等，重复运行不覆盖人工修订。

1. **跨午夜与贪心漏配**：批次占位后查看方案——LG-901→LG-903、LG-904→LG-902，共20吨。若按“先到先得”贪心，LG-901 会占掉 LG-902 的唯一舱位，LG-904 因40分换装不够只能滞留，总量跌到10吨；最小费用最大流给出全局最优。LG-905 未到发暂不配，LG-906 未发不作候选。
2. **占位后入箱前中断**：发起批次看到“已占位”后 `docker compose stop worker`，再 `docker compose start worker`；到点订阅照常把批次随晨报入箱，回执只有一份、舱位只占一次。
3. **并发争舱位/台账修订**：占位后修订台账（如把 LG-903 实际发提前到进站换装不足的时刻）或让相邻业务日批次共享同一出港班次，先入箱者占用舱位；后入箱者指纹校验失败，过期占位方案被拒绝入箱并按最新台账重算，被替换方案留在批次历史（最多10份）。
4. **重叠订阅复用**：同时启用“北站”与“全部”两个订阅，同日到点生成两份回执，北站批次只入箱一次；第二份回执标记复用同份配载，不重复占用舱位。

## 计算与调度口径

**归档**按计划到发时间转Asia/Shanghai后的自然日，而非实际到达日。后端时间输入必须有偏移（如+08:00），统一保存UTC；前端datetime-local明确按上海解释。实际可空，表示未到发。时间差超过3天拒绝，提示核对。

**延误**=max(0,实际−计划)分钟，提前到达记0。已到发才进入延误率与分位数分母；未到发单独计数。P50/P95使用排序后位置(n−1)p的线性插值；没有已到发样本时分位数、均值和延误率为null，页面显示“未定义”。输出带完整选中来源、口径版本与SHA256 checksum。

**到点调度**由worker每秒扫描UTC next_run_at，Redis锁串行化扫描，数据库用行锁和唯一约束 `(subscription_id, report_day)` 防止同订阅同报告日重复入箱。首次时间可设未来数秒进行真实调度验证；以后按Asia/Shanghai每日HH:MM安排。到点或服务中断恢复时只生成“执行时刻的最新昨日”一份，不补历史天；同日再次到点只推进next_run_at，不新增回执。暂停订阅不执行。修订订阅如果未填写首次时间，会重新安排下一个每日时刻；恢复暂停也按此规则。

**配载**按港站+业务日唯一发起批次，录入进站货量（班次+吨数）、出港候选（班次+舱位+最短换装分钟）。只按台账实际到发计算：进站未到发的货量暂不配，出港未发的班次暂不作候选；接续要求 实际到+最短换装≤实际发，等待=实际发−实际到。优化目标先使接续总货量最大，再使货量加权总等待（吨·分）最小；货量可拆分到多个候选，共享舱位按已入箱批次的占用扣减，不超卖。算法为最小费用最大流（`connection-mcmf-v1`），未配货量逐条给出原因（未到发/无可接续班次/舱位不足）。

批次状态机：`pending`待计算 → `computed`已占位 → `loaded`已入箱（终态）。worker每秒把待计算批次算出占位方案；占位不扣减舱位。晨报回执生成时，把回执覆盖的每个港站+报告日批次一并入箱：舱位占用与回执在同一数据库事务生效；重叠订阅（北站与全部）复用同一份已入箱配载，不重复占用。占位指纹覆盖录入内容、引用班次的计划/实际到发、其他批次已占舱位；入箱前指纹不符（并发争舱位或台账修订）即拒绝入箱并按最新台账重算，被替换方案留存在批次历史。中断恢复由同一tick循环保证：回执唯一约束防重复入箱，批次状态机防重复占用，重试安全。已入箱批次冻结，不能修订或重算；旧回执payload永不改变。

晨报“送达”表示已提交站内数据库收件箱，不是SMTP邮件。回执保存冻结payload，DB提交后附加写共享产物卷；附加文件失败不影响DB回执和导出。值班复核仅管理员可做，一次复核不可覆盖，且不改变payload。支持单worker；唯一约束与锁防重复，但不声称对外消息的exactly-once。

## 工程、环境变量和开发

Python3.11/FastAPI/SQLAlchemy/PyJWT、原生ES modules/CSS、Nginx、PostgreSQL16、Redis7。恰好frontend/backend/worker/db/redis五服务，各有健康检查；backend等db/redis、worker还等backend、frontend等backend。Redis实际提供调度锁；worker心跳 `/tmp/heartbeat`，DB/Redis/产物分别命名卷。Nginx `/api/` 去前缀代理后端根路由。

`.env.example`列出COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、DB_PASSWORD、JWT_SECRET、SEED_DEMO、NETWORK_SUBNET。显式子网10.253.113.0/24规避当前机默认地址池耗尽，可按环境调整。演示凭据应在正式部署替换。清理本项目用 `docker compose down -v --remove-orphans`。

本地开发：启动db/redis，backend安装requirements，设置DATABASE_URL/REDIS_URL/JWT_SECRET，再运行 `uvicorn src.main:app --reload` 和 `python -m src.worker`；前端仍建议用Nginx同源代理。后端目录src按routes/controllers/services/models/schemas/middlewares/config/utils/constants分工；前端src按api/stores/pages/components/hooks/utils/constants/types/router分工。ORM首次建表，migrations保留实际初始DDL（002为配载批次表），无在线迁移执行器。

枚举：后端 `src/constants/enums.py`、`src/schemas/business.py` 与前端 `src/constants/enums.js` 定义ROLES、STATIONS、RECEIPT_STATES、LOAD_STATES；TIMEZONE固定Asia/Shanghai。共用表格、表单、状态标签、晨报摘要组件；表单hooks、HTML转义和日期工具；请求ID/安全响应头两个中间件，业务审计与全局错误恢复。配载核心在 `src/services/connection.py`（纯函数：最小费用最大流、方案构建、来源指纹），`src/services/loadplan.py` 负责占位/入箱编排，`src/services/scheduler.py` 在回执事务内调用。测试与截图在 `../../test-artifacts/gb-3113/`，不放源码内。

范围：逐条录入/完整修订，无CSV导入、删除或分页；只有三个固定港站与上海时区。站内收件箱按名称记录，当前所有登录角色可读业务回执，无多租户邮箱隔离；不连接邮件、短信或外部IM。Google Fonts离线时字体回退。许可证MIT，见LICENSE。
