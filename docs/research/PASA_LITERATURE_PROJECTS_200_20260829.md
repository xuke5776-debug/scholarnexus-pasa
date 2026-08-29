# PaSa 赛题相关论文与开源项目调研目录（200+ 条）

> 生成日期：2026-08-29。论文 120 篇，开源项目 120 个。
> 本目录面向 PaSa 的复杂学术查询、论文召回/排序、引文扩展、集合 F1 与评测工程。每条记录都保留公开来源链接和原始 API 文件名；“对 PaSa 的帮助”是可执行迁移建议，不等价于已在官方榜单上验证。

## 数据源与筛选协议

- 论文：OpenAlex Works 公共 API（19 个成功主题响应，每主题最多 200 条）与 Crossref Works API（20 个主题，每主题最多 100 条）；按规范化题名去重，以 OpenAlex 摘要/开放链接/引用数优先，结合主题命中做可解释排序。
- 项目：GitHub REST `search/repositories` 公共 API，12 个检索主题，每主题最多 100 条；排除 fork/archived，按仓库描述、topics、星标和主题命中去重排序。
- 相关性分层：`P0` 直接影响 PaSa 召回/排序/评测，`P1` 支撑图、RAG、部署或基础设施，优先级不是比赛成绩。
- 评测纪律：所有方法必须只用 train 标签训练或调参；dev 封存后比较；test 只用于最终导出；严格 arXiv ID 与官方标题脚本并报。
- 原始响应目录：`F:\pasa_research_20260829\openalex`、`F:\pasa_research_20260829\crossref`、`F:\pasa_research_20260829\github`。

## 结论摘要

1. 当前作品最需要补的是候选池覆盖和候选内相关性排序，优先级应放在密集/稀疏互补、查询改写、学术引文图和可校准重排，而不是继续堆生成式摘要。
2. 论文侧最值得先做的路线是：多路 query 编译 → lexical+dense 高召回 → train-only L2 融合/重排 → 概率校准的排名前缀 F1-Gate。
3. 项目侧最值得先读的实现是：BEIR/Pyserini/ir-measures（评测）、FAISS/Qdrant/Milvus（向量检索）、Sentence-Transformers/ColBERT/Cross-Encoder（表示与重排）、LangChain/LlamaIndex/Haystack（管线）、学术图谱与引文工具（领域扩展）。
4. 星标、论文引用数和仓库 README 只能帮助筛选，不能证明对 PaSa 有效；每个候选都应有最小 ablation 和 paired strict-ID 证据。

## 论文目录

### 检索基础与稀疏召回（14 篇）

#### P008. From Vector Space to Neural Ranking: A Comparative Study of Modern Information Retrieval Models
- 来源：[https://doi.org/10.64823/ijter.2621011](https://doi.org/10.64823/ijter.2621011)；年份：2026；venue：International Journal of Technology and Emerging Research；引用数：0；优先级：`P1`
- 证据摘要：Information retrieval has changed dramatically over the past decades. Early systems relied on simple keyword matching, but modern search engines must understand meaning, context, and user intent. This paper examines three major families of retrieval models that have shaped this evolution: vector space models, probabilistic retrieval, and neural retrieval. Vector space models represent documents and queries as weighted term vectors and rank them by similarity, providing a simple yet effective way to handle partial matches. Probabilistic models, such as BM25, treat relevance as a probability and rank documents according to how likely they are t
- 主题命中：检索基础与稀疏召回:3, 密集与对比学习检索:2, 重排与学习排序:2
- 原始响应：`02.json`
- 对 PaSa 的帮助：针对《From Vector Space to Neural Ranking: A Comparative Study of Modern Information Retrieval Models》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《From Vector Space to Neural Ranking: A Comparative Study of Modern Information Retrieval Models》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P018. Joint Optimization Framework Combining Sparse Representation and Dense Retrieval in PubMed Retrieval
- 来源：[https://doi.org/10.66238/ijcbs46](https://doi.org/10.66238/ijcbs46)；年份：2026；venue：International Journal of Computational and Biological Sciences；引用数：0；优先级：`P1`
- 证据摘要：The exponential growth of biomedical literature indexed in PubMed has necessitated thedevelopment of advanced information retrieval systems capable of navigating complexterminologies and user intents. Traditional sparse retrieval models, such as BM25, excel atexact lexical matching but fail to capture semantic nuances, whereas emerging denseretrieval techniques utilizing transformer-based encoders offer semantic understanding butoften struggle with precise entity matching and out-of-vocabulary domain-specific terms.This paper proposes a novel framework that jointly optimizes sparse representations anddense retrieval vectors within a unified l
- 主题命中：检索基础与稀疏召回:3, 评测、数据集与稳健性:2, 密集与对比学习检索:1, 重排与学习排序:1
- 原始响应：`13.json`
- 对 PaSa 的帮助：针对《Joint Optimization Framework Combining Sparse Representation and Dense Retrieval in PubMed Retrieval》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《Joint Optimization Framework Combining Sparse Representation and Dense Retrieval in PubMed Retrieval》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P028. CO-Search: COVID-19 Information Retrieval with Semantic Search, Question Answering, and Abstractive Summarization
- 来源：[https://doi.org/10.48550/arxiv.2006.09595](https://doi.org/10.48550/arxiv.2006.09595)；年份：2020；venue：arXiv (Cornell University)；引用数：32；优先级：`P1`
- 证据摘要：The COVID-19 global pandemic has resulted in international efforts to understand, track, and mitigate the disease, yielding a significant corpus of COVID-19 and SARS-CoV-2-related publications across scientific disciplines. As of May 2020, 128,000 coronavirus-related publications have been collected through the COVID-19 Open Research Dataset Challenge. Here we present CO-Search, a retriever-ranker semantic search engine designed to handle complex queries over the COVID-19 literature, potentially aiding overburdened health workers in finding scientific answers during a time of crisis. The retriever is built from a Siamese-BERT encoder that is
- 主题命中：检索基础与稀疏召回:3, 多跳检索与搜索智能体:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《CO-Search: COVID-19 Information Retrieval with Semantic Search, Question Answering, and Abstractive Summarization》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《CO-Search: COVID-19 Information Retrieval with Semantic Search, Question Answering, and Abstractive Summarization》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P038. Anserini Gets Dense Retrieval: Integration of Lucene's HNSW Indexes
- 来源：[https://doi.org/10.1145/3583780.3615112](https://doi.org/10.1145/3583780.3615112)；年份：2023；venue：未知；引用数：7；优先级：`P1`
- 证据摘要：Anserini is a Lucene-based toolkit for reproducible information retrieval research in Java that has been gaining traction in the community. It provides retrieval capabilities for both "traditional" bag-of-words retrieval models such as BM25 as well as retrieval using learned sparse representations such as SPLADE. With Pyserini, which provides a Python interface to Anserini, users gain access to both sparse and dense retrieval models, as Pyserini implements bindings to the Faiss vector search library alongside Lucene inverted indexes in a uniform, consistent interface. Nevertheless, hybrid fusion techniques that integrate sparse and dense retr
- 主题命中：检索基础与稀疏召回:3, 密集与对比学习检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/13.json`
- 对 PaSa 的帮助：针对《Anserini Gets Dense Retrieval: Integration of Lucene's HNSW Indexes》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《Anserini Gets Dense Retrieval: Integration of Lucene's HNSW Indexes》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P048. Nor-CaseHOLD: A Retrieval Benchmark for Norwegian Legal AI
- 来源：[https://doi.org/10.2139/ssrn.6459080](https://doi.org/10.2139/ssrn.6459080)；年份：2026；venue：未知；引用数：0；优先级：`P1`
- 证据摘要：&lt;p&gt;This paper presents two contributions to Norwegian legal NLP: Norwegian Legal BERT, a domain-adapted BERT model built by continuing masked language model pretraining of NbAiLab/nb-bert-base using 9,140 Norwegian legal documents; and Nor-CaseHOLD, a legal retrieval benchmark built from 1,244 documents — 627 Supreme Court (Høyesterett) decisions and 617 Skatteetaten bindende forhåndsuttalelser (BFU) — each paired with its official summary.&amp;nbsp;&lt;/p&gt; &lt;p&gt;To the author's knowledge, Norwegian Legal BERT is the first open-source domain-adapted Norwegian legal language model, and Nor-CaseHOLD is the first Norwegian open-sourc
- 主题命中：检索基础与稀疏召回:3, 重排与学习排序:2, 评测、数据集与稳健性:1
- 原始响应：`18.json`
- 对 PaSa 的帮助：针对《Nor-CaseHOLD: A Retrieval Benchmark for Norwegian Legal AI》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《Nor-CaseHOLD: A Retrieval Benchmark for Norwegian Legal AI》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P058. Pyserini: A Python Toolkit for Reproducible Information Retrieval Research with Sparse and Dense Representations
- 来源：[https://doi.org/10.1145/3404835.3463238](https://doi.org/10.1145/3404835.3463238)；年份：2021；venue：未知；引用数：356；优先级：`P1`
- 证据摘要：Pyserini is a Python toolkit for reproducible information retrieval research with sparse and dense representations. It aims to provide effective, reproducible, and easy-to-use first-stage retrieval in a multi-stage ranking architecture. Our toolkit is self-contained as a standard Python package and comes with queries, relevance judgments, pre-built indexes, and evaluation scripts for many commonly used IR test collections. We aim to support, out of the box, the entire research lifecycle of efforts aimed at improving ranking with modern neural approaches. In particular, Pyserini supports sparse retrieval (e.g., BM25 scoring using bag-of-words
- 主题命中：检索基础与稀疏召回:3, 密集与对比学习检索:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Pyserini: A Python Toolkit for Reproducible Information Retrieval Research with Sparse and Dense Representations》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《Pyserini: A Python Toolkit for Reproducible Information Retrieval Research with Sparse and Dense Representations》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P068. COVID-19 information retrieval with deep-learning based semantic search, question answering, and abstractive summarization
- 来源：[https://doi.org/10.1038/s41746-021-00437-0](https://doi.org/10.1038/s41746-021-00437-0)；年份：2021；venue：npj Digital Medicine；引用数：111；优先级：`P1`
- 证据摘要：The COVID-19 global pandemic has resulted in international efforts to understand, track, and mitigate the disease, yielding a significant corpus of COVID-19 and SARS-CoV-2-related publications across scientific disciplines. Throughout 2020, over 400,000 coronavirus-related publications have been collected through the COVID-19 Open Research Dataset. Here, we present CO-Search, a semantic, multi-stage, search engine designed to handle complex queries over the COVID-19 literature, potentially aiding overburdened health workers in finding scientific answers and avoiding misinformation during a time of crisis. CO-Search is built from two sequentia
- 主题命中：检索基础与稀疏召回:3, 评测、数据集与稳健性:1
- 原始响应：`openalex/05.json`
- 对 PaSa 的帮助：针对《COVID-19 information retrieval with deep-learning based semantic search, question answering, and abstractive summarization》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《COVID-19 information retrieval with deep-learning based semantic search, question answering, and abstractive summarization》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P078. Comparative Evaluation Of Sparse, Dense, And Hybrid Retrieval Models On Indonesian Wikipedia
- 来源：[https://doi.org/10.52436/1.jutif.2026.7.3.5776](https://doi.org/10.52436/1.jutif.2026.7.3.5776)；年份：2026；venue：Jurnal Teknik Informatika (Jutif)；引用数：0；优先级：`P1`
- 证据摘要：This study presents a comparative evaluation of Information Retrieval (IR) models on the Indonesian Wikipedia corpus, focusing on sparse, dense, and hybrid retrieval approaches. The evaluated methods include TF-IDF and BM25 as sparse models, SBERT (MiniLM) as a dense retrieval model, and hybrid retrieval implemented through score fusion. The dataset consists of 713,044 Wikipedia articles, with experiments conducted using 1,000 test queries. Performance is measured using Precision@10 (P@10) and Mean Reciprocal Rank (MRR). The results show that BM25 achieves the highest performance, with a P@10 of 0.973 and an MRR of 0.9174, significantly outpe
- 主题命中：检索基础与稀疏召回:3, 密集与对比学习检索:1, 评测、数据集与稳健性:1
- 原始响应：`13.json`
- 对 PaSa 的帮助：针对《Comparative Evaluation Of Sparse, Dense, And Hybrid Retrieval Models On Indonesian Wikipedia》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《Comparative Evaluation Of Sparse, Dense, And Hybrid Retrieval Models On Indonesian Wikipedia》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P088. Simple and Effective Unsupervised Redundancy Elimination to Compress Dense Vectors for Passage Retrieval
- 来源：[https://doi.org/10.18653/v1/2021.emnlp-main.227](https://doi.org/10.18653/v1/2021.emnlp-main.227)；年份：2021；venue：Proceedings of the 2021 Conference on Empirical Methods in Natural Language Processing；引用数：17；优先级：`P1`
- 证据摘要：Recent work has shown that dense passage retrieval techniques achieve better ranking accuracy in open-domain question answering compared to sparse retrieval techniques such as BM25, but at the cost of large space and memory requirements. In this paper, we analyze the redundancy present in encoded dense vectors and show that the default dimension of 768 is unnecessarily large. To improve space efficiency, we propose a simple unsupervised compression pipeline that consists of principal component analysis (PCA), product quantization, and hybrid search. We further investigate other supervised baselines and find surprisingly that unsupervised PCA
- 主题命中：检索基础与稀疏召回:2, 密集与对比学习检索:2, RAG与长文档检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Simple and Effective Unsupervised Redundancy Elimination to Compress Dense Vectors for Passage Retrieval》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《Simple and Effective Unsupervised Redundancy Elimination to Compress Dense Vectors for Passage Retrieval》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P098. Deep learning-based approach for Arabic open domain question answering
- 来源：[https://doi.org/10.7717/peerj-cs.952](https://doi.org/10.7717/peerj-cs.952)；年份：2022；venue：PeerJ Computer Science；引用数：20；优先级：`P1`
- 证据摘要：Open-domain question answering (OpenQA) is one of the most challenging yet widely investigated problems in natural language processing. It aims at building a system that can answer any given question from large-scale unstructured text or structured knowledge-base. To solve this problem, researchers traditionally use information retrieval methods to retrieve the most relevant documents and then use answer extractions techniques to extract the answer or passage from the candidate documents. In recent years, deep learning techniques have shown great success in OpenQA by using dense representation for document retrieval and reading comprehension
- 主题命中：检索基础与稀疏召回:2, 密集与对比学习检索:2, RAG与长文档检索:1, 评测、数据集与稳健性:1
- 原始响应：`17.json`
- 对 PaSa 的帮助：针对《Deep learning-based approach for Arabic open domain question answering》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《Deep learning-based approach for Arabic open domain question answering》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P107. ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT
- 来源：[https://doi.org/10.48550/arxiv.2004.12832](https://doi.org/10.48550/arxiv.2004.12832)；年份：2020；venue：arXiv (Cornell University)；引用数：192；优先级：`P1`
- 证据摘要：Recent progress in Natural Language Understanding (NLU) is driving fast-paced advances in Information Retrieval (IR), largely owed to fine-tuning deep language models (LMs) for document ranking. While remarkably effective, the ranking models based on these LMs increase computational cost by orders of magnitude over prior approaches, particularly as they must feed each query-document pair through a massive neural network to compute a single relevance score. To tackle this, we present ColBERT, a novel ranking model that adapts deep LMs (in particular, BERT) for efficient retrieval. ColBERT introduces a late interaction architecture that indepen
- 主题命中：检索基础与稀疏召回:1, 重排与学习排序:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/02.json`
- 对 PaSa 的帮助：针对《ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT》：优先做候选内 late-interaction 试验：保留 token-level MaxSim 或等价的多粒度匹配特征，限制到现有 L2 候选，观察严格 ID 的 R@20/R@100 是否同时改善。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P108. Large Language Models for Information Retrieval: A Survey
- 来源：[https://doi.org/10.48550/arxiv.2308.07107](https://doi.org/10.48550/arxiv.2308.07107)；年份：2023；venue：arXiv (Cornell University)；引用数：97；优先级：`P1`
- 证据摘要：As a primary means of information acquisition, information retrieval (IR) systems, such as search engines, have integrated themselves into our daily lives. These systems also serve as components of dialogue, question-answering, and recommender systems. The trajectory of IR has evolved dynamically from its origins in term-based methods to its integration with advanced neural models. While the neural models excel at capturing complex contextual signals and semantic nuances, thereby reshaping the IR landscape, they still face challenges such as data scarcity, interpretability, and the generation of contextually plausible yet potentially inaccura
- 主题命中：检索基础与稀疏召回:2, 重排与学习排序:1, 多跳检索与搜索智能体:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Large Language Models for Information Retrieval: A Survey》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《Large Language Models for Information Retrieval: A Survey》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P113. SPLADE: Sparse Lexical and Expansion Model for First Stage Ranking
- 来源：[https://doi.org/10.1145/3404835.3463098](https://doi.org/10.1145/3404835.3463098)；年份：2021；venue：未知；引用数：379；优先级：`P1`
- 证据摘要：In neural Information Retrieval, ongoing research is directed towards improving the first retriever in ranking pipelines. Learning dense embeddings to conduct retrieval using efficient approximate nearest neighbors methods has proven to work well. Meanwhile, there has been a growing interest in learning sparse representations for documents and queries, that could inherit from the desirable properties of bag-of-words models such as the exact matching of terms and the efficiency of inverted indexes. In this work, we present a new first-stage ranker based on explicit sparsity regularization and a log-saturation effect on term weights, leading to
- 主题命中：检索基础与稀疏召回:1
- 原始响应：`openalex/02.json`
- 对 PaSa 的帮助：针对《SPLADE: Sparse Lexical and Expansion Model for First Stage Ranking》：把 learned-sparse expansion 作为独立 L1 通道，与现有字段 BM25 做 union；记录该通道独有的 gold ID，只有 candidate recall 和 F1 都不回退才保留。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《SPLADE: Sparse Lexical and Expansion Model for First Stage Ranking》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P118. Do Neural Ranking Models Intensify Gender Bias?
- 来源：[https://doi.org/10.1145/3397271.3401280](https://doi.org/10.1145/3397271.3401280)；年份：2020；venue：未知；引用数：47；优先级：`P1`
- 证据摘要：Concerns regarding the footprint of societal biases in information retrieval (IR) systems have been raised in several previous studies. In this work, we examine various recent IR models from the perspective of the degree of gender bias in their retrieval results. To this end, we first provide a bias measurement framework which includes two metrics to quantify the degree of the unbalanced presence of gender-related concepts in a given IR model's ranking list. To examine IR models by means of the framework, we create a dataset of non-gendered queries, selected by human annotators. Applying these queries to the MS MARCO Passage retrieval collect
- 主题命中：检索基础与稀疏召回:2, 密集与对比学习检索:1, 重排与学习排序:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/02.json`
- 对 PaSa 的帮助：针对《Do Neural Ranking Models Intensify Gender Bias?》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 把论文中的词法匹配、倒排索引或概率检索思想作为 PaSa 的高召回 L1 层。优先在 title、abstract、section 与 reference title 分字段建索引，并用字段权重和 BM25 产生可解释的候选。在 dev 封存集上比较单字段、字段融合和查询词清洗，确认 widening 提升的是严格 ID candidate recall 而不是只增加噪声。
- 建议实测：围绕《Do Neural Ranking Models Intensify Gender Bias?》设计一个 train-only ablation：将其核心信号接入 检索基础与稀疏召回，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

### 密集与对比学习检索（16 篇）

#### P005. Span prompt dense passage retrieval for Chinese open domain question answering
- 来源：[https://doi.org/10.3233/jifs-231328](https://doi.org/10.3233/jifs-231328)；年份：2023；venue：Journal of Intelligent &amp; Fuzzy Systems；引用数：1；优先级：`P0`
- 证据摘要：Dense passage retrieval is a popular method in information retrieval recently, especially in open domain question answering. It aims to retrieve related articles from massive passages to answer the question. Retriever can increase retrieval speed with less loss of accuracy compared to other methods. However, the pretrained language models used in recent research are often ineffective in semantic embedding, which will reduce accuracy. In addition, we find that contrastive learning will diverge the representation space, and Siamese models with independent parameters on both sides will decrease generalization performance. Therefore, we propose s
- 主题命中：密集与对比学习检索:4, 检索基础与稀疏召回:1, 评测、数据集与稳健性:1
- 原始响应：`01.json`
- 对 PaSa 的帮助：针对《Span prompt dense passage retrieval for Chinese open domain question answering》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Span prompt dense passage retrieval for Chinese open domain question answering》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P015. Topic-DPR: Topic-based Prompts for Dense Passage Retrieval
- 来源：[https://doi.org/10.18653/v1/2023.findings-emnlp.480](https://doi.org/10.18653/v1/2023.findings-emnlp.480)；年份：2023；venue：未知；引用数：1；优先级：`P0`
- 证据摘要：Prompt-based learning's efficacy across numerous natural language processing tasks has led to its integration into dense passage retrieval. Prior research has mainly focused on enhancing the semantic understanding of pre-trained language models by optimizing a single vector as a continuous prompt. This approach, however, leads to a semantic space collapse; identical semantic information seeps into all representations, causing their distributions to converge in a restricted region. This hinders differentiation between relevant and irrelevant passages during dense retrieval. To tackle this issue, we present Topic-DPR, a dense passage retrieval
- 主题命中：密集与对比学习检索:4, 评测、数据集与稳健性:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Topic-DPR: Topic-based Prompts for Dense Passage Retrieval》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Topic-DPR: Topic-based Prompts for Dense Passage Retrieval》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P025. Distilling Cross-Encoder Signals into Bi-Encoders for Domain Retrieval
- 来源：[https://doi.org/10.64917/feaiml/volume02issue10-04](https://doi.org/10.64917/feaiml/volume02issue10-04)；年份：2025；venue：Frontiers in Emerging Artificial Intelligence and Machine Learning；引用数：0；优先级：`P0`
- 证据摘要：Dense retrieval models have become crucial for information retrieval tasks, but their success is frequently reliant on large, computationally expensive architectures. While existing approaches like REFINE [1] achieve strong performance through model fusion requiring dual model serving and weighted interpolation at inference time, this work proposes a novel fusion-free teacher-student knowledge distillation framework that achieves competitive performance with significantly simpler deployment. The key innovation lies in transferring fine-grained cross-encoder relevance judgments directly into a single deployable bi-encoder through listwise know
- 主题命中：密集与对比学习检索:3, 检索基础与稀疏召回:2, 重排与学习排序:2, 评测、数据集与稳健性:1
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对《Distilling Cross-Encoder Signals into Bi-Encoders for Domain Retrieval》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Distilling Cross-Encoder Signals into Bi-Encoders for Domain Retrieval》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P035. Knowledge-Aware Graph-Enhanced Transformer for Semantic Retrieval
- 来源：[https://doi.org/10.21203/rs.3.rs-9003446/v1](https://doi.org/10.21203/rs.3.rs-9003446/v1)；年份：2026；venue：未知；引用数：0；优先级：`P0`
- 证据摘要：Abstract Neural information retrieval has transformed search systems through powerful contextual embeddings, yet struggles persist with vocabulary mismatch and lack of explicit relational knowledge. A knowledge-aware framework combines transformer-based semantic encoding with graph-structured reasoning to significantly improve document ranking accuracy. The approach automatically constructs a corpus-level knowledge graph from entity relationships, generates dense embeddings via bi-encoders with synonym expansion, and employs graph convolutional networks for multi-hop relational reasoning. Contrastive learning then aligns relevant query-docume
- 主题命中：密集与对比学习检索:4, 检索基础与稀疏召回:1
- 原始响应：`14.json`
- 对 PaSa 的帮助：针对《Knowledge-Aware Graph-Enhanced Transformer for Semantic Retrieval》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Knowledge-Aware Graph-Enhanced Transformer for Semantic Retrieval》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P045. Analysing the Robustness of Dual Encoders for Dense Retrieval Against Misspellings
- 来源：[https://doi.org/10.1145/3477495.3531818](https://doi.org/10.1145/3477495.3531818)；年份：2022；venue：Proceedings of the 45th International ACM SIGIR Conference on Research and Development in Information Retrieval；引用数：18；优先级：`P0`
- 证据摘要：Dense retrieval is becoming one of the standard approaches for document and passage ranking. The dual-encoder architecture is widely adopted for scoring question-passage pairs due to its efficiency and high performance. Typically, dense retrieval models are evaluated on clean and curated datasets. However, when deployed in real-life applications, these models encounter noisy user-generated text. That said, the performance of state-of-the-art dense retrievers can substantially deteriorate when exposed to noisy text. In this work, we study the robustness of dense retrievers against typos in the user question. We observe a significant drop in th
- 主题命中：密集与对比学习检索:3, 检索基础与稀疏召回:1, RAG与长文档检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Analysing the Robustness of Dual Encoders for Dense Retrieval Against Misspellings》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Analysing the Robustness of Dual Encoders for Dense Retrieval Against Misspellings》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P055. DoSSIER@COLIEE 2021: Leveraging dense retrieval and summarization-based re-ranking for case law retrieval
- 来源：[https://doi.org/10.48550/arxiv.2108.03937](https://doi.org/10.48550/arxiv.2108.03937)；年份：2021；venue：arXiv (Cornell University)；引用数：10；优先级：`P0`
- 证据摘要：In this paper, we present our approaches for the case law retrieval and the case entailment task in the Competition on Legal Information /Entailment (COLIEE) 2021. As first stage retrieval methods combined neural re-ranking methods using contextualized language models like BERT great performance improvements for information retrieval in the web news domain, we evaluate these methods for the legal domain. A distinct of legal case retrieval is that the query case and case in the corpus tend to be long documents and therefore exceed the length of BERT. We address this challenge by combining lexical and dense methods on the paragraph-level of the
- 主题命中：密集与对比学习检索:3, 检索基础与稀疏召回:2, 重排与学习排序:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《DoSSIER@COLIEE 2021: Leveraging dense retrieval and summarization-based re-ranking for case law retrieval》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《DoSSIER@COLIEE 2021: Leveraging dense retrieval and summarization-based re-ranking for case law retrieval》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P065. MD2PR: A Multi-level Distillation based Dense Passage Retrieval Model
- 来源：[https://doi.org/10.21203/rs.3.rs-6219315/v1](https://doi.org/10.21203/rs.3.rs-6219315/v1)；年份：2025；venue：未知；引用数：0；优先级：`P0`
- 证据摘要：Abstract Reranker and retriever are two important components in information retrieval. The retriever typically adopts a dual-encoder model, where queries and documents are separately input into two pre-trained models, and the vectors generated by the models are used for similarity calculation. The reranker often uses a cross-encoder model, where the concatenated query-document pairs are input into a pre-trained model to obtain word similarities. However, the dual-encoder model lacks interaction between queries and documents due to its independent encoding, while the cross-encoder model requires substantial computational cost for attention cal
- 主题命中：密集与对比学习检索:3, 重排与学习排序:2, 检索基础与稀疏召回:1, 评测、数据集与稳健性:1
- 原始响应：`01.json`
- 对 PaSa 的帮助：针对《MD2PR: A Multi-level Distillation based Dense Passage Retrieval Model》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《MD2PR: A Multi-level Distillation based Dense Passage Retrieval Model》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P075. On Single and Multiple Representations in Dense Passage Retrieval
- 来源：[https://doi.org/10.48550/arxiv.2108.06279](https://doi.org/10.48550/arxiv.2108.06279)；年份：2021；venue：arXiv (Cornell University)；引用数：5；优先级：`P0`
- 证据摘要：The advent of contextualised language models has brought gains in search effectiveness, not just when applied for re-ranking the output of classical weighting models such as BM25, but also when used directly for passage indexing and retrieval, a technique which is called dense retrieval. In the existing literature in neural ranking, two dense retrieval families have become apparent: single representation, where entire passages are represented by a single embedding (usually BERT's [CLS] token, as exemplified by the recent ANCE approach), or multiple representations, where each token in a passage is represented by its own embedding (as exemplif
- 主题命中：密集与对比学习检索:3, 重排与学习排序:2, 检索基础与稀疏召回:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《On Single and Multiple Representations in Dense Passage Retrieval》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《On Single and Multiple Representations in Dense Passage Retrieval》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P085. TempRetriever: Fusion-based Temporal Dense Passage Retrieval for Time-Sensitive Questions
- 来源：[https://doi.org/10.1145/3773966.3777938](https://doi.org/10.1145/3773966.3777938)；年份：2026；venue：未知；引用数：2；优先级：`P0`
- 证据摘要：Temporal information is crucial for information retrieval, yet most dense retrieval systems focus exclusively on semantic similarity while neglecting temporal alignment between queries and documents. We propose TempRetriever, a lightweight framework that explicitly incorporates temporal information into dense passage retrieval through learned fusion techniques. Unlike existing approaches requiring extensive architectural modifications or specialized pre-training, TempRetriever enhances standard dense retrievers by combining semantic embeddings with temporal representations using four fusion strategies: Feature Stacking, Vector Summation, Rela
- 主题命中：密集与对比学习检索:3, 检索基础与稀疏召回:1, RAG与长文档检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《TempRetriever: Fusion-based Temporal Dense Passage Retrieval for Time-Sensitive Questions》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《TempRetriever: Fusion-based Temporal Dense Passage Retrieval for Time-Sensitive Questions》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P095. Challenging Decoder helps in Masked Auto-Encoder Pre-training for Dense Passage Retrieval
- 来源：[https://doi.org/10.48550/arxiv.2305.13197](https://doi.org/10.48550/arxiv.2305.13197)；年份：2023；venue：arXiv (Cornell University)；引用数：1；优先级：`P0`
- 证据摘要：Recently, various studies have been directed towards exploring dense passage retrieval techniques employing pre-trained language models, among which the masked auto-encoder (MAE) pre-training architecture has emerged as the most promising. The conventional MAE framework relies on leveraging the passage reconstruction of decoder to bolster the text representation ability of encoder, thereby enhancing the performance of resulting dense retrieval systems. Within the context of building the representation ability of the encoder through passage reconstruction of decoder, it is reasonable to postulate that a ``more demanding'' decoder will necessit
- 主题命中：密集与对比学习检索:3, 评测、数据集与稳健性:3
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Challenging Decoder helps in Masked Auto-Encoder Pre-training for Dense Passage Retrieval》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Challenging Decoder helps in Masked Auto-Encoder Pre-training for Dense Passage Retrieval》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P103. Query2doc: Query Expansion with Large Language Models
- 来源：[https://doi.org/10.18653/v1/2023.emnlp-main.585](https://doi.org/10.18653/v1/2023.emnlp-main.585)；年份：2023；venue：未知；引用数：182；优先级：`P0`
- 证据摘要：This paper introduces a simple yet effective query expansion approach, denoted as query2doc, to improve both sparse and dense retrieval systems
- 主题命中：密集与对比学习检索:1, 查询扩展与改写:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Query2doc: Query Expansion with Large Language Models》：将查询扩展限制为原问题、约束化问题两个可审计视图，扩展只负责提高候选覆盖，不能直接改写最终排序；按 route_id 做去重和 paired ablation。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Query2doc: Query Expansion with Large Language Models》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P104. Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering
- 来源：[https://doi.org/10.18653/v1/2021.eacl-main.74](https://doi.org/10.18653/v1/2021.eacl-main.74)；年份：2021；venue：未知；引用数：99；优先级：`P0`
- 证据摘要：Generative models for open domain question answering have proven to be competitive, without resorting to external knowledge. While promising, this approach requires to use models with billions of parameters, which are expensive to train and query. In this paper, we investigate how much these models can benefit from retrieving text passages, potentially containing evidence. We obtain state-of-the-art results on the Natural Questions and TriviaQA open benchmarks. Interestingly, we observe that the performance of this method significantly improves when increasing the number of retrieved passages. This is evidence that generative models are good
- 主题命中：密集与对比学习检索:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Leveraging Passage Retrieval with Generative Models for Open Domain Question Answering》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P105. Aggretriever: A Simple Approach to Aggregate Textual Representations for Robust Dense Passage Retrieval
- 来源：[https://doi.org/10.1162/tacl_a_00556](https://doi.org/10.1162/tacl_a_00556)；年份：2023；venue：Transactions of the Association for Computational Linguistics；引用数：24；优先级：`P0`
- 证据摘要：Abstract Pre-trained language models have been successful in many knowledge-intensive NLP tasks. However, recent work has shown that models such as BERT are not “structurally ready” to aggregate textual information into a [CLS] vector for dense passage retrieval (DPR). This “lack of readiness” results from the gap between language model pre-training and DPR fine-tuning. Previous solutions call for computationally expensive techniques such as hard negative mining, cross-encoder distillation, and further pre-training to learn a robust DPR model. In this work, we instead propose to fully exploit knowledge in a pre-trained language model for DPR
- 主题命中：密集与对比学习检索:3, 重排与学习排序:1, RAG与长文档检索:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Aggretriever: A Simple Approach to Aggregate Textual Representations for Robust Dense Passage Retrieval》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Aggretriever: A Simple Approach to Aggregate Textual Representations for Robust Dense Passage Retrieval》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P114. Precise Zero-Shot Dense Retrieval without Relevance Labels
- 来源：[https://doi.org/10.18653/v1/2023.acl-long.99](https://doi.org/10.18653/v1/2023.acl-long.99)；年份：2023；venue：未知；引用数：297；优先级：`P0`
- 证据摘要：While dense retrieval has been shown to be effective and efficient across tasks and languages, it remains difficult to create effective fully zero-shot dense retrieval systems when no relevance labels are available. In this paper, we recognize the difficulty of zero-shot learning and encoding relevance. Instead, we propose to pivot through Hypothetical Document Embeddings (HyDE). Given a query, HyDE first zero-shot prompts an instruction-following language model (e.g., InstructGPT) to generate a hypothetical document. The document captures relevance patterns but is "fake" and may contain hallucinations. Then, an unsupervised contrastively lea
- 主题命中：密集与对比学习检索:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Precise Zero-Shot Dense Retrieval without Relevance Labels》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Precise Zero-Shot Dense Retrieval without Relevance Labels》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P115. Negative Sampling Techniques for Dense Passage Retrieval in a Multilingual Setting
- 来源：[https://doi.org/10.1145/3626772.3657854](https://doi.org/10.1145/3626772.3657854)；年份：2024；venue：未知；引用数：7；优先级：`P0`
- 证据摘要：The bi-encoder transformer architecture has become popular in open-domain retrieval, surpassing traditional sparse retrieval methods. Using hard negatives during training can improve the effectiveness of dense retrievers, and various techniques have been proposed to generate these hard negatives. We investigate the effectiveness of multiple negative sampling methods based on lexical methods (BM25), clustering, and periodically updated dense indices. We examine techniques that were introduced for finding hard negatives in a monolingual setting and reproduce them in a multilingual setting. We discover a gap amongst these techniques that we fill
- 主题命中：密集与对比学习检索:3, 检索基础与稀疏召回:2
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Negative Sampling Techniques for Dense Passage Retrieval in a Multilingual Setting》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Negative Sampling Techniques for Dense Passage Retrieval in a Multilingual Setting》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P117. Dense Passage Retrieval for Open-Domain Question Answering
- 来源：[https://doi.org/10.18653/v1/2020.emnlp-main.550](https://doi.org/10.18653/v1/2020.emnlp-main.550)；年份：2020；venue：未知；引用数：142；优先级：`P0`
- 证据摘要：Vladimir Karpukhin, Barlas Oguz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey Edunov, Danqi Chen, Wen-tau Yih. Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP). 2020
- 主题命中：密集与对比学习检索:2, RAG与长文档检索:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Dense Passage Retrieval for Open-Domain Question Answering》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 将其双编码器、对比学习或语义向量检索作为词法召回的互补通道。PaSa 中应固定 raw-question embedding，先扩大候选池，再把 dense rank/score 与 L1/RRF 一起送入 L2；不能把 dense top-k 直接当最终答案，因为领域词、数字和方法名可能被语义相似度淹没。
- 建议实测：围绕《Dense Passage Retrieval for Open-Domain Question Answering》设计一个 train-only ablation：将其核心信号接入 密集与对比学习检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

### 重排与学习排序（13 篇）

#### P010. A Thorough Comparison of Cross-Encoders and LLMs for Reranking SPLADE
- 来源：[https://doi.org/10.48550/arxiv.2403.10407](https://doi.org/10.48550/arxiv.2403.10407)；年份：2024；venue：arXiv (Cornell University)；引用数：2；优先级：`P0`
- 证据摘要：We present a comparative study between cross-encoder and LLMs rerankers in the context of re-ranking effective SPLADE retrievers. We conduct a large evaluation on TREC Deep Learning datasets and out-of-domain datasets such as BEIR and LoTTE. In the first set of experiments, we show how cross-encoder rerankers are hard to distinguish when it comes to re-rerank SPLADE on MS MARCO. Observations shift in the out-of-domain scenario, where both the type of model and the number of documents to re-rank have an impact on effectiveness. Then, we focus on listwise rerankers based on Large Language Models -- especially GPT-4. While GPT-4 demonstrates imp
- 主题命中：重排与学习排序:4, 评测、数据集与稳健性:1
- 原始响应：`openalex/12.json`
- 对 PaSa 的帮助：针对《A Thorough Comparison of Cross-Encoders and LLMs for Reranking SPLADE》：把 learned-sparse expansion 作为独立 L1 通道，与现有字段 BM25 做 union；记录该通道独有的 gold ID，只有 candidate recall 和 F1 都不回退才保留。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《A Thorough Comparison of Cross-Encoders and LLMs for Reranking SPLADE》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P020. RocketQAv2: A Joint Training Method for Dense Passage Retrieval and Passage Re-ranking
- 来源：[https://doi.org/10.18653/v1/2021.emnlp-main.224](https://doi.org/10.18653/v1/2021.emnlp-main.224)；年份：2021；venue：Proceedings of the 2021 Conference on Empirical Methods in Natural Language Processing；引用数：151；优先级：`P0`
- 证据摘要：In various natural language processing tasks, passage retrieval and passage re-ranking are two key procedures in finding and ranking relevant information. Since both the two procedures contribute to the final performance, it is important to jointly optimize them in order to achieve mutual improvement. In this paper, we propose a novel joint training approach for dense passage retrieval and passage reranking. A major contribution is that we introduce the dynamic listwise distillation, where we design a unified listwise training approach for both the retriever and the re-ranker. During the dynamic distillation, the retriever and the re-ranker c
- 主题命中：重排与学习排序:3, 密集与对比学习检索:2, 评测、数据集与稳健性:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《RocketQAv2: A Joint Training Method for Dense Passage Retrieval and Passage Re-ranking》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《RocketQAv2: A Joint Training Method for Dense Passage Retrieval and Passage Re-ranking》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P030. Zero-Shot Listwise Document Reranking with a Large Language Model
- 来源：[https://doi.org/10.48550/arxiv.2305.02156](https://doi.org/10.48550/arxiv.2305.02156)；年份：2023；venue：arXiv (Cornell University)；引用数：24；优先级：`P0`
- 证据摘要：Supervised ranking methods based on bi-encoder or cross-encoder architectures have shown success in multi-stage text ranking tasks, but they require large amounts of relevance judgments as training data. In this work, we propose Listwise Reranker with a Large Language Model (LRL), which achieves strong reranking effectiveness without using any task-specific training data. Different from the existing pointwise ranking methods, where documents are scored independently and ranked according to the scores, LRL directly generates a reordered list of document identifiers given the candidate documents. Experiments on three TREC web search datasets de
- 主题命中：重排与学习排序:3, 密集与对比学习检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/12.json`
- 对 PaSa 的帮助：针对《Zero-Shot Listwise Document Reranking with a Large Language Model》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《Zero-Shot Listwise Document Reranking with a Large Language Model》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P040. FIRST: Faster Improved Listwise Reranking with Single Token Decoding
- 来源：[https://doi.org/10.18653/v1/2024.emnlp-main.491](https://doi.org/10.18653/v1/2024.emnlp-main.491)；年份：2024；venue：未知；引用数：20；优先级：`P0`
- 证据摘要：Large Language Models (LLMs) have significantly advanced the field of information retrieval, particularly for reranking.Listwise LLM rerankers typically showcase superior performance and generalizability over conventional supervised approaches.However, existing LLM rerankers can be inefficient as they provide ranking output in the form of a generated ordered sequence of candidate passage identifiers.Further, they are trained using the standard language modeling objective, which treats all ranking errors uniformly, potentially at the cost of misranking highly relevant passages.Addressing these limitations, we introduce FIRST 1 , a novel listwi
- 主题命中：重排与学习排序:3, 检索基础与稀疏召回:1
- 原始响应：`openalex/12.json`
- 对 PaSa 的帮助：针对《FIRST: Faster Improved Listwise Reranking with Single Token Decoding》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《FIRST: Faster Improved Listwise Reranking with Single Token Decoding》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P050. Leveraging Passage Embeddings for Efficient Listwise Reranking with Large Language Models
- 来源：[https://doi.org/10.1145/3696410.3714554](https://doi.org/10.1145/3696410.3714554)；年份：2025；venue：未知；引用数：16；优先级：`P0`
- 证据摘要：Recent studies have demonstrated the effectiveness of using large language language models (LLMs) in passage ranking. The listwise approaches, such as RankGPT, have become new state-of-the-art in this task. However, the efficiency of RankGPT models is limited by the maximum context length and relatively high latency of LLM inference. To address these issues, in this paper, we propose PE-Rank, leveraging the single passage embedding as a good context compression for efficient listwise passage reranking. By treating each passage as a special token, we can directly input passage embeddings into LLMs, thereby reducing input length. Additionally,
- 主题命中：重排与学习排序:3
- 原始响应：`openalex/12.json`
- 对 PaSa 的帮助：针对《Leveraging Passage Embeddings for Efficient Listwise Reranking with Large Language Models》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《Leveraging Passage Embeddings for Efficient Listwise Reranking with Large Language Models》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P060. The Impact of Query Decomposition and Cross-Encoder Reranking in Multi-Hop Retrieval-Augmented Generation
- 来源：[https://doi.org/10.66245/jyi.v1.i1.002](https://doi.org/10.66245/jyi.v1.i1.002)；年份：2026；venue：Journal of Youth Impact；引用数：0；优先级：`P0`
- 证据摘要：Retrieval-Augmented Generation (RAG) has emerged as a promising paradigm for open-domain question answering. However, standard single-hop retrieval often fails on complex, multi-hop queries where the answer requires synthesizing information from disparate documents. In this work, we propose an enhanced Multi-Hop RAG pipeline augmented with Cross-Encoder Reranking to address the challenges of reasoning across multiple documents. Our approach decomposes complex queries into self-contained sub-questions and employs a Cross-Encoder to rerank candidates at each retrieval step, mitigating the "semantic drift" inherent in dense vector search. We sys
- 主题命中：重排与学习排序:2, RAG与长文档检索:2, 密集与对比学习检索:1, 多跳检索与搜索智能体:1, 评测、数据集与稳健性:1
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对《The Impact of Query Decomposition and Cross-Encoder Reranking in Multi-Hop Retrieval-Augmented Generation》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《The Impact of Query Decomposition and Cross-Encoder Reranking in Multi-Hop Retrieval-Augmented Generation》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P070. MEGA-RAG: a retrieval-augmented generation framework with multi-evidence guided answer refinement for mitigating hallucinations of LLMs in public health
- 来源：[https://doi.org/10.3389/fpubh.2025.1635381](https://doi.org/10.3389/fpubh.2025.1635381)；年份：2025；venue：Frontiers in Public Health；引用数：36；优先级：`P0`
- 证据摘要：Introduction: The increasing adoption of large language models (LLMs) in public health has raised significant concerns about hallucinations-factually inaccurate or misleading outputs that can compromise clinical communication and policy decisions. Methods: We propose a retrieval-augmented generation framework with multi-evidence guided answer refinement (MEGA-RAG), specifically designed to mitigate hallucinations in public health applications. The framework integrates multi-source evidence retrieval (dense retrieval via FAISS, keyword-based retrieval via BM25, and biomedical knowledge graphs), employs a cross-encoder reranker to ensure semant
- 主题命中：重排与学习排序:2, 检索基础与稀疏召回:1, 密集与对比学习检索:1, RAG与长文档检索:1
- 原始响应：`openalex/20.json`
- 对 PaSa 的帮助：针对《MEGA-RAG: a retrieval-augmented generation framework with multi-evidence guided answer refinement for mitigating hallucinations of LLMs in public health》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《MEGA-RAG: a retrieval-augmented generation framework with multi-evidence guided answer refinement for mitigating hallucinations of LLMs in public health》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P080. Learning to rank for information retrieval
- 来源：[https://doi.org/10.1145/1835449.1835676](https://doi.org/10.1145/1835449.1835676)；年份：2010；venue：未知；引用数：1953；优先级：`P0`
- 证据摘要：This tutorial is concerned with a comprehensive introduction to the research area of learning to rank for information retrieval. In the first part of the tutorial, we will introduce three major approaches to learning to rank, i.e., the pointwise, pairwise, and listwise approaches, analyze the relationship between the loss functions used in these approaches and the widely-used IR evaluation measures, evaluate the performance of these approaches on the LETOR benchmark datasets, and demonstrate how to use these approaches to solve real ranking applications. In the second part of the tutorial, we will discuss some advanced topics regarding learni
- 主题命中：重排与学习排序:2, 检索基础与稀疏召回:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/03.json`
- 对 PaSa 的帮助：针对《Learning to rank for information retrieval》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《Learning to rank for information retrieval》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P087. MTEB: Massive Text Embedding Benchmark
- 来源：[https://doi.org/10.18653/v1/2023.eacl-main.148](https://doi.org/10.18653/v1/2023.eacl-main.148)；年份：2023；venue：未知；引用数：424；优先级：`P0`
- 证据摘要：Text embeddings are commonly evaluated on a small set of datasets from a single task not covering their possible applications to other tasks. It is unclear whether state-of-the-art embeddings on semantic textual similarity (STS) can be equally well applied to other tasks like clustering or reranking. This makes progress in the field difficult to track, as various models are constantly being proposed without proper evaluation. To solve this problem, we introduce the Massive Text Embedding Benchmark (MTEB). MTEB spans 8 embedding tasks covering a total of 58 datasets and 112 languages. Through the benchmarking of 33 models on MTEB, we establish
- 主题命中：重排与学习排序:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/12.json`
- 对 PaSa 的帮助：针对《MTEB: Massive Text Embedding Benchmark》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《MTEB: Massive Text Embedding Benchmark》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P090. Retrieval, Re-ranking and Multi-task Learning for Knowledge-Base Question Answering
- 来源：[https://doi.org/10.18653/v1/2021.eacl-main.26](https://doi.org/10.18653/v1/2021.eacl-main.26)；年份：2021；venue：未知；引用数：26；优先级：`P0`
- 证据摘要：Question answering over knowledge bases (KBQA) usually involves three sub-tasks, namely topic entity detection, entity linking and relation detection. Due to the large number of entities and relations inside knowledge bases (KB), previous work usually utilized sophisticated rules to narrow down the search space and managed only a subset of KBs in memory. In this work, we leverage a retrieveand-rerank framework to access KBs via traditional information retrieval (IR) method, and re-rank retrieved candidates with more powerful neural networks such as the pre-trained BERT model. Considering the fact that directly assigning a different BERT model
- 主题命中：重排与学习排序:2, 检索基础与稀疏召回:1, 图检索与知识图谱:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《Retrieval, Re-ranking and Multi-task Learning for Knowledge-Base Question Answering》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《Retrieval, Re-ranking and Multi-task Learning for Knowledge-Base Question Answering》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P100. Question Decomposition for Retrieval-Augmented Generation
- 来源：[https://doi.org/10.18653/v1/2025.acl-srw.32](https://doi.org/10.18653/v1/2025.acl-srw.32)；年份：2025；venue：未知；引用数：11；优先级：`P0`
- 证据摘要：Grounding large language models (LLMs) in verifiable external sources is a wellestablished strategy for generating reliable answers.Retrieval-augmented generation (RAG) is one such approach, particularly effective for tasks like question answering: it retrieves passages that are semantically related to the question and then conditions the model on this evidence.However, multi-hop questions, such as "Which company among NVIDIA, Apple, and Google made the biggest profit in 2023?," challenge RAG because relevant facts are often distributed across multiple documents rather than co-occurring in one source, making it difficult for standard RAG to r
- 主题命中：重排与学习排序:2, 多跳检索与搜索智能体:1, RAG与长文档检索:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《Question Decomposition for Retrieval-Augmented Generation》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《Question Decomposition for Retrieval-Augmented Generation》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P110. A Multi-Stage Hybrid Retrieval Framework for the Scientific Literature with Cross-Encoder Re-Ranking
- 来源：[https://doi.org/10.3390/app16104813](https://doi.org/10.3390/app16104813)；年份：2026；venue：Applied Sciences；引用数：0；优先级：`P0`
- 证据摘要：Effective scientific literature retrieval requires moving beyond surface-level term matching toward structured semantic reasoning. This paper presents a controlled empirical study of multi-stage retrieval for scientific literature, integrating lexical matching, dense semantic modeling, hybrid fusion, and cross-encoder re-ranking within a unified evaluation framework. The study is designed to analyze the interactions, trade-offs, and failure modes of these components in claim-based scientific search. Experiments on the SciFact benchmark demonstrate that dense models capture semantic similarity but remain insufficient when used in isolation. Hy
- 主题命中：重排与学习排序:2, 评测、数据集与稳健性:2, 检索基础与稀疏召回:1, 查询扩展与改写:1
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对《A Multi-Stage Hybrid Retrieval Framework for the Scientific Literature with Cross-Encoder Re-Ranking》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《A Multi-Stage Hybrid Retrieval Framework for the Scientific Literature with Cross-Encoder Re-Ranking》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P120. From Neural Re-Ranking to Neural Ranking
- 来源：[https://doi.org/10.1145/3269206.3271800](https://doi.org/10.1145/3269206.3271800)；年份：2018；venue：未知；引用数：186；优先级：`P0`
- 证据摘要：The availability of massive data and computing power allowing for effective data driven neural approaches is having a major impact on machine learning and information retrieval research, but these models have a basic problem with efficiency. Current neural ranking models are implemented as multistage rankers: for efficiency reasons, the neural model only re-ranks the top ranked documents retrieved by a first-stage efficient ranker in response to a given query. Neural ranking models learn dense representations causing essentially every query term to match every document term, making it highly inefficient or intractable to rank the whole collec
- 主题命中：重排与学习排序:2, 检索基础与稀疏召回:1, 查询扩展与改写:1
- 原始响应：`openalex/02.json`
- 对 PaSa 的帮助：针对《From Neural Re-Ranking to Neural Ranking》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 用于 PaSa 的候选内排序，而不是用来弥补候选池漏召回。建议提取论文的 lexical rank、dense rank、cross-encoder 分数、字段命中、查询类型和引文证据，在 train 严格 arXiv ID 标签上训练 pairwise/listwise 或轻量融合器，并以 R@20、R@100 和最终 F1 联合门控。
- 建议实测：围绕《From Neural Re-Ranking to Neural Ranking》设计一个 train-only ablation：将其核心信号接入 重排与学习排序，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

### 查询扩展与改写（8 篇）

#### P007. Multi-Stage Conversational Passage Retrieval: An Approach to Fusing Term Importance Estimation and Neural Query Rewriting
- 来源：[https://doi.org/10.1145/3446426](https://doi.org/10.1145/3446426)；年份：2021；venue：ACM Transactions on Information Systems；引用数：55；优先级：`P0`
- 证据摘要：Conversational search plays a vital role in conversational information seeking. As queries in information seeking dialogues are ambiguous for traditional ad hoc information retrieval (IR) systems due to the coreference and omission resolution problems inherent in natural language dialogue, resolving these ambiguities is crucial. In this article, we tackle conversational passage retrieval, an important component of conversational search, by addressing query ambiguities with query reformulation integrated into a multi-stage ad hoc IR system. Specifically, we propose two conversational query reformulation (CQR) methods: (1) term importance estim
- 主题命中：查询扩展与改写:2, 对话、推荐与集合选择:2, 检索基础与稀疏召回:1, 密集与对比学习检索:1
- 原始响应：`openalex/15.json`
- 对 PaSa 的帮助：针对《Multi-Stage Conversational Passage Retrieval: An Approach to Fusing Term Importance Estimation and Neural Query Rewriting》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 用于把自然语言科研问题编译成多个互补检索动作：原问题、方法/数据集/指标窄探针和受控同义改写。扩展词只负责提高候选覆盖，排除词必须隔离在负向惩罚或过滤通道；每个改写要保留 route_id，用 RRF 或学习融合去重，避免把一个宽泛改写的偏差放大到最终排名。
- 建议实测：围绕《Multi-Stage Conversational Passage Retrieval: An Approach to Fusing Term Importance Estimation and Neural Query Rewriting》设计一个 train-only ablation：将其核心信号接入 查询扩展与改写，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P017. TREC CAsT 2019: The Conversational Assistance Track Overview
- 来源：[https://doi.org/10.48550/arxiv.2003.13624](https://doi.org/10.48550/arxiv.2003.13624)；年份：2020；venue：arXiv (Cornell University)；引用数：31；优先级：`P0`
- 证据摘要：The Conversational Assistance Track (CAsT) is a new track for TREC 2019 to facilitate Conversational Information Seeking (CIS) research and to create a large-scale reusable test collection for conversational search systems. The document corpus is 38,426,252 passages from the TREC Complex Answer Retrieval (CAR) and Microsoft MAchine Reading COmprehension (MARCO) datasets. Eighty information seeking dialogues (30 train, 50 test) are an average of 9 to 10 questions long. Relevance assessments are provided for 30 training topics and 20 test topics. This year 21 groups submitted a total of 65 runs using varying methods for conversational query und
- 主题命中：查询扩展与改写:2, 对话、推荐与集合选择:2, 重排与学习排序:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/15.json`
- 对 PaSa 的帮助：针对《TREC CAsT 2019: The Conversational Assistance Track Overview》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 用于把自然语言科研问题编译成多个互补检索动作：原问题、方法/数据集/指标窄探针和受控同义改写。扩展词只负责提高候选覆盖，排除词必须隔离在负向惩罚或过滤通道；每个改写要保留 route_id，用 RRF 或学习融合去重，避免把一个宽泛改写的偏差放大到最终排名。
- 建议实测：围绕《TREC CAsT 2019: The Conversational Assistance Track Overview》设计一个 train-only ablation：将其核心信号接入 查询扩展与改写，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P027. ConvGQR: Generative Query Reformulation for Conversational Search
- 来源：[https://doi.org/10.18653/v1/2023.acl-long.274](https://doi.org/10.18653/v1/2023.acl-long.274)；年份：2023；venue：未知；引用数：36；优先级：`P0`
- 证据摘要：In conversational search, the user's real search intent for the current conversation turn is dependent on the previous conversation history. It is challenging to determine a good search query from the whole conversation context. To avoid the expensive re-training of the query encoder, most existing methods try to learn a rewriting model to de-contextualize the current query by mimicking the manual query rewriting. However, manually rewritten queries are not always the best search queries. Thus, training a rewriting model on them would lead to sub-optimal queries. Another useful information to enhance the search query is the potential answer t
- 主题命中：查询扩展与改写:2, 评测、数据集与稳健性:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/15.json`
- 对 PaSa 的帮助：针对《ConvGQR: Generative Query Reformulation for Conversational Search》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 用于把自然语言科研问题编译成多个互补检索动作：原问题、方法/数据集/指标窄探针和受控同义改写。扩展词只负责提高候选覆盖，排除词必须隔离在负向惩罚或过滤通道；每个改写要保留 route_id，用 RRF 或学习融合去重，避免把一个宽泛改写的偏差放大到最终排名。
- 建议实测：围绕《ConvGQR: Generative Query Reformulation for Conversational Search》设计一个 train-only ablation：将其核心信号接入 查询扩展与改写，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P037. Query Reformulation using Query History for Passage Retrieval in Conversational Search
- 来源：[https://arxiv.org/abs/2005.02230](https://arxiv.org/abs/2005.02230)；年份：2020；venue：arXiv (Cornell University)；引用数：20；优先级：`P0`
- 证据摘要：Passage retrieval in a conversational context is essential for many downstream applications; it is however extremely challenging due to limited data resources. To address this problem, we present an effective multi-stage pipeline for passage ranking in conversational search that integrates a widely-used IR system with a conversational query reformulation module. Along these lines, we propose two simple yet effective query reformulation approaches: historical query expansion (HQE) and neural transfer reformulation (NTR). Whereas HQE applies query expansion, a traditional IR query reformulation technique, NTR transfers human knowledge of conver
- 主题命中：查询扩展与改写:2, 密集与对比学习检索:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/15.json`
- 对 PaSa 的帮助：针对《Query Reformulation using Query History for Passage Retrieval in Conversational Search》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 用于把自然语言科研问题编译成多个互补检索动作：原问题、方法/数据集/指标窄探针和受控同义改写。扩展词只负责提高候选覆盖，排除词必须隔离在负向惩罚或过滤通道；每个改写要保留 route_id，用 RRF 或学习融合去重，避免把一个宽泛改写的偏差放大到最终排名。
- 建议实测：围绕《Query Reformulation using Query History for Passage Retrieval in Conversational Search》设计一个 train-only ablation：将其核心信号接入 查询扩展与改写，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P047. Combining Query Reformulation and Re-ranking to Improve Query Expansion in Chinese EMR Retrieval
- 来源：[https://doi.org/10.1109/bibm52615.2021.9669713](https://doi.org/10.1109/bibm52615.2021.9669713)；年份：2021；venue：2021 IEEE International Conference on Bioinformatics and Biomedicine (BIBM)；引用数：1；优先级：`P0`
- 证据摘要：Crossref 未提供摘要；以题名、venue 和引用元数据作为可核验线索。
- 主题命中：查询扩展与改写:2, 重排与学习排序:1
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对《Combining Query Reformulation and Re-ranking to Improve Query Expansion in Chinese EMR Retrieval》：将查询扩展限制为原问题、约束化问题两个可审计视图，扩展只负责提高候选覆盖，不能直接改写最终排序；按 route_id 做去重和 paired ablation。 用于把自然语言科研问题编译成多个互补检索动作：原问题、方法/数据集/指标窄探针和受控同义改写。扩展词只负责提高候选覆盖，排除词必须隔离在负向惩罚或过滤通道；每个改写要保留 route_id，用 RRF 或学习融合去重，避免把一个宽泛改写的偏差放大到最终排名。
- 建议实测：围绕《Combining Query Reformulation and Re-ranking to Improve Query Expansion in Chinese EMR Retrieval》设计一个 train-only ablation：将其核心信号接入 查询扩展与改写，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P057. Improving Scientific Document Retrieval with Concept Coverage-based Query Set Generation
- 来源：[https://doi.org/10.1145/3701551.3703544](https://doi.org/10.1145/3701551.3703544)；年份：2025；venue：未知；引用数：2；优先级：`P0`
- 证据摘要：In specialized fields like the scientific domain, constructing large-scale human-annotated datasets poses a significant challenge due to the need for domain expertise. Recent methods have employed large language models to generate synthetic queries, which serve as proxies for actual user queries. However, they lack control over the content generated, often resulting in incomplete coverage of academic concepts in documents. We introduce Concept Coverage-based Query set Generation (CCQGen) framework, designed to generate a set of queries with comprehensive coverage of the document's concepts. A key distinction of CCQGen is that it adaptively ad
- 主题命中：查询扩展与改写:1, 学术搜索与引文推荐:1, 评测、数据集与稳健性:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/08.json`
- 对 PaSa 的帮助：针对《Improving Scientific Document Retrieval with Concept Coverage-based Query Set Generation》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 用于把自然语言科研问题编译成多个互补检索动作：原问题、方法/数据集/指标窄探针和受控同义改写。扩展词只负责提高候选覆盖，排除词必须隔离在负向惩罚或过滤通道；每个改写要保留 route_id，用 RRF 或学习融合去重，避免把一个宽泛改写的偏差放大到最终排名。
- 建议实测：围绕《Improving Scientific Document Retrieval with Concept Coverage-based Query Set Generation》设计一个 train-only ablation：将其核心信号接入 查询扩展与改写，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P067. Conversational Query Understanding Using Sequence to Sequence Modeling
- 来源：[https://doi.org/10.1145/3178876.3186083](https://doi.org/10.1145/3178876.3186083)；年份：2018；venue：未知；引用数：55；优先级：`P0`
- 证据摘要：Understanding conversations is crucial to enabling conversational search in technologies such as chatbots, digital assistants, and smart home devices that are becoming increasingly popular. Conventional search engines are powerful at answering open domain queries but are mostly capable of stateless search. In this paper, we define a conversational query as a query that depends on the context of the current conversation, and we formulate the conversational query understanding problem as context-aware query reformulation, where the goal is to reformulate the conversational query into a search engine friendly query in order to satisfy users» inf
- 主题命中：查询扩展与改写:1, 评测、数据集与稳健性:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/15.json`
- 对 PaSa 的帮助：针对《Conversational Query Understanding Using Sequence to Sequence Modeling》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 用于把自然语言科研问题编译成多个互补检索动作：原问题、方法/数据集/指标窄探针和受控同义改写。扩展词只负责提高候选覆盖，排除词必须隔离在负向惩罚或过滤通道；每个改写要保留 route_id，用 RRF 或学习融合去重，避免把一个宽泛改写的偏差放大到最终排名。
- 建议实测：围绕《Conversational Query Understanding Using Sequence to Sequence Modeling》设计一个 train-only ablation：将其核心信号接入 查询扩展与改写，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P077. Improving Retrieval-Augmented Generation in Medicine with Iterative Follow-up Questions
- 来源：[https://doi.org/10.1142/9789819807024_0015](https://doi.org/10.1142/9789819807024_0015)；年份：2024；venue：未知；引用数：55；优先级：`P0`
- 证据摘要：The emergent abilities of large language models (LLMs) have demonstrated great potential in solving medical questions. They can possess considerable medical knowledge, but may still hallucinate and are inflexible in the knowledge updates. While Retrieval-Augmented Generation (RAG) has been proposed to enhance the medical question-answering capabilities of LLMs with external knowledge bases, it may still fail in complex cases where multiple rounds of information-seeking are required. To address such an issue, we propose iterative RAG for medicine (i-MedRAG), where LLMs can iteratively ask follow-up queries based on previous information-seeking
- 主题命中：查询扩展与改写:1, RAG与长文档检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/09.json`
- 对 PaSa 的帮助：针对《Improving Retrieval-Augmented Generation in Medicine with Iterative Follow-up Questions》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 用于把自然语言科研问题编译成多个互补检索动作：原问题、方法/数据集/指标窄探针和受控同义改写。扩展词只负责提高候选覆盖，排除词必须隔离在负向惩罚或过滤通道；每个改写要保留 route_id，用 RRF 或学习融合去重，避免把一个宽泛改写的偏差放大到最终排名。
- 建议实测：围绕《Improving Retrieval-Augmented Generation in Medicine with Iterative Follow-up Questions》设计一个 train-only ablation：将其核心信号接入 查询扩展与改写，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

### 多跳检索与搜索智能体（10 篇）

#### P003. MERMAIDS: Structured Memory and Evidence Reuse for Reducing Multi-Hop Retrieval Hallucinations in Agentic RAG
- 来源：[https://doi.org/10.1109/cisce69494.2026.11504621](https://doi.org/10.1109/cisce69494.2026.11504621)；年份：2026；venue：未知；引用数：14；优先级：`P0`
- 证据摘要：Agentic Retrieval-Augmented Generation (RAG) systems have advanced the ability of large language models to handle complex, multi-step questions by dynamically planning and executing retrieval operations. However, these systems remain vulnerable to intermediate reasoning breakdowns, redundant retrieval, and evidence inconsistency, which collectively cause answer drift in multi-hop question answering. We propose MERMAIDS, a framework that augments Agentic RAG with a Structured Evidence Memory (SEM) module and a Cross-task Evidence Reuse Cache (ERC). Extracted evidence is organized into a lightweight knowledge graph following a claim-evidence-so
- 主题命中：多跳检索与搜索智能体:2, RAG与长文档检索:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《MERMAIDS: Structured Memory and Evidence Reuse for Reducing Multi-Hop Retrieval Hallucinations in Agentic RAG》：将其行动循环压缩成离线策略：状态只看通道重叠、未满足约束、rank decay 和剩余预算，每个动作都记录预期/实际严格召回增益，避免无界 API 调用。 借鉴其观察—行动—反馈循环，让 Crawler 根据候选缺口选择下一步查询、章节和引文动作。在本地 4GB GPU 约束下可先做离线 contextual policy 或规则策略，状态只使用 query features、通道重叠、rank decay、未满足约束和预算；每次行动必须记录预期增益与实际严格召回变化。
- 建议实测：围绕《MERMAIDS: Structured Memory and Evidence Reuse for Reducing Multi-Hop Retrieval Hallucinations in Agentic RAG》设计一个 train-only ablation：将其核心信号接入 多跳检索与搜索智能体，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P013. Dynamic Multi-Hop Retrieval-Augmented Generation Framework for Professional Domain Question Answering
- 来源：[https://doi.org/10.22541/au.177499050.00368942/v1](https://doi.org/10.22541/au.177499050.00368942/v1)；年份：2026；venue：未知；引用数：0；优先级：`P0`
- 证据摘要：Multi-hop question answering in high-stakes professional domains presents significant challenges, as Large Language Models (LLMs) often suffer from hallucinations and lack specific domain knowledge. Existing Retrieval-Augmented Generation (RAG) frameworks, while grounding LLM responses, often struggle with multi-hop reasoning due to static retrieval, inadequate contextual fusion, and lack of self-correction. To address these limitations, we propose Dynamic Multi-Hop RAG (DMH-RAG), built upon the LLaMA model. DMH-RAG integrates iterative query refinement with dynamic retrieval, a Contextual Belief Graph (CBG) for knowledge structuring, and a b
- 主题命中：多跳检索与搜索智能体:2, RAG与长文档检索:1
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对《Dynamic Multi-Hop Retrieval-Augmented Generation Framework for Professional Domain Question Answering》：将其行动循环压缩成离线策略：状态只看通道重叠、未满足约束、rank decay 和剩余预算，每个动作都记录预期/实际严格召回增益，避免无界 API 调用。 借鉴其观察—行动—反馈循环，让 Crawler 根据候选缺口选择下一步查询、章节和引文动作。在本地 4GB GPU 约束下可先做离线 contextual policy 或规则策略，状态只使用 query features、通道重叠、rank decay、未满足约束和预算；每次行动必须记录预期增益与实际严格召回变化。
- 建议实测：围绕《Dynamic Multi-Hop Retrieval-Augmented Generation Framework for Professional Domain Question Answering》设计一个 train-only ablation：将其核心信号接入 多跳检索与搜索智能体，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P023. End-to-End Beam Retrieval for Multi-Hop Question Answering
- 来源：[https://doi.org/10.48550/arxiv.2308.08973](https://doi.org/10.48550/arxiv.2308.08973)；年份：2023；venue：arXiv (Cornell University)；引用数：1；优先级：`P0`
- 证据摘要：Multi-hop question answering (QA) involves finding multiple relevant passages and step-by-step reasoning to answer complex questions, indicating a retrieve-and-read paradigm. However, previous retrievers were customized for two-hop questions, and most of them were trained separately across different hops, resulting in a lack of supervision over the entire multi-hop retrieval process and leading to poor performance in complicated scenarios beyond two hops. In this work, we introduce Beam Retrieval, an end-to-end beam retrieval framework for multi-hop QA. This approach models the multi-hop retrieval process in an end-to-end manner by jointly op
- 主题命中：多跳检索与搜索智能体:2
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《End-to-End Beam Retrieval for Multi-Hop Question Answering》：将其行动循环压缩成离线策略：状态只看通道重叠、未满足约束、rank decay 和剩余预算，每个动作都记录预期/实际严格召回增益，避免无界 API 调用。 借鉴其观察—行动—反馈循环，让 Crawler 根据候选缺口选择下一步查询、章节和引文动作。在本地 4GB GPU 约束下可先做离线 contextual policy 或规则策略，状态只使用 query features、通道重叠、rank decay、未满足约束和预算；每次行动必须记录预期增益与实际严格召回变化。
- 建议实测：围绕《End-to-End Beam Retrieval for Multi-Hop Question Answering》设计一个 train-only ablation：将其核心信号接入 多跳检索与搜索智能体，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P033. Budgeted Multi-Hop Retrieval Agent for Compositional Question Answering: A Retrieval-Policy Evaluation on the Official MultiHop-RAG Benchmark
- 来源：[https://doi.org/10.51903/jtie.v4i3.543](https://doi.org/10.51903/jtie.v4i3.543)；年份：2025；venue：Journal of Technology Informatics and Engineering；引用数：0；优先级：`P0`
- 证据摘要：Multi-hop question answering requires a retrieval system to assemble several complementary evidence documents before an answer module can reason reliably. Single-shot retrieval is efficient, but it often misses later-hop evidence when a question combines source, time, comparison, and entity constraints. This paper evaluates a budgeted multi-hop retrieval agent for compositional question answering on the official MultiHop-RAG benchmark. The benchmark contains 2,556 queries and 609 news-article corpus documents, with answerable evidence distributed across two to four documents. Four retrieval policies are compared under the same sparse lexical
- 主题命中：多跳检索与搜索智能体:2
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对《Budgeted Multi-Hop Retrieval Agent for Compositional Question Answering: A Retrieval-Policy Evaluation on the Official MultiHop-RAG Benchmark》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 借鉴其观察—行动—反馈循环，让 Crawler 根据候选缺口选择下一步查询、章节和引文动作。在本地 4GB GPU 约束下可先做离线 contextual policy 或规则策略，状态只使用 query features、通道重叠、rank decay、未满足约束和预算；每次行动必须记录预期增益与实际严格召回变化。
- 建议实测：围绕《Budgeted Multi-Hop Retrieval Agent for Compositional Question Answering: A Retrieval-Policy Evaluation on the Official MultiHop-RAG Benchmark》设计一个 train-only ablation：将其核心信号接入 多跳检索与搜索智能体，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P043. "Brimful of STARLITE": toward standards for reporting literature searches.
- 来源：[http://eprints.whiterose.ac.uk/124889/1/2006%20Booth%20Brimful%20of%20STARLITE.pdf](http://eprints.whiterose.ac.uk/124889/1/2006%20Booth%20Brimful%20of%20STARLITE.pdf)；年份：2006；venue：PubMed；引用数：269；优先级：`P0`
- 证据摘要：CONTEXT: Systematic reviews of qualitative research studies extend understanding of health care beyond effectiveness to acceptability and user views. OBJECTIVE: The paper surveys reports of qualitative systematic reviews and, by characterizing techniques used to identify articles for inclusion, proposes standards for reporting of literature searches. DATA SOURCES AND STUDY SELECTION: A search of MEDLINE was performed for qualitative systematic reviews published from 1988 to December 2004, supported by searches of CINAHL, Web of Knowledge (including the Science and Social Sciences Citation Index), and the Cochrane Methodology Register, and Int
- 主题命中：多跳检索与搜索智能体:1, 学术搜索与引文推荐:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/10.json`
- 对 PaSa 的帮助：针对《"Brimful of STARLITE": toward standards for reporting literature searches.》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 借鉴其观察—行动—反馈循环，让 Crawler 根据候选缺口选择下一步查询、章节和引文动作。在本地 4GB GPU 约束下可先做离线 contextual policy 或规则策略，状态只使用 query features、通道重叠、rank decay、未满足约束和预算；每次行动必须记录预期增益与实际严格召回变化。
- 建议实测：围绕《"Brimful of STARLITE": toward standards for reporting literature searches.》设计一个 train-only ablation：将其核心信号接入 多跳检索与搜索智能体，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P053. HybridQA: A Dataset of Multi-Hop Question Answering over Tabular and Textual Data
- 来源：[https://doi.org/10.18653/v1/2020.findings-emnlp.91](https://doi.org/10.18653/v1/2020.findings-emnlp.91)；年份：2020；venue：未知；引用数：199；优先级：`P0`
- 证据摘要：Existing question answering datasets focus on dealing with homogeneous information, based either only on text or KB/Table information alone. However, as human knowledge is distributed over heterogeneous forms, using homogeneous information alone might lead to severe coverage problems. To fill in the gap, we present HybridQA 1 , a new large-scale question-answering dataset that requires reasoning on heterogeneous information. Each question is aligned with a Wikipedia table and multiple free-form corpora linked with the entities in the table. The questions are designed to aggregate both tabular information and text information, i.e., lack of ei
- 主题命中：多跳检索与搜索智能体:1, 评测、数据集与稳健性:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《HybridQA: A Dataset of Multi-Hop Question Answering over Tabular and Textual Data》：将其行动循环压缩成离线策略：状态只看通道重叠、未满足约束、rank decay 和剩余预算，每个动作都记录预期/实际严格召回增益，避免无界 API 调用。 借鉴其观察—行动—反馈循环，让 Crawler 根据候选缺口选择下一步查询、章节和引文动作。在本地 4GB GPU 约束下可先做离线 contextual policy 或规则策略，状态只使用 query features、通道重叠、rank decay、未满足约束和预算；每次行动必须记录预期增益与实际严格召回变化。
- 建议实测：围绕《HybridQA: A Dataset of Multi-Hop Question Answering over Tabular and Textual Data》设计一个 train-only ablation：将其核心信号接入 多跳检索与搜索智能体，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P063. GeneGPT: augmenting large language models with domain tools for improved access to biomedical information
- 来源：[https://doi.org/10.1093/bioinformatics/btae075](https://doi.org/10.1093/bioinformatics/btae075)；年份：2024；venue：Bioinformatics；引用数：170；优先级：`P0`
- 证据摘要：MOTIVATION: While large language models (LLMs) have been successfully applied to various tasks, they still face challenges with hallucinations. Augmenting LLMs with domain-specific tools such as database utilities can facilitate easier and more precise access to specialized knowledge. In this article, we present GeneGPT, a novel method for teaching LLMs to use the Web APIs of the National Center for Biotechnology Information (NCBI) for answering genomics questions. Specifically, we prompt Codex to solve the GeneTuring tests with NCBI Web APIs by in-context learning and an augmented decoding algorithm that can detect and execute API calls. RES
- 主题命中：多跳检索与搜索智能体:1, RAG与长文档检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《GeneGPT: augmenting large language models with domain tools for improved access to biomedical information》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 借鉴其观察—行动—反馈循环，让 Crawler 根据候选缺口选择下一步查询、章节和引文动作。在本地 4GB GPU 约束下可先做离线 contextual policy 或规则策略，状态只使用 query features、通道重叠、rank decay、未满足约束和预算；每次行动必须记录预期增益与实际严格召回变化。
- 建议实测：围绕《GeneGPT: augmenting large language models with domain tools for improved access to biomedical information》设计一个 train-only ablation：将其核心信号接入 多跳检索与搜索智能体，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P073. Cross-Granularity Hypergraph Retrieval-Augmented Generation for Multi-hop Question Answering
- 来源：[https://doi.org/10.1609/aaai.v40i39.40623](https://doi.org/10.1609/aaai.v40i39.40623)；年份：2026；venue：Proceedings of the AAAI Conference on Artificial Intelligence；引用数：2；优先级：`P0`
- 证据摘要：Multi-hop question answering (MHQA) requires integrating knowledge scattered across multiple passages to derive the correct answer. Traditional retrieval-augmented generation (RAG) methods primarily focus on coarse-grained textual semantic similarity and ignore structural associations among dispersed knowledge, which limits their effectiveness in MHQA tasks. GraphRAG methods address this by leveraging knowledge graphs (KGs) to capture structural associations, but they tend to overly rely on structural information and fine-grained word- or phrase-level retrieval, resulting in an underutilization of textual semantics. In this paper, we propose
- 主题命中：多跳检索与搜索智能体:1, 图检索与知识图谱:1, RAG与长文档检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《Cross-Granularity Hypergraph Retrieval-Augmented Generation for Multi-hop Question Answering》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 借鉴其观察—行动—反馈循环，让 Crawler 根据候选缺口选择下一步查询、章节和引文动作。在本地 4GB GPU 约束下可先做离线 contextual policy 或规则策略，状态只使用 query features、通道重叠、rank decay、未满足约束和预算；每次行动必须记录预期增益与实际严格召回变化。
- 建议实测：围绕《Cross-Granularity Hypergraph Retrieval-Augmented Generation for Multi-hop Question Answering》设计一个 train-only ablation：将其核心信号接入 多跳检索与搜索智能体，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P083. Tree of Reviews: A Tree-based Dynamic Iterative Retrieval Framework for Multi-hop Question Answering
- 来源：[https://doi.org/10.48550/arxiv.2404.14464](https://doi.org/10.48550/arxiv.2404.14464)；年份：2024；venue：arXiv (Cornell University)；引用数：2；优先级：`P0`
- 证据摘要：Multi-hop question answering is a knowledge-intensive complex problem. Large Language Models (LLMs) use their Chain of Thoughts (CoT) capability to reason complex problems step by step, and retrieval-augmentation can effectively alleviate factual errors caused by outdated and unknown knowledge in LLMs. Recent works have introduced retrieval-augmentation in the CoT reasoning to solve multi-hop question answering. However, these chain methods have the following problems: 1) Retrieved irrelevant paragraphs may mislead the reasoning; 2) An error in the chain structure may lead to a cascade of errors. In this paper, we propose a dynamic retrieval
- 主题命中：多跳检索与搜索智能体:1, RAG与长文档检索:1, 评测、数据集与稳健性:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《Tree of Reviews: A Tree-based Dynamic Iterative Retrieval Framework for Multi-hop Question Answering》：将其行动循环压缩成离线策略：状态只看通道重叠、未满足约束、rank decay 和剩余预算，每个动作都记录预期/实际严格召回增益，避免无界 API 调用。 借鉴其观察—行动—反馈循环，让 Crawler 根据候选缺口选择下一步查询、章节和引文动作。在本地 4GB GPU 约束下可先做离线 contextual policy 或规则策略，状态只使用 query features、通道重叠、rank decay、未满足约束和预算；每次行动必须记录预期增益与实际严格召回变化。
- 建议实测：围绕《Tree of Reviews: A Tree-based Dynamic Iterative Retrieval Framework for Multi-hop Question Answering》设计一个 train-only ablation：将其核心信号接入 多跳检索与搜索智能体，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P093. HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering
- 来源：[https://doi.org/10.18653/v1/d18-1259](https://doi.org/10.18653/v1/d18-1259)；年份：2018；venue：未知；引用数：1740；优先级：`P0`
- 证据摘要：Zhilin Yang, Peng Qi, Saizheng Zhang, Yoshua Bengio, William Cohen, Ruslan Salakhutdinov, Christopher D. Manning. Proceedings of the 2018 Conference on Empirical Methods in Natural Language Processing. 2018
- 主题命中：多跳检索与搜索智能体:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering》：将其行动循环压缩成离线策略：状态只看通道重叠、未满足约束、rank decay 和剩余预算，每个动作都记录预期/实际严格召回增益，避免无界 API 调用。 借鉴其观察—行动—反馈循环，让 Crawler 根据候选缺口选择下一步查询、章节和引文动作。在本地 4GB GPU 约束下可先做离线 contextual policy 或规则策略，状态只使用 query features、通道重叠、rank decay、未满足约束和预算；每次行动必须记录预期增益与实际严格召回变化。
- 建议实测：围绕《HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering》设计一个 train-only ablation：将其核心信号接入 多跳检索与搜索智能体，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

### 学术搜索与引文推荐（10 篇）

#### P004. PARK: Personalized academic retrieval with knowledge-graphs
- 来源：[https://doi.org/10.1016/j.is.2025.102574](https://doi.org/10.1016/j.is.2025.102574)；年份：2025；venue：Information Systems；引用数：7；优先级：`P0`
- 证据摘要：Academic Search is a search task aimed to manage and retrieve scientific documents like journal articles and conference papers. Personalization in this context meets individual researchers’ needs by leveraging, through user profiles, the user related information (e.g. documents authored by a researcher), to improve search effectiveness and to reduce the information overload. While citation graphs are a valuable means to support the outcome of recommender systems, their use in personalized academic search (with, e.g. nodes as papers and edges as citations) is still under-explored. Existing personalized models for academic search often struggle
- 主题命中：学术搜索与引文推荐:2, 图检索与知识图谱:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/14.json`
- 对 PaSa 的帮助：针对《PARK: Personalized academic retrieval with knowledge-graphs》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 直接对应 PaSa 的论文发现任务。可迁移的重点是跨源实体对齐、作者/年份/venue 过滤、参考文献与被引关系扩展，以及论文标题和摘要的领域化表示。先用 lexical/dense 找种子，再仅对高置信种子做一跳扩展，并审计扩展带来的新增 gold 与 API 成本。
- 建议实测：围绕《PARK: Personalized academic retrieval with knowledge-graphs》设计一个 train-only ablation：将其核心信号接入 学术搜索与引文推荐，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P014. Scientific paper recommendation systems: a literature review of recent publications
- 来源：[https://doi.org/10.1007/s00799-022-00339-w](https://doi.org/10.1007/s00799-022-00339-w)；年份：2022；venue：International Journal on Digital Libraries；引用数：63；优先级：`P0`
- 证据摘要：Abstract Scientific writing builds upon already published papers. Manual identification of publications to read, cite or consider as related papers relies on a researcher’s ability to identify fitting keywords or initial papers from which a literature search can be started. The rapidly increasing amount of papers has called for automatic measures to find the desired relevant publications, so-called paper recommendation systems. As the number of publications increases so does the amount of paper recommendation systems. Former literature reviews focused on discussing the general landscape of approaches throughout the years and highlight the mai
- 主题命中：学术搜索与引文推荐:2, 评测、数据集与稳健性:1
- 原始响应：`openalex/06.json`
- 对 PaSa 的帮助：针对《Scientific paper recommendation systems: a literature review of recent publications》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 直接对应 PaSa 的论文发现任务。可迁移的重点是跨源实体对齐、作者/年份/venue 过滤、参考文献与被引关系扩展，以及论文标题和摘要的领域化表示。先用 lexical/dense 找种子，再仅对高置信种子做一跳扩展，并审计扩展带来的新增 gold 与 API 成本。
- 建议实测：围绕《Scientific paper recommendation systems: a literature review of recent publications》设计一个 train-only ablation：将其核心信号接入 学术搜索与引文推荐，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P024. A Context-Aware Citation Recommendation Model with BERT and Graph Convolutional Networks
- 来源：[https://doi.org/10.48550/arxiv.1903.06464](https://doi.org/10.48550/arxiv.1903.06464)；年份：2019；venue：arXiv (Cornell University)；引用数：29；优先级：`P0`
- 证据摘要：With the tremendous growth in the number of scientific papers being published, searching for references while writing a scientific paper is a time-consuming process. A technique that could add a reference citation at the appropriate place in a sentence will be beneficial. In this perspective, context-aware citation recommendation has been researched upon for around two decades. Many researchers have utilized the text data called the context sentence, which surrounds the citation tag, and the metadata of the target paper to find the appropriate cited research. However, the lack of well-organized benchmarking datasets and no model that can atta
- 主题命中：学术搜索与引文推荐:2, 评测、数据集与稳健性:1
- 原始响应：`openalex/06.json`
- 对 PaSa 的帮助：针对《A Context-Aware Citation Recommendation Model with BERT and Graph Convolutional Networks》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 直接对应 PaSa 的论文发现任务。可迁移的重点是跨源实体对齐、作者/年份/venue 过滤、参考文献与被引关系扩展，以及论文标题和摘要的领域化表示。先用 lexical/dense 找种子，再仅对高置信种子做一跳扩展，并审计扩展带来的新增 gold 与 API 成本。
- 建议实测：围绕《A Context-Aware Citation Recommendation Model with BERT and Graph Convolutional Networks》设计一个 train-only ablation：将其核心信号接入 学术搜索与引文推荐，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P034. Global citation recommendation using knowledge graphs
- 来源：[https://doi.org/10.3233/jifs-169493](https://doi.org/10.3233/jifs-169493)；年份：2018；venue：Journal of Intelligent & Fuzzy Systems；引用数：28；优先级：`P0`
- 证据摘要：Scholarly search engines, reference management tools, and academic social networks enable modern researchers to organize their scientific libraries. Moreover, they often provide recommendations for scientific publications that might be of interest to researchers. Because of the exponentially increasing volume of publications, effective citation recommendation is of great importance to researchers, as it reduces the time and effort spent on retrieving, understanding, and selecting research papers. In this context, we address the problem of citation recommendation , i.e., the task of recommending citations for a new paper. Current research inve
- 主题命中：学术搜索与引文推荐:2, 重排与学习排序:1
- 原始响应：`openalex/06.json`
- 对 PaSa 的帮助：针对《Global citation recommendation using knowledge graphs》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 直接对应 PaSa 的论文发现任务。可迁移的重点是跨源实体对齐、作者/年份/venue 过滤、参考文献与被引关系扩展，以及论文标题和摘要的领域化表示。先用 lexical/dense 找种子，再仅对高置信种子做一跳扩展，并审计扩展带来的新增 gold 与 API 成本。
- 建议实测：围绕《Global citation recommendation using knowledge graphs》设计一个 train-only ablation：将其核心信号接入 学术搜索与引文推荐，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P044. "Towards higher relevance and serendipity in scholarly paper recommendation" by Kazunari Sugiyama and Min-Yen Kan with Martin Vesely as coordinator
- 来源：[https://doi.org/10.1145/2719943.2719947](https://doi.org/10.1145/2719943.2719947)；年份：2015；venue：ACM SIGWEB Newsletter；引用数：19；优先级：`P0`
- 证据摘要：Finding relevant scholarly papers is an important task for researchers. Such a literature search involves identifying drawbacks in existing works and proposing new approaches that address them. However, the growing number of scientific published papers results in information overload even for simple searches, such that researchers have difficulty in finding papers relevant to their interests. Recommendation systems can help address this problem to find relevant papers efficiently. In this article, we summarize our work on scholarly paper recommendation from both relevance and serendipitous perspectives. Experimental results on a publicly-avai
- 主题命中：学术搜索与引文推荐:2, 评测、数据集与稳健性:1
- 原始响应：`openalex/16.json`
- 对 PaSa 的帮助：针对《"Towards higher relevance and serendipity in scholarly paper recommendation" by Kazunari Sugiyama and Min-Yen Kan with Martin Vesely as coordinator》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 直接对应 PaSa 的论文发现任务。可迁移的重点是跨源实体对齐、作者/年份/venue 过滤、参考文献与被引关系扩展，以及论文标题和摘要的领域化表示。先用 lexical/dense 找种子，再仅对高置信种子做一跳扩展，并审计扩展带来的新增 gold 与 API 成本。
- 建议实测：围绕《"Towards higher relevance and serendipity in scholarly paper recommendation" by Kazunari Sugiyama and Min-Yen Kan with Martin Vesely as coordinator》设计一个 train-only ablation：将其核心信号接入 学术搜索与引文推荐，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P054. Citation recommendation without author supervision
- 来源：[https://doi.org/10.1145/1935826.1935926](https://doi.org/10.1145/1935826.1935926)；年份：2011；venue：未知；引用数：123；优先级：`P0`
- 证据摘要：Automatic recommendation of citations for a manuscript is highly valuable for scholarly activities since it can substantially improve the efficiency and quality of literature search. The prior techniques placed a considerable burden on users, who were required to provide a representative bibliography or to mark passages where citations are needed. In this paper we present a system that considerably reduces this burden: a user simply inputs a query manuscript (without a bibliography) and our system automatically finds locations where citations are needed. We show that naïve approaches do not work well due to massive noise in the document corpu
- 主题命中：学术搜索与引文推荐:2
- 原始响应：`openalex/16.json`
- 对 PaSa 的帮助：针对《Citation recommendation without author supervision》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 直接对应 PaSa 的论文发现任务。可迁移的重点是跨源实体对齐、作者/年份/venue 过滤、参考文献与被引关系扩展，以及论文标题和摘要的领域化表示。先用 lexical/dense 找种子，再仅对高置信种子做一跳扩展，并审计扩展带来的新增 gold 与 API 成本。
- 建议实测：围绕《Citation recommendation without author supervision》设计一个 train-only ablation：将其核心信号接入 学术搜索与引文推荐，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P064. unarXive: a large scholarly data set with publications’ full-text, annotated in-text citations, and links to metadata
- 来源：[https://doi.org/10.1007/s11192-020-03382-z](https://doi.org/10.1007/s11192-020-03382-z)；年份：2020；venue：Scientometrics；引用数：40；优先级：`P0`
- 证据摘要：Abstract In recent years, scholarly data sets have been used for various purposes, such as paper recommendation, citation recommendation, citation context analysis, and citation context-based document summarization. The evaluation of approaches to such tasks and their applicability in real-world scenarios heavily depend on the used data set. However, existing scholarly data sets are limited in several regards. In this paper, we propose a new data set based on all publications from all scientific disciplines available on arXiv.org. Apart from providing the papers’ plain text, in-text citations were annotated via global identifiers. Furthermore
- 主题命中：学术搜索与引文推荐:2
- 原始响应：`openalex/06.json`
- 对 PaSa 的帮助：针对《unarXive: a large scholarly data set with publications’ full-text, annotated in-text citations, and links to metadata》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 直接对应 PaSa 的论文发现任务。可迁移的重点是跨源实体对齐、作者/年份/venue 过滤、参考文献与被引关系扩展，以及论文标题和摘要的领域化表示。先用 lexical/dense 找种子，再仅对高置信种子做一跳扩展，并审计扩展带来的新增 gold 与 API 成本。
- 建议实测：围绕《unarXive: a large scholarly data set with publications’ full-text, annotated in-text citations, and links to metadata》设计一个 train-only ablation：将其核心信号接入 学术搜索与引文推荐，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P074. Keywords-Driven and Popularity-Aware Paper Recommendation Based on Undirected Paper Citation Graph
- 来源：[https://doi.org/10.1155/2020/2085638](https://doi.org/10.1155/2020/2085638)；年份：2020；venue：Complexity；引用数：77；优先级：`P0`
- 证据摘要：Nowadays, scholar recommender systems often recommend academic papers based on users’ personalized retrieval demands. Typically, a recommender system analyzes the keywords typed by a user and then returns his or her preferred papers, in an efficient and economic manner. In practice, one paper often contains partial keywords that a user is interested in. Therefore, the recommender system needs to return the user a set of papers that collectively covers all the queried keywords. However, existing recommender systems only use the exact keyword matching technique for recommendation decisions, while neglecting the correlation relationships among d
- 主题命中：学术搜索与引文推荐:1, 图检索与知识图谱:1, 评测、数据集与稳健性:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/06.json`
- 对 PaSa 的帮助：针对《Keywords-Driven and Popularity-Aware Paper Recommendation Based on Undirected Paper Citation Graph》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 直接对应 PaSa 的论文发现任务。可迁移的重点是跨源实体对齐、作者/年份/venue 过滤、参考文献与被引关系扩展，以及论文标题和摘要的领域化表示。先用 lexical/dense 找种子，再仅对高置信种子做一跳扩展，并审计扩展带来的新增 gold 与 API 成本。
- 建议实测：围绕《Keywords-Driven and Popularity-Aware Paper Recommendation Based on Undirected Paper Citation Graph》设计一个 train-only ablation：将其核心信号接入 学术搜索与引文推荐，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P084. DiSCern: A diversified citation recommendation system for scientific queries
- 来源：[https://doi.org/10.1109/icde.2015.7113314](https://doi.org/10.1109/icde.2015.7113314)；年份：2015；venue：未知；引用数：40；优先级：`P0`
- 证据摘要：Performing literature survey for scholarly activities has become a challenging and time consuming task due to the rapid growth in the number of scientific articles. Thus, automatic recommendation of high quality citations for a given scientific query topic is immensely valuable. The state-of-the-art on the problem of citation recommendation suffers with the following three limitations. First, most of the existing approaches for citation recommendation require input in the form of either the full article or a seed set of citations, or both. Nevertheless, obtaining the recommendation for citations given a set of keywords is extremely useful for
- 主题命中：学术搜索与引文推荐:1, 图检索与知识图谱:1, 评测、数据集与稳健性:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/06.json`
- 对 PaSa 的帮助：针对《DiSCern: A diversified citation recommendation system for scientific queries》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 直接对应 PaSa 的论文发现任务。可迁移的重点是跨源实体对齐、作者/年份/venue 过滤、参考文献与被引关系扩展，以及论文标题和摘要的领域化表示。先用 lexical/dense 找种子，再仅对高置信种子做一跳扩展，并审计扩展带来的新增 gold 与 API 成本。
- 建议实测：围绕《DiSCern: A diversified citation recommendation system for scientific queries》设计一个 train-only ablation：将其核心信号接入 学术搜索与引文推荐，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P094. DisenCite: Graph-Based Disentangled Representation Learning for Context-Specific Citation Generation
- 来源：[https://doi.org/10.1609/aaai.v36i10.21397](https://doi.org/10.1609/aaai.v36i10.21397)；年份：2022；venue：Proceedings of the AAAI Conference on Artificial Intelligence；引用数：32；优先级：`P0`
- 证据摘要：Citing and describing related literature are crucial to scientific writing. Many existing approaches show encouraging performance in citation recommendation, but are unable to accomplish the more challenging and onerous task of citation text generation. In this paper, we propose a novel disentangled representation based model DisenCite to automatically generate the citation text through integrating paper text and citation graph. A key novelty of our method compared with existing approaches is to generate context-specific citation text, empowering the generation of different types of citations for the same paper. In particular, we first build
- 主题命中：学术搜索与引文推荐:1, 图检索与知识图谱:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/06.json`
- 对 PaSa 的帮助：针对《DisenCite: Graph-Based Disentangled Representation Learning for Context-Specific Citation Generation》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 直接对应 PaSa 的论文发现任务。可迁移的重点是跨源实体对齐、作者/年份/venue 过滤、参考文献与被引关系扩展，以及论文标题和摘要的领域化表示。先用 lexical/dense 找种子，再仅对高置信种子做一跳扩展，并审计扩展带来的新增 gold 与 API 成本。
- 建议实测：围绕《DisenCite: Graph-Based Disentangled Representation Learning for Context-Specific Citation Generation》设计一个 train-only ablation：将其核心信号接入 学术搜索与引文推荐，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

### 图检索与知识图谱（12 篇）

#### P002. CG-RAG: Research Question Answering by Citation Graph Retrieval-Augmented LLMs
- 来源：[https://doi.org/10.1145/3726302.3729920](https://doi.org/10.1145/3726302.3729920)；年份：2025；venue：未知；引用数：8；优先级：`P1`
- 证据摘要：Research question answering requires accurate retrieval and contextual understanding of scientific literature. However, current Retrieval-Augmented Generation (RAG) methods often struggle to balance complex document relationships with precise information retrieval. In this paper, we introduce Contextualized Graph Retrieval-Augmented Generation (CG-RAG), a novel framework that integrates sparse and dense retrieval signals within graph structures to enhance retrieval efficiency and subsequently improve generation quality for research question answering. First, we propose a contextual graph representation for citation graphs, effectively capturi
- 主题命中：图检索与知识图谱:2, 检索基础与稀疏召回:1, 密集与对比学习检索:1, RAG与长文档检索:1
- 原始响应：`openalex/13.json`
- 对 PaSa 的帮助：针对《CG-RAG: Research Question Answering by Citation Graph Retrieval-Augmented LLMs》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《CG-RAG: Research Question Answering by Citation Graph Retrieval-Augmented LLMs》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P012. TCM MLKG-RAG: Traditional Chinese Medicine Intelligent Diagnosis Based on Multi-Layer Knowledge Graph Retrieval-Augmented Generation
- 来源：[https://doi.org/10.1109/eiecc64539.2024.10929529](https://doi.org/10.1109/eiecc64539.2024.10929529)；年份：2024；venue：未知；引用数：2；优先级：`P1`
- 证据摘要：Traditional Chinese Medicine (TCM) search engines often struggle with the issue of redundant data volumes, making it difficult to meet users' demands for precise information retrieval. Large Language Models (LLMs) excel in understanding questions and summarizing key points due to their vast number of parameters. However, keeping pace with updates in TCM knowledge requires significant computational resources and time for finetuning these large models. Retrieval-augmented generation (RAG) allows LLMs to generate more accurate, specialized, and timely responses without the need to update their parameters. TCM knowledge is characterized by its di
- 主题命中：图检索与知识图谱:2, 检索基础与稀疏召回:1, RAG与长文档检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/14.json`
- 对 PaSa 的帮助：针对《TCM MLKG-RAG: Traditional Chinese Medicine Intelligent Diagnosis Based on Multi-Layer Knowledge Graph Retrieval-Augmented Generation》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《TCM MLKG-RAG: Traditional Chinese Medicine Intelligent Diagnosis Based on Multi-Layer Knowledge Graph Retrieval-Augmented Generation》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P022. GRAG: Graph Retrieval-Augmented Generation
- 来源：[https://doi.org/10.18653/v1/2025.findings-naacl.232](https://doi.org/10.18653/v1/2025.findings-naacl.232)；年份：2025；venue：未知；引用数：67；优先级：`P1`
- 证据摘要：Naive Retrieval-Augmented Generation (RAG) focuses on individual documents during retrieval and, as a result, falls short in handling networked documents which are very popular in many applications such as citation graphs, social media, and knowledge graphs.To overcome this limitation, we introduce Graph Retrieval-Augmented Generation (GRAG), which tackles the fundamental challenges in retrieving textual subgraphs and integrating the joint textual and topological information into Large Language Models (LLMs) to enhance its generation.To enable efficient textual subgraph retrieval, we propose a novel divide-and-conquer strategy that retrieves
- 主题命中：图检索与知识图谱:2, RAG与长文档检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/09.json`
- 对 PaSa 的帮助：针对《GRAG: Graph Retrieval-Augmented Generation》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《GRAG: Graph Retrieval-Augmented Generation》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P032. Enhancing Question-Answering with Knowledge Graph Retrieval and Generation using LLMs
- 来源：[https://doi.org/10.1109/icaiqsa64000.2024.10882212](https://doi.org/10.1109/icaiqsa64000.2024.10882212)；年份：2024；venue：未知；引用数：6；优先级：`P1`
- 证据摘要：This paper describes a novel technique to improving Large Language Models (LLMs) for document analysis that employs knowledge graphs and retrieval-augmented generation (RAG). We are working on constructing a chatbot system that can handle and analyze large documents from a variety of fields. Our approach addresses basic LLM issues including context maintenance and hallucination avoidance. The system combines document chunking, vector embedding, and similarity search with graph-based knowledge representation. Users can upload large papers and answer questions accurately. We show that integrating standard information retrieval approaches with g
- 主题命中：图检索与知识图谱:2, 检索基础与稀疏召回:1, RAG与长文档检索:1
- 原始响应：`openalex/14.json`
- 对 PaSa 的帮助：针对《Enhancing Question-Answering with Knowledge Graph Retrieval and Generation using LLMs》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《Enhancing Question-Answering with Knowledge Graph Retrieval and Generation using LLMs》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P042. Knowledge Graph Retrieval-Augmented Generation for LLM-based Recommendation
- 来源：[https://doi.org/10.48550/arxiv.2501.02226](https://doi.org/10.48550/arxiv.2501.02226)；年份：2025；venue：arXiv (Cornell University)；引用数：1；优先级：`P1`
- 证据摘要：Recommender systems have become increasingly vital in our daily lives, helping to alleviate the problem of information overload across various user-oriented online services. The emergence of Large Language Models (LLMs) has yielded remarkable achievements, demonstrating their potential for the development of next-generation recommender systems. Despite these advancements, LLM-based recommender systems face inherent limitations stemming from their LLM backbones, particularly issues of hallucinations and the lack of up-to-date and domain-specific knowledge. Recently, Retrieval-Augmented Generation (RAG) has garnered significant attention for ad
- 主题命中：图检索与知识图谱:2, RAG与长文档检索:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/14.json`
- 对 PaSa 的帮助：针对《Knowledge Graph Retrieval-Augmented Generation for LLM-based Recommendation》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《Knowledge Graph Retrieval-Augmented Generation for LLM-based Recommendation》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P052. TagRAG: Tag-guided Hierarchical Knowledge Graph Retrieval-Augmented Generation
- 来源：[https://doi.org/10.18653/v1/2026.findings-acl.321](https://doi.org/10.18653/v1/2026.findings-acl.321)；年份：2026；venue：未知；引用数：1；优先级：`P1`
- 证据摘要：Retrieval-Augmented Generation enhances language models by retrieving external knowledge to support informed and grounded responses.However, traditional RAG methods rely on fragment-level retrieval, limiting their ability to address query-focused summarization queries.GraphRAG introduces a graphbased paradigm for global knowledge reasoning, yet suffers from inefficiencies in information extraction, costly resource consumption, and poor adaptability to incremental updates.To overcome these limitations, we propose TagRAG, a tag-guided hierarchical knowledge graph RAG framework designed for efficient global reasoning and scalable graph maintenan
- 主题命中：图检索与知识图谱:2, RAG与长文档检索:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/14.json`
- 对 PaSa 的帮助：针对《TagRAG: Tag-guided Hierarchical Knowledge Graph Retrieval-Augmented Generation》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《TagRAG: Tag-guided Hierarchical Knowledge Graph Retrieval-Augmented Generation》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P062. GNN-RAG: Graph Neural Retrieval for Efficient Large Language Model Reasoning on Knowledge Graphs
- 来源：[https://doi.org/10.18653/v1/2025.findings-acl.856](https://doi.org/10.18653/v1/2025.findings-acl.856)；年份：2025；venue：未知；引用数：59；优先级：`P1`
- 证据摘要：Retrieval-augmented generation (RAG) in Knowledge Graph Question Answering (KGQA) enhances the context of Large Language Models (LLMs) by incorporating information retrieved from the Knowledge Graph (KG).Most recent approaches rely on costly LLM calls to generate executable relation paths or traverse the KG, which is inefficient in complex KGQA tasks, such as those involving multi-hop or multi-entity questions.We introduce the GNN-RAG framework, which utilizes lightweight Graph Neural Networks (GNNs) for effective and efficient graph retrieval.The GNN learns to assign importance weights to nodes based on their relevance to the question, as we
- 主题命中：图检索与知识图谱:2, RAG与长文档检索:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《GNN-RAG: Graph Neural Retrieval for Efficient Large Language Model Reasoning on Knowledge Graphs》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《GNN-RAG: Graph Neural Retrieval for Efficient Large Language Model Reasoning on Knowledge Graphs》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P072. Predict then Propagate: Graph Neural Networks meet Personalized PageRank
- 来源：[https://doi.org/10.48550/arxiv.1810.05997](https://doi.org/10.48550/arxiv.1810.05997)；年份：2018；venue：arXiv (Cornell University)；引用数：435；优先级：`P1`
- 证据摘要：Neural message passing algorithms for semi-supervised classification on graphs have recently achieved great success. However, for classifying a node these methods only consider nodes that are a few propagation steps away and the size of this utilized neighborhood is hard to extend. In this paper, we use the relationship between graph convolutional networks (GCN) and PageRank to derive an improved propagation scheme based on personalized PageRank. We utilize this propagation procedure to construct a simple model, personalized propagation of neural predictions (PPNP), and its fast approximation, APPNP. Our model's training time is on par or fas
- 主题命中：图检索与知识图谱:2
- 原始响应：`openalex/02.json`
- 对 PaSa 的帮助：针对《Predict then Propagate: Graph Neural Networks meet Personalized PageRank》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《Predict then Propagate: Graph Neural Networks meet Personalized PageRank》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P082. ChatASD: A Dialogue Framework for LLMs Enhanced by Autism Knowledge Graph Retrieval
- 来源：[https://doi.org/10.1145/3698587.3701538](https://doi.org/10.1145/3698587.3701538)；年份：2024；venue：未知；引用数：5；优先级：`P1`
- 证据摘要：Autism Spectrum Disorder (ASD) is a neurodevelopmental disorder characterized by developmental delays, communication difficulties, repetitive behaviors, and restricted interests. Large Language Models (LLMs) have demonstrated exceptional capabilities in various natural language tasks, particularly in providing personalized question-and-answer(Q&A) services, making them well-suited for constructing dialogue engines for autism Q&A systems. However, general LLMs often lack integrated autism knowledge during training, limiting their professional competency in autism consultation. Additionally, the automatic evaluation of scientific accuracy in au
- 主题命中：图检索与知识图谱:2, RAG与长文档检索:1
- 原始响应：`openalex/14.json`
- 对 PaSa 的帮助：针对《ChatASD: A Dialogue Framework for LLMs Enhanced by Autism Knowledge Graph Retrieval》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《ChatASD: A Dialogue Framework for LLMs Enhanced by Autism Knowledge Graph Retrieval》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P092. DEMENTIA-PLAN: An Agent-Based Framework for Multi-Knowledge Graph Retrieval-Augmented Generation in Dementia Care
- 来源：[https://doi.org/10.48550/arxiv.2503.20950](https://doi.org/10.48550/arxiv.2503.20950)；年份：2025；venue：arXiv (Cornell University)；引用数：4；优先级：`P1`
- 证据摘要：Mild-stage dementia patients primarily experience two critical symptoms: severe memory loss and emotional instability. To address these challenges, we propose DEMENTIA-PLAN, an innovative retrieval-augmented generation framework that leverages large language models to enhance conversational support. Our model employs a multiple knowledge graph architecture, integrating various dimensional knowledge representations including daily routine graphs and life memory graphs. Through this multi-graph architecture, DEMENTIA-PLAN comprehensively addresses both immediate care needs and facilitates deeper emotional resonance through personal memories, he
- 主题命中：图检索与知识图谱:2, RAG与长文档检索:1
- 原始响应：`openalex/14.json`
- 对 PaSa 的帮助：针对《DEMENTIA-PLAN: An Agent-Based Framework for Multi-Knowledge Graph Retrieval-Augmented Generation in Dementia Care》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《DEMENTIA-PLAN: An Agent-Based Framework for Multi-Knowledge Graph Retrieval-Augmented Generation in Dementia Care》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P102. Design of Knowledge Graph Retrieval System for Legal and Regulatory Framework of Multilevel Latent Semantic Indexing
- 来源：[https://doi.org/10.1155/2022/6781043](https://doi.org/10.1155/2022/6781043)；年份：2022；venue：Computational Intelligence and Neuroscience；引用数：8；优先级：`P1`
- 证据摘要：Latent semantic analysis (LSA) is a natural language statistical model, which is considered as a method to acquire, generalize, and represent knowledge. Compared with other retrieval models based on concept dictionaries or concept networks, the retrieval model based on LSA has the advantages of strong computability and less human participation. LSA establishes a latent semantic space through truncated singular value decomposition. Words and documents in the latent semantic space are projected onto the dimension representing the latent concept, and then the semantic relationship between words can be extracted to present the semantic structure
- 主题命中：图检索与知识图谱:2
- 原始响应：`openalex/14.json`
- 对 PaSa 的帮助：针对《Design of Knowledge Graph Retrieval System for Legal and Regulatory Framework of Multilevel Latent Semantic Indexing》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《Design of Knowledge Graph Retrieval System for Legal and Regulatory Framework of Multilevel Latent Semantic Indexing》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P112. EWEK-QA : Enhanced Web and Efficient Knowledge Graph Retrieval for Citation-based Question Answering Systems
- 来源：[https://doi.org/10.18653/v1/2024.acl-long.764](https://doi.org/10.18653/v1/2024.acl-long.764)；年份：2024；venue：未知；引用数：8；优先级：`P1`
- 证据摘要：Mohammad Dehghan, Mohammad Alomrani, Sunyam Bagga, David Alfonso-Hermelo, Khalil Bibi, Abbas Ghaddar, Yingxue Zhang, Xiaoguang Li, Jianye Hao, Qun Liu, Jimmy Lin, Boxing Chen, Prasanna Parthasarathi, Mahdi Biparva, Mehdi Rezagholizadeh. Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers). 2024
- 主题命中：图检索与知识图谱:2
- 原始响应：`openalex/14.json`
- 对 PaSa 的帮助：针对《EWEK-QA : Enhanced Web and Efficient Knowledge Graph Retrieval for Citation-based Question Answering Systems》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 用于把论文间引用、共享参考文献、共享被引和实体关系变成额外排序证据。图分数应作为候选内 feature 或低权重传播项，不应覆盖直接 query relevance；对 locate/方法名查询要关闭无关图扩展，并做有无图通道的 paired ablation。
- 建议实测：围绕《EWEK-QA : Enhanced Web and Efficient Knowledge Graph Retrieval for Citation-based Question Answering Systems》设计一个 train-only ablation：将其核心信号接入 图检索与知识图谱，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

### RAG与长文档检索（13 篇）

#### P001. Retrieval-Augmented Generation and Knowledge-Grounded Large Language Models
- 来源：[https://doi.org/10.2139/ssrn.7357178](https://doi.org/10.2139/ssrn.7357178)；年份：2026；venue：未知；引用数：0；优先级：`P1`
- 证据摘要：AI capabilities of knowledge-intensive systems like question answering, scientific research, decision support, education and enterprise information systems have greatly benefited from the rapid development of large language models (LLMs). However, traditional parametric language models have several drawbacks, such as a lack of up-to-date information, completeness, verifiability and the ability to generate hallucinations. To overcome these drawbacks, we introduced a novel approach combining information retrieval with generative language models called Retrieval-Augmented Generation (RAG).To overcome these drawbacks, we proposed a novel approach
- 主题命中：RAG与长文档检索:4, 密集与对比学习检索:2, 检索基础与稀疏召回:1
- 原始响应：`09.json`
- 对 PaSa 的帮助：针对《Retrieval-Augmented Generation and Knowledge-Grounded Large Language Models》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《Retrieval-Augmented Generation and Knowledge-Grounded Large Language Models》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P011. W-RAG: Weakly Supervised Dense Retrieval in RAG for Open-domain Question Answering
- 来源：[https://doi.org/10.1145/3731120.3744578](https://doi.org/10.1145/3731120.3744578)；年份：2025；venue：未知；引用数：8；优先级：`P1`
- 证据摘要：In knowledge-intensive tasks such as open-domain question answering (OpenQA), large language models (LLMs) often struggle to generate factual answers, relying solely on their internal (parametric) knowledge. To address this limitation, Retrieval-Augmented Generation (RAG) systems enhance LLMs by retrieving relevant information from external sources, thereby positioning the retriever as a pivotal component. Although dense retrieval demonstrates state-of-the-art performance, its training poses challenges due to the scarcity of ground-truth evidence, largely attributed to the high costs of human annotation. In this paper, we propose W-RAG, a met
- 主题命中：RAG与长文档检索:3, 检索基础与稀疏召回:1, 密集与对比学习检索:1, 重排与学习排序:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/17.json`
- 对 PaSa 的帮助：针对《W-RAG: Weakly Supervised Dense Retrieval in RAG for Open-domain Question Answering》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《W-RAG: Weakly Supervised Dense Retrieval in RAG for Open-domain Question Answering》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P021. Optimizing open-domain question answering with graph-based retrieval augmented generation
- 来源：[https://doi.org/10.1145/3737412.3743489](https://doi.org/10.1145/3737412.3743489)；年份：2025；venue：未知；引用数：3；优先级：`P1`
- 证据摘要：In this work, we benchmark various graph-based retrieval-augmented generation (RAG) systems across a broad spectrum of query types, including OLTP-style (fact-based) and OLAP-style (thematic) queries, to address the complex demands of open-domain question answering (QA).Traditional RAG methods often fall short in handling nuanced, multi-document synthesis tasks.By structuring knowledge as graphs, we can facilitate the retrieval of context that captures greater semantic depth and enhances language model operations.We explore graph-based RAG methodologies and introduce TREX, a novel, cost-effective alternative that combines graph-based indexing
- 主题命中：RAG与长文档检索:3, 评测、数据集与稳健性:1
- 原始响应：`openalex/17.json`
- 对 PaSa 的帮助：针对《Optimizing open-domain question answering with graph-based retrieval augmented generation》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《Optimizing open-domain question answering with graph-based retrieval augmented generation》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P031. Bridging dual knowledge graphs for multi-hop question answering in construction safety
- 来源：[https://doi.org/10.1016/j.autcon.2026.106794](https://doi.org/10.1016/j.autcon.2026.106794)；年份：2026；venue：Automation in Construction；引用数：9；优先级：`P1`
- 证据摘要：Information retrieval and question answering from safety regulations are essential for automated construction compliance checking but are hindered by the linguistic and structural complexity of regulatory text. Many queries are multi-hop, requiring synthesis across interlinked clauses. To address the challenge, this paper introduces BifrostRAG, a dual-graph retrieval-augmented generation (RAG) system that models both linguistic relationships and document structure. The proposed architecture supports a hybrid retrieval mechanism that combines graph traversal with vector-based semantic search, enabling large language models to reason over both
- 主题命中：RAG与长文档检索:2, 检索基础与稀疏召回:1, 多跳检索与搜索智能体:1, 图检索与知识图谱:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《Bridging dual knowledge graphs for multi-hop question answering in construction safety》：仅在 lexical+dense 已命中的种子上做一跳图扩展，图分数作为 tie-break 或小权重，不允许覆盖直接 query relevance；按查询类型分层评估。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《Bridging dual knowledge graphs for multi-hop question answering in construction safety》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P041. TreeQA: Enhanced LLM-RAG with logic tree reasoning for reliable and interpretable multi-hop question answering
- 来源：[https://doi.org/10.1016/j.knosys.2025.114526](https://doi.org/10.1016/j.knosys.2025.114526)；年份：2025；venue：Knowledge-Based Systems；引用数：10；优先级：`P1`
- 证据摘要：Multi-Hop Question Answering (MHQA), crucial for complex information retrieval, remains challenging for current Large Language Models (LLMs) and Retrieval-Augmented Generation (RAG) systems, which often suffer from hallucination, reliance on incomplete knowledge, and opaque reasoning processes. Existing RAG methods, while beneficial, still struggle with the intricacies of multi-step inference and ensuring verifiable accuracy. This research introduces TreeQA, a novel framework designed to significantly enhance the reliability and interpretability of LLM-RAG systems in MHQA tasks. TreeQA addresses these limitations by decomposing complex multi-
- 主题命中：RAG与长文档检索:2, 检索基础与稀疏召回:1, 多跳检索与搜索智能体:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/11.json`
- 对 PaSa 的帮助：针对《TreeQA: Enhanced LLM-RAG with logic tree reasoning for reliable and interpretable multi-hop question answering》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《TreeQA: Enhanced LLM-RAG with logic tree reasoning for reliable and interpretable multi-hop question answering》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P051. Autoregressive Entity Retrieval
- 来源：[https://doi.org/10.48550/arxiv.2010.00904](https://doi.org/10.48550/arxiv.2010.00904)；年份：2020；venue：arXiv (Cornell University)；引用数：200；优先级：`P1`
- 证据摘要：Entities are at the center of how we represent and aggregate knowledge. For instance, Encyclopedias such as Wikipedia are structured by entities (e.g., one per Wikipedia article). The ability to retrieve such entities given a query is fundamental for knowledge-intensive tasks such as entity linking and open-domain question answering. Current approaches can be understood as classifiers among atomic labels, one for each entity. Their weight vectors are dense entity representations produced by encoding entity meta information such as their descriptions. This approach has several shortcomings: (i) context and entity affinity is mainly captured th
- 主题命中：RAG与长文档检索:2, 图检索与知识图谱:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/17.json`
- 对 PaSa 的帮助：针对《Autoregressive Entity Retrieval》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《Autoregressive Entity Retrieval》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P061. Document GraphRAG: Knowledge Graph Enhanced Retrieval Augmented Generation for Document Question Answering Within the Manufacturing Domain
- 来源：[https://doi.org/10.3390/electronics14112102](https://doi.org/10.3390/electronics14112102)；年份：2025；venue：Electronics；引用数：43；优先级：`P1`
- 证据摘要：Retrieval-Augmented Generation (RAG) systems have shown significant potential for domain-specific Question Answering (QA) tasks, although persistent challenges in retrieval precision and context selection continue to hinder their effectiveness. This study introduces Document Graph RAG (GraphRAG), a novel framework that bolsters retrieval robustness and enhances answer generation by incorporating Knowledge Graphs (KGs) built upon a document’s intrinsic structure into the RAG pipeline. Through the application of the Design Science Research methodology, we systematically design, implement, and evaluate GraphRAG, leveraging graph-based document s
- 主题命中：RAG与长文档检索:2, 多跳检索与搜索智能体:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/09.json`
- 对 PaSa 的帮助：针对《Document GraphRAG: Knowledge Graph Enhanced Retrieval Augmented Generation for Document Question Answering Within the Manufacturing Domain》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《Document GraphRAG: Knowledge Graph Enhanced Retrieval Augmented Generation for Document Question Answering Within the Manufacturing Domain》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P071. A Systematic Literature Review of Retrieval-Augmented Generation: Techniques, Metrics, and Challenges
- 来源：[https://doi.org/10.3390/bdcc9120320](https://doi.org/10.3390/bdcc9120320)；年份：2025；venue：Big Data and Cognitive Computing；引用数：36；优先级：`P1`
- 证据摘要：Background: Retrieval-augmented generation (RAG) aims to reduce hallucinations and outdated knowledge by grounding LLM outputs in retrieved evidence, but empirical results are scattered across tasks, systems, and metrics, limiting cumulative insight. Objective: We aimed to synthesise empirical evidence on RAG effectiveness versus parametric-only baselines, map datasets/architectures/evaluation practices, and surface limitations and research gaps. Methods: This systematic review was conducted and reported in accordance with PRISMA 2020. We searched the ACM Digital Library, IEEE Xplore, Scopus, ScienceDirect, and DBLP; all sources were last sea
- 主题命中：RAG与长文档检索:2, 评测、数据集与稳健性:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/09.json`
- 对 PaSa 的帮助：针对《A Systematic Literature Review of Retrieval-Augmented Generation: Techniques, Metrics, and Challenges》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《A Systematic Literature Review of Retrieval-Augmented Generation: Techniques, Metrics, and Challenges》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P081. Understand What LLM Needs: Dual Preference Alignment for Retrieval-Augmented Generation
- 来源：[https://doi.org/10.1145/3696410.3714717](https://doi.org/10.1145/3696410.3714717)；年份：2025；venue：未知；引用数：30；优先级：`P1`
- 证据摘要：Retrieval-augmented generation (RAG) has effectively mitigated the hallucination problem of large language models (LLMs). However, the difficulty of aligning the retriever with the LLMs' diverse knowledge preferences inevitably poses a challenge in developing a reliable RAG system. To address this issue, we propose DPA-RAG, a universal framework designed to align diverse knowledge preferences within RAG systems. Specifically, we initially introduce a preference knowledge construction pipeline and incorporate five novel query augmentation strategies to alleviate preference data scarcity. Based on preference data, DPA-RAG accomplishes both exte
- 主题命中：RAG与长文档检索:2, 重排与学习排序:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/20.json`
- 对 PaSa 的帮助：针对《Understand What LLM Needs: Dual Preference Alignment for Retrieval-Augmented Generation》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《Understand What LLM Needs: Dual Preference Alignment for Retrieval-Augmented Generation》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P091. FeB4RAG: Evaluating Federated Search in the Context of Retrieval Augmented Generation
- 来源：[https://doi.org/10.1145/3626772.3657853](https://doi.org/10.1145/3626772.3657853)；年份：2024；venue：未知；引用数：26；优先级：`P1`
- 证据摘要：Federated search systems aggregate results from multiple search engines, selecting appropriate sources to enhance result quality and align with user intent. With the increasing uptake of Retrieval-Augmented Generation (RAG) pipelines, federated search can play a pivotal role in sourcing relevant information across heterogeneous data sources to generate informed responses. However, existing datasets, such as those developed in the past TREC FedWeb tracks, predate the RAG paradigm shift and lack representation of modern information retrieval challenges
- 主题命中：RAG与长文档检索:2, 检索基础与稀疏召回:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/09.json`
- 对 PaSa 的帮助：针对《FeB4RAG: Evaluating Federated Search in the Context of Retrieval Augmented Generation》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《FeB4RAG: Evaluating Federated Search in the Context of Retrieval Augmented Generation》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P097. REALM: Retrieval-Augmented Language Model Pre-Training
- 来源：[https://doi.org/10.48550/arxiv.2002.08909](https://doi.org/10.48550/arxiv.2002.08909)；年份：2020；venue：arXiv (Cornell University)；引用数：521；优先级：`P1`
- 证据摘要：Language model pre-training has been shown to capture a surprising amount of world knowledge, crucial for NLP tasks such as question answering. However, this knowledge is stored implicitly in the parameters of a neural network, requiring ever-larger networks to cover more facts. To capture knowledge in a more modular and interpretable way, we augment language model pre-training with a latent knowledge retriever, which allows the model to retrieve and attend over documents from a large corpus such as Wikipedia, used during pre-training, fine-tuning and inference. For the first time, we show how to pre-train such a knowledge retriever in an uns
- 主题命中：RAG与长文档检索:2
- 原始响应：`openalex/17.json`
- 对 PaSa 的帮助：针对《REALM: Retrieval-Augmented Language Model Pre-Training》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《REALM: Retrieval-Augmented Language Model Pre-Training》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P101. Integrating Knowledge Retrieval with Generation: A Comprehensive Survey of RAG Models in NLP
- 来源：[https://doi.org/10.20944/preprints202504.0351.v1](https://doi.org/10.20944/preprints202504.0351.v1)；年份：2025；venue：Preprints.org；引用数：10；优先级：`P1`
- 证据摘要：Retrieval-Augmented Generation (RAG) models have emerged as a powerful paradigm in natural language processing (NLP), combining the strengths of information retrieval and text generation to enhance the quality and accuracy of generated responses. Recent advances in natural language processing have led to the development of Retrieval-Augmented Generation (RAG) models, a hybrid approach that combines the benefits of retrieval-based and generative models. Unlike traditional generative models that rely solely on pre-existing knowledge encoded within the model’s parameters, RAG models leverage external knowledge sources, such as large-scale text c
- 主题命中：RAG与长文档检索:2, 检索基础与稀疏召回:1, 密集与对比学习检索:1
- 原始响应：`openalex/13.json`
- 对 PaSa 的帮助：针对《Integrating Knowledge Retrieval with Generation: A Comprehensive Survey of RAG Models in NLP》：只迁移证据定位和长文档切片来辅助候选/重排，论文 ID 仍由本地库提供；生成文本不能替代严格 ID 匹配，也不能直接作为官方输出。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《Integrating Knowledge Retrieval with Generation: A Comprehensive Survey of RAG Models in NLP》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P111. ClimRetrieve: A Benchmarking Dataset for Information Retrieval from Corporate Climate Disclosures
- 来源：[https://doi.org/10.18653/v1/2024.emnlp-main.969](https://doi.org/10.18653/v1/2024.emnlp-main.969)；年份：2024；venue：未知；引用数：8；优先级：`P1`
- 证据摘要：To handle the vast amounts of qualitative data produced in corporate climate communication, stakeholders increasingly rely on Retrieval Augmented Generation (RAG) systems.However, a significant gap remains in evaluating domain-specific information retrieval -the basis for answer generation.To address this challenge, this work simulates the typical tasks of a sustainability analyst by examining 30 sustainability reports with 16 detailed climate-related questions.As a result, we obtain a dataset with over 8.5K unique question-source-answer pairs labeled by different levels of relevance.Furthermore, we develop a use case with the dataset to inve
- 主题命中：RAG与长文档检索:2, 检索基础与稀疏召回:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/18.json`
- 对 PaSa 的帮助：针对《ClimRetrieve: A Benchmarking Dataset for Information Retrieval from Corporate Climate Disclosures》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 提供长摘要/全文切片、证据定位和 grounded 输出的设计参考。PaSa 的 ranking 仍需按论文 ID 评测，因此先用 section-level evidence 辅助候选和重排，再把证据片段绑定到论文卡；生成式摘要不能被当作召回或严格匹配的替代指标。
- 建议实测：围绕《ClimRetrieve: A Benchmarking Dataset for Information Retrieval from Corporate Climate Disclosures》设计一个 train-only ablation：将其核心信号接入 RAG与长文档检索，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

### 评测、数据集与稳健性（12 篇）

#### P009. BEIR-PL: Zero Shot Information Retrieval Benchmark for the Polish Language
- 来源：[https://doi.org/10.48550/arxiv.2305.19840](https://doi.org/10.48550/arxiv.2305.19840)；年份：2023；venue：arXiv (Cornell University)；引用数：4；优先级：`P0`
- 证据摘要：The BEIR dataset is a large, heterogeneous benchmark for Information Retrieval (IR) in zero-shot settings, garnering considerable attention within the research community. However, BEIR and analogous datasets are predominantly restricted to the English language. Our objective is to establish extensive large-scale resources for IR in the Polish language, thereby advancing the research in this NLP area. In this work, inspired by mMARCO and Mr.~TyDi datasets, we translated all accessible open IR datasets into Polish, and we introduced the BEIR-PL benchmark -- a new benchmark which comprises 13 datasets, facilitating further development, training
- 主题命中：评测、数据集与稳健性:3, 检索基础与稀疏召回:2, 重排与学习排序:1
- 原始响应：`openalex/18.json`
- 对 PaSa 的帮助：针对《BEIR-PL: Zero Shot Information Retrieval Benchmark for the Polish Language》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《BEIR-PL: Zero Shot Information Retrieval Benchmark for the Polish Language》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P019. Cocktail: A Comprehensive Information Retrieval Benchmark with LLM-Generated Documents Integration
- 来源：[https://doi.org/10.18653/v1/2024.findings-acl.421](https://doi.org/10.18653/v1/2024.findings-acl.421)；年份：2024；venue：未知；引用数：11；优先级：`P0`
- 证据摘要：The proliferation of Large Language Models (LLMs) has led to an influx of AI-generated content (AIGC) on the internet, transforming the corpus of Information Retrieval (IR) systems from solely human-written to a coexistence with LLM-generated content.The impact of this surge in AIGC on IR systems remains an open question, with the primary challenge being the lack of a dedicated benchmark for researchers.In this paper, we introduce Cocktail, a comprehensive benchmark tailored for evaluating IR models in this mixed-sourced data landscape of the LLM era.Cocktail consists of 16 diverse datasets with mixed human-written and LLM-generated corpora a
- 主题命中：评测、数据集与稳健性:3, 检索基础与稀疏召回:1
- 原始响应：`openalex/18.json`
- 对 PaSa 的帮助：针对《Cocktail: A Comprehensive Information Retrieval Benchmark with LLM-Generated Documents Integration》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《Cocktail: A Comprehensive Information Retrieval Benchmark with LLM-Generated Documents Integration》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P029. Task-aware Retrieval with Instructions
- 来源：[https://doi.org/10.18653/v1/2023.findings-acl.225](https://doi.org/10.18653/v1/2023.findings-acl.225)；年份：2023；venue：未知；引用数：42；优先级：`P0`
- 证据摘要：We study the problem of retrieval with instructions, where users provide explicit descriptions of their intent along with their queries to guide a retrieval system. Our solution is a generalpurpose task-aware retrieval system, trained using multi-task instruction tuning and can follow human-written instructions to find relevant documents to a given query. We introduce the first large-scale collection of 37 retrieval datasets with instructions, BERRI, and present TART, a single multi-task retrieval system trained on BERRI with instructions that can adapt to a new task without any parameter updates. TART advances the state of the art on two zer
- 主题命中：评测、数据集与稳健性:3
- 原始响应：`openalex/12.json`
- 对 PaSa 的帮助：针对《Task-aware Retrieval with Instructions》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《Task-aware Retrieval with Instructions》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P039. Improving zero-shot retrieval using dense external expansion
- 来源：[https://doi.org/10.1016/j.ipm.2022.103026](https://doi.org/10.1016/j.ipm.2022.103026)；年份：2022；venue：Information Processing & Management；引用数：14；优先级：`P0`
- 证据摘要：Pseudo-relevance feedback (PRF) is a classical technique to improve search engine retrieval effectiveness, by closing the vocabulary gap between users’ query formulations and the relevant documents. While PRF is typically applied on the same target corpus as the final retrieval, in the past, external expansion techniques have sometimes been applied to obtain a high-quality pseudo-relevant feedback set using the external corpus . However, such external expansion approaches have only been studied for sparse (BoW) retrieval methods, and its effectiveness for recent dense retrieval methods remains under-investigated. Indeed, dense retrieval appro
- 主题命中：评测、数据集与稳健性:2, 检索基础与稀疏召回:1, 密集与对比学习检索:1, 查询扩展与改写:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Improving zero-shot retrieval using dense external expansion》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《Improving zero-shot retrieval using dense external expansion》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P049. Particular object retrieval with integral max-pooling of CNN activations
- 来源：[https://doi.org/10.48550/arxiv.1511.05879](https://doi.org/10.48550/arxiv.1511.05879)；年份：2015；venue：arXiv (Cornell University)；引用数：680；优先级：`P0`
- 证据摘要：Recently, image representation built upon Convolutional Neural Network (CNN) has been shown to provide effective descriptors for image search, outperforming pre-CNN features as short-vector representations. Yet such models are not compatible with geometry-aware re-ranking methods and still outperformed, on some particular object retrieval benchmarks, by traditional image search systems relying on precise descriptor matching, geometric re-ranking, or query expansion. This work revisits both retrieval stages, namely initial search and re-ranking, by employing the same primitive information derived from the CNN. We build compact feature vectors
- 主题命中：评测、数据集与稳健性:2, 重排与学习排序:1, 查询扩展与改写:1
- 原始响应：`openalex/02.json`
- 对 PaSa 的帮助：针对《Particular object retrieval with integral max-pooling of CNN activations》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《Particular object retrieval with integral max-pooling of CNN activations》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P059. DiSCo: LLM Knowledge Distillation for Efficient Sparse Retrieval in Conversational Search
- 来源：[https://doi.org/10.1145/3726302.3729966](https://doi.org/10.1145/3726302.3729966)；年份：2025；venue：未知；引用数：5；优先级：`P0`
- 证据摘要：Conversational Search (CS) involves retrieving relevant documents from a corpus while considering the conversational context, integrating retrieval with context modeling. Recent advancements in Large Language Models (LLMs) have significantly enhanced CS by enabling query rewriting based on conversational context. However, employing LLMs during inference poses efficiency challenges. Existing solutions mitigate this issue by distilling embeddings derived from human-rewritten queries, focusing primarily on learning the context modeling task. These methods, however, often separate the contrastive retrieval task from the distillation process, trea
- 主题命中：评测、数据集与稳健性:2, 检索基础与稀疏召回:1, 查询扩展与改写:1, 对话、推荐与集合选择:1
- 原始响应：`openalex/15.json`
- 对 PaSa 的帮助：针对《DiSCo: LLM Knowledge Distillation for Efficient Sparse Retrieval in Conversational Search》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《DiSCo: LLM Knowledge Distillation for Efficient Sparse Retrieval in Conversational Search》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P069. Optimizing Dense Retrieval Model Training with Hard Negatives
- 来源：[https://doi.org/10.1145/3404835.3462880](https://doi.org/10.1145/3404835.3462880)；年份：2021；venue：未知；引用数：239；优先级：`P0`
- 证据摘要：Ranking has always been one of the top concerns in information retrieval researches. For decades, the lexical matching signal has dominated the ad-hoc retrieval process, but solely using this signal in retrieval may cause the vocabulary mismatch problem. In recent years, with the development of representation learning techniques, many researchers turn to Dense Retrieval (DR) models for better ranking performance. Although several existing DR models have already obtained promising results, their performance improvement heavily relies on the sampling of training examples. Many effective sampling strategies are not efficient enough for practical
- 主题命中：评测、数据集与稳健性:2, 检索基础与稀疏召回:1, 密集与对比学习检索:1
- 原始响应：`openalex/18.json`
- 对 PaSa 的帮助：针对《Optimizing Dense Retrieval Model Training with Hard Negatives》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《Optimizing Dense Retrieval Model Training with Hard Negatives》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P079. Evaluation of Retrieval-Augmented Generation: A Survey
- 来源：[https://doi.org/10.48550/arxiv.2405.07437](https://doi.org/10.48550/arxiv.2405.07437)；年份：2024；venue：arXiv (Cornell University)；引用数：19；优先级：`P0`
- 证据摘要：Retrieval-Augmented Generation (RAG) has recently gained traction in natural language processing. Numerous studies and real-world applications are leveraging its ability to enhance generative models through external information retrieval. Evaluating these RAG systems, however, poses unique challenges due to their hybrid structure and reliance on dynamic knowledge sources. To better understand these challenges, we conduct A Unified Evaluation Process of RAG (Auepora) and aim to provide a comprehensive overview of the evaluation and benchmarks of RAG systems. Specifically, we examine and compare several quantifiable metrics of the Retrieval and
- 主题命中：评测、数据集与稳健性:2, 检索基础与稀疏召回:1, RAG与长文档检索:1
- 原始响应：`openalex/09.json`
- 对 PaSa 的帮助：针对《Evaluation of Retrieval-Augmented Generation: A Survey》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《Evaluation of Retrieval-Augmented Generation: A Survey》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P089. Development and Evaluation of a Retrieval-Augmented Generation-Based Electronic Medical Record Chatbot System
- 来源：[https://doi.org/10.4258/hir.2025.31.3.218](https://doi.org/10.4258/hir.2025.31.3.218)；年份：2025；venue：Healthcare Informatics Research；引用数：7；优先级：`P0`
- 证据摘要：OBJECTIVES: This study aimed to develop and evaluate a retrieval-augmented generation (RAG)-based chatbot system designed to optimize hospital operations. By leveraging electronic medical record (EMR) manuals, the system seeks to streamline administrative workflows and enhance healthcare delivery. METHODS: The system integrated fine-tuned multilingual embedding models (Multilingual-E5-Large and BGE-M3) for indexing and retrieving information from EMR manuals. A dataset comprising 5,931 question-document pairs was constructed through query augmentation and validated by domain experts. Fine-tuning was performed using contrastive learning to enh
- 主题命中：评测、数据集与稳健性:2, 密集与对比学习检索:1, RAG与长文档检索:1
- 原始响应：`openalex/09.json`
- 对 PaSa 的帮助：针对《Development and Evaluation of a Retrieval-Augmented Generation-Based Electronic Medical Record Chatbot System》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《Development and Evaluation of a Retrieval-Augmented Generation-Based Electronic Medical Record Chatbot System》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P099. Llama2Vec: Unsupervised Adaptation of Large Language Models for Dense Retrieval
- 来源：[https://doi.org/10.18653/v1/2024.acl-long.191](https://doi.org/10.18653/v1/2024.acl-long.191)；年份：2024；venue：未知；引用数：14；优先级：`P0`
- 证据摘要：Dense retrieval calls for discriminative embeddings to represent the semantic relationship between query and document.It may benefit from the using of large language models (LLMs), given LLMs' strong capability on semantic understanding.However, the LLMs are learned by auto-regression, whose working mechanism is completely different from representing whole text as one discriminative embedding.Thus, it is imperative to study how to adapt LLMs properly so that they can be effectively initialized as the backbone encoder for dense retrieval.In this paper, we propose a novel approach, called Llama2Vec, which performs unsupervised adaptation of LLM
- 主题命中：评测、数据集与稳健性:2, 密集与对比学习检索:1
- 原始响应：`openalex/01.json`
- 对 PaSa 的帮助：针对《Llama2Vec: Unsupervised Adaptation of Large Language Models for Dense Retrieval》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《Llama2Vec: Unsupervised Adaptation of Large Language Models for Dense Retrieval》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P109. Domain-Specific Embedding Models for Hydrology and Environmental Sciences: Enhancing Semantic Retrieval and Question Answering
- 来源：[https://doi.org/10.31223/x5dq71](https://doi.org/10.31223/x5dq71)；年份：2025；venue：未知；引用数：1；优先级：`P0`
- 证据摘要：Large Language Models (LLMs) have shown strong performance across natural language processing tasks, yet their general-purpose embeddings often fall short in domains with specialized terminology and complex syntax, such as hydrology and environmental science. This study introduces HydroEmbed, a suite of open-source sentence embedding models fine-tuned for four QA formats: multiple-choice (MCQ), true/false (TF), fill-in-the-blank (FITB), and open-ended questions. Models were trained on the HydroLLM Benchmark, a domain-aligned dataset combining textbook and scientific article content. Fine-tuning strategies included MultipleNegativesRankingLoss
- 主题命中：评测、数据集与稳健性:2, 密集与对比学习检索:1, RAG与长文档检索:1
- 原始响应：`17.json`
- 对 PaSa 的帮助：针对《Domain-Specific Embedding Models for Hydrology and Environmental Sciences: Enhancing Semantic Retrieval and Question Answering》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《Domain-Specific Embedding Models for Hydrology and Environmental Sciences: Enhancing Semantic Retrieval and Question Answering》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P119. Moving Beyond Downstream Task Accuracy for Information Retrieval Benchmarking
- 来源：[https://doi.org/10.18653/v1/2023.findings-acl.738](https://doi.org/10.18653/v1/2023.findings-acl.738)；年份：2023；venue：未知；引用数：8；优先级：`P0`
- 证据摘要：Keshav Santhanam, Jon Saad-Falcon, Martin Franz, Omar Khattab, Avi Sil, Radu Florian, Md Arafat Sultan, Salim Roukos, Matei Zaharia, Christopher Potts. Findings of the Association for Computational Linguistics: ACL 2023. 2023
- 主题命中：评测、数据集与稳健性:2, 检索基础与稀疏召回:1
- 原始响应：`openalex/18.json`
- 对 PaSa 的帮助：针对《Moving Beyond Downstream Task Accuracy for Information Retrieval Benchmarking》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 用于建立可复现实验协议。应同时保留 candidate recall、R@20/R@50/R@100、严格 arXiv-ID 集合 P/R/F1、官方 metrics.py 输出、延迟和 API 成本。每个新组件只能在 train 内部验证晋级，dev 作为封存决策集，test 只在最终导出后使用。
- 建议实测：围绕《Moving Beyond Downstream Task Accuracy for Information Retrieval Benchmarking》设计一个 train-only ablation：将其核心信号接入 评测、数据集与稳健性，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

### 对话、推荐与集合选择（12 篇）

#### P006. Avoiding monotony
- 来源：[https://doi.org/10.1145/1454008.1454030](https://doi.org/10.1145/1454008.1454030)；年份：2008；venue：未知；引用数：457；优先级：`P1`
- 证据摘要：The primary premise upon which top-N recommender systems operate is that similar users are likely to have similar tastes with regard to their product choices. For this reason, recommender algorithms depend deeply on similarity metrics to build the recommendation lists for end-users.However, it has been noted that the products offered on recommendation lists are often too similar to each other and attention has been paid towards the goal of improving diversity to avoid monotonous recommendations.Noting that the retrieval of a set of items matching a user query is a common problem across many applications of information retrieval, we model the
- 主题命中：对话、推荐与集合选择:2, 检索基础与稀疏召回:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/18.json`
- 对 PaSa 的帮助：针对《Avoiding monotony》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《Avoiding monotony》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P016. A Theoretical Framework for Conversational Search
- 来源：[https://doi.org/10.1145/3020165.3020183](https://doi.org/10.1145/3020165.3020183)；年份：2017；venue：未知；引用数：441；优先级：`P1`
- 证据摘要：This paper studies conversational approaches to information retrieval, presenting a theory and model of information interaction in a chat setting. In particular, we consider the question of what properties would be desirable for a conversational information retrieval system so that the system can allow users to answer a variety of information needs in a natural and efficient manner. We study past work on human conversations, and propose a small set of properties that taken together could measure the extent to which a system is conversational. Following this, we present a theoretical model of a conversational system that implements the propert
- 主题命中：对话、推荐与集合选择:2, 检索基础与稀疏召回:1, 多跳检索与搜索智能体:1
- 原始响应：`openalex/10.json`
- 对 PaSa 的帮助：针对《A Theoretical Framework for Conversational Search》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《A Theoretical Framework for Conversational Search》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P026. Proceedings of the 36th international ACM SIGIR conference on Research and development in information retrieval
- 来源：[https://doi.org/10.1145/2484028](https://doi.org/10.1145/2484028)；年份：2013；venue：未知；引用数：388；优先级：`P1`
- 证据摘要：Welcome to the 40th Annual International ACM SIGIR Conference on Research and Development in Information Retrieval (SIGIR 2017). SIGIR is the premier scientific conference in the broad area of information retrieval. We received a high-quality set of full-paper submissions to consider for inclusion in the conference program. We thank the 66 Senior Program Committee (SPC) members, 216 Program Committee (PC) members, and at least 70 additional reviewers for their contributions to paper selection. This pool of committed SIGIR volunteers was based in 33 countries and over 170 institutions, spanning academia, industry, and beyond. We recognized 8 S
- 主题命中：对话、推荐与集合选择:2, 检索基础与稀疏召回:1, 学术搜索与引文推荐:1
- 原始响应：`openalex/19.json`
- 对 PaSa 的帮助：针对《Proceedings of the 36th international ACM SIGIR conference on Research and development in information retrieval》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《Proceedings of the 36th international ACM SIGIR conference on Research and development in information retrieval》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P036. LLM4Rerank: LLM-based Auto-Reranking Framework for Recommendations
- 来源：[https://doi.org/10.1145/3696410.3714922](https://doi.org/10.1145/3696410.3714922)；年份：2025；venue：未知；引用数：19；优先级：`P1`
- 证据摘要：Reranking is significant for recommender systems due to its pivotal role in refining recommendation results. Numerous reranking models have emerged to meet diverse reranking requirements in practical applications, which not only prioritize accuracy but also consider additional aspects such as diversity and fairness. However, most of the existing models struggle to strike a harmonious balance between these diverse aspects at the model level. Additionally, the scalability and personalization of these models are often limited by their complexity and a lack of attention to the varying importance of different aspects in diverse reranking scenarios
- 主题命中：对话、推荐与集合选择:2, 重排与学习排序:1, 评测、数据集与稳健性:1
- 原始响应：`openalex/12.json`
- 对 PaSa 的帮助：针对《LLM4Rerank: LLM-based Auto-Reranking Framework for Recommendations》：把论文中的排序信号蒸馏成冻结候选上的轻量 feature fusion，使用严格 arXiv ID 的 hard negatives 训练，并以 R@20、R@100、F1 三重门控，防止只优化单一 cutoff。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《LLM4Rerank: LLM-based Auto-Reranking Framework for Recommendations》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P046. A Recommendation System Based on Hierarchical Clustering of an Article-Level Citation Network
- 来源：[https://doi.org/10.1109/tbdata.2016.2541167](https://doi.org/10.1109/tbdata.2016.2541167)；年份：2016；venue：IEEE Transactions on Big Data；引用数：139；优先级：`P1`
- 证据摘要：The scholarly literature is expanding at a rate that necessitates intelligent algorithms for search and navigation.For the most part, the problem of delivering scholarly articles has been solved. If one knows the title of an article, locating it requires little effort and, paywalls permitting, acquiring a digital copy has become trivial. However, the navigational aspect of scientific search - finding relevant, influential articles that one does not know exist - is in its early development. In this paper, we introduce EigenfactorRecommends - a citation-based method for improving scholarly navigation. The algorithm uses the hierarchical structu
- 主题命中：对话、推荐与集合选择:2, 评测、数据集与稳健性:1
- 原始响应：`openalex/16.json`
- 对 PaSa 的帮助：针对《A Recommendation System Based on Hierarchical Clustering of an Article-Level Citation Network》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《A Recommendation System Based on Hierarchical Clustering of an Article-Level Citation Network》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P056. A hybrid personalized scholarly venue recommender system integrating social network analysis and contextual similarity
- 来源：[https://doi.org/10.1016/j.future.2019.11.017](https://doi.org/10.1016/j.future.2019.11.017)；年份：2019；venue：Future Generation Computer Systems；引用数：59；优先级：`P1`
- 证据摘要：Rapidly developing academic venues throw a challenge to researchers in identifying the most appropriate ones that are in-line with their scholarly interests and of high relevance. Even a high-quality paper is sometimes rejected due to a mismatch between the area of the paper, and the scope of the journal attempted to. Recommending appropriate academic venues can, therefore, enable researchers to identify and take part in relevant conferences and to publish in impactful journals. Although a researcher may know a few leading high-profile venues for her specific field of interest, a venue recommender system becomes particularly helpful when one
- 主题命中：对话、推荐与集合选择:2, 评测、数据集与稳健性:1
- 原始响应：`openalex/16.json`
- 对 PaSa 的帮助：针对《A hybrid personalized scholarly venue recommender system integrating social network analysis and contextual similarity》：把实体对齐、引用/被引邻居和 venue/year 约束作为低权重图特征；先验证新增 gold 和噪声比，再决定是否进入默认扩展。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《A hybrid personalized scholarly venue recommender system integrating social network analysis and contextual similarity》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P066. Conversational Information Seeking
- 来源：[https://doi.org/10.1561/9781638282013](https://doi.org/10.1561/9781638282013)；年份：2023；venue：未知；引用数：41；优先级：`P1`
- 证据摘要：Over the years, information retrieval and search systems have become more conversational. The last few years have seen a tremendous acceleration of this evolution driven by progress in machine learning. Whereas the possibility of a conversational information seeking (CIS) system robustly understanding conversational input from a person was previously limited, it can now almost be taken for granted. Consumer hardware that supports and encourages conversation is now common, raising awareness of — and the expectation of — conversational support in information retrieval systems. From the research community, this has been accompanied by significan
- 主题命中：对话、推荐与集合选择:2, 检索基础与稀疏召回:1
- 原始响应：`openalex/15.json`
- 对 PaSa 的帮助：针对《Conversational Information Seeking》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《Conversational Information Seeking》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P076. Rank and relevance in novelty and diversity metrics for recommender systems
- 来源：[https://doi.org/10.1145/2043932.2043955](https://doi.org/10.1145/2043932.2043955)；年份：2011；venue：未知；引用数：707；优先级：`P1`
- 证据摘要：The Recommender Systems community is paying increasing attention to novelty and diversity as key qualities beyond accuracy in real recommendation scenarios. Despite the raise of interest and work on the topic in recent years, we find that a clear common methodological and conceptual ground for the evaluation of these dimensions is still to be consolidated. Different evaluation metrics have been reported in the literature but the precise relation, distinction or equivalence between them has not been explicitly studied. Furthermore, the metrics reported so far miss important properties such as taking into consideration the ranking of recommende
- 主题命中：对话、推荐与集合选择:2
- 原始响应：`openalex/03.json`
- 对 PaSa 的帮助：针对《Rank and relevance in novelty and diversity metrics for recommender systems》：将该工作的双编码器/对比学习思想作为 raw-question dense 通道，先与 BM25 union，再只在 L2 候选内融合，避免单向量覆盖掉方法名、数字和版本号。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《Rank and relevance in novelty and diversity metrics for recommender systems》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P086. Taxonomy in a Changing World: Seeking Solutions for a Science in Crisis
- 来源：[https://doi.org/10.1080/10635150701424546](https://doi.org/10.1080/10635150701424546)；年份：2007；venue：Systematic Biology；引用数：317；优先级：`P1`
- 证据摘要：One of the fundamental quests of biology is learning what organisms inhabit the earth. To date approximately 2 million species have been described, with realistic estimates of actual diversity ranging from 4 to 12 million (Stork, 1997; Reaka-Kudla et al., 1997). But while species are disappearing at an ever increasing rate (Pimm and Raven, 2000; Thomas et al., 2004), species discovery and description—taxonomy—is facing a crisis (Wilson, 2004; Wheeler, 2004). Overcoming this “taxonomic impediment” (Rodman and Cody, 2003) is the primary goal of the ambitious and ongoing NSF PEET (Partnerships for Enhancing Expertise in Taxonomy) initiative (NSF
- 主题命中：对话、推荐与集合选择:2
- 原始响应：`openalex/06.json`
- 对 PaSa 的帮助：针对《Taxonomy in a Changing World: Seeking Solutions for a Science in Crisis》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《Taxonomy in a Changing World: Seeking Solutions for a Science in Crisis》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P096. Towards Effective Modeling and Exploitation of Search and User Context in Conversational Information Retrieval
- 来源：[https://doi.org/10.1145/3583780.3616005](https://doi.org/10.1145/3583780.3616005)；年份：2023；venue：未知；引用数：2；优先级：`P1`
- 证据摘要：Conversational information retrieval has garnered considerable attention in recent years. A major challenge in conversational search is formulating the most effective query during the dialogue between the searcher and the conversational agent. Unlike traditional information retrieval systems that assume users can independently create queries, conversational settings allow agents to assist users in query formulation. This alleviates the burden on users by leveraging the multi-turn nature of the conversation to aid them in reaching their information goals. Conversational context plays a vital role in the query process. In this work, we focus on
- 主题命中：对话、推荐与集合选择:2, 检索基础与稀疏召回:1
- 原始响应：`openalex/15.json`
- 对 PaSa 的帮助：针对《Towards Effective Modeling and Exploitation of Search and User Context in Conversational Information Retrieval》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《Towards Effective Modeling and Exploitation of Search and User Context in Conversational Information Retrieval》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P106. Research paper recommender system evaluation
- 来源：[https://doi.org/10.1145/2532508.2532512](https://doi.org/10.1145/2532508.2532512)；年份：2013；venue：未知；引用数：158；优先级：`P1`
- 证据摘要：Over 80 approaches for academic literature recommendation exist today. The approaches were introduced and evaluated in more than 170 research articles, as well as patents, presentations and blogs. We reviewed these approaches and found most evaluations to contain major shortcomings. Of the approaches proposed, 21% were not evaluated. Among the evaluated approaches, 19% were not evaluated against a baseline. Of the user studies performed, 60% had 15 or fewer participants or did not report on the number of participants. Information on runtime and coverage was rarely provided. Due to these and several other shortcomings described in this paper,
- 主题命中：对话、推荐与集合选择:2
- 原始响应：`openalex/16.json`
- 对 PaSa 的帮助：针对《Research paper recommender system evaluation》：借鉴其数据切分、指标和 bootstrap 协议，补齐 PaSa 的 candidate recall、严格 ID R@20/R@50/R@100、前缀 F1 与成本报告，但不把外部 benchmark 分数当作 PaSa 成绩。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《Research paper recommender system evaluation》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

#### P116. How Am I Doing?: Evaluating Conversational Search Systems Offline
- 来源：[https://doi.org/10.1145/3451160](https://doi.org/10.1145/3451160)；年份：2021；venue：ACM Transactions on Information Systems；引用数：44；优先级：`P1`
- 证据摘要：As conversational agents like Siri and Alexa gain in popularity and use, conversation is becoming a more and more important mode of interaction for search. Conversational search shares some features with traditional search, but differs in some important respects: conversational search systems are less likely to return ranked lists of results (a SERP), more likely to involve iterated interactions, and more likely to feature longer, well-formed user queries in the form of natural language questions. Because of these differences, traditional methods for search evaluation (such as the Cranfield paradigm) do not translate easily to conversational
- 主题命中：对话、推荐与集合选择:2
- 原始响应：`openalex/15.json`
- 对 PaSa 的帮助：针对《How Am I Doing?: Evaluating Conversational Search Systems Offline》：先从该论文摘要中抽取一个可独立开关的检索或评测信号，在固定候选池上做 train-only ablation；只保留能同时通过严格 ID 召回与集合 F1 门槛的改动。 借鉴对话状态、用户意图、覆盖度和多样性建模来优化最终输出集合。PaSa 中应把固定 top-k 改为排序前缀选择：使用 train 校准的相关概率和 cardinality prior，最大化期望集合 F1，同时强制输出是严格排名前缀并保留置信区间。
- 建议实测：围绕《How Am I Doing?: Evaluating Conversational Search Systems Offline》设计一个 train-only ablation：将其核心信号接入 对话、推荐与集合选择，固定候选池和预算，报告 strict arXiv-ID candidate recall、R@20/R@100、集合 F1、延迟与调用成本；若 R@20 提升但 R@100 或 F1 下降，则只保留为审计对照。
- 风险：文献元数据来源为 OpenAlex + Crossref 公共 API；本条的迁移价值是工程假设，必须在 PaSa train/dev 上实测，不能直接视为赛题有效。

## 开源项目目录

### 稀疏与混合检索基础（12 个）

#### R009. codelibs/fess
- 来源：[https://github.com/codelibs/fess](https://github.com/codelibs/fess)；星标：1127；fork：175；语言：Java；最近更新：2026-08-28T10:08:40Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：Open-source, self-hosted enterprise & site search server built on OpenSearch. Crawls web / file / DB / cloud sources, 20+ languages, REST API, and AI/RAG & semantic search. Apache-2.0.
- topics：ai-search, crawler, docker, elasticsearch, elasticsearch-alternative, enterprise-search, full-text-search, java, llm, lucene, mcp, opensearch
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `codelibs/fess`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 codelibs/fess 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R019. RamakrishnaChilaka/FerrisSearch
- 来源：[https://github.com/RamakrishnaChilaka/FerrisSearch](https://github.com/RamakrishnaChilaka/FerrisSearch)；星标：14；fork：0；语言：Rust；最近更新：2026-07-22T11:23:02Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：A distributed search and SQL analytics engine in Rust with Raft consensus, hybrid BM25+vector search, and a search-aware query planner — powered by Tantivy, DataFusion, and USearch
- topics：big-data, database, distributed-systems, opensearch, raft, rust, search, search-engine, sql, tantivy, usearch
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `RamakrishnaChilaka/FerrisSearch`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 RamakrishnaChilaka/FerrisSearch 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R029. chirags1725/Enterprise-knowledge-platform
- 来源：[https://github.com/chirags1725/Enterprise-knowledge-platform](https://github.com/chirags1725/Enterprise-knowledge-platform)；星标：3；fork：0；语言：JavaScript；最近更新：2026-08-07T21:30:36Z；许可证：未标注；优先级：`P1`
- 项目描述：A self-hosted enterprise search engine that ingests any file type, retrieves with true hybrid search, links everything in a rich knowledge graph, and answers questions locally with verifiable citations — all offline, zero API cost.
- topics：bm25, docker, docker-compose, elasticsearch, graphrag, hybrid-search, javascript, kafka, llm, neo4j, ollama, postgresql
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `chirags1725/Enterprise-knowledge-platform`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 chirags1725/Enterprise-knowledge-platform 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R039. pelick/VerticleSearchEngine
- 来源：[https://github.com/pelick/VerticleSearchEngine](https://github.com/pelick/VerticleSearchEngine)；星标：101；fork：57；语言：Java；最近更新：2026-07-11T13:11:27Z；许可证：未标注；优先级：`P1`
- 项目描述：Academic Search Engine using Scrapy, MongoDB, Lucene/Solr, Tika, Struts2, Jquery, Bootstrap, D3, CAS
- topics：无 topics
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `pelick/VerticleSearchEngine`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 pelick/VerticleSearchEngine 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R053. opensemanticsearch/open-semantic-etl
- 来源：[https://github.com/opensemanticsearch/open-semantic-etl](https://github.com/opensemanticsearch/open-semantic-etl)；星标：284；fork：70；语言：Python；最近更新：2026-08-14T01:55:46Z；许可证：GPL-3.0；优先级：`P1`
- 项目描述：Python based Open Source ETL tools for file crawling, document processing (text extraction, OCR), content analysis (Entity Extraction & Named Entity Recognition) & data enrichment (annotation) pipelines & ingestor to Solr or Elastic search index & linked data graph database
- topics：annotation, documents, elasticsearch, enrichment, etl, extract, extract-information, extract-text, extractor, ingest, ingestion-pipeline, ingests-documents
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `opensemanticsearch/open-semantic-etl`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 opensemanticsearch/open-semantic-etl 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R062. danieljhkim/dsearch
- 来源：[https://github.com/danieljhkim/dsearch](https://github.com/danieljhkim/dsearch)；星标：2；fork：0；语言：Java；最近更新：2026-08-22T18:56:30Z；许可证：MIT；优先级：`P1`
- 项目描述：A distributed search engine supporting BM25, vector search, and hybrid ranking over sharded Lucene indices.
- topics：distributed-search-engine, grpc, java, lucene, prometheus, vector-search
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `danieljhkim/dsearch`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 danieljhkim/dsearch 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R071. divyanshujethi/SearchRank-AI-Production-Search-Ranking-Engine
- 来源：[https://github.com/divyanshujethi/SearchRank-AI-Production-Search-Ranking-Engine](https://github.com/divyanshujethi/SearchRank-AI-Production-Search-Ranking-Engine)；星标：2；fork：0；语言：Python；最近更新：2026-06-11T09:01:20Z；许可证：MIT；优先级：`P1`
- 项目描述：Production-grade search engine with hybrid retrieval (BM25 + FAISS), Learning-to-Rank, neural reranking, and real-time query understanding for scalable information retrieval systems.
- topics：bm25, faiss, fastapi, information-retrieval, learning-to-rank, lightgbm, machine-learning, mloops, neural-ranking, nlp, nlp-machine-learning, query-understanding
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `divyanshujethi/SearchRank-AI-Production-Search-Ranking-Engine`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 divyanshujethi/SearchRank-AI-Production-Search-Ranking-Engine 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R080. castorini/anserini
- 来源：[https://github.com/castorini/anserini](https://github.com/castorini/anserini)；星标：1191；fork：666；语言：Java；最近更新：2026-08-28T16:09:04Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：Anserini is a Lucene toolkit for reproducible information retrieval research
- topics：information-retrieval, lucene
- 原始响应：`01.json`
- 对 PaSa 的帮助：针对 `castorini/anserini`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 castorini/anserini 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R089. larroy/mycelium
- 来源：[https://github.com/larroy/mycelium](https://github.com/larroy/mycelium)；星标：87；fork：12；语言：C++；最近更新：2024-03-23T08:11:27Z；许可证：NOASSERTION；优先级：`P1`
- 项目描述：An open source information retrieval system written in C++11 and Python. Aspires to be an alternative to Nutch / Lucene. It uses MongoDB as an storage engine.
- topics：无 topics
- 原始响应：`01.json`
- 对 PaSa 的帮助：针对 `larroy/mycelium`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 larroy/mycelium 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R098. shramanb113/ZENITH
- 来源：[https://github.com/shramanb113/ZENITH](https://github.com/shramanb113/ZENITH)；星标：35；fork：1；语言：Go；最近更新：2026-08-16T03:35:58Z；许可证：未标注；优先级：`P1`
- 项目描述：From scratch search engine in Go - no Elasticsearch, no Lucene, just LSM trees, and hybrid ranking
- topics：无 topics
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `shramanb113/ZENITH`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 shramanb113/ZENITH 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R107. imcoza/NeuralSearch
- 来源：[https://github.com/imcoza/NeuralSearch](https://github.com/imcoza/NeuralSearch)；星标：3；fork：0；语言：Python；最近更新：2026-02-16T09:51:45Z；许可证：MIT；优先级：`P1`
- 项目描述：An advanced AI-powered search engine built with Vespa, FastAPI, and Groq, featuring neural query intelligence, hybrid search (BM25 + semantic), multi-model embeddings, result diversification, and comprehensive analytics.
- topics：portfolio, showcase
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `imcoza/NeuralSearch`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 imcoza/NeuralSearch 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R116. win4r/GraphRAG4OpenWebUI
- 来源：[https://github.com/win4r/GraphRAG4OpenWebUI](https://github.com/win4r/GraphRAG4OpenWebUI)；星标：605；fork：123；语言：Python；最近更新：2026-08-28T09:18:45Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：GraphRAG4OpenWebUI integrates Microsoft's GraphRAG technology into Open WebUI, providing a versatile information retrieval API. It combines local, global, and web searches for advanced Q&A systems and search engines. This tool simplifies graph-based retrieval integration in open web environments.
- topics：aiagents, graphrag, llms, ollama, openai, openwebui, rag
- 原始响应：`01.json`
- 对 PaSa 的帮助：针对 `win4r/GraphRAG4OpenWebUI`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 优先借鉴倒排索引、BM25 字段权重、过滤器和稀疏/稠密混合接口，把它接入 PaSa L1 候选层；用严格 ID candidate recall 验证，不以 demo 相关性替代指标。
- 建议实测：先阅读 win4r/GraphRAG4OpenWebUI 的 README、examples 和评测脚本，抽取 稀疏与混合检索基础 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

### 密集向量检索与索引（14 个）

#### R003. athina-ai/rag-cookbooks
- 来源：[https://github.com/athina-ai/rag-cookbooks](https://github.com/athina-ai/rag-cookbooks)；星标：2570；fork：324；语言：Jupyter Notebook；最近更新：2026-08-28T16:26:01Z；许可证：MIT；优先级：`P0`
- 项目描述：This repository contains various advanced techniques for Retrieval-Augmented Generation (RAG) systems.
- topics：ai, chromadb, cookbooks, faiss, langchain, llm, llms, openai, pinecone, python, qdrant, rag
- 原始响应：`06.json`
- 对 PaSa 的帮助：针对 `athina-ai/rag-cookbooks`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 athina-ai/rag-cookbooks 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R013. milvus-io/milvus
- 来源：[https://github.com/milvus-io/milvus](https://github.com/milvus-io/milvus)；星标：45852；fork：4207；语言：Go；最近更新：2026-08-28T19:38:32Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：Milvus is a high-performance, cloud-native vector database built for scalable vector ANN search
- topics：anns, cloud-native, diskann, distributed, embedding-database, embedding-similarity, embedding-store, faiss, golang, hnsw, image-search, llm
- 原始响应：`known_12_milvus-io_milvus.json`
- 对 PaSa 的帮助：针对 `milvus-io/milvus`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 milvus-io/milvus 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R023. qdrant/qdrant
- 来源：[https://github.com/qdrant/qdrant](https://github.com/qdrant/qdrant)；星标：34247；fork：2623；语言：Rust；最近更新：2026-08-28T19:50:57Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：Qdrant - High-performance, massive-scale Vector Database and Vector Search Engine for the next generation of AI. Also available in the cloud https://cloud.qdrant.io/
- topics：ai-search, ai-search-engine, embeddings-similarity, hnsw, hybrid-search, image-search, knn-algorithm, machine-learning, mlops, nearest-neighbor-search, neural-network, neural-search
- 原始响应：`known_11_qdrant_qdrant.json`
- 对 PaSa 的帮助：针对 `qdrant/qdrant`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 qdrant/qdrant 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R033. weaviate/weaviate
- 来源：[https://github.com/weaviate/weaviate](https://github.com/weaviate/weaviate)；星标：16758；fork：1381；语言：Go；最近更新：2026-08-28T14:39:26Z；许可证：BSD-3-Clause；优先级：`P0`
- 项目描述：Weaviate is an open-source vector database that stores both objects and vectors, allowing for the combination of vector search with structured filtering with the fault tolerance and scalability of a cloud-native database​.
- topics：approximate-nearest-neighbor-search, generative-search, grpc, hnsw, hybrid-search, image-search, information-retrieval, mlops, nearest-neighbor-search, neural-search, recommender-system, search-engine
- 原始响应：`known_13_weaviate_weaviate.json`
- 对 PaSa 的帮助：针对 `weaviate/weaviate`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 weaviate/weaviate 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R043. LeDat98/NexusRAG
- 来源：[https://github.com/LeDat98/NexusRAG](https://github.com/LeDat98/NexusRAG)；星标：503；fork：110；语言：Python；最近更新：2026-08-27T23:03:31Z；许可证：未标注；优先级：`P0`
- 项目描述：Hybrid RAG system combining vector search, knowledge graph (LightRAG), and cross-encoder reranking — with Docling document parsing, visual intelligence (image/table captioning), agentic streaming chat, and inline citations. Powered by Gemini or local Ollama models.
- topics：chromadb, citation, docling, document-parsing, fastapi, gemini, knowledge-base, knowledge-graph, lightrag, ollama, rag, react
- 原始响应：`09.json`
- 对 PaSa 的帮助：针对 `LeDat98/NexusRAG`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 LeDat98/NexusRAG 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R048. langchain4j/langchain4j
- 来源：[https://github.com/langchain4j/langchain4j](https://github.com/langchain4j/langchain4j)；星标：12973；fork：2504；语言：Java；最近更新：2026-08-28T14:34:48Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：LangChain4j is an idiomatic, open-source Java library for building LLM-powered applications on the JVM. It offers a unified API over popular LLM providers and vector stores, and makes implementing tool calling (including MCP support), agents and RAG easy. It integrates seamlessly with enterprise Java frameworks like Quarkus and Spring Boot.
- topics：anthropic, chatgpt, chroma, embeddings, gemini, gpt, huggingface, java, langchain, llama, llm, llms
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `langchain4j/langchain4j`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 langchain4j/langchain4j 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R057. Happy-Chen-CH/Educational_RAG_System
- 来源：[https://github.com/Happy-Chen-CH/Educational_RAG_System](https://github.com/Happy-Chen-CH/Educational_RAG_System)；星标：125；fork：5；语言：Python；最近更新：2026-08-28T06:29:58Z；许可证：未标注；优先级：`P0`
- 项目描述：End-to-end educational RAG system: dual-engine retrieval (BM25 + BGE-M3 hybrid vector search), adaptive query strategies (HyDE/sub-query/backtracking), BERT intent classification, BGE-Reranker precision ranking, Chinese-optimized text splitting, and FastAPI SSE streaming — from documents to real-time answers.
- topics：ai, llm, milvus, mysql, python, rag, redis
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `Happy-Chen-CH/Educational_RAG_System`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 Happy-Chen-CH/Educational_RAG_System 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R066. aikho/retrivex
- 来源：[https://github.com/aikho/retrivex](https://github.com/aikho/retrivex)；星标：15；fork：0；语言：Jupyter Notebook；最近更新：2026-02-24T05:27:46Z；许可证：LGPL-2.1；优先级：`P0`
- 项目描述：Explainability toolkit for retrieval models. Explain prediction of vector search models (embeddings similarity models, siamese encoders, bi-encoders, dense retrieval models). Debug your vector search models for RAG or agentic AI system.
- topics：ai, deep-learning, embedding-explainability, embeddings, explainability, explainable-ai, information-retrieval, machine-learning, model-explainability, neural-network, sentence-transformers, similarity
- 原始响应：`02.json`
- 对 PaSa 的帮助：针对 `aikho/retrivex`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 aikho/retrivex 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R075. tainguyen07/semantic-search-faiss
- 来源：[https://github.com/tainguyen07/semantic-search-faiss](https://github.com/tainguyen07/semantic-search-faiss)；星标：6；fork：0；语言：Python；最近更新：2026-08-21T00:42:48Z；许可证：MIT；优先级：`P0`
- 项目描述：Semantic search engine over documents: sentence-transformers embeddings, FAISS ANN index, hybrid BM25+dense retrieval, reranking and a query API.
- topics：embeddings, faiss, information-retrieval, nlp, semantic-search, sentence-transformers, vector-search
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `tainguyen07/semantic-search-faiss`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 tainguyen07/semantic-search-faiss 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R084. AmirhosseinHonardoust/Graph-RAG-Engine
- 来源：[https://github.com/AmirhosseinHonardoust/Graph-RAG-Engine](https://github.com/AmirhosseinHonardoust/Graph-RAG-Engine)；星标：25；fork：2；语言：Python；最近更新：2026-08-21T09:06:06Z；许可证：MIT；优先级：`P0`
- 项目描述：An explainable AI system that combines Graph Intelligence, Vector Search, and Retrieval-Augmented Generation (RAG) to deliver grounded answers and transparent reasoning paths. Includes a FastAPI backend, Streamlit UI, FAISS vector index, and an in-memory knowledge graph for hybrid retrieval and recommendations.
- topics：document-intelligence, explainable-ai, faiss, fastapi, graph-ai, graph-embeddings, knowledge-graph, machine-learning, nlp, python, rag, retrieval-augmented-generation
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `AmirhosseinHonardoust/Graph-RAG-Engine`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 AmirhosseinHonardoust/Graph-RAG-Engine 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R093. AmirhosseinHonardoust/Designing-Hybrid-AI-Systems
- 来源：[https://github.com/AmirhosseinHonardoust/Designing-Hybrid-AI-Systems](https://github.com/AmirhosseinHonardoust/Designing-Hybrid-AI-Systems)；星标：22；fork：0；语言：未知；最近更新：2026-07-08T12:39:57Z；许可证：MIT；优先级：`P0`
- 项目描述：Hybrid AI is the future of explainable intelligence. This article explores how combining vector search, knowledge graphs, and retrieval-augmented generation (RAG) creates AI systems that can reason, cite, and explain their answers with insights learned from building a real Graph-Powered RAG Engine.
- topics：ai-engineering, deep-learning, explainable-ai, faiss, fastapi, graph-neural-networks, graph-rag, hybrid-ai, knowledge-graphs, llm-applications, machine-learning, retrieval-augmented-generation
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `AmirhosseinHonardoust/Designing-Hybrid-AI-Systems`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 AmirhosseinHonardoust/Designing-Hybrid-AI-Systems 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R102. zerefnochills/BIS-HYBRID-RAG-SYSTEM
- 来源：[https://github.com/zerefnochills/BIS-HYBRID-RAG-SYSTEM](https://github.com/zerefnochills/BIS-HYBRID-RAG-SYSTEM)；星标：1；fork：1；语言：Python；最近更新：2026-05-05T19:49:50Z；许可证：MIT；优先级：`P0`
- 项目描述：6-layer Hybrid RAG pipeline that maps product descriptions to BIS IS standards using FAISS dense retrieval, BM25, RRF fusion, and a TinyBERT cross-encoder reranker. Built for IIT Tirupati × SS BIS Hackathon 2026.
- topics：无 topics
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `zerefnochills/BIS-HYBRID-RAG-SYSTEM`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 zerefnochills/BIS-HYBRID-RAG-SYSTEM 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R111. piyushpathak03/Recommendation-systems
- 来源：[https://github.com/piyushpathak03/Recommendation-systems](https://github.com/piyushpathak03/Recommendation-systems)；星标：217；fork：56；语言：Jupyter Notebook；最近更新：2026-07-29T13:24:36Z；许可证：GPL-3.0；优先级：`P0`
- 项目描述：Recommendation Systems This is a workshop on using Machine Learning and Deep Learning Techniques to build Recommendation Systesm Theory: ML & DL Formulation, Prediction vs. Ranking, Similiarity, Biased vs. Unbiased Paradigms: Content-based, Collaborative filtering, Knowledge-based, Hybrid and Ensembles Data: Tabular, Images, Text (Sequences) Models: (Deep) Matrix Factorisation, Auto-Encoders, Wide & Deep, Rank-Learning, Sequence Modelling Methods: Explicit vs. implicit feedback, User-Item matrix, Embeddings, Convolution, Recurrent, Domain Signals: location, time, context, social, Process: Setup, Encode & Embed, Design, Train & Select, Serve & Scale, Measure, Test & Improve Tools: python-data-stack: numpy, pandas, scikit-learn, keras, spacy, implicit, lightfm Notes & Slides Basics: Deep Learning AI Conference 2019: WhiteBoard Notes | In-Class Notebooks Notebooks Movies - Movielens 01-Acquire 02-Augment 03-Refine 04-Transform 05-Evaluation 06-Model-Baseline 07-Feature-extractor 08-Model-Matrix-Factorization 09-Model-Matrix-Factorization-with-Bias 10-Model-MF-NNMF 11-Model-Deep-Matrix-Factorization 12-Model-Neural-Collaborative-Filtering 13-Model-Implicit-Matrix-Factorization 14-Features-Image 15-Features-NLP Ecommerce - YooChoose 01-Data-Preparation 02-Models News - Hackernews Product - Groceries Python Libraries Deep Recommender Libraries Tensorrec - Built on Tensorflow Spotlight - Built on PyTorch TFranking - Built on TensorFlow (Learning to Rank) Matrix Factorisation Based Libraries Implicit - Implicit Matrix Factorisation QMF - Implicit Matrix Factorisation Lightfm - For Hybrid Recommedations Surprise - Scikit-learn type api for traditional alogrithms Similarity Search Libraries Annoy - Approximate Nearest Neighbour NMSLib - kNN methods FAISS - Similarity search and clustering Learning Resources Reference Slides Deep Learning in RecSys by Balázs Hidasi Lessons from Industry RecSys by Xavier Amatriain Architecting Recommendation Systems by James Kirk Recommendation Systems Overview by Raimon and Basilico Benchmarks MovieLens Benchmarks for Traditional Setup Microsoft Tutorial on Recommendation System at KDD 2019 Algorithms & Approaches Collaborative Filtering for Implicit Feedback Datasets Bayesian Personalised Ranking for Implicit Data Logistic Matrix Factorisation Neural Network Matrix Factorisation Neural Collaborative Filtering Variational Autoencoders for Collaborative Filtering Evaluations Evaluating Recommendation Systems
- topics：无 topics
- 原始响应：`03.json`
- 对 PaSa 的帮助：针对 `piyushpathak03/Recommendation-systems`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 piyushpathak03/Recommendation-systems 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R120. Wendy-James/llm-rag-system
- 来源：[https://github.com/Wendy-James/llm-rag-system](https://github.com/Wendy-James/llm-rag-system)；星标：1；fork：0；语言：Python；最近更新：2026-06-16T16:25:17Z；许可证：未标注；优先级：`P0`
- 项目描述：RAG retrieval evaluation supplement: BM25 + dense retrieval + reranker, Faiss-style indexing, Recall@5/MRR, citation and badcase analysis.
- topics：bm25, citation-evaluation, dense-retrieval, faiss, information-retrieval, rag, recall-at-k, reranker
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `Wendy-James/llm-rag-system`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 优先借鉴 ANN 索引、批量编码、向量持久化和 top-k API；在本地 MiniLM 通道上增加可复现实验，确保 raw-question embedding 与论文向量版本固定，并监控召回上限。
- 建议实测：先阅读 Wendy-James/llm-rag-system 的 README、examples 和评测脚本，抽取 密集向量检索与索引 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

### 模型训练与重排（12 个）

#### R008. MISBAHULLL/Information-Retrieval-RAG
- 来源：[https://github.com/MISBAHULLL/Information-Retrieval-RAG](https://github.com/MISBAHULLL/Information-Retrieval-RAG)；星标：2；fork：0；语言：Python；最近更新：2026-05-01T01:26:10Z；许可证：未标注；优先级：`P0`
- 项目描述：Membuat system RAG sederhana dengan dataset News, model yang digunakan EMBEDDING_MODEL menggunakan "sentence-transformers/all-MiniLM-L6-v2" LLM_MODEL menggunakan "models/flan-t5-small" RERANKER_MODEL menggunakan "cross-encoder/ms-marco-MiniLM-L-6-v2". Semua model di ambil dari Huggingface
- topics：无 topics
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `MISBAHULLL/Information-Retrieval-RAG`：先以冻结模型在现有 L2 候选内批量打分，保留分数、rank 和模型版本，避免把不可复现的在线 demo 直接放入默认路径。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 MISBAHULLL/Information-Retrieval-RAG 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R018. vTuanpham/Vietnamese_QA_System
- 来源：[https://github.com/vTuanpham/Vietnamese_QA_System](https://github.com/vTuanpham/Vietnamese_QA_System)；星标：21；fork：9；语言：Python；最近更新：2025-11-07T10:06:43Z；许可证：MIT；优先级：`P0`
- 项目描述：Vietnamese long form question answering system with documents retrieval.
- topics：document-retrieval, dpr, instruction-tune, instructions, lfqa, nlp, qa, question-answering, sentence-embeddings, sentence-similarity, sentence-transformers, vietnamese
- 原始响应：`10.json`
- 对 PaSa 的帮助：针对 `vTuanpham/Vietnamese_QA_System`：先以冻结模型在现有 L2 候选内批量打分，保留分数、rank 和模型版本，避免把不可复现的在线 demo 直接放入默认路径。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 vTuanpham/Vietnamese_QA_System 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R028. ma787639046/bowdpr
- 来源：[https://github.com/ma787639046/bowdpr](https://github.com/ma787639046/bowdpr)；星标：18；fork：2；语言：Python；最近更新：2025-07-21T01:46:44Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：[SIGIR24] Pre-training with Bag-of-Word Prediction for Dense Passage Retrieval
- topics：information-retrieval, pre-training, sentence-transformers
- 原始响应：`02.json`
- 对 PaSa 的帮助：针对 `ma787639046/bowdpr`：先以冻结模型在现有 L2 候选内批量打分，保留分数、rank 和模型版本，避免把不可复现的在线 demo 直接放入默认路径。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 ma787639046/bowdpr 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R038. BaranziniLab/KG_RAG
- 来源：[https://github.com/BaranziniLab/KG_RAG](https://github.com/BaranziniLab/KG_RAG)；星标：943；fork：114；语言：Jupyter Notebook；最近更新：2026-08-22T05:36:06Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：Empower Large Language Models (LLM) using Knowledge Graph based Retrieval-Augmented Generation (KG-RAG) for knowledge intensive tasks
- topics：bert-models, bioinformatics, bioinformatics-algorithms, biomedical-applications, biomedical-informatics, context-aware, gpt, gpt35turbo, gpt4, knowledge-base, knowledge-graph, large-language-models
- 原始响应：`06.json`
- 对 PaSa 的帮助：针对 `BaranziniLab/KG_RAG`：先以冻结模型在现有 L2 候选内批量打分，保留分数、rank 和模型版本，避免把不可复现的在线 demo 直接放入默认路径。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 BaranziniLab/KG_RAG 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R052. vivekvar-dl/internet-context-mcp
- 来源：[https://github.com/vivekvar-dl/internet-context-mcp](https://github.com/vivekvar-dl/internet-context-mcp)；星标：1；fork：1；语言：TypeScript；最近更新：2026-05-12T04:20:11Z；许可证：MIT；优先级：`P0`
- 项目描述：Read-only MCP server giving AI agents the web as compact, ranked, verified evidence. Local cross-encoder reranker, NLI claim verification, semantic cross-source agreement and contradiction detection. No API keys.
- topics：ai-agents, anthropic, claude, llm, mcp, mcp-server, model-context-protocol, prompt-injection, rag, retrieval, transformers-js, typescript
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `vivekvar-dl/internet-context-mcp`：先以冻结模型在现有 L2 候选内批量打分，保留分数、rank 和模型版本，避免把不可复现的在线 demo 直接放入默认路径。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 vivekvar-dl/internet-context-mcp 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R061. NovaSearch-Team/RAG-Retrieval
- 来源：[https://github.com/NovaSearch-Team/RAG-Retrieval](https://github.com/NovaSearch-Team/RAG-Retrieval)；星标：1127；fork：88；语言：Python；最近更新：2026-08-28T18:12:54Z；许可证：MIT；优先级：`P0`
- 项目描述：Unify Efficient Fine-tuning of RAG Retrieval, including Embedding, ColBERT, ReRanker.
- topics：ai, llm, nlp, rag, retrieval-augmented-generation
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `NovaSearch-Team/RAG-Retrieval`：先以冻结模型在现有 L2 候选内批量打分，保留分数、rank 和模型版本，避免把不可复现的在线 demo 直接放入默认路径。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 NovaSearch-Team/RAG-Retrieval 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R070. tom1030507/OpenNotebookLM
- 来源：[https://github.com/tom1030507/OpenNotebookLM](https://github.com/tom1030507/OpenNotebookLM)；星标：41；fork：4；语言：Python；最近更新：2026-08-26T02:44:26Z；许可证：MIT；优先级：`P0`
- 项目描述：Self-hosted alternative to Google's NotebookLM: import PDFs, web pages and YouTube transcripts, then get answers with citations back to the source. Hybrid dense + BM25 retrieval over a local SQLite database, with Claude, any OpenAI-compatible provider, or a model on your own machine.
- topics：bm25, embeddings, fastapi, hybrid-search, llm, nextjs, notebooklm, rag, retrieval-augmented-generation, self-hosted, sentence-transformers, sqlite
- 原始响应：`02.json`
- 对 PaSa 的帮助：针对 `tom1030507/OpenNotebookLM`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 tom1030507/OpenNotebookLM 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R079. amirshq/personal-chatbot
- 来源：[https://github.com/amirshq/personal-chatbot](https://github.com/amirshq/personal-chatbot)；星标：2；fork：0；语言：Python；最近更新：2026-08-27T14:23:31Z；许可证：未标注；优先级：`P0`
- 项目描述：Personal AI assistant chatbot and RAG built with FastAPI, SQLAlchemy, and Hugging Face LLMs. Clean architecture, rate limiting, and vector database support.
- topics：chromadb, fastapi, huggingface, huggingface-transformers, llm, react, redis, redis-cache, reranker, retrieval, retrieval-augmented-generation, sqlalchemy
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `amirshq/personal-chatbot`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 amirshq/personal-chatbot 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R088. denizzozupek/multi-doc-rag-assistant
- 来源：[https://github.com/denizzozupek/multi-doc-rag-assistant](https://github.com/denizzozupek/multi-doc-rag-assistant)；星标：1；fork：0；语言：Python；最近更新：2026-08-28T11:06:20Z；许可证：未标注；优先级：`P0`
- 项目描述：Hybrid RAG pipeline (Dense + BM25 + Cross-Encoder Reranker) with conversational memory and systematic evaluation. 5 retrieval experiments, 92.3% Hit Rate, 5.0/5.0 LLM-as-a-Judge. Built with LangChain LCEL & ChromaDB.
- topics：chromadb, cross-encoder-reranking, hybrid-search, information-retrieval, langchain, lcel, llm-evaluation, openai, pydantic, python, rag, rag-chatbot
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `denizzozupek/multi-doc-rag-assistant`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 denizzozupek/multi-doc-rag-assistant 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R097. hec-ovi/rag-suite
- 来源：[https://github.com/hec-ovi/rag-suite](https://github.com/hec-ovi/rag-suite)；星标：1；fork：0；语言：Python；最近更新：2026-07-16T19:41:18Z；许可证：NOASSERTION；优先级：`P0`
- 项目描述：Production-focused RAG platform: 4 isolated backends (inference, ingestion, RAG, reranker) with hybrid (dense + BM25) and reranked retrieval. FastAPI + Qdrant + local Ollama on AMD ROCm, Docker Compose.
- topics：ai-search, cross-encoder, fastapi, hybrid-search, llm, ollama, qdrant, rag, reranker, retrieval-augmented-generation, self-hosted, semantic-search
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `hec-ovi/rag-suite`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 hec-ovi/rag-suite 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R106. nhonhoccode/vn-legal-rag-zalo-2021
- 来源：[https://github.com/nhonhoccode/vn-legal-rag-zalo-2021](https://github.com/nhonhoccode/vn-legal-rag-zalo-2021)；星标：1；fork：0；语言：Jupyter Notebook；最近更新：2026-05-30T11:33:48Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：Vietnamese Legal Text Retrieval-Augmented Generation. Fine-tune sentence embeddings (BGE-M3, E5, GTE, vietnamese-sbert) with hard negatives mining on Zalo AI Challenge 2021. Hybrid Dense (ChromaDB) + Sparse (BM25 + pyvi) + Cross-encoder reranker pipeline. BGE-M3 hardneg achieves F2@10 0.3209, Recall@10 0.8985, MRR 0.7444.
- topics：docker-compose, retrieval-augmented-generation, sentence-embeddings, vietnamese-nlp, zalo-ai-challenge
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `nhonhoccode/vn-legal-rag-zalo-2021`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 nhonhoccode/vn-legal-rag-zalo-2021 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R115. CodeBendKit/codeseek
- 来源：[https://github.com/CodeBendKit/codeseek](https://github.com/CodeBendKit/codeseek)；星标：765；fork：43；语言：Rust；最近更新：2026-08-27T13:28:03Z；许可证：MIT；优先级：`P0`
- 项目描述：Rust-powered code intelligence CLI for AI coding agents. Builds call graphs and hybrid semantic search indexes (Dense + Sparse + RRF + Reranker) across 7 languages. Ships as native MCP tools for Claude Code and Codex CLI.
- topics：agent-tools, ai-development-tools, ai-tools, bm25, call-graph, claude-code, cli, code-analysis, code-intelligence, cross-encoder, embedding, hybrid-search
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `CodeBendKit/codeseek`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 借鉴模型加载、batch 推理、hard negative 和 cross-encoder/reranker 接口，在 L2 内训练或融合；所有权重必须只来自 train，且以 R@20/R@100/F1 非回归门控。
- 建议实测：先阅读 CodeBendKit/codeseek 的 README、examples 和评测脚本，抽取 模型训练与重排 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

### 查询改写与检索管线（13 个）

#### R006. flamehaven01/Flamehaven-Filesearch
- 来源：[https://github.com/flamehaven01/Flamehaven-Filesearch](https://github.com/flamehaven01/Flamehaven-Filesearch)；星标：107；fork：15；语言：Python；最近更新：2026-08-24T23:20:43Z；许可证：MIT；优先级：`P0`
- 项目描述：Self-hosted RAG search engine — 34 formats, BM25+hybrid search, multi-LLM (Gemini/OpenAI/Claude/Ollama), FastAPI + Docker, production-ready in 3 min
- topics：bm25, crewai, docker, document-parsing, document-search, fastapi, haystack, hybrid-search, knowledge-base, langchain, llamaindex, llm
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `flamehaven01/Flamehaven-Filesearch`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 flamehaven01/Flamehaven-Filesearch 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R016. oceanbase/seekdb
- 来源：[https://github.com/oceanbase/seekdb](https://github.com/oceanbase/seekdb)；星标：2890；fork：322；语言：C++；最近更新：2026-08-28T12:16:24Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：The AI-Native Search Database. Best for agent storage, it unifies vector, text, structured, and semi-structured data into a single engine. This all-in-one database makes agents smarter, easier to run, and more stable.
- topics：ai-agents, copy-on-write, embedded-database, full-text-search, hnsw, hybrid-search, langchain, llamaindex, mysql, oceanbase, python, rag
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `oceanbase/seekdb`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 oceanbase/seekdb 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R026. LazyAGI/LazyLLM
- 来源：[https://github.com/LazyAGI/LazyLLM](https://github.com/LazyAGI/LazyLLM)；星标：3880；fork：408；语言：Python；最近更新：2026-08-28T06:43:48Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：Easiest and laziest way for building multi-agent LLMs applications.
- topics：agents, ai-agent, data, deep-learning, documentation-tool, finetuning, framework, knowlege-graph, langchain, lazyllm, llamaindex, llm
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `LazyAGI/LazyLLM`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 LazyAGI/LazyLLM 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R036. comet-ml/opik
- 来源：[https://github.com/comet-ml/opik](https://github.com/comet-ml/opik)；星标：21655；fork：1735；语言：Python；最近更新：2026-08-28T20:13:44Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：Debug, evaluate, and monitor your LLM applications, RAG systems, and agentic workflows with comprehensive tracing, automated evaluations, and production-ready dashboards.
- topics：evaluation, hacktoberfest, hacktoberfest2025, langchain, llama-index, llm, llm-evaluation, llm-observability, llmops, open-source, openai, playground
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `comet-ml/opik`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 comet-ml/opik 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R046. NirDiamant/GenAI_Agents
- 来源：[https://github.com/NirDiamant/GenAI_Agents](https://github.com/NirDiamant/GenAI_Agents)；星标：24024；fork：4038；语言：Jupyter Notebook；最近更新：2026-08-28T18:58:44Z；许可证：NOASSERTION；优先级：`P0`
- 项目描述：50+ tutorials and implementations for Generative AI Agent techniques, from basic conversational bots to complex multi-agent systems.
- topics：agentic-ai, agents, ai, ai-agents, autonomous-agents, genai, generative-ai, langchain, langgraph, llm, llms, machine-learning
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `NirDiamant/GenAI_Agents`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 NirDiamant/GenAI_Agents 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R051. 1Panel-dev/MaxKB
- 来源：[https://github.com/1Panel-dev/MaxKB](https://github.com/1Panel-dev/MaxKB)；星标：22640；fork：3126；语言：Python；最近更新：2026-08-28T20:24:55Z；许可证：GPL-3.0；优先级：`P0`
- 项目描述：🔥 MaxKB is an open-source platform for building enterprise-grade agents. 强大易用的开源企业级智能体平台。
- topics：agent, agentic-ai, chatbot, deepseek-r1, knowledgebase, langchain, llama3, llm, maxkb, mcp-server, ollama, pgvector
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `1Panel-dev/MaxKB`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 1Panel-dev/MaxKB 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R060. adongwanai/AgentGuide
- 来源：[https://github.com/adongwanai/AgentGuide](https://github.com/adongwanai/AgentGuide)；星标：8923；fork：873；语言：HTML；最近更新：2026-08-28T19:47:46Z；许可证：未标注；优先级：`P0`
- 项目描述：https://adongwanai.github.io/AgentGuide | AI Agent开发指南 | LangGraph实战 | 高级RAG | 转行大模型 | 大模型面试 | 算法工程师 | 面试题库 | 强化学习｜数据合成
- topics：agenticrag, ai-agent, crewai, graphrag, grpo, interview, job-hunting, langchain, llm, multi-agent, rag, sft
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `adongwanai/AgentGuide`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 adongwanai/AgentGuide 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R069. the-open-agent/openagent
- 来源：[https://github.com/the-open-agent/openagent](https://github.com/the-open-agent/openagent)；星标：5579；fork：651；语言：Go；最近更新：2026-08-28T15:52:31Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：⚡️next-generation personal AI assistant powered by LLM, RAG and agent loops, supporting computer-use, browser-use and coding agent, demo: https://demo.openagentai.org
- topics：agent, agentic, agentic-ai, agi, chatbot, chatgpt, gpt, harness, hermes-agent, knowledge-base, langchain, llm
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `the-open-agent/openagent`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 the-open-agent/openagent 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R078. ragapp/ragapp
- 来源：[https://github.com/ragapp/ragapp](https://github.com/ragapp/ragapp)；星标：4442；fork：474；语言：TypeScript；最近更新：2026-08-26T10:38:15Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：The easiest way to use Agentic RAG in any enterprise
- topics：agentic, agents, ai, docker, llamaindex, rag
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `ragapp/ragapp`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 ragapp/ragapp 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R087. didilili/ai-agents-from-zero
- 来源：[https://github.com/didilili/ai-agents-from-zero](https://github.com/didilili/ai-agents-from-zero)；星标：4159；fork：590；语言：Python；最近更新：2026-08-28T18:05:27Z；许可证：MIT；优先级：`P0`
- 项目描述：🚀 2026 最系统的 AI Agent 速成指南｜智能体实战教程 · 完整学习路径 + 实战项目 + 面试题库 · 对标大模型应用开发工程师岗位 · 覆盖LangChain / LangGraph / Coze / Dify / MCP / skills / LLM / RAG / 提示词 · 企业级部署与微调 · 从0到企业级落地 + 从学习到上线项目 + 面试准备一体化
- topics：agent, agent-framework, agentic-ai, ai-agent, aigc, coze, cursor, deepagents, dify, gpt, langchain, langgraph
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `didilili/ai-agents-from-zero`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 didilili/ai-agents-from-zero 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R096. Atmosphere/atmosphere
- 来源：[https://github.com/Atmosphere/atmosphere](https://github.com/Atmosphere/atmosphere)；星标：3796；fork：760；语言：Java；最近更新：2026-08-28T16:16:10Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：Portable AI agent runtime for the JVM. One @Agent class runs on Spring AI, LangChain4j, Anthropic, or 9 more behind one SPI. Token streaming, tool calls, human approvals, and governance over WebSocket, SSE, gRPC, or WebTransport/HTTP3. Speaks MCP, A2A, and AG-UI.
- topics：a2a, acp, agentic-ai, ai-agents, anthropic, crewai, embabel, event-driven, java, koog, langchain4j, llm
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `Atmosphere/atmosphere`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 Atmosphere/atmosphere 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R105. pipeshub-ai/pipeshub-ai
- 来源：[https://github.com/pipeshub-ai/pipeshub-ai](https://github.com/pipeshub-ai/pipeshub-ai)；星标：3697；fork：554；语言：Python；最近更新：2026-08-28T18:35:37Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：PipesHub is an open-source fully extensible AI context layer that unifies your business data for explainable enterprise search and agentic workflow automation.
- topics：agent, agents, ai, drive, glean, gmail, knowledge-graph, langchain, langgraph, llamaparse, notion, ollama
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `pipeshub-ai/pipeshub-ai`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 pipeshub-ai/pipeshub-ai 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R114. wassim249/YT-Navigator
- 来源：[https://github.com/wassim249/YT-Navigator](https://github.com/wassim249/YT-Navigator)；星标：602；fork：75；语言：Python；最近更新：2026-08-19T12:40:26Z；许可证：MIT；优先级：`P0`
- 项目描述：YT Navigator: AI-powered YouTube content explorer that lets you search and chat with channel videos using AI agents. Extract insights from hours of content in seconds with semantic search and precise timestamps.
- topics：agentic-ai, agentic-rag, ai, django, langchain, langgraph, llm, python, rag, reranking, youtube, youtube-bot
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `wassim249/YT-Navigator`：先以冻结模型在现有 L2 候选内批量打分，保留分数、rank 和模型版本，避免把不可复现的在线 demo 直接放入默认路径。 借鉴可组合的 query pipeline、路由和缓存，将原问题、窄约束探针、受控改写拆成独立通道；每条结果保留 route/rank 供 RRF 和审计。
- 建议实测：先阅读 wassim249/YT-Navigator 的 README、examples 和评测脚本，抽取 查询改写与检索管线 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

### RAG与知识库问答（13 个）

#### R001. chatchat-space/Langchain-Chatchat
- 来源：[https://github.com/chatchat-space/Langchain-Chatchat](https://github.com/chatchat-space/Langchain-Chatchat)；星标：38590；fork：6266；语言：Python；最近更新：2026-08-28T11:51:46Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：Langchain-Chatchat（原Langchain-ChatGLM）基于 Langchain 与 ChatGLM, Qwen 与 Llama 等语言模型的 RAG 与 Agent 应用 | Langchain-Chatchat (formerly langchain-ChatGLM), local knowledge based LLM (like ChatGLM, Qwen and Llama) RAG and Agent app with langchain
- topics：chatbot, chatchat, chatglm, chatgpt, embedding, faiss, fastchat, gpt, knowledge-base, langchain, langchain-chatglm, llama
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `chatchat-space/Langchain-Chatchat`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 chatchat-space/Langchain-Chatchat 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R011. zilliztech/akcio
- 来源：[https://github.com/zilliztech/akcio](https://github.com/zilliztech/akcio)；星标：258；fork：40；语言：Python；最近更新：2026-07-31T02:26:16Z；许可证：NOASSERTION；优先级：`P1`
- 项目描述：Akcio is a demonstration project for Retrieval Augmented Generation (RAG). It leverages the power of LLM to generate responses and uses vector databases to fetch relevant documents to enhance the quality and relevance of the output.
- topics：artificial-intelligence, chatbot, chatgpt, dolly, embeddings, ernie-bot, fastapi, gradio, langchain, llm, milvus, minimax
- 原始响应：`06.json`
- 对 PaSa 的帮助：针对 `zilliztech/akcio`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 zilliztech/akcio 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R021. ImprintLab/Medical-Graph-RAG
- 来源：[https://github.com/ImprintLab/Medical-Graph-RAG](https://github.com/ImprintLab/Medical-Graph-RAG)；星标：825；fork：143；语言：Python；最近更新：2026-08-28T08:21:32Z；许可证：MIT；优先级：`P1`
- 项目描述：A Graph RAG System for Evidenced-based Medical Information Retrieval [ACL 2025]
- topics：deep-learning, graph-rag, large-language-model, large-language-models, machine-learning, medical, retrieval-augmented-generation
- 原始响应：`01.json`
- 对 PaSa 的帮助：针对 `ImprintLab/Medical-Graph-RAG`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 ImprintLab/Medical-Graph-RAG 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R031. teilomillet/raggo
- 来源：[https://github.com/teilomillet/raggo](https://github.com/teilomillet/raggo)；星标：224；fork：13；语言：Go；最近更新：2026-08-27T18:47:40Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：A lightweight, production-ready RAG (Retrieval Augmented Generation) library in Go.
- topics：ai, chromadb, document-search, embeddings, golang, llm, milvus, openai, question-answering, rag, retrieval-augmented-generation, vector-database
- 原始响应：`06.json`
- 对 PaSa 的帮助：针对 `teilomillet/raggo`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 teilomillet/raggo 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R041. boluo2077/deep-rag
- 来源：[https://github.com/boluo2077/deep-rag](https://github.com/boluo2077/deep-rag)；星标：209；fork：29；语言：Python；最近更新：2026-08-26T11:43:38Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：🔍 Deep RAG: Advanced Retrieval-Augmented Generation system that goes beyond vector search. Enables AI to perform multi-hop reasoning, negation queries, numerical comparisons & global aggregation on your knowledge base. Supports OpenAI, Anthropic, Google Gemini. Python FastAPI + React UI
- topics：无 topics
- 原始响应：`06.json`
- 对 PaSa 的帮助：针对 `boluo2077/deep-rag`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 boluo2077/deep-rag 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R055. automataIA/graphrag-rs
- 来源：[https://github.com/automataIA/graphrag-rs](https://github.com/automataIA/graphrag-rs)；星标：525；fork：49；语言：Rust；最近更新：2026-08-27T00:59:06Z；许可证：MIT；优先级：`P1`
- 项目描述：GraphRAG-rs is a high-performance, state-of-the-art Rust implementation of GraphRAG (Graph-based Retrieval Augmented Generation) that builds knowledge graphs from documents and enables natural language querying with configurable entity extraction and local LLM integration
- topics：ai, embeddings, entity-extraction, graphrag, knowledge-graph, llama-cpp, llm, nlp, ollama-api, retrieval-augmented-generation, rust, rust-crate
- 原始响应：`06.json`
- 对 PaSa 的帮助：针对 `automataIA/graphrag-rs`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 automataIA/graphrag-rs 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R064. LightningRAG/LightningRAG
- 来源：[https://github.com/LightningRAG/LightningRAG](https://github.com/LightningRAG/LightningRAG)；星标：451；fork：43；语言：Go；最近更新：2026-08-24T09:57:29Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：LightningRAG is a full-stack Vue + Gin starter with a decoupled frontend and backend, plus built-in, extensible RAG (retrieval-augmented generation): knowledge bases, vector search, and integrations with many LLM and vector-store providers
- topics：agent, ai, deepseek, dify, gin, go, golang, rag, ragflow, retrieval-augmented-generation, vue
- 原始响应：`06.json`
- 对 PaSa 的帮助：针对 `LightningRAG/LightningRAG`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 LightningRAG/LightningRAG 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R073. jxzhangjhu/Awesome-LLM-RAG
- 来源：[https://github.com/jxzhangjhu/Awesome-LLM-RAG](https://github.com/jxzhangjhu/Awesome-LLM-RAG)；星标：1343；fork：94；语言：未知；最近更新：2026-08-15T09:03:27Z；许可证：未标注；优先级：`P1`
- 项目描述：Awesome-LLM-RAG: a curated list of advanced retrieval augmented generation (RAG) in Large Language Models
- topics：embeddings, large-language-models, llm, rag, rag-embeddings, retrieval-augmented-generation, retrieval-information
- 原始响应：`06.json`
- 对 PaSa 的帮助：针对 `jxzhangjhu/Awesome-LLM-RAG`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 jxzhangjhu/Awesome-LLM-RAG 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R082. nanditab35/Quantum-RAG-FAQ
- 来源：[https://github.com/nanditab35/Quantum-RAG-FAQ](https://github.com/nanditab35/Quantum-RAG-FAQ)；星标：2；fork：1；语言：Jupyter Notebook；最近更新：2026-08-01T20:24:00Z；许可证：未标注；优先级：`P1`
- 项目描述：This repository contains a collection of notebooks for building and evaluating a RAG application on the topic of Quantum Mechanics. It demonstrates various retrieval strategies, such as Vector RAG and Graph RAG, and includes a pipeline for extracting a Knowledge Graph from the training documents.
- topics：generative-ai, llm, nlp, openai, physics, python, pytorch, quantum-mechanics, rag, reranker, retrieval-augmented-generation, vector-database
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `nanditab35/Quantum-RAG-FAQ`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 nanditab35/Quantum-RAG-FAQ 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R091. muntasirhsn/Introduction-to-Retrieval-Augmented-Generation
- 来源：[https://github.com/muntasirhsn/Introduction-to-Retrieval-Augmented-Generation](https://github.com/muntasirhsn/Introduction-to-Retrieval-Augmented-Generation)；星标：17；fork：5；语言：Jupyter Notebook；最近更新：2025-08-04T12:15:38Z；许可证：未标注；优先级：`P1`
- 项目描述：This is an introduction to Retrieval-Augmented Generation (RAG) for beginners . It uses Llama 2 LLM, FAISS vector store, and LangChain as the orchestrator to perform generative question answering (QA) to a knowledge base/data source.
- topics：无 topics
- 原始响应：`10.json`
- 对 PaSa 的帮助：针对 `muntasirhsn/Introduction-to-Retrieval-Augmented-Generation`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 muntasirhsn/Introduction-to-Retrieval-Augmented-Generation 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R100. vasiliskou/Experimentation_Hub_for_RAG
- 来源：[https://github.com/vasiliskou/Experimentation_Hub_for_RAG](https://github.com/vasiliskou/Experimentation_Hub_for_RAG)；星标：1；fork：0；语言：Jupyter Notebook；最近更新：2025-12-27T18:47:38Z；许可证：MIT；优先级：`P1`
- 项目描述：A comprehensive framework to create, test, and benchmark Retrieval-Augmented Generation (RAG) pipelines, supporting multiple architectures (e.g., Graph RAG and Agentic RAG), document splitters, embedding models, vectorstores, retrievers, rerankers, and LLM providers, with an interactive Gradio UI and experiment logging.
- topics：agenticrag, embeddings, framework, graphrag, llms, rag, retrieval-augmented-generation, retrievers, vectorstores
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `vasiliskou/Experimentation_Hub_for_RAG`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 vasiliskou/Experimentation_Hub_for_RAG 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R109. jonfairbanks/local-rag
- 来源：[https://github.com/jonfairbanks/local-rag](https://github.com/jonfairbanks/local-rag)；星标：757；fork：95；语言：Python；最近更新：2026-08-24T16:53:25Z；许可证：GPL-3.0；优先级：`P1`
- 项目描述：Ingest files for retrieval augmented generation (RAG) with open-source Large Language Models (LLMs), all without 3rd parties or sensitive data leaving your network.
- topics：large-language-models, llm, ollama, rag, retrieval-augmented-generation
- 原始响应：`06.json`
- 对 PaSa 的帮助：针对 `jonfairbanks/local-rag`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 jonfairbanks/local-rag 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R118. NVIDIA-AI-Blueprints/rag
- 来源：[https://github.com/NVIDIA-AI-Blueprints/rag](https://github.com/NVIDIA-AI-Blueprints/rag)；星标：751；fork：317；语言：Python；最近更新：2026-08-28T12:10:27Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：This NVIDIA RAG blueprint serves as a reference solution for a foundational Retrieval Augmented Generation (RAG) pipeline.
- topics：blueprint, nim, rag, retrieval-augmented-generation
- 原始响应：`06.json`
- 对 PaSa 的帮助：针对 `NVIDIA-AI-Blueprints/rag`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴文档切片、证据引用、检索—生成边界和缓存；在 PaSa 中只让证据帮助候选/重排，不能让生成文本伪造论文 ID 或替代官方打分。
- 建议实测：先阅读 NVIDIA-AI-Blueprints/rag 的 README、examples 和评测脚本，抽取 RAG与知识库问答 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

### 学术搜索与论文工具（14 个）

#### R002. TaewoooPark/scholar-megasearch
- 来源：[https://github.com/TaewoooPark/scholar-megasearch](https://github.com/TaewoooPark/scholar-megasearch)；星标：26；fork：8；语言：Python；最近更新：2026-08-27T13:53:04Z；许可证：MIT；优先级：`P0`
- 项目描述：Massive multi-source academic literature search for Claude Code — one skill fans out subagents across 20+ scholarly databases (arXiv, Semantic Scholar, Crossref, OpenAlex, PubMed, …), merges into a deduplicated ranked corpus, and acquires the original PDFs.
- topics：academic-search, agent-skills, anthropic, arxiv, claude, claude-code, literature-review, mcp, model-context-protocol, multi-agent, openalex, pubmed
- 原始响应：`07.json`
- 对 PaSa 的帮助：针对 `TaewoooPark/scholar-megasearch`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 TaewoooPark/scholar-megasearch 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R012. wp-a/nature-academic-search
- 来源：[https://github.com/wp-a/nature-academic-search](https://github.com/wp-a/nature-academic-search)；星标：151；fork：9；语言：Python；最近更新：2026-08-28T15:28:41Z；许可证：MIT；优先级：`P0`
- 项目描述：Academic Paper Search：面向中文科研用户的 Codex / Claude Code 文献检索 Skill + MCP；跨 CrossRef、PubMed、arXiv、OpenAlex、Europe PMC 检索去重，支持 Semantic Scholar 富化、ClinicalTrials.gov 试验与引用导出。
- topics：academic-search, agent-skills, arxiv, chinese, citation-management, claude-code, clinicaltrials-gov, codex, crossref, europe-pmc, literature-review, mcp
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `wp-a/nature-academic-search`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 wp-a/nature-academic-search 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R022. Magiciangel/open-literature-search
- 来源：[https://github.com/Magiciangel/open-literature-search](https://github.com/Magiciangel/open-literature-search)；星标：5；fork：0；语言：TypeScript；最近更新：2026-06-15T11:50:07Z；许可证：MIT；优先级：`P0`
- 项目描述：Open-source academic literature search across open scholarly sources.
- topics：academic-search, arxiv, crossref, docker, literature-search, nextjs, open-access, open-source, openalex, pubmed, semantic-scholar, typescript
- 原始响应：`07.json`
- 对 PaSa 的帮助：针对 `Magiciangel/open-literature-search`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 Magiciangel/open-literature-search 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R032. nirholas/x402-research
- 来源：[https://github.com/nirholas/x402-research](https://github.com/nirholas/x402-research)；星标：3；fork：0；语言：TypeScript；最近更新：2026-08-17T02:54:25Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：Scholarly search over arXiv, Crossref, and Semantic Scholar — papers, citation graphs, formatted bibliographies. Paid per query with x402: USDC on Base or Solana.
- topics：agentic-commerce, ai-agents, base, http-402, micropayments, solana, usdc, x402
- 原始响应：`07.json`
- 对 PaSa 的帮助：针对 `nirholas/x402-research`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 nirholas/x402-research 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R042. CharlesPikachu/paperdl
- 来源：[https://github.com/CharlesPikachu/paperdl](https://github.com/CharlesPikachu/paperdl)；星标：69；fork：16；语言：Python；最近更新：2026-08-16T05:41:31Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：Paperdl: A Unified Asynchronous Framework for Scholarly Paper Search and Download. (轻量级论文下载器：支持Arxiv，Scihub，OpenReview，ACL Anthology，bioRxiv，medRxiv，PMLR，PMC等平台)
- topics：arxiv, arxiv-papers, baidu, baiduwenku, biorxiv, google, googlescholar, medrxiv, pmc, sci-hub
- 原始响应：`07.json`
- 对 PaSa 的帮助：针对 `CharlesPikachu/paperdl`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 CharlesPikachu/paperdl 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R047. lstudlo/ScholarMCP
- 来源：[https://github.com/lstudlo/ScholarMCP](https://github.com/lstudlo/ScholarMCP)；星标：25；fork：4；语言：TypeScript；最近更新：2026-08-23T05:29:22Z；许可证：MIT；优先级：`P0`
- 项目描述：ScholarMCP - An academic research MCP server with comprehensive literature search, PDF ingestion, and citation management tools. Integrates with Google Scholar, OpenAlex, Crossref, and Semantic Scholar for automated research workflows.
- topics：无 topics
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `lstudlo/ScholarMCP`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 lstudlo/ScholarMCP 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R056. Query-farm/vgi-scholar
- 来源：[https://github.com/Query-farm/vgi-scholar](https://github.com/Query-farm/vgi-scholar)；星标：1；fork：0；语言：Python；最近更新：2026-08-28T16:16:46Z；许可证：MIT；优先级：`P0`
- 项目描述：Scholarly search across OpenAlex/arXiv/Crossref for DuckDB (Python)
- topics：arxiv, crossref, duckdb, openalex, python, query-farm, scholarly-search, vgi
- 原始响应：`07.json`
- 对 PaSa 的帮助：针对 `Query-farm/vgi-scholar`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 Query-farm/vgi-scholar 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R065. bytedance/pasa
- 来源：[https://github.com/bytedance/pasa](https://github.com/bytedance/pasa)；星标：1652；fork：122；语言：Python；最近更新：2026-08-28T12:12:29Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：PaSa -- an advanced paper search agent powered by large language models. It can autonomously make a series of decisions, including invoking search tools, reading papers, and selecting relevant references, to ultimately obtain comprehensive and accurate results for complex scholarly queries.
- topics：research
- 原始响应：`07.json`
- 对 PaSa 的帮助：针对 `bytedance/pasa`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 bytedance/pasa 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R074. vtmike2015/Graph-Based-Literature-Review-Tool
- 来源：[https://github.com/vtmike2015/Graph-Based-Literature-Review-Tool](https://github.com/vtmike2015/Graph-Based-Literature-Review-Tool)；星标：14；fork：3；语言：Jupyter Notebook；最近更新：2026-01-24T18:08:11Z；许可证：GPL-3.0；优先级：`P0`
- 项目描述：This Network-graph based literature review tool uses the open-source version of Neo4j with Jupyter Notebooks written in Python to import academic literature metadata from a variety of sources including OpenAlex, arXiv, Sematic Scholar and Web of Science. Also incorporated are OpenAI vector embeddings using Neo4j's Vector Search Index capabilities.
- topics：arxiv, embedding-vectors, embeddings, graph-database, neo4j, opeanai, openalex, semantic-scholar, vector, web-of-science
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `vtmike2015/Graph-Based-Literature-Review-Tool`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 vtmike2015/Graph-Based-Literature-Review-Tool 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R083. O0000-code/paper-search-pro
- 来源：[https://github.com/O0000-code/paper-search-pro](https://github.com/O0000-code/paper-search-pro)；星标：149；fork：10；语言：HTML；最近更新：2026-08-28T16:21:49Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：Academic literature discovery as a Skill — Claude Code · Codex · any agent that loads SKILL.md. Five sources · four tiers · single-file Shadcn report.
- topics：academic-research, agent-skill, arxiv, claude-code-skill, codex, literature-search, openalex, prisma-s, pubmed, semantic-scholar, shadcn-ui, systematic-review
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `O0000-code/paper-search-pro`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 O0000-code/paper-search-pro 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R092. aritra741/FindResearch.online
- 来源：[https://github.com/aritra741/FindResearch.online](https://github.com/aritra741/FindResearch.online)；星标：32；fork：2；语言：TypeScript；最近更新：2026-06-28T14:07:06Z；许可证：MIT；优先级：`P0`
- 项目描述：An intelligent academic search engine for discovering and accessing relevant scholarly articles
- topics：无 topics
- 原始响应：`07.json`
- 对 PaSa 的帮助：针对 `aritra741/FindResearch.online`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 aritra741/FindResearch.online 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R101. TobiasBlask/open-paper-machine
- 来源：[https://github.com/TobiasBlask/open-paper-machine](https://github.com/TobiasBlask/open-paper-machine)；星标：18；fork：5；语言：Python；最近更新：2026-08-14T10:51:27Z；许可证：MIT；优先级：`P0`
- 项目描述：An autonomous LLM research agent that executes the full academic paper pipeline — from literature search to compiled PDF
- topics：academic-writing, arxiv, claude, claude-code, claude-code-plugin, claude-skills, constitutional-ai, mcp, open-science, paper-generation, research-automation
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `TobiasBlask/open-paper-machine`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 TobiasBlask/open-paper-machine 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R110. Demfier/openleaf
- 来源：[https://github.com/Demfier/openleaf](https://github.com/Demfier/openleaf)；星标：128；fork：5；语言：TypeScript；最近更新：2026-08-20T04:13:18Z；许可证：未标注；优先级：`P0`
- 项目描述：AI-powered citation search & paper review for Overleaf — Chrome extension. Think Google Scholar but inside Overleaf. Also works with OpenAI Prism, & Opera.
- topics：academic-writing, ai-assistant, bibliography, bibtex, chrome-extension, citation-search, latex, literature-search, litreview, litserach, llm, openai-prism
- 原始响应：`07.json`
- 对 PaSa 的帮助：针对 `Demfier/openleaf`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 Demfier/openleaf 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R119. afrise/academic-search-mcp-server
- 来源：[https://github.com/afrise/academic-search-mcp-server](https://github.com/afrise/academic-search-mcp-server)；星标：118；fork：11；语言：Python；最近更新：2026-08-25T08:09:54Z；许可证：AGPL-3.0；优先级：`P0`
- 项目描述：Academic Paper Search MCP Server for Claude Desktop integration. Allows Claude to access data from Semantic Scholar and Crossref.
- topics：academic, ai, llm, mcp, mcp-server, search
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `afrise/academic-search-mcp-server`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴 arXiv/OpenAlex/Semantic Scholar 的字段规范化、去重、元数据过滤和论文展示；优先实现稳定 ID 对齐、标题/摘要/引用字段审计。
- 建议实测：先阅读 afrise/academic-search-mcp-server 的 README、examples 和评测脚本，抽取 学术搜索与论文工具 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

### 引文图与知识图谱（13 个）

#### R004. xerrors/Yuxi
- 来源：[https://github.com/xerrors/Yuxi](https://github.com/xerrors/Yuxi)；星标：6580；fork：980；语言：Python；最近更新：2026-08-28T19:07:28Z；许可证：MIT；优先级：`P1`
- 项目描述：可私有部署的多租户知识智能体平台：统一 RAG、知识图谱、多智能体、MCP/Skills、沙盒与权限管理。Self-hosted knowledge agent platform for RAG, knowledge graphs and multi-agent workflows.
- topics：agentic-rag, ai-agents, deepagents, docker, document-ai, fastapi, harness, kbqa, kgqa, knowledge-base, knowledge-graph, langgraph
- 原始响应：`11.json`
- 对 PaSa 的帮助：针对 `xerrors/Yuxi`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 xerrors/Yuxi 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R014. huypham-0607/startorch
- 来源：[https://github.com/huypham-0607/startorch](https://github.com/huypham-0607/startorch)；星标：7；fork：0；语言：C++；最近更新：2026-08-27T15:11:00Z；许可证：未标注；优先级：`P1`
- 项目描述：Literature retrieval engine using BM25 and Personalized PageRank over the OpenAlex citation graph.
- topics：无 topics
- 原始响应：`09.json`
- 对 PaSa 的帮助：针对 `huypham-0607/startorch`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 huypham-0607/startorch 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R024. xdotech/goatlas
- 来源：[https://github.com/xdotech/goatlas](https://github.com/xdotech/goatlas)；星标：34；fork：2；语言：Go；最近更新：2026-07-27T18:35:20Z；许可证：MIT；优先级：`P1`
- 项目描述：GoAtlas: The AI-Powered Code Intelligence Engine — A server-side MCP platform that deeply indexes Go/TypeScript codebases via AST parsing, builds a Neo4j knowledge graph, and provides hybrid semantic search (BM25 + pgvector). Features process detection, community clustering, auto-generated docs, and a Gemini AI agent.
- topics：无 topics
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `xdotech/goatlas`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 xdotech/goatlas 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R034. chriskal96/physics-theory-citation-network
- 来源：[https://github.com/chriskal96/physics-theory-citation-network](https://github.com/chriskal96/physics-theory-citation-network)；星标：6；fork：0；语言：Cycript；最近更新：2025-05-11T18:43:02Z；许可证：未标注；优先级：`P1`
- 项目描述：High energy physics theory citation network analysis using Neo4j Graph database.
- topics：无 topics
- 原始响应：`09.json`
- 对 PaSa 的帮助：针对 `chriskal96/physics-theory-citation-network`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 chriskal96/physics-theory-citation-network 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R044. opensemanticsearch/open-semantic-search
- 来源：[https://github.com/opensemanticsearch/open-semantic-search](https://github.com/opensemanticsearch/open-semantic-search)；星标：1205；fork：200；语言：Shell；最近更新：2026-08-28T03:33:28Z；许可证：GPL-3.0；优先级：`P1`
- 项目描述：Open Source research tool to search, browse, analyze and explore large document collections by Semantic Search Engine and Open Source Text Mining & Text Analytics platform (Integrates ETL for document processing, OCR for images & PDF, named entity recognition for persons, organizations & locations, metadata management by thesaurus & ontologies, search user interface & search apps for fulltext search, faceted search & knowledge graph)
- topics：annotation, faceted-search, fulltext-search, investigative-journalism, journalism, named-entity-recognition, ocr, ontologies, osint, python, research-tool, search
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `opensemanticsearch/open-semantic-search`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 opensemanticsearch/open-semantic-search 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R049. 0xK3vin/MegaMemory
- 来源：[https://github.com/0xK3vin/MegaMemory](https://github.com/0xK3vin/MegaMemory)；星标：511；fork：47；语言：TypeScript；最近更新：2026-08-28T11:24:24Z；许可证：MIT；优先级：`P1`
- 项目描述：Persistent project knowledge graph for coding agents. MCP server with semantic search, in-process embeddings, and web explorer.
- topics：agentic-coding, ai, ai-agents, claude-code, code-context, coding-agent, embeddings, knowledge-graph, llm, mcp, mcp-server, opencode
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `0xK3vin/MegaMemory`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 0xK3vin/MegaMemory 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R058. dennybritz/papergraph
- 来源：[https://github.com/dennybritz/papergraph](https://github.com/dennybritz/papergraph)；星标：189；fork：10；语言：Jupyter Notebook；最近更新：2026-08-28T00:59:47Z；许可证：未标注；优先级：`P1`
- 项目描述：AI/ML citation graph with postgres + graphql
- topics：无 topics
- 原始响应：`09.json`
- 对 PaSa 的帮助：针对 `dennybritz/papergraph`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 dennybritz/papergraph 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R067. jaks6/citation_map
- 来源：[https://github.com/jaks6/citation_map](https://github.com/jaks6/citation_map)；星标：154；fork：17；语言：Python；最近更新：2026-06-07T09:58:18Z；许可证：未标注；优先级：`P1`
- 项目描述：Create a Gephi Citation Graph based on Text Analysis of PDFs from Zotero
- topics：articles, citation-graph, gephi, pdfminer, zotero
- 原始响应：`09.json`
- 对 PaSa 的帮助：针对 `jaks6/citation_map`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 jaks6/citation_map 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R076. 45645678a/Scholar-mcp
- 来源：[https://github.com/45645678a/Scholar-mcp](https://github.com/45645678a/Scholar-mcp)；星标：95；fork：8；语言：Python；最近更新：2026-07-28T22:27:44Z；许可证：MIT；优先级：`P1`
- 项目描述：Local academic paper MCP server — 9-source search, multi-source download, AI analysis, translation, citation graph, code-based paper recommendation
- topics：无 topics
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `45645678a/Scholar-mcp`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 45645678a/Scholar-mcp 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R085. intuit/infigraph
- 来源：[https://github.com/intuit/infigraph](https://github.com/intuit/infigraph)；星标：78；fork：16；语言：Rust；最近更新：2026-08-28T09:32:54Z；许可证：NOASSERTION；优先级：`P1`
- 项目描述：AST-powered code intelligence engine. Graph database + hybrid semantic search for 62 languages. Zero LLM dependency. Runs locally.
- topics：ai-tools, ast-parsing, code-analysis, code-intelligence, code-understanding, codebase-analysis, develo, graph-database, knowledge-graph, local-first, semantic-search
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `intuit/infigraph`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 intuit/infigraph 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R094. TuGraph-family/Awesome-Graphs
- 来源：[https://github.com/TuGraph-family/Awesome-Graphs](https://github.com/TuGraph-family/Awesome-Graphs)；星标：75；fork：8；语言：HTML；最近更新：2026-07-31T12:16:34Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：Think Graphs Like A Graph.
- topics：awesome-list, citation, graph, hacktoberfest, paper, reference, visualization
- 原始响应：`09.json`
- 对 PaSa 的帮助：针对 `TuGraph-family/Awesome-Graphs`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 TuGraph-family/Awesome-Graphs 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R103. linmy666/madcop
- 来源：[https://github.com/linmy666/madcop](https://github.com/linmy666/madcop)；星标：73；fork：5；语言：Python；最近更新：2026-08-28T18:28:11Z；许可证：NOASSERTION；优先级：`P1`
- 项目描述：Your desktop AI partner that actually knows you. It watches the files you edit and the commands you run, flags bugs you missed, and turns long conversations into reusable SKILL.md files. Citations on every claim, a knowledge graph that grows with you, every byte stays on your machine.
- topics：ai-agent, desktop-app, electron, llm, local-first, mcp, python, typescript, vue, workflow-automation
- 原始响应：`09.json`
- 对 PaSa 的帮助：针对 `linmy666/madcop`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 linmy666/madcop 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R112. jonashertner/opencaselaw
- 来源：[https://github.com/jonashertner/opencaselaw](https://github.com/jonashertner/opencaselaw)；星标：57；fork：17；语言：Python；最近更新：2026-08-28T20:06:36Z；许可证：MIT；优先级：`P1`
- 项目描述：Open Swiss legal corpus + MCP server: 1M+ court decisions (1875–today), 21k laws, 10M-edge citation graph, 42 MCP tools. CC0 data, MIT code. Live at mcp.opencaselaw.ch
- topics：ai-agents, caselaw, citation-graph, dataset, legal-data, legal-research, mcp, mcp-server, model-context-protocol, open-data, swiss-law, switzerland
- 原始响应：`09.json`
- 对 PaSa 的帮助：针对 `jonashertner/opencaselaw`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴图存储、邻居扩展、PageRank/图 RAG 和实体对齐，将引用关系作为低权重增益通道；用 paired ablation 证明它没有污染普通语义查询。
- 建议实测：先阅读 jonashertner/opencaselaw 的 README、examples 和评测脚本，抽取 引文图与知识图谱 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

### 智能体与多步搜索（13 个）

#### R005. YS0meone/Corvus
- 来源：[https://github.com/YS0meone/Corvus](https://github.com/YS0meone/Corvus)；星标：98；fork：13；语言：Python；最近更新：2026-08-10T15:46:07Z；许可证：MIT；优先级：`P0`
- 项目描述：Multi-agent AI research system — finds academic papers via semantic search & citation snowballing, then answers questions over them using agentic RAG with self-reflection. Built with LangGraph, FastAPI, Celery, and Qdrant.
- topics：academic-research, agentic-rag, ai-agent, celery, fastapi, grobid, langchain, langgraph, multi-agent, python, qdrant, rag
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `YS0meone/Corvus`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 YS0meone/Corvus 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R015. dralkh/seerai
- 来源：[https://github.com/dralkh/seerai](https://github.com/dralkh/seerai)；星标：77；fork：5；语言：TypeScript；最近更新：2026-08-25T02:19:29Z；许可证：MIT；优先级：`P0`
- 项目描述：Zotero AI plugin Research assistant for Zotero 9. Chat with your library, run federated scholarly search, RAG, OCR, systematic reviews, and manage cloud storage. Includes standalone MCP, Agentic capabilities, and skills library.
- topics：academic-research, agent, ai, ai-agent, bibliography, cloud-storage, knowledge-management, mcp, mcp-server, model-context-protocol, ocr, rag
- 原始响应：`07.json`
- 对 PaSa 的帮助：针对 `dralkh/seerai`：先抽取其 ID 规范化、去重和元数据字段映射，接入本地论文库审计；任何外部结果都必须回填可验证 arXiv ID。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 dralkh/seerai 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R025. microsoft/autogen
- 来源：[https://github.com/microsoft/autogen](https://github.com/microsoft/autogen)；星标：60676；fork：9162；语言：Python；最近更新：2026-08-28T20:16:05Z；许可证：CC-BY-4.0；优先级：`P0`
- 项目描述：A programming framework for agentic AI
- topics：agentic, agentic-agi, agents, ai, autogen, autogen-ecosystem, chatgpt, framework, llm-agent, llm-framework
- 原始响应：`known_22_microsoft_autogen.json`
- 对 PaSa 的帮助：针对 `microsoft/autogen`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 microsoft/autogen 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R035. PawanOsman/OpenCursor
- 来源：[https://github.com/PawanOsman/OpenCursor](https://github.com/PawanOsman/OpenCursor)；星标：6004；fork：1027；语言：TypeScript；最近更新：2026-08-28T15:18:55Z；许可证：MIT；优先级：`P0`
- 项目描述：Open-source Cursor-like AI coding agent for VS Code — agentic chat, multi-provider LLMs (OpenAI, Ollama, llama.cpp), semantic search, and MCP support
- topics：agent, ai, code, coder, cursor, extension, ide, vscode
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `PawanOsman/OpenCursor`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 PawanOsman/OpenCursor 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R045. AkariAsai/learning_to_retrieve_reasoning_paths
- 来源：[https://github.com/AkariAsai/learning_to_retrieve_reasoning_paths](https://github.com/AkariAsai/learning_to_retrieve_reasoning_paths)；星标：436；fork：66；语言：Python；最近更新：2026-06-26T02:01:15Z；许可证：MIT；优先级：`P0`
- 项目描述：The official implementation of ICLR 2020, "Learning to Retrieve Reasoning Paths over Wikipedia Graph for Question Answering".
- topics：hotpotqa, multi-hop-reasoning, natural-questions, open-domain-qa, reading-comprehension, retrieval, squad
- 原始响应：`10.json`
- 对 PaSa 的帮助：针对 `AkariAsai/learning_to_retrieve_reasoning_paths`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 AkariAsai/learning_to_retrieve_reasoning_paths 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R050. DCI-Agent/DCI-Agent-Lite
- 来源：[https://github.com/DCI-Agent/DCI-Agent-Lite](https://github.com/DCI-Agent/DCI-Agent-Lite)；星标：392；fork：50；语言：Python；最近更新：2026-08-28T10:11:37Z；许可证：MIT；优先级：`P0`
- 项目描述：Beyond Semantic Similarity: Rethinking Retrieval for Agentic Search via Direct Corpus Interaction
- topics：无 topics
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `DCI-Agent/DCI-Agent-Lite`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 DCI-Agent/DCI-Agent-Lite 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R059. ory/lumen
- 来源：[https://github.com/ory/lumen](https://github.com/ory/lumen)；星标：254；fork：31；语言：Go；最近更新：2026-08-27T13:48:17Z；许可证：NOASSERTION；优先级：`P0`
- 项目描述：Save 30% token costs when using Claude Code, Codex, OpenCode for free - with open source, local semantic search. Works for small and large codebases and monorepos! Enterprise-ready and fully compliant via Ollama and SQLite-vec.
- topics：agentic-coding, claude, claude-ai, claude-code, claude-pl, codex, context, gemini, golang, gpt-5, mcp, mcp-server
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `ory/lumen`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 ory/lumen 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R068. canghongjian/beam_retriever
- 来源：[https://github.com/canghongjian/beam_retriever](https://github.com/canghongjian/beam_retriever)；星标：135；fork：16；语言：Python；最近更新：2026-08-20T21:15:57Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：[NAACL 2024] End-to-End Beam Retrieval for Multi-Hop Question Answering
- topics：无 topics
- 原始响应：`10.json`
- 对 PaSa 的帮助：针对 `canghongjian/beam_retriever`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 canghongjian/beam_retriever 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R077. rayl15/OpenVision
- 来源：[https://github.com/rayl15/OpenVision](https://github.com/rayl15/OpenVision)；星标：127；fork：19；语言：Swift；最近更新：2026-08-27T19:28:00Z；许可证：MIT；优先级：`P0`
- 项目描述：Open-source iOS app connecting Meta Ray-Ban smart glasses to AI — 5 backends (on-device MLX models, Apple Intelligence, OpenAI, Gemini Live, OpenClaw), on-device neural voice, face recognition & live web search. Private and offline-capable.
- topics：ai-assistant, apple-intelligence, face-recognition, gemini, gemma, ios, llm, meta-glasses, mlx, offline-ai, on-device-ai, openclaw
- 原始响应：`03.json`
- 对 PaSa 的帮助：针对 `rayl15/OpenVision`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 rayl15/OpenVision 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R086. damionrashford/RivalSearchMCP
- 来源：[https://github.com/damionrashford/RivalSearchMCP](https://github.com/damionrashford/RivalSearchMCP)；星标：124；fork：21；语言：Python；最近更新：2026-08-27T21:06:58Z；许可证：MIT；优先级：`P0`
- 项目描述：Deterministic research MCP server on FastMCP 3 — 5-engine web search, 9-platform social search, 6 academic DBs, news aggregation, entity profiles, conflict detection, document analysis. No API keys. No in-server LLM. Structured outputs for agent chaining.
- topics：agent-skills, ai-agent, ai-assistant, claude-code, claude-code-skills, claude-mcp, competitor-analysis, cursor-mcp, deterministic-tools, entity-research, fastmcp, market-intelligence
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `damionrashford/RivalSearchMCP`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 damionrashford/RivalSearchMCP 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R095. alphaparkinc/genpark-vector-semantic-db-search-skill
- 来源：[https://github.com/alphaparkinc/genpark-vector-semantic-db-search-skill](https://github.com/alphaparkinc/genpark-vector-semantic-db-search-skill)；星标：9；fork：0；语言：Python；最近更新：2026-08-23T05:06:03Z；许可证：未标注；优先级：`P0`
- 项目描述：High-performance vector index and hybrid semantic search engine
- topics：agentic-workflow, ai-agents, autonomous-agents, genpark, mcp-server
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `alphaparkinc/genpark-vector-semantic-db-search-skill`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 alphaparkinc/genpark-vector-semantic-db-search-skill 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R104. adam-s/alphadidactic
- 来源：[https://github.com/adam-s/alphadidactic](https://github.com/adam-s/alphadidactic)；星标：72；fork：9；语言：Python；最近更新：2026-08-17T21:41:54Z；许可证：未标注；优先级：`P0`
- 项目描述：An iteration research agent: searches academic research, applies it to time series data, and probes it to find novel discoveries.
- topics：backtesting, quant, stock-price-prediction, timescaledb
- 原始响应：`08.json`
- 对 PaSa 的帮助：针对 `adam-s/alphadidactic`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 adam-s/alphadidactic 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R113. sycny/RAE
- 来源：[https://github.com/sycny/RAE](https://github.com/sycny/RAE)；星标：41；fork：5；语言：Python；最近更新：2026-05-23T06:53:49Z；许可证：未标注；优先级：`P0`
- 项目描述：[CIKM2024] Retrieval-enhanced Knowledge Editing in Language Models for Multi-Hop Question Answering
- topics：无 topics
- 原始响应：`10.json`
- 对 PaSa 的帮助：针对 `sycny/RAE`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴工具调用、状态机、预算账本和行动轨迹，让搜索策略按可观测缺口选择下一步；先离线回放，再小预算线上验证，禁止无界递归。
- 建议实测：先阅读 sycny/RAE 的 README、examples 和评测脚本，抽取 智能体与多步搜索 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

### 检索评测与数据集（4 个）

#### R007. beir-cellar/beir
- 来源：[https://github.com/beir-cellar/beir](https://github.com/beir-cellar/beir)；星标：2276；fork：251；语言：Python；最近更新：2026-08-28T15:28:58Z；许可证：Apache-2.0；优先级：`P0`
- 项目描述：A Heterogeneous Benchmark for Information Retrieval. Easy to use, evaluate your models across 15+ diverse IR datasets.
- topics：benchmark, bert, colbert, dataset, deep-learning, dpr, elasticsearch, information-retrieval, llm, nlp, passage-retrieval, pytorch
- 原始响应：`01.json`
- 对 PaSa 的帮助：针对 `beir-cellar/beir`：先复用其倒排字段、BM25 参数或混合检索 API，新增独立 channel_id，验证字段权重对严格 candidate recall 的增益。 借鉴 benchmark loader、官方 scorer、bootstrap 和实验追踪，实现 PaSa 的严格 ID、官方标题脚本、分层切分与无泄漏评测。
- 建议实测：先阅读 beir-cellar/beir 的 README、examples 和评测脚本，抽取 检索评测与数据集 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R017. cvangysel/pytrec_eval
- 来源：[https://github.com/cvangysel/pytrec_eval](https://github.com/cvangysel/pytrec_eval)；星标：351；fork：36；语言：C++；最近更新：2026-08-20T11:28:16Z；许可证：MIT；优先级：`P0`
- 项目描述：pytrec_eval is an Information Retrieval evaluation tool for Python, based on the popular trec_eval.
- topics：evaluation, information-retrieval
- 原始响应：`01.json`
- 对 PaSa 的帮助：针对 `cvangysel/pytrec_eval`：先借鉴其 benchmark loader、指标和可复现实验结构，统一 PaSa 的严格 ID、官方 metrics.py、bootstrap 和成本报表。 借鉴 benchmark loader、官方 scorer、bootstrap 和实验追踪，实现 PaSa 的严格 ID、官方标题脚本、分层切分与无泄漏评测。
- 建议实测：先阅读 cvangysel/pytrec_eval 的 README、examples 和评测脚本，抽取 检索评测与数据集 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R027. GioiaZheng/msmarco-genqa
- 来源：[https://github.com/GioiaZheng/msmarco-genqa](https://github.com/GioiaZheng/msmarco-genqa)；星标：18；fork：0；语言：Python；最近更新：2026-08-25T16:33:26Z；许可证：MIT；优先级：`P0`
- 项目描述：RAG-based question answering system on MS MARCO with retrieval, reranking, evaluation, and reproducibility checks.
- topics：evaluation, faiss, information-retrieval, msmarco, rag, transformer
- 原始响应：`10.json`
- 对 PaSa 的帮助：针对 `GioiaZheng/msmarco-genqa`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴 benchmark loader、官方 scorer、bootstrap 和实验追踪，实现 PaSa 的严格 ID、官方标题脚本、分层切分与无泄漏评测。
- 建议实测：先阅读 GioiaZheng/msmarco-genqa 的 README、examples 和评测脚本，抽取 检索评测与数据集 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R037. shbryangh-ch/Dify-Multi-Reranker-Knowledge-Retrieval-Chatflow
- 来源：[https://github.com/shbryangh-ch/Dify-Multi-Reranker-Knowledge-Retrieval-Chatflow](https://github.com/shbryangh-ch/Dify-Multi-Reranker-Knowledge-Retrieval-Chatflow)；星标：1；fork：0；语言：未知；最近更新：2026-06-18T07:47:44Z；许可证：未标注；优先级：`P0`
- 项目描述：在 self-hosted Dify 中建立單一 Chatflow，透過 `reranker_name` API 輸入切換 BGE、msmarco、Qwen3-Reranker-4B 等不同 reranker 分支。內容涵蓋 Workflow 架構、Dify 匯入方式、API 呼叫範例，以及搭配 Jupyter Notebook 進行批次問題測試與 reranker 效果比較的方法，適合用於 RAG 知識庫檢索評測與多 reranker 整合實驗。
- topics：无 topics
- 原始响应：`04.json`
- 对 PaSa 的帮助：针对 `shbryangh-ch/Dify-Multi-Reranker-Knowledge-Retrieval-Chatflow`：先以冻结模型在现有 L2 候选内批量打分，保留分数、rank 和模型版本，避免把不可复现的在线 demo 直接放入默认路径。 借鉴 benchmark loader、官方 scorer、bootstrap 和实验追踪，实现 PaSa 的严格 ID、官方标题脚本、分层切分与无泄漏评测。
- 建议实测：先阅读 shbryangh-ch/Dify-Multi-Reranker-Knowledge-Retrieval-Chatflow 的 README、examples 和评测脚本，抽取 检索评测与数据集 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

### 部署、服务与可观测性（12 个）

#### R010. Semafind/semadb
- 来源：[https://github.com/Semafind/semadb](https://github.com/Semafind/semadb)；星标：32；fork：3；语言：Go；最近更新：2026-08-27T15:49:04Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：No fuss multi-index hybrid vector database / search engine
- topics：search-engine, vector-database
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `Semafind/semadb`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 Semafind/semadb 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R020. meilisearch/meilisearch
- 来源：[https://github.com/meilisearch/meilisearch](https://github.com/meilisearch/meilisearch)；星标：59116；fork：2686；语言：Rust；最近更新：2026-08-28T19:25:04Z；许可证：NOASSERTION；优先级：`P1`
- 项目描述：A lightning-fast search engine API bringing AI-powered hybrid search to your sites and applications.
- topics：ai, api, app-search, database, enterprise-search, faceting, full-text-search, fuzzy-search, geosearch, hybrid-search, instantsearch, search
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `meilisearch/meilisearch`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 meilisearch/meilisearch 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R030. memfreeme/memfree
- 来源：[https://github.com/memfreeme/memfree](https://github.com/memfreeme/memfree)；星标：1506；fork：210；语言：TypeScript；最近更新：2026-08-26T06:08:55Z；许可证：MIT；优先级：`P1`
- 项目描述：MemFree - Hybrid AI Search Engine & AI Page Generator
- topics：ai, ai-search, ai-search-engine, devfast, generate-ui, hacktoberfest, hacktoberfest-accepted, hybrid-ai-search, page-generator, react, search-engine, serverless-vector
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `memfreeme/memfree`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 memfreeme/memfree 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R040. kantord/SeaGOAT
- 来源：[https://github.com/kantord/SeaGOAT](https://github.com/kantord/SeaGOAT)；星标：1304；fork：91；语言：Python；最近更新：2026-08-25T08:42:52Z；许可证：MIT；优先级：`P1`
- 项目描述：local-first semantic code search engine
- topics：ai, ai-project, code-search, code-search-engine, embeddings, grep, grep-like, hacktoberfest, hacktoberfest2023, llm, regular-expression, ripgrep
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `kantord/SeaGOAT`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 kantord/SeaGOAT 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R054. probelabs/probe
- 来源：[https://github.com/probelabs/probe](https://github.com/probelabs/probe)；星标：696；fork：63；语言：Rust；最近更新：2026-08-28T04:09:15Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：AI-friendly semantic code search engine for large codebases. Combines ripgrep speed with tree-sitter AST parsing. Powers AI coding assistants with precise, context-aware code understanding.
- topics：ai, ai-coder, ast, cli, code-search, mcp, nodejs-sdk, ripgrep, rust, search-engine, semantic-search, tree-sitter
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `probelabs/probe`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 probelabs/probe 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R063. nixiesearch/nixiesearch
- 来源：[https://github.com/nixiesearch/nixiesearch](https://github.com/nixiesearch/nixiesearch)；星标：616；fork：15；语言：Scala；最近更新：2026-07-28T18:45:13Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：Hybrid search engine, combining best features of text and semantic search worlds
- topics：search, search-engine, semantic-search
- 原始响应：`05.json`
- 对 PaSa 的帮助：针对 `nixiesearch/nixiesearch`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 nixiesearch/nixiesearch 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R072. floere/picky
- 来源：[https://github.com/floere/picky](https://github.com/floere/picky)；星标：442；fork：49；语言：HTML；最近更新：2026-07-22T20:19:28Z；许可证：NOASSERTION；优先级：`P1`
- 项目描述：Picky is an easy to use and fast Ruby semantic search engine that helps your users find what they are looking for.
- topics：ruby, search-engine
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `floere/picky`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 floere/picky 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R081. eagledot/hachi
- 来源：[https://github.com/eagledot/hachi](https://github.com/eagledot/hachi)；星标：326；fork：18；语言：Python；最近更新：2026-08-16T16:09:38Z；许可证：AGPL-3.0；优先级：`P1`
- 项目描述：An end to end semantic and meta-data search engine for personal data.
- topics：无 topics
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `eagledot/hachi`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 eagledot/hachi 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R090. kaijiezhu11/SearchAnything
- 来源：[https://github.com/kaijiezhu11/SearchAnything](https://github.com/kaijiezhu11/SearchAnything)；星标：311；fork：25；语言：Python；最近更新：2026-08-27T11:19:10Z；许可证：MIT；优先级：`P1`
- 项目描述：A semantic local search engine powered by AI models.
- topics：无 topics
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `kaijiezhu11/SearchAnything`：先阅读 README、examples 和测试用例，抽取一个可隔离的检索组件，在固定 PaSa 候选池和预算上做 train-only ablation。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 kaijiezhu11/SearchAnything 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R099. thesephist/revery
- 来源：[https://github.com/thesephist/revery](https://github.com/thesephist/revery)；星标：301；fork：7；语言：JavaScript；最近更新：2026-07-21T17:30:15Z；许可证：MIT；优先级：`P1`
- 项目描述：A personal semantic search engine capable of surfacing relevant bookmarks, journal entries, notes, blogs, contacts, and more, built on an efficient document embedding algorithm and Monocle's personal search index.
- topics：browser-extension, natural-language-processing, search-engine, torus-dom, word2vec
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `thesephist/revery`：先把其工具调用改成有上限的离线状态机，记录每次 query/section/citation 动作和严格召回变化，再评估是否值得增加 API 成本。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 thesephist/revery 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R108. scarletkc/vexor
- 来源：[https://github.com/scarletkc/vexor](https://github.com/scarletkc/vexor)；星标：239；fork：15；语言：Python；最近更新：2026-08-26T01:47:51Z；许可证：MIT；优先级：`P1`
- 项目描述：A semantic search engine for files and code.
- topics：ai, claude, cli, codex, embeddings, mcp-server, python, search, skills, terminal, vector
- 原始响应：`12.json`
- 对 PaSa 的帮助：针对 `scarletkc/vexor`：先复用其 ANN 批量检索/持久化接口，做同一 query、同一论文向量版本的 top-k 对照，并记录召回上限、内存和延迟。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 scarletkc/vexor 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

#### R117. mixedbread-ai/baguetter
- 来源：[https://github.com/mixedbread-ai/baguetter](https://github.com/mixedbread-ai/baguetter)；星标：213；fork：11；语言：Python；最近更新：2026-08-26T17:15:47Z；许可证：Apache-2.0；优先级：`P1`
- 项目描述：Baguetter is a flexible, efficient, and hackable search engine library implemented in Python. It's designed for quickly benchmarking, implementing, and testing new search methods. Baguetter supports sparse (traditional), dense (semantic), and hybrid retrieval methods.
- topics：无 topics
- 原始响应：`02.json`
- 对 PaSa 的帮助：针对 `mixedbread-ai/baguetter`：先借鉴其 benchmark loader、指标和可复现实验结构，统一 PaSa 的严格 ID、官方 metrics.py、bootstrap 和成本报表。 借鉴批处理、并发、缓存、服务化和 trace 设计，让 1000 题评测可恢复；每题保存版本、耗时、调用数、错误和排名摘要，避免一次性大文件导致全量丢失。
- 建议实测：先阅读 mixedbread-ai/baguetter 的 README、examples 和评测脚本，抽取 部署、服务与可观测性 的最小可复现组件；在 PaSa 中以 feature/channel 方式接入，记录版本、输入输出、显存/CPU、吞吐和严格 ID 指标，不要直接复制未经许可证核对的代码或把仓库 demo 分数当作 PaSa 成绩。
- 风险：GitHub 搜索元数据来自公开 REST API；星标是影响力线索而非准确率证明，项目可能停更、许可证不完整或与 PaSa 语料分布不同。

## 下一步落地顺序

1. 从 `P0` 论文和项目中各选 10 个，先做组件级 smoke test；所有输入、模型版本和候选池固定。
2. 在 PaSa train 上训练/校准融合重排和 cardinality/F1 前缀选择器，使用独立 train validation 做晋级门控。
3. 在封存 dev800-999 上做严格 ID paired bootstrap；只保留 R@20、R@50、R@100 和 F1 同时不回退的方案。
4. 将成功的组件写回可恢复评测 runner，保留原始 API 响应、配置、排名、官方导出和失败日志。

## 可复核清单

- 论文条数：`120`（要求至少 100）
- 开源项目条数：`120`（要求至少 100）
- 论文类别覆盖：10/10
- 项目类别覆盖：10/10
- 详细机器可读清单：同目录的 `PASA_RESEARCH_CATALOG_200_20260829.json`
- 原始响应：F 盘 staging 目录中对应的 Crossref/GitHub JSON 文件；不要删除，以便后续核验筛选结果。
