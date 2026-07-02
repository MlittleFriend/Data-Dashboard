# -*- coding: utf-8 -*-
"""
superpowers_workflow.py | Superpowers 高级工作流规划技能包 (V1.1.3.2)
"""
import re


def plan_agentic_workflow(task_description: str) -> dict:
    """
    针对输入的目标任务描述，运用 Superpowers 框架方法论，
    自动拆解并生成一套高规范的 Agentic 规划、开发、测试与复盘工作流方案。
    
    Args:
        task_description: 待执行的任务或需求描述。
        
    Returns:
        包含规划、隔离、TDD、验证与反思五个阶段步骤的字典对象。
    """
    if not task_description:
        task_description = "未指定具体任务"

    # 模拟从任务描述中智能提取关键词
    keywords = re.findall(r'[a-zA-Z0-9\u4e00-\u9fa5]+', task_description)
    target_subject = keywords[0] if keywords else "默认模块"

    # 阶段 1：Brainstorming & Planning
    planning_steps = [
        f"评估 '{task_description}' 的基本可行性，识别潜在依赖关系。",
        f"针对 '{target_subject}' 模块的设计方案与性能瓶颈进行多角度头脑风暴。",
        "定义清晰的输入/输出接口契约，绘制交互时序与控制链路图。",
    ]

    # 阶段 2：Isolation (沙箱与分支隔离)
    isolation_steps = [
        "执行 `git worktree add` 创建独立的物理干净分支工作区，避免交叉污染。",
        "进入临时工作区，配置对应依赖项与独立虚拟沙盒环境。",
    ]

    # 阶段 3：TDD (测试驱动开发设计)
    tdd_steps = [
        f"优先设计针对 '{target_subject}' 边界情况的测试用例（编写断言失败用例）。",
        "运行测试脚本，确认初始状态下该边界用例返回失败状态（红灯）。",
        "编写最小可行性实现代码（MVP），直至该测试用例顺利通过（绿灯）。",
    ]

    # 阶段 4：Verification (工程化静态自检与性能度量)
    verification_steps = [
        "执行本地静态代码规范校验，运行 `ruff check` 或类似 Lint 检查。",
        "执行本地语法及编译自检，防止将缩进、拼写或未声明变量带入版本库。",
        "进行小规模能耗或执行效率度量，拦截冗余计算黑洞。",
    ]

    # 阶段 5：Reflection & Review (复盘与审查)
    reflection_steps = [
        "分析代码架构中是否有冗余逻辑或重构空间。",
        "验证该方案是否对其他既有完好业务产生了破坏性变更（防退化校验）。",
        "确认是否完成了 Git 状态的暂存、本地提交与推送闭环。",
    ]

    return {
        "task": task_description,
        "framework": "Superpowers Agentic Workflow ( Jesse Vincent Methodology )",
        "workflow": {
            "1_Planning": planning_steps,
            "2_Isolation": isolation_steps,
            "3_TDD": tdd_steps,
            "4_Verification": verification_steps,
            "5_Reflection": reflection_steps,
        },
    }
