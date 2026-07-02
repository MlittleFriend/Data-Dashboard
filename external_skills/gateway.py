# -*- coding: utf-8 -*-
"""
gateway.py | 外部技能动态挂载与加载网关 (V1.1.3)
"""
import importlib.util
import json
import os
import sys

# 确保 external_skills 目录在 python path 中，方便导入
GATEWAY_DIR = os.path.dirname(os.path.abspath(__file__))
if GATEWAY_DIR not in sys.path:
    sys.path.append(GATEWAY_DIR)

MANIFEST_PATH = os.path.join(GATEWAY_DIR, "manifest.json")


class SkillGateway:

    def __init__(self):
        self.toolbox = {}
        self.manifest = {}
        self.load_gateway()

    def load_gateway(self):
        """
        从 manifest.json 中读取注册清单，并使用 importlib 动态按需加载模块并绑定到 toolbox 中。
        """
        if not os.path.exists(MANIFEST_PATH):
            print(f"[Skill Gateway] 配置文件 {MANIFEST_PATH} 不存在。")
            return

        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                self.manifest = json.load(f)
        except Exception as e:
            print(f"[Skill Gateway] 读取 manifest.json 失败: {e}")
            return

        skills = self.manifest.get("skills", [])
        for skill_info in skills:
            name = skill_info.get("name")
            module_name = skill_info.get("module")
            if not name or not module_name:
                continue

            module_path = os.path.join(GATEWAY_DIR, f"{module_name}.py")
            if not os.path.exists(module_path):
                print(f"[Skill Gateway] 未找到模块源文件: {module_path}")
                continue

            try:
                # 动态加载外部 Python 模块
                spec = importlib.util.spec_from_file_location(
                    module_name, module_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 从模块中获取对应的函数
                func = getattr(module, name, None)
                if func and callable(func):
                    self.toolbox[name] = func
                    print(
                        f"[Skill Gateway] 成功注册外部技能: '{name}' (源模块: {module_name})"
                    )
                else:
                    print(
                        f"[Skill Gateway] 模块 {module_name} 中未找到函数 {name}"
                    )
            except Exception as e:
                print(f"[Skill Gateway] 加载技能 '{name}' 模块时出错: {e}")

    def get_registered_skills(self) -> list:
        """返回所有注册的技能元数据清单"""
        return self.manifest.get("skills", [])

    def execute_skill(self, name: str, **kwargs):
        """
        执行指定外部已注册技能。
        """
        if name not in self.toolbox:
            raise KeyError(
                f"技能 '{name}' 未在动态网关中注册或加载失败。"
            )
        return self.toolbox[name](**kwargs)


# 全局常驻网关单例
gateway = SkillGateway()
