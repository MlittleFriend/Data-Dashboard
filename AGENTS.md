# Data Dashboard 项目约定

## 云端同步（改完自动推）

- 部署链路：GitHub `origin/main` → Streamlit Cloud 自动重新部署。
- 用户已授权：**完成代码或数据改动后，直接 commit 并 push 到 `origin/main`，无需逐次确认**。
- `cloud_sync.py` 在 26630.xlsx 变更入库存后自动推送 `SYNC_FILES`（数据产物 + 看板核心代码）。
- 环境变量：`CLOUD_SYNC_ENABLED=0` 关闭自动同步；`CLOUD_SYNC_DRY_RUN=1` 演练模式。

## 界面图表口径

- Streamlit 界面只展示 26630 底稿中存在的图表（20 张内嵌图 + 经济数据区按底稿补建的 2 张折线），不新增底稿之外的图表。
- 底稿未命名图表（Chart 13–20）的展示标题维护在 `App.py` 的 `EMBEDDED_CHART_TITLE_OVERRIDES`。

## 验证

- 改动后运行 `./.venv/Scripts/python.exe -m py_compile App.py` 及 Streamlit `AppTest` 无头测试。
