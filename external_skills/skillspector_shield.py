# -*- coding: utf-8 -*-
"""
skillspector_shield.py | NVIDIA SkillSpector 技能代码安全扫描看门狗 (V1.1.3.3)
"""
import ast
import os
import re


def scan_agent_skills(target_path: str = "./external_skills") -> dict:
    """
    对指定路径下的所有 AI 技能 Python 代码执行 AST 静态分析，
    识别可能包含的恶意模式（RCE 漏洞、未授权网络请求、越权文件读写及敏感提示词泄露等）。
    
    Args:
        target_path: 需要进行安全审计的目标文件夹或文件路径。
        
    Returns:
        包含扫描结果、审计摘要及发现的潜在漏洞的字典。
    """
    if not target_path:
        target_path = "./external_skills"

    # 规范化路径
    target_path = os.path.abspath(target_path)
    files_to_scan = []

    if os.path.isfile(target_path):
        if target_path.endswith(".py"):
            files_to_scan.append(target_path)
    elif os.path.isdir(target_path):
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith(".py"):
                    files_to_scan.append(os.path.join(root, file))

    findings = []
    total_files_scanned = len(files_to_scan)

    # 漏洞检查模式
    risk_imports = {
        "requests",
        "urllib",
        "socket",
        "http",
        "ftplib",
        "smtplib",
        "webbrowser",
    }
    dangerous_calls = {"eval", "exec", "compile"}
    sys_execs = {
        "system",
        "popen",
        "spawn",
        "subprocess",
        "run",
        "call",
        "check_output",
    }

    for filepath in files_to_scan:
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                code_content = f.read()

            # 1. 语义分析 AST 树结构
            tree = ast.parse(code_content, filename=filename)

            # 定义 AST 遍历器
            for node in ast.walk(tree):
                # 检查导入包漏洞
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in risk_imports:
                            findings.append(
                                {
                                    "file": filename,
                                    "type": "Network Access",
                                    "severity": "Medium",
                                    "detail": f"导入了可能发起外部网络连接的库 '{alias.name}'，存在潜在数据外泄风险。",
                                }
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module in risk_imports:
                        findings.append(
                            {
                                "file": filename,
                                "type": "Network Access",
                                "severity": "Medium",
                                "detail": f"从网络敏感库中引入了元素: 'from {node.module} import ...'",
                            }
                        )

                # 检查危险函数调用
                elif isinstance(node, ast.Call):
                    # 直接调用危险函数
                    if isinstance(node.func, ast.Name):
                        if node.func.id in dangerous_calls:
                            findings.append(
                                {
                                    "file": filename,
                                    "type": "Remote Code Execution (RCE)",
                                    "severity": "High",
                                    "detail": f"使用了动态代码执行危险函数 '{node.func.id}'，可能被恶意注入指令。",
                                }
                            )
                    # 检查 os.system / subprocess.run 等系统执行方法
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                        # 检查 os.system 等
                        if isinstance(node.func.value, ast.Name):
                            module_ref = node.func.value.id
                            if module_ref == "os" and func_name in sys_execs:
                                findings.append(
                                    {
                                        "file": filename,
                                        "type": "System Command Execution",
                                        "severity": "High",
                                        "detail": f"调用了系统命令行执行方法 'os.{func_name}'，可能被用于执行未授权的 shell 指令。",
                                    }
                                )
                            elif (
                                module_ref == "subprocess"
                                and func_name in sys_execs
                            ):
                                findings.append(
                                    {
                                        "file": filename,
                                        "type": "System Command Execution",
                                        "severity": "High",
                                        "detail": f"调用了子进程执行方法 'subprocess.{func_name}'，请注意输入参数的安全消毒。",
                                    }
                                )

            # 2. 补充正则文本检测 (主要是提示词泄露及敏感标签分析)
            if re.search(
                r'(?i)(system\s*prompt|ignore\s*previous\s*instruction|delete\s*database)',
                code_content,
            ):
                findings.append(
                    {
                        "file": filename,
                        "type": "Prompt Injection / Integrity Violation",
                        "severity": "Medium",
                        "detail": "检测到可能包含‘系统提示词绕过’或‘数据库抹除’等高风险提示敏感词，存在被劫持与绕过防御的潜在风险。",
                    }
                )

        except Exception as e:
            findings.append(
                {
                    "file": filename,
                    "type": "Scanner Failure",
                    "severity": "Low",
                    "detail": f"解析或扫描该脚本时出错: {e}",
                }
            )

    # 最终计算判定
    is_safe = len([f for f in findings if f["severity"] == "High"]) == 0

    return {
        "target_scanned": target_path,
        "total_files_scanned": total_files_scanned,
        "is_safe_to_execute": is_safe,
        "security_rating": "A" if len(findings) == 0 else ("B" if is_safe else "C"),
        "findings": findings,
    }
