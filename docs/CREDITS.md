# 引用、借鉴与创新边界

## 代码与工程来源

ScholarNexus 是本次融合迭代产生的新版本，以当前提供的 PaperCompass、Ray-Scholar 与
ScholarWeave 三个原型为设计输入。实现主体沿用 PaperCompass 的模块化工程骨架，并吸收
另外两个原型中经过核验的设计；没有把三套代码简单拼接成三条重复流水线。

Ray-Source 仅提供证据优先 RAG、执行审计、接口分离与失败降级方面的工程启发。
ScholarNexus 面向开放学术搜索重新实现检索、排序、集合决策与展示逻辑。

## 学术方法

| 方法 | 主要出处 | 项目用途 |
|---|---|---|
| 最优 F1 阈值 | Lipton, Elkan, Naryanaswamy, 2014 | F1-Gate 理论基础 |
| Chao1 捕获–再捕获 | Chao, 1984/1987 | 相关集合规模与覆盖率估计 |
| 谱式无监督集成 | Parisi et al., PNAS 2014 | 多路排序信号可靠性估计 |
| Reciprocal Rank Fusion | Cormack et al., SIGIR 2009 | 多通道召回融合 |
| Personalized PageRank | Haveliwala, 2002 | 双向引文图扩散 |
| 共被引/文献耦合 | Small, 1973; Kessler, 1963 | 引文邻域相关性 |
| Platt/Isotonic calibration | Platt, 1999; Zadrozny & Elkan, 2002 | 概率校准 |

特别说明：`p*=F1*/2` 不是本项目原创定理。可主张的创新是可执行约束图、
覆盖率估计、概率校准、F1 集合边界与信息价值预算在复杂学术检索中的闭环组合。

## 对标系统

- PaSa：借鉴引文网络驱动的多步检索思想；未使用其训练权重。
- SPAR：借鉴查询分解和演化思想；本项目默认关闭未经真实集验证的演化调用。
- AstaBench / Ai2 Paper Finder：借鉴公开评测契约、多索引与证据要求。
- PaperQA2：作为全文证据检索方向的对照，当前版本不冒充已经具备全文逐字证据。

## 数据与服务

- OpenAlex：开放学术元数据和引文图。
- Semantic Scholar Academic Graph API：语义检索、引用和被引信息。
- arXiv API：预印本元数据。
- PubMed E-utilities：生物医学扩展通道。
- `data/fixture`：项目自生成的离线回归夹具。
- `benchmarks/public/AutoScholarQuery_test.jsonl`：来自 SPAR 仓库的公开测试文件，
  随文件原许可使用，仅用于评测适配。

## 模型

- Qwen `qwen-flash`：查询解析和可选归纳。
- Qwen `qwen-plus`：可选的证据约束精判。
- Qwen `qwen3-rerank`：候选集合批量语义精排。
- `text-embedding-v3`：可选向量召回。
- `BAAI/bge-reranker-v2-m3`：可选本地或托管重排。

正式提交时必须记录实际调用日期、服务端模型版本、温度、预算和失败降级情况。
