# 发布验证记录

验证日期：2026-08-19

| 项目 | 结果 |
|---|---|
| 零网络测试 | 44/44 通过 |
| Python compileall | 通过 |
| 离线 Macro-F1 | 0.5399 |
| 离线 Macro Precision / Recall | 0.4135 / 0.8436 |
| 离线平均 LLM 调用 | 1.86 |
| 离线平均 tokens | 1082.8 |
| SPAR 文件解析 | 1000/1000 条通过 |
| 300字简介 | 252 字符 |
| wheel 构建与隔离安装 | 通过 |
| 安装后静态界面读取 | 通过 |
| HTTP `/health` 与 `/retrieve` | 通过 |
| 源码密钥扫描 | 未发现真实密钥 |

复现命令：

```bash
python tests/run_tests.py
python scripts/run_eval.py --profile offline
python scripts/run_eval.py --profile offline --ablation
PIP_NO_INDEX=1 python -m pip wheel . --no-deps --no-build-isolation -w dist
```

限制：当前F1为合成回归夹具成绩；真实SPAR成绩须配置有效学术API与千问密钥后运行，
不得用本记录替代公开测试结果。
