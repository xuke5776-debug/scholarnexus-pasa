"""命令行入口：python -m scholarnexus.cli "你的查询" """
from __future__ import annotations

import argparse
import json
import sys

from .config import Config
from .core.pipeline import ScholarNexus
from .present.insightboard import render_markdown
from .schema import Budget


def main(argv=None):
    ap = argparse.ArgumentParser(prog="scholarnexus",
                                 description="面向集合级 F1 的学术论文智能搜索")
    ap.add_argument("query", nargs="?", help="自然语言查询")
    ap.add_argument("-c", "--config", default=None, help="配置文件路径")
    ap.add_argument("-p", "--profile", default=None,
                    choices=["cloud", "local", "offline"], help="运行档位")
    ap.add_argument("--corpus", default=None, help="本地语料 jsonl（离线检索）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    ap.add_argument("--trace", action="store_true", help="实时打印执行链路")
    ap.add_argument("--max-llm", type=int, default=None, help="LLM 调用上限")
    ap.add_argument("--out", default=None, help="结果写入文件")
    a = ap.parse_args(argv)

    if not a.query:
        ap.print_help()
        return 1

    cfg = Config.load(a.config, a.profile)
    registry = None
    if a.corpus:
        from .sources.base import SourceRegistry
        from .sources.local_corpus import LocalCorpusSource
        registry = SourceRegistry().register(LocalCorpusSource(path=a.corpus))

    budget = Budget(max_llm_calls=a.max_llm) if a.max_llm else None
    on_event = None
    if a.trace:
        def on_event(stage, rec):
            brief = {k: v for k, v in rec.items()
                     if k not in ("stage", "plan", "views")}
            print(f"  [{rec['t']:>6.2f}s] {stage:<12} {brief}", file=sys.stderr)

    engine = ScholarNexus(cfg, registry=registry)
    res = engine.search(a.query, budget=budget, on_event=on_event)
    text = res.to_json() if a.json else render_markdown(res)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已写入 {a.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
