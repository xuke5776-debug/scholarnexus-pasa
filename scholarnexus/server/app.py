"""ScholarNexus HTTP 服务（纯标准库，零外部依赖）。

两个接口刻意分离，这一点很重要：

    POST /retrieve   纯检索。同步返回结构化 JSON，不含任何生成式文本。
                     **自动评测走这个接口** —— 评测的是集合级 F1，
                     不该被演示用的流式渲染、归纳文案等逻辑污染。

    POST /chat       演示用。SSE 流式推送执行链路（查询解析 → 多通道召回 →
                     引文扩散 → 判定级联 → 基数估计 → 门限决策 → 归纳），
                     前端右栏据此实时显示"系统正在想什么"。

接口分离的设计借鉴自 Ray-Source 的 /retrieve 端点约定（见 docs/CREDITS.md）：
让评测路径保持纯净、可复现，是把 F1 做扎实的前提。

用不用 FastAPI 是个真实取舍。这里选标准库 http.server 的理由是：
评委/用户 clone 下来 `python -m scholarnexus.server` 就能跑起来看到界面，
不需要先解决依赖安装。并发量在演示与评测场景下完全够用（ThreadingHTTPServer）。
生产部署可换 uvicorn + FastAPI，业务逻辑一行不用改。
"""
from __future__ import annotations

import json
import os
import queue
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from ..config import Config
from ..core.pipeline import ScholarNexus
from ..present.insightboard import render_markdown
from ..schema import Budget

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "web")


class _State:
    engine: Optional[ScholarNexus] = None
    config: Optional[Config] = None
    lock = threading.Lock()
    search_lock = threading.Lock()


STATE = _State()


def get_engine() -> ScholarNexus:
    with STATE.lock:
        if STATE.engine is None:
            STATE.config = Config.load(os.environ.get("SN_CONFIG"),
                                       os.environ.get("SN_PROFILE"))
            registry = None
            # SN_CORPUS 指向本地语料时改用离线检索后端。
            # 这让整套界面在无网络、无 API Key 的环境下也能完整演示，
            # 评委不需要先配好一堆凭据才能看到系统在做什么。
            corpus = os.environ.get("SN_CORPUS")
            if corpus and os.path.exists(corpus):
                from ..sources.base import SourceRegistry
                from ..sources.local_corpus import LocalCorpusSource
                registry = SourceRegistry().register(
                    LocalCorpusSource(path=corpus))
            STATE.engine = ScholarNexus(STATE.config, registry=registry)
        return STATE.engine


class Handler(BaseHTTPRequestHandler):
    server_version = "ScholarNexus/1.0"

    # ---------------- 基础工具 ----------------
    def log_message(self, fmt, *args):
        if os.environ.get("SN_VERBOSE"):
            super().log_message(fmt, *args)

    def _json(self, obj: Any, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:                                        # noqa: BLE001
            return {}

    def do_OPTIONS(self):                                        # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    # ---------------- GET ----------------
    def do_GET(self):                                            # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._serve_static("index.html")
        if path == "/health":
            return self._json({"ok": True, "version": "1.0.0"})
        if path == "/config":
            cfg = get_engine().cfg
            return self._json(cfg.to_dict())
        if path.startswith("/static/"):
            return self._serve_static(path[len("/static/"):])
        return self._json({"error": "not found"}, 404)

    def _serve_static(self, name: str):
        safe = os.path.normpath(name).lstrip("./")
        fp = os.path.join(WEB_DIR, safe)
        if not fp.startswith(WEB_DIR) or not os.path.isfile(fp):
            return self._json({"error": "not found"}, 404)
        ctype = {"html": "text/html", "css": "text/css", "js": "application/javascript",
                 "json": "application/json", "svg": "image/svg+xml"}.get(
                     fp.rsplit(".", 1)[-1], "application/octet-stream")
        with open(fp, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---------------- POST ----------------
    def do_POST(self):                                           # noqa: N802
        path = urlparse(self.path).path
        if path == "/retrieve":
            return self._retrieve()
        if path == "/chat":
            return self._chat_sse()
        return self._json({"error": "not found"}, 404)

    def _budget_of(self, body: Dict[str, Any]) -> Optional[Budget]:
        b = body.get("budget")
        if not isinstance(b, dict):
            return None
        allowed = {"max_llm_calls", "max_tokens", "max_api_calls",
                   "max_seconds", "max_rounds", "max_l3_judgments"}
        return Budget(**{k: v for k, v in b.items() if k in allowed})

    # ---- 评测接口：纯检索，同步 JSON ----
    def _retrieve(self):
        body = self._read_json()
        q = (body.get("query") or "").strip()
        if not q:
            return self._json({"error": "query is required"}, 400)
        try:
            with STATE.search_lock:
                res = get_engine().search(q, budget=self._budget_of(body))
        except Exception as e:                                   # noqa: BLE001
            return self._json({"error": f"{type(e).__name__}: {e}",
                               "trace": traceback.format_exc()[-1200:]}, 500)
        out = res.to_dict(include_all=bool(body.get("include_all")))
        if not body.get("include_trace", True):
            out.pop("trace", None)
        # 评测方通常只要一个 pid 列表，直接给出，免得它自己去解析结构
        out["result_ids"] = [c.pid for c in res.core]
        out["result_ids_with_partial"] = out["result_ids"] + [
            c.pid for c in res.partial]
        return self._json(out)

    # ---- 演示接口：SSE 流式执行链路 ----
    def _chat_sse(self):
        body = self._read_json()
        q = (body.get("query") or "").strip()
        if not q:
            return self._json({"error": "query is required"}, 400)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")   # 关掉反代缓冲，否则不流式
        # SSE 流长度未知，必须显式关闭连接来标记结束；沿用 keep-alive 会让
        # 客户端在收到 done 之后继续等待，直到超时。
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.close_connection = True

        events: "queue.Queue" = queue.Queue()

        def on_event(stage, rec):
            events.put(("stage", rec))

        def run():
            try:
                with STATE.search_lock:
                    res = get_engine().search(q, budget=self._budget_of(body),
                                              on_event=on_event)
                payload = res.to_dict()
                payload["markdown"] = render_markdown(res)
                payload["result_ids"] = [c.pid for c in res.core]
                events.put(("result", payload))
            except Exception as e:                               # noqa: BLE001
                events.put(("error", {"message": f"{type(e).__name__}: {e}"}))
            finally:
                events.put((None, None))

        th = threading.Thread(target=run, daemon=True)
        th.start()
        try:
            while True:
                ev, data = events.get()
                if ev is None:
                    self._sse("done", {})
                    break
                self._sse(ev, data)
        except (BrokenPipeError, ConnectionResetError):
            pass                    # 客户端提前关闭连接是正常情况，不该刷错误栈

    def _sse(self, event: str, data: Any):
        self.wfile.write(f"event: {event}\n".encode())
        self.wfile.write(
            f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode())
        self.wfile.flush()


def serve(host: str = "127.0.0.1", port: int = 8080):
    srv = ThreadingHTTPServer((host, port), Handler)
    cfg = get_engine().cfg
    degr = getattr(cfg, "degradations", [])
    print(f"ScholarNexus 服务已启动  http://{host}:{port}")
    print(f"  运行档位: {cfg.profile}")
    if degr:
        print("  能力降级:")
        for d in degr:
            print(f"    - {d['layer']} → {d['to']}（{d['reason']}）")
    else:
        print("  全部能力就绪")
    if os.environ.get("SN_CORPUS"):
        print(f"  检索后端: 本地语料 {os.environ['SN_CORPUS']}")
    print(f"  评测接口 POST /retrieve   演示接口 POST /chat (SSE)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.server_close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--profile", default=None)
    a = ap.parse_args()
    if a.profile:
        os.environ["SN_PROFILE"] = a.profile
    serve(a.host, a.port)
