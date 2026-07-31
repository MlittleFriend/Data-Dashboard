# Data Dashboard 项目约定

## 云端同步（改完自动推）

- 部署链路：GitHub `origin/main` → Streamlit Cloud 自动重新部署。
- 用户已授权：**完成代码或数据改动后，直接 commit 并 push 到 `origin/main`，无需逐次确认**。
- 数据流：手动更新本地 26630.xlsx → watcher 识别 SHA 变化 → 对齐管线入库 → 校验闸门通过 → `cloud_sync.py` 推送 `SYNC_FILES`（26630 + schema 文件 + 看板核心代码 + `econ_overview_cache.json`）。
- **`my_data.db` 不入库**：云端容器启动时由对齐管线从 26630.xlsx 现场重建，避免二进制冲突与仓库膨胀。每日 GitHub Action 只做管线冒烟校验，不再提交任何文件。
- 经济数据区 2 张折线（CPI长历史、PMI新订单季节图）的数据源是 `经济数据更新/` 下的「经济数据一览」底稿（本地目录，不入库）；管线解析后落盘 `econ_overview_cache.json` 随同步推送，云端启动时从该 JSON 回退重建 `dashboard_cpi_core_history` / `dashboard_pmi_new_orders_history` 两表。
- 推送前校验闸门：`schema_aligner.validate_pipeline_output()`（嵌入图 20 张、KPI 关键列非空），不通过则拦截推送。
- 最近一次同步结果持久化在 `cloud_sync_status.json`（已 gitignore），侧栏有状态巡检卡。
- 环境变量：`CLOUD_SYNC_ENABLED=0` 关闭自动同步；`CLOUD_SYNC_DRY_RUN=1` 演练模式。

## 界面图表口径

- Streamlit 界面只展示 26630 底稿中存在的图表（20 张内嵌图 + 经济数据区按「经济数据一览」原图口径补建的 2 张折线：CPI/核心CPI 当月同比长历史、全国制造业 PMI 新订单按年叠放季节图），不新增底稿之外的图表。两张折线均为直线连接（`shape="linear"`），不做 spline 平滑。
- 底稿未命名图表（Chart 13–20）的展示标题维护在 `App.py` 的 `EMBEDDED_CHART_TITLE_OVERRIDES`。

## 验证

- 改动后运行 `./.venv/Scripts/python.exe -m py_compile App.py` 及 Streamlit `AppTest` 无头测试。
