# -*- coding: utf-8 -*-
"""
cloud_sync.py | 26630 数据变更云端同步器 (V1.0.0)
在本地对齐管线成功入库后，将 26630.xlsx 与 my_data.db 等数据产物
自动提交并推送至 GitHub，触发 Streamlit Cloud 自动重新部署，
完成 “文件变更 → 本地校验入库 → 云端同步” 的完整闭环。

特性：
1. 去抖保护：两次推送之间强制最小间隔，防止 Excel 频繁保存引发提交风暴
2. 并发互斥：多线程触发（Watcher / Self-Inspection）时串行执行
3. 环境自检：非 git 仓库或无远程地址时（如 Streamlit Cloud 容器内）自动静默跳过
4. 可开关：环境变量 CLOUD_SYNC_ENABLED=0 关闭；CLOUD_SYNC_DRY_RUN=1 仅演练不提交
"""
import json
import os
import subprocess
import threading
import time
from datetime import datetime

# 需要随 26630 数据更新一并同步到云端的产物文件（含看板代码，实现“改完自动推”）
# 注意：my_data.db 不入库——云端启动时由对齐管线从 26630.xlsx 现场重建，避免二进制冲突与仓库膨胀
SYNC_FILES = [
    # 数据产物
    "26630.xlsx", "schema_lock.json", "schema_snapshot.json",
    "econ_overview_cache.json", "wechat_articles_cache.json",
    # 看板核心代码
    "App.py", "schema_aligner.py", "cloud_sync.py", "upload_data.py",
    "news_sanitizer.py", "agent_skill_kernel.py", "requirements.txt",
]

# 去抖：两次云端推送的最小间隔（秒）
MIN_SYNC_INTERVAL = 120

# 最近一次同步结果的状态文件（供 Streamlit 侧栏展示，已加入 .gitignore）
STATUS_FILE = "cloud_sync_status.json"

_sync_lock = threading.Lock()
_last_sync_ts = 0.0


def record_sync_result(ok, message, commit=""):
    """将最近一次云端同步结果持久化到状态文件，供界面侧栏巡检展示"""
    try:
        payload = {
            "ok": bool(ok),
            "message": message,
            "commit": commit,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Cloud Sync] 写入同步状态文件失败: {e}")


def _run_git(args, timeout=90):
    """执行 git 子命令并返回 CompletedProcess，异常时返回 None"""
    try:
        return subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except Exception as e:
        print(f"[Cloud Sync] git {' '.join(args)} 执行异常: {e}")
        return None


def cloud_sync_enabled():
    """环境变量开关，默认开启"""
    return os.getenv("CLOUD_SYNC_ENABLED", "1").strip().lower() not in ("0", "false", "off", "no")


def _is_dry_run():
    return os.getenv("CLOUD_SYNC_DRY_RUN", "0").strip().lower() in ("1", "true", "on", "yes")


def sync_to_cloud(reason="26630 数据更新"):
    """
    将 SYNC_FILES 中的变更提交并推送到当前分支的远程仓库。
    返回 True 表示完成了一次推送，False 表示跳过或失败（均不抛异常）。
    """
    global _last_sync_ts

    if not cloud_sync_enabled():
        print("[Cloud Sync] 已通过 CLOUD_SYNC_ENABLED=0 关闭，跳过云端同步。")
        return False

    # 环境自检：仅在本地 git 仓库且配置了远程时工作（Streamlit Cloud 容器内自动跳过）
    if not os.path.isdir(".git"):
        print("[Cloud Sync] 当前环境非 git 仓库（可能为云端容器），跳过同步。")
        return False
    res = _run_git(["remote"])
    if res is None or not res.stdout.strip():
        print("[Cloud Sync] 未配置 git 远程仓库，跳过同步。")
        return False

    # 并发互斥：若已有同步在进行，直接放弃本次触发
    if not _sync_lock.acquire(blocking=False):
        print("[Cloud Sync] 上一次同步仍在进行中，合并放弃本次触发。")
        return False

    try:
        # 去抖保护
        now = time.time()
        if now - _last_sync_ts < MIN_SYNC_INTERVAL:
            print(f"[Cloud Sync] 距上次同步不足 {MIN_SYNC_INTERVAL}s，去抖跳过。")
            return False

        dry_run = _is_dry_run()

        # 1. 检查待同步文件是否存在变更
        res = _run_git(["status", "--porcelain", "--"] + SYNC_FILES)
        if res is None:
            return False
        if not res.stdout.strip():
            print("[Cloud Sync] 数据产物无变更，无需同步。")
            record_sync_result(True, "数据无变更 (Idle)")
            _last_sync_ts = now
            return False

        if dry_run:
            print(f"[Cloud Sync] (DRY RUN) 检测到以下数据产物变更，将提交并推送:\n{res.stdout.strip()}")
            print(f"[Cloud Sync] (DRY RUN) 提交信息: auto: 同步{reason} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
            _last_sync_ts = now
            return True

        # 2. 暂存数据产物
        res = _run_git(["add", "--"] + SYNC_FILES)
        if res is None or res.returncode != 0:
            print(f"[Cloud Sync] git add 失败: {res.stderr if res else 'unknown'}")
            return False

        # 3. 确认暂存区确有内容
        res = _run_git(["diff", "--cached", "--quiet"])
        if res is not None and res.returncode == 0:
            print("[Cloud Sync] 暂存区无有效变更，无需提交。")
            _last_sync_ts = now
            return False

        # 4. 提交
        commit_msg = f"auto: 同步{reason} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
        res = _run_git(["commit", "-m", commit_msg])
        if res is None or res.returncode != 0:
            err = res.stderr.strip() if res else "unknown"
            print(f"[Cloud Sync] git commit 失败: {err}")
            record_sync_result(False, f"git commit 失败: {err[:120]}")
            return False
        print(f"[Cloud Sync] 已创建本地提交: {commit_msg}")

        # 取本次提交的短哈希用于状态展示
        commit_sha = ""
        res = _run_git(["rev-parse", "--short", "HEAD"])
        if res is not None and res.returncode == 0:
            commit_sha = res.stdout.strip()

        # 5. 确定当前分支
        branch = "HEAD"
        res = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if res is not None and res.returncode == 0 and res.stdout.strip():
            branch = res.stdout.strip()

        # 6. 先 rebase 拉齐远程（与每日 GitHub Actions 的自动提交共存），再推送
        res = _run_git(["pull", "--rebase", "--autostash", "origin", branch], timeout=180)
        if res is None or res.returncode != 0:
            err = res.stderr.strip() if res else "unknown"
            print(f"[Cloud Sync] git pull --rebase 失败（保留本地提交，下次同步重试）: {err}")
            record_sync_result(False, f"pull --rebase 失败: {err[:120]}", commit_sha)
            _last_sync_ts = now  # 已提交成功，计入去抖，避免 tight loop
            return False

        res = _run_git(["push", "origin", branch], timeout=180)
        if res is None or res.returncode != 0:
            err = res.stderr.strip() if res else "unknown"
            print(f"[Cloud Sync] git push 失败（保留本地提交，下次同步重试）: {err}")
            record_sync_result(False, f"push 失败: {err[:120]}", commit_sha)
            _last_sync_ts = now
            return False

        _last_sync_ts = time.time()
        record_sync_result(True, f"已推送至 origin/{branch}", commit_sha)
        print(f"[Cloud Sync] ✅ 数据产物已推送至 origin/{branch}，Streamlit Cloud 将自动重新部署。")
        return True
    except Exception as e:
        print(f"[Cloud Sync] 同步过程异常: {e}")
        return False
    finally:
        _sync_lock.release()


if __name__ == "__main__":
    print("=" * 60)
    print("🤖 26630 云端同步器测试 (DRY RUN 演练模式)")
    print("=" * 60)
    os.environ["CLOUD_SYNC_DRY_RUN"] = "1"
    sync_to_cloud(reason="手动触发测试")
