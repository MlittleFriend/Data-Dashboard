# -*- coding: utf-8 -*-
"""
agent_skill_kernel.py | 通用自适应环境加载器 (V1.1.3.1)
"""
import importlib.util
import json
import os
import sys


class GenericSkillGateway:

    def __init__(self, base_dir=None):
        # 自适应获取运行目录下的 external_skills
        if base_dir is None:
            self.base_dir = os.path.join(os.getcwd(), "external_skills")
        else:
            self.base_dir = base_dir

        self.manifest_path = os.path.join(self.base_dir, "manifest.json")
        self.toolbox = {}
        self.manifest = {}
        self.load_skills()

    def load_skills(self):
        if not os.path.exists(self.manifest_path):
            print(f"[Agent Skill Kernel] 配置文件 {self.manifest_path} 不存在。")
            return

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self.manifest = json.load(f)
        except Exception as e:
            print(f"[Agent Skill Kernel] 读取 manifest.json 失败: {e}")
            return

        # 将 external_skills 目录加入 path 以支持内部相对导入
        if self.base_dir not in sys.path:
            sys.path.append(self.base_dir)

        skills = self.manifest.get("skills", [])
        for skill_info in skills:
            name = skill_info.get("name")
            module_name = skill_info.get("module")
            if not name or not module_name:
                continue

            module_path = os.path.join(self.base_dir, f"{module_name}.py")
            if not os.path.exists(module_path):
                print(f"[Agent Skill Kernel] 未找到模块源文件: {module_path}")
                continue

            try:
                spec = importlib.util.spec_from_file_location(
                    module_name, module_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                func = getattr(module, name, None)
                if func and callable(func):
                    self.toolbox[name] = func
                    print(
                        f"[Agent Skill Kernel] 成功注册外部技能: '{name}' (源模块: {module_name})"
                    )
                else:
                    print(
                        f"[Agent Skill Kernel] 模块 {module_name} 中未找到函数 {name}"
                    )
            except Exception as e:
                print(f"[Agent Skill Kernel] 加载技能 '{name}' 模块时出错: {e}")

    def execute_skill(self, name: str, **kwargs):
        if name not in self.toolbox:
            raise KeyError(f"技能 '{name}' 未注册或加载失败。")
        return self.toolbox[name](**kwargs)

    def get_skills_list(self) -> list:
        return list(self.toolbox.keys())


# 实例化单例
gateway = None


def init_skills() -> list:
    global gateway
    gateway = GenericSkillGateway()
    return gateway.get_skills_list()
