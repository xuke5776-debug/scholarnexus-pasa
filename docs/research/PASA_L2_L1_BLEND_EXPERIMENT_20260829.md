# PaSa L2/L1 候选内融合实验

日期：2026-08-29

## 目的

验证扩大 L2 输入后，单独使用 lexical L2 是否会让低质量候选挤掉高质量的多通道候选，并测试一个不改变候选池的 L1/L2 排序融合。该实验只使用已经冻结的 train 候选审计，答案在排名文件完成后才加入；没有读取 dev/test。

## 输入与协议

- 数据：完整 PaSa train `recovered_bucket_20260821/train.jsonl`。
- 审计：两个不重叠的 8-query label-blind P2/P3 train rollout，共 16 个 query。
- 候选：只使用审计中已经获得 `s_l2` 的候选；不为新增候选臆造 L2 分数。
- 分数：分别在每个 query 的 L2 候选池内做 min-max 归一化，再计算 `score=(1-w)*L2+w*L1`。
- 指标：严格 arXiv ID 的候选内 R@20、R@50、R@100；不估计重新执行后的 F1-Gate、API 成本或端到端收益。
- 原始可复现结果：`docs/eval/pasa_l2_blend_counterfactual_train16_20260829.json`。

## 结果

| L1 权重 `w` | R@20 | R@50 | R@100 |
|---:|---:|---:|---:|
| 0.00（纯 L2） | 0.1063 | 0.2104 | 0.3427 |
| 0.25 | 0.1479 | 0.2417 | 0.4135 |
| 0.50 | 0.1740 | 0.3510 | 0.4135 |
| 0.75 | **0.2781** | 0.2885 | **0.4656** |
| 1.00（纯 L1） | 0.2031 | **0.3615** | 0.4656 |

相对 `w=0`，`w=0.75` 的 R@20 增加 `0.1719`（约 `+162%`），R@100 增加 `0.1229`（约 `+36%`）。这是 16-query 诊断，置信区间尚未计算，不能宣称比赛成绩提升 300%。

## 实现

- `scholarnexus/core/judge.py` 新增 `pipeline.l2_rank_blend_l1_weight`，默认 `0`，因此不改变既有 H8/P2 基线。
- `configs/pasa_h8_raw_dense_p3_l1blend_experiment.json` 提供可复现实验配置：L2 输入/输出 300、L1 权重 `0.75`、dense 始终开启。
- `tests/run_tests.py` 新增默认关闭与启用排序顺序回归测试。

## 解释与下一步

结果支持“扩大 L2 必须同时保留 L1 多通道证据”的假设，但不能证明该权重在全量数据上最优。下一步应在 1,024 train policy-train + 256 disjoint policy-validation 上重新生成 P2/P3 rollout，训练或门控融合器；只有满足预先声明的 R@20、R@100、F1 非回归门槛才进入 dev 封存比较。不得使用当前 dev 全量评测结果调权重。
