# ScholarNexus 架构说明

## 设计目标

系统同时优化集合级 F1、调用成本和可审计性。所有模块共享统一 `QueryPlan`、
`Candidate`、`SearchResult` 和 `Ledger`，任一外部服务失败时只降级该层。

## 模块边界

| 模块 | 输入 | 输出 | 默认成本 |
|---|---|---|---:|
| QueryLens | 自然语言查询 | 查询类型、约束图、子查询、预算 | 1 次 LLM |
| MultiProbe | 欠约束检索式 | 多源候选及通道命中 | 学术 API |
| CitationRipple | 高置信种子 | 前向/后向引用与图先验 | 有界 API |
| CascadeJudge L0-L2 | 候选与完整约束 | 多级相关性信号 | 0 LLM |
| CascadeJudge L3 | VoI 不确定带 | 带证据约束判断 | 默认关闭 |
| Calibration | 多路信号 | 相关概率 | 本地计算 |
| CoverageMeter | 通道重叠与概率 | N̂、覆盖率、置信区间 | 本地计算 |
| F1-Gate | 概率与 N̂ | core/partial/excluded | 本地计算 |
| InsightBoard | 最终集合 | 矩阵、分面、图、时间线 | 最多 1 次 LLM |

## 可执行约束图

查询中的每条语义约束是一组可替换表述：`OR(原词, 别名, 缩写)`；不同正向组按
AND 解释；排除组按 NOT 解释。只有 anchor 进入检索式，其余语义约束只参与判定。
同类重复约束会被合并，避免 LLM 同义复述造成重复计权。

## 低成本策略

默认 `max_rounds=2`，但 `enable_query_evolution=false`，因此常规请求只执行一轮
主检索与同轮引文扩散。默认 `l3_policy=disabled`；cloud 配置可设为 `adaptive`，
只有最高 VoI 超过门限时才批量精判，最多12篇。

## 确定性

并行检索按任务提交顺序聚合；每个评测查询创建独立引擎；本地语料返回论文副本，
避免跨查询的去重合并污染共享数据。相同配置和输入应产生相同排序与集合边界。
