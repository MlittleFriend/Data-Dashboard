# 通用 Agent 技能脚手架 (Generic Agent Boilerplate)

本模块是一套通用的外部技能动态载入脚手架，用于在新旧项目中实现动态函数加载与 Function Calling 元数据管理。

## 跨项目快速迁移三步走

1. **复制文件**：
   直接复制整个 `external_skills/` 文件夹及 `agent_skill_kernel.py` 文件到新项目的根目录。

2. **元数据配置**：
   修改新项目根目录下的 `external_skills/manifest.json`，配置符合新项目业务标准的 Function Calling 规范及参数格式。

3. **单行引入加载**：
   在新项目的主入口逻辑（例如 `main.py` 或 `App.py`）中，单行导入并初始化技能动态网关：
   ```python
   from agent_skill_kernel import init_skills
   loaded_skills = init_skills()
   print(f"Loaded skills: {loaded_skills}")
   ```
