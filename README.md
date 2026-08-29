# ScholarNexus v1.0

面向复杂科研查询的低成本智能论文搜索与推荐系统。ScholarNexus 融合三类互补能力：

- PaperCompass 的多源检索、引文图、覆盖率估计、集合级输出决策和结构化界面；
- Ray-Scholar 的硬/软约束、别名、排除条件、可选监督校准与预算意识；
- ScholarWeave 的公开 SPAR 评测、严格调用上限、可安装工程和诚实评测规范。

系统默认只使用一次查询规划和一次结构化归纳；逐篇 LLM 精判与查询演化默认关闭，
只有在真实开发集证明收益后才通过配置开启。

## 当前可复现结果

离线合成夹具：618 篇论文、21 个集合检索查询。

| 方案 | Macro-F1 | Precision | Recall | 平均 LLM 调用 | 平均 tokens |
|---|---:|---:|---:|---:|---:|
| ScholarNexus | **0.5399** | 0.4135 | 0.8436 | **1.86** | **1082.8** |
| 固定 Top-20 | 0.4314 | 0.3786 | 0.6460 | 1.86 | 1082.8 |
| 固定阈值 0.5 | 0.4343 | 0.3288 | 0.6854 | 1.86 | 1082.8 |
| 关闭引文扩散 | 0.2712 | 0.2368 | 0.3756 | 1.95 | 916.4 |

相对融合前 PaperCompass 的同夹具结果，Macro-F1 从 0.5131 提升到 0.5399，
平均 LLM 调用从 8.5 降到 1.86。以上是合成回归结果，不冒充公开榜单成绩。
公开 SPAR 的 1000 条测试数据和评测入口已经包含在项目中，真实 API 结果需在同一
预算、固定模型版本下重新运行。

## 核心流程

1. QueryLens 将自然语言解析为查询类型、元数据硬约束、召回锚点、语义核验项和排除项。
2. ConstraintGraph 将别名组织为 OR 组，将不同正向约束组织为 AND，将排除项组织为 NOT。
3. MultiProbe 并行访问 OpenAlex、Semantic Scholar、arXiv、PubMed或本地夹具，并做跨源去重。
4. CitationRipple 对高置信种子执行双向引文扩散、共被引和文献耦合打分。
5. CascadeJudge 进行元数据过滤、零成本粗排和可选 reranker；昂贵 L3 只允许走 VoI 不确定带。
6. Calibration + CoverageMeter 估计相关概率、目标集合规模和当前覆盖率。
7. F1-Gate 根据校准概率选择输出前缀，避免固定 Top-K 对不同查询规模失配。
8. InsightBoard 输出高度相关、部分相关、约束矩阵、分面、时间线、关系图和成本账本。

F1 最优阈值与最优 F1 一半的关系已有 Lipton、Elkan、Naryanaswamy（2014）理论工作；
本项目不把该定理本身声明为原创。项目贡献是把它与相关集合规模估计、学术引文发现、
倾向性修正和 VoI 预算控制组合成可执行检索闭环。

## 快速开始

```bash
cd scholarnexus
python -m pip install -e .
python tests/run_tests.py
python scripts/run_eval.py --profile offline --ablation
python -m scholarnexus.cli \
  "2022年后将对比学习用于医学图像分割的论文，排除综述" \
  --corpus data/fixture/corpus.jsonl --profile offline
```

启动 Web 界面：

```bash
SN_CORPUS=data/fixture/corpus.jsonl python -m scholarnexus.server --profile offline --port 8090
```

浏览器打开 `http://127.0.0.1:8090`。页面提供查询理解、F1-Gate 输出决策、
约束满足矩阵、引文关系图、执行链路和成本账本；顶部快捷查询可直接演示完整检索流程。

## 千问配置

密钥只能通过环境变量传入：

```bash
export DASHSCOPE_API_KEY="你的新密钥"
export SN_PROFILE=cloud
python -m scholarnexus.cli "你的复杂学术查询" --profile cloud --trace
```

默认模型：查询规划使用 `qwen-flash`，批量语义精排使用 `qwen3-rerank`，可选 L3
使用 `qwen-plus`，三者共用一个 DashScope Key。如果相关服务不可用，相应层会独立
降级并在结果账本记录，密钥不会写进缓存和输出。

## 公开 SPAR 评测

```bash
python scripts/run_public.py \
  --data benchmarks/public/AutoScholarQuery_test.jsonl \
  --profile cloud --offset 0 --limit 100 \
  --api-budget 8 --llm-budget 2
```

评测优先使用 arXiv ID，其次使用规范化标题精确匹配；不会用模糊标题匹配抬高成绩。

## 可选监督校准

```bash
python scripts/fit_calibrator.py \
  --corpus data/fixture/corpus.jsonl \
  --queries path/to/dev.jsonl \
  --out models/calibrator.json
```

随后在配置中设置 `supervised_calibrator_path`。只能使用开发集拟合，测试集不得参与。

## 工程交付

- 44 项零网络测试；
- Python 3.10+ 可安装包与 CLI；
- 标准库 HTTP/SSE 服务和三栏审计界面；
- Dockerfile、cloud/local/offline 三档配置；
- SPAR 公开评测、离线评测、消融和监督校准脚本；
- 完整引用、创新边界、评测说明和初赛提交提纲。

更多信息见 `docs/ARCHITECTURE.md`、`docs/INNOVATION.md`、
`docs/EVALUATION.md`、`docs/CREDITS.md` 和 `docs/SUBMISSION.md`。
