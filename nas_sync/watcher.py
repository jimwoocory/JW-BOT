"""
NAS 知识库文件监听器
====================
监听 NAS inbox 目录，自动将新文件摄入 AstrBot 知识库。

运行方式：
    python nas_sync/watcher.py           # 前台运行
    python nas_sync/watcher.py --once    # 扫描一次 inbox 后退出（适合 cron）

依赖：
    pip install watchdog pyyaml requests
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

import requests
import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ----------------------------------------------------------------
# 路径配置
# ----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
STATE_PATH = Path(__file__).resolve().parent / "state.json"


# ----------------------------------------------------------------
# 配置加载
# ----------------------------------------------------------------
def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------
# 状态持久化（记录哪些文件已摄入，避免重复）
# ----------------------------------------------------------------
class IngestState:
    def __init__(self):
        self._path = STATE_PATH
        self._data: dict = {"ingested": {}}
        self._load()

    def _load(self):
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                self._data = json.load(f)

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def is_ingested(self, rel_path: str, file_hash: str) -> bool:
        entry = self._data["ingested"].get(rel_path)
        if not entry:
            return False
        return entry.get("file_hash") == file_hash

    def mark_ingested(self, rel_path: str, file_hash: str, doc_id: str):
        self._data["ingested"][rel_path] = {
            "file_hash": file_hash,
            "doc_id": doc_id,
            "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._save()

    def remove(self, rel_path: str):
        self._data["ingested"].pop(rel_path, None)
        self._save()


# ----------------------------------------------------------------
# AstrBot API 客户端
# ----------------------------------------------------------------
class AstrBotKBClient:
    def __init__(self, cfg: dict):
        self._api_base = cfg["astrbot"]["api_base"].rstrip("/")
        self._username = cfg["astrbot"]["username"]
        self._password = cfg["astrbot"]["password"]
        self._kb_id: str = cfg["astrbot"].get("kb_id", "") or ""
        self._embedding_provider_id: str = (
            cfg["astrbot"].get("embedding_provider_id", "") or ""
        )
        self._kb_mapping: dict = cfg["astrbot"].get("kb_mapping", {})
        self._token: str = ""
        self._token_fetched_at: float = 0
        self._token_ttl: int = int(cfg["astrbot"].get("token_refresh_interval", 3600))
        self._chunk_size: int = int(cfg["astrbot"].get("chunk_size", 512))
        self._chunk_overlap: int = int(cfg["astrbot"].get("chunk_overlap", 50))
        self.log = logging.getLogger("nas.client")

    # ---- Auth ----

    def _md5(self, s: str) -> str:
        return hashlib.md5(s.encode()).hexdigest()

    def _ensure_token(self):
        if self._token and (time.time() - self._token_fetched_at) < self._token_ttl:
            return
        self.log.info("获取 AstrBot JWT Token...")
        resp = requests.post(
            f"{self._api_base}/auth/login",
            json={"username": self._username, "password": self._md5(self._password)},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") not in (200, "ok"):
            raise RuntimeError(f"登录失败：{data.get('message', '未知错误')}")
        self._token = data["data"]["token"]
        self._token_fetched_at = time.time()
        self.log.info("Token 获取成功。")

    def _headers(self) -> dict:
        self._ensure_token()
        return {"Authorization": f"Bearer {self._token}"}

    def get_kb_id_for_file(self, file_path: str) -> str | None:
        """根据文件路径返回对应的知识库 ID"""
        if self._kb_mapping:
            for folder_prefix, kb_id in self._kb_mapping.items():
                if folder_prefix in file_path:
                    return kb_id
        return None

    # ---- KB 管理 ----

    def ensure_kb(self) -> str:
        """确保目标知识库存在，返回 kb_id。"""
        if self._kb_id:
            return self._kb_id

        # 查找名为 nas_knowledge 的 KB
        resp = requests.get(
            f"{self._api_base}/kb/list",
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        for kb in data.get("data", {}).get("items", []):
            if kb["kb_name"] == "nas_knowledge":
                self._kb_id = kb["kb_id"]
                self.log.info(f"使用已有知识库 nas_knowledge（{self._kb_id}）")
                return self._kb_id

        # 自动创建
        if not self._embedding_provider_id:
            raise RuntimeError(
                "知识库不存在且 config.yaml 中未配置 embedding_provider_id，"
                "请先在 AstrBot Dashboard 创建知识库，或填写 embedding_provider_id。"
            )
        self.log.info("创建新知识库 nas_knowledge ...")
        resp = requests.post(
            f"{self._api_base}/kb/create",
            headers=self._headers(),
            json={
                "kb_name": "nas_knowledge",
                "description": "公司 NAS 知识库（自动摄入）",
                "emoji": "🗄️",
                "embedding_provider_id": self._embedding_provider_id,
                "chunk_size": self._chunk_size,
                "chunk_overlap": self._chunk_overlap,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") not in (200, "ok"):
            raise RuntimeError(f"创建知识库失败：{data.get('message')}")
        self._kb_id = data["data"]["kb_id"]
        self.log.info(f"知识库已创建：{self._kb_id}")
        return self._kb_id

    # ---- 文档摄入 ----

    def upload_file(self, file_path: Path) -> str:
        """将文件上传到知识库，返回 doc_id。"""
        # 先尝试从 kb_mapping 获取知识库 ID
        kb_id = self.get_kb_id_for_file(str(file_path))
        if not kb_id:
            kb_id = self.ensure_kb()
        self.log.info(f"上传文件：{file_path.name} → KB {kb_id}")

        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}
            data = {
                "kb_id": kb_id,
                "chunk_size": str(self._chunk_size),
                "chunk_overlap": str(self._chunk_overlap),
            }
            resp = requests.post(
                f"{self._api_base}/kb/document/upload",
                headers=self._headers(),
                files=files,
                data=data,
                timeout=120,
            )

        resp.raise_for_status()
        result = resp.json()
        if result.get("status") not in (200, "ok"):
            raise RuntimeError(f"上传失败：{result.get('message')}")

        task_id = result["data"]["task_id"]
        self.log.info(f"上传任务已提交，task_id={task_id}，等待完成...")
        return self._wait_for_task(task_id, file_path.name)

    def _wait_for_task(self, task_id: str, file_name: str, timeout: int = 300) -> str:
        """轮询任务进度，返回 doc_id。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = requests.get(
                f"{self._api_base}/kb/document/upload/progress",
                headers=self._headers(),
                params={"task_id": task_id},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            status = data.get("status", "")

            if status == "completed":
                uploaded = data.get("result", {}).get("uploaded", [])
                if uploaded:
                    doc_id = uploaded[0].get("doc_id", task_id)
                    self.log.info(f"摄入完成：{file_name}（doc_id={doc_id}）")
                    return doc_id
                raise RuntimeError(f"任务完成但无上传记录：{data}")

            if status == "failed":
                raise RuntimeError(f"任务失败：{data.get('error', '未知错误')}")

            stage = data.get("stage", "")
            current = data.get("current", 0)
            total = data.get("total", 100)
            self.log.debug(f"  进度 [{stage}] {current}/{total}")
            time.sleep(2)

        raise TimeoutError(f"等待任务超时（{timeout}s）：{task_id}")


# ----------------------------------------------------------------
# 文件事件处理器
# ----------------------------------------------------------------
def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class NASIngestHandler(FileSystemEventHandler):
    def __init__(self, cfg: dict, client: AstrBotKBClient, state: IngestState):
        super().__init__()
        self._cfg = cfg
        self._client = client
        self._state = state
        self._inbox = Path(cfg["nas"]["mount_point"]) / cfg["watch"]["inbox_dir"]
        self._processed = (
            Path(cfg["nas"]["mount_point"]) / cfg["watch"]["processed_dir"]
        )
        self._extensions = set(cfg["watch"]["supported_extensions"])
        self._settle = float(cfg["watch"].get("settle_seconds", 3))
        self.log = logging.getLogger("nas.handler")

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() in self._extensions:
            self.log.info(f"检测到新文件：{path.name}，等待写入完成...")
            time.sleep(self._settle)
            self._ingest(path)

    def on_moved(self, event):
        if event.is_directory:
            return
        path = Path(event.dest_path)
        if path.suffix.lower() in self._extensions:
            time.sleep(self._settle)
            self._ingest(path)

    def _ingest(self, path: Path):
        if not path.exists():
            return
        try:
            file_hash = md5_file(path)
            rel = str(path.relative_to(self._inbox))
            if self._state.is_ingested(rel, file_hash):
                self.log.debug(f"跳过（已摄入）：{path.name}")
                return

            doc_id = self._client.upload_file(path)
            self._state.mark_ingested(rel, file_hash, doc_id)

            # 移动到 processed
            dest = self._processed / path.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))
            self.log.info(f"已归档到 processed/：{path.name}")

        except Exception as e:
            self.log.error(f"摄入失败：{path.name}  原因：{e}")


# ----------------------------------------------------------------
# 全量扫描（处理启动前已存在的文件 / --once 模式）
# ----------------------------------------------------------------
def scan_inbox(cfg: dict, client: AstrBotKBClient, state: IngestState):
    mount = Path(cfg["nas"]["mount_point"])
    full_scan: bool = cfg["watch"].get("full_scan", False)
    extensions = set(cfg["watch"]["supported_extensions"])
    exclude_dirs = set(
        cfg["watch"].get("exclude_dirs", ["#recycle", "processed", "archive"])
    )
    log = logging.getLogger("nas.scan")

    if not mount.exists():
        log.warning(f"挂载点不存在：{mount}（NAS 是否已挂载？）")
        return

    if full_scan:
        # 递归扫描整个挂载目录，跳过排除目录
        scan_root = mount
        log.info(f"全量扫描模式：{scan_root}")

        all_files = []
        for dirpath, dirnames, filenames in os.walk(scan_root):
            # 过滤排除目录
            dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                if fpath.suffix.lower() in extensions:
                    all_files.append(fpath)

        if not all_files:
            log.info("未找到可索引的文件。")
            return

        log.info(f"发现 {len(all_files)} 个可索引文件，开始摄入...")
        for f in all_files:
            try:
                file_hash = md5_file(f)
                rel = str(f.relative_to(mount))
                if state.is_ingested(rel, file_hash):
                    log.debug(f"跳过（已摄入）：{rel}")
                    continue

                doc_id = client.upload_file(f)
                state.mark_ingested(rel, file_hash, doc_id)
                log.info(f"已摄入：{rel}")

            except Exception as e:
                log.error(f"摄入失败：{f}  原因：{e}")

    else:
        # 只扫描 inbox 目录（原有逻辑）
        inbox = mount / cfg["watch"]["inbox_dir"]
        processed = mount / cfg["watch"]["processed_dir"]

        if not inbox.exists():
            log.warning(f"inbox 目录不存在：{inbox}")
            return

        files = [
            f for f in inbox.iterdir() if f.is_file() and f.suffix.lower() in extensions
        ]
        if not files:
            log.info("inbox 目录无待处理文件。")
            return

        log.info(f"扫描到 {len(files)} 个文件，开始批量摄入...")
        for f in files:
            try:
                file_hash = md5_file(f)
                rel = f.name
                if state.is_ingested(rel, file_hash):
                    log.debug(f"跳过（已摄入）：{f.name}")
                    continue

                doc_id = client.upload_file(f)
                state.mark_ingested(rel, file_hash, doc_id)

                dest = processed / f.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(dest))
                log.info(f"已归档到 processed/：{f.name}")

            except Exception as e:
                log.error(f"摄入失败：{f.name}  原因：{e}")


# ----------------------------------------------------------------
# 入口
# ----------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="NAS 知识库文件监听摄入器")
    parser.add_argument(
        "--once", action="store_true", help="扫描一次 inbox 后退出（适合 cron）"
    )
    args = parser.parse_args()

    cfg = load_config()

    # 日志配置
    log_level = getattr(logging, cfg["logging"]["level"].upper(), logging.INFO)
    log_file = PROJECT_ROOT / cfg["logging"]["file"]
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    log = logging.getLogger("nas")

    # 检查 NAS 挂载
    mount_point = Path(cfg["nas"]["mount_point"])
    if not mount_point.exists():
        log.error(f"挂载点不存在：{mount_point}，请先运行 ./nas_sync/mount.sh mount")
        sys.exit(1)

    client = AstrBotKBClient(cfg)
    state = IngestState()

    # --once 模式：扫描一次退出
    if args.once:
        log.info("--once 模式：扫描 inbox 一次后退出")
        scan_inbox(cfg, client, state)
        return

    # 常驻模式：先全量扫描，再 watchdog 监听
    log.info("启动 NAS 知识库监听器...")
    scan_inbox(cfg, client, state)

    inbox = mount_point / cfg["watch"]["inbox_dir"]
    handler = NASIngestHandler(cfg, client, state)
    observer = Observer()
    observer.schedule(handler, str(inbox), recursive=False)
    observer.start()

    poll_interval = int(cfg["watch"].get("poll_interval", 60))
    log.info(f"监听中：{inbox}  （每 {poll_interval}s 额外全量扫描）")

    try:
        elapsed = 0
        while True:
            time.sleep(5)
            elapsed += 5
            if elapsed >= poll_interval:
                elapsed = 0
                scan_inbox(cfg, client, state)
    except KeyboardInterrupt:
        log.info("收到中断信号，退出...")
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
