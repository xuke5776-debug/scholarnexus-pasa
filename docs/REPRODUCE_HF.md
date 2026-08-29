# PaSa 数据与 ScholarNexus 复现说明

本文给远程 GPT Work、评审机器和新开发环境使用。仓库本身不携带官方 PaSa 大文件。

## 1. 获取源码

```bash
git clone https://github.com/xuke5776-debug/scholarnexus-pasa.git
cd scholarnexus-pasa
python -m pip install -e .
```

仓库根目录的 `scholarnexus-source-bundle-*.zip` 是完整轻量源码备份。如果某个镜像只展示可见模块，先下载并解压该 zip 到仓库根目录；zip 不包含 `data/pasa`、`data/models`、`docs/eval`、密钥或虚拟环境。

## 2. HF bucket 文件

权威公开镜像：

`https://huggingface.co/buckets/XK2026/pasa-dataset-bucket`

Bucket 当前包含 12 个对象，总大小约 2.67 GB。至少需要：

- `AutoScholarQuery/train.jsonl`：33,551 条，qid 连续为 `AutoScholarQuery_train_0` 到 `AutoScholarQuery_train_33550`；用于训练和内部验证。
- `AutoScholarQuery/dev.jsonl`：公开开发集；只用于封存比较，不参与训练、阈值选择或策略拟合。
- `AutoScholarQuery/test.jsonl`：公开测试集；只在最终排名冻结后用于官方导出和打分。
- PaSa 论文元数据/论文库对象：用于把输出的 arXiv ID 解析为标题，并构建本地检索索引。

对象可用以下稳定 URL 下载：

`https://huggingface.co/buckets/XK2026/pasa-dataset-bucket/resolve/<对象路径>?download=true`

例如：

```bash
mkdir -p official_reference_data/PaSa/AutoScholarQuery
curl -L --fail --retry 3 -o official_reference_data/PaSa/AutoScholarQuery/dev.jsonl \
  'https://huggingface.co/buckets/XK2026/pasa-dataset-bucket/resolve/AutoScholarQuery/dev.jsonl?download=true'
curl -L --fail --retry 3 -o official_reference_data/PaSa/AutoScholarQuery/test.jsonl \
  'https://huggingface.co/buckets/XK2026/pasa-dataset-bucket/resolve/AutoScholarQuery/test.jsonl?download=true'
```

如果 bucket 对象名有变化，打开 bucket 页面查看对象路径后替换 `<对象路径>`；不要把下载结果提交回 GitHub。

## 3. 恢复并校验 train

不要覆盖已有文件。使用仓库脚本以 staging 文件下载，并在完整 JSON、qid 连续性、非空答案 ID、字节数和 SHA-256 全部通过后原子提升：

```bash
python scripts/recover_pasa_autoscholar_train.py \
  --repo XK2026/pasa-dataset-bucket \
  --filename AutoScholarQuery/train.jsonl \
  --expected-records 33551 \
  --out official_reference_data/PaSa/AutoScholarQuery/train.recovered.jsonl
```

脚本会生成同名 `.manifest.json`。已核对的权威版本 SHA-256 为：

`fe5a776c3fea0fa4189a3df83e9fb6508b2edc31180d0c902c71293a27d57821`

manifest 中应记录来源 revision、etag、关联大小、实际字节数、记录数和校验结果。

## 4. 本地论文库与索引

论文库、BM25/FTS、MiniLM/BGE/SPECTER2 向量和模型权重均为本地生成产物，默认放在 `data/pasa/` 与 `data/models/`，不进 GitHub。先按机器显存选择配置，再运行对应的 `build_*` 脚本；RTX 3050 4GB 只使用串行 MiniLM/BGE 推理，禁止把 7B PPO/LoRA 当作复现前置条件。

## 5. 评测纪律与命令

```bash
python tests/run_tests.py
python scripts/audit_pasa_autoscholar_splits.py \
  --train official_reference_data/PaSa/AutoScholarQuery/train.recovered.jsonl \
  --dev official_reference_data/PaSa/AutoScholarQuery/dev.jsonl \
  --test official_reference_data/PaSa/AutoScholarQuery/test.jsonl
```

训练和内部验证只能读取 train；dev800-999 必须在排名冻结后读取答案；test 只用于最终导出。官方输出应由本地论文库提供 title/arXiv ID，保留 top-100，分数严格递减，F1-Gate 输出严格是排序前缀。

```bash
python scripts/run_public.py \
  --data official_reference_data/PaSa/AutoScholarQuery/test.jsonl \
  --profile cloud --offset 0 --limit 1000 \
  --api-budget 8 --llm-budget 2
```

严禁将 API key 写入仓库、zip、缓存、trace 或评测结果；使用 `DASHSCOPE_API_KEY` 等环境变量注入。
