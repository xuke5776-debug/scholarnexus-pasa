.PHONY: fixture test eval ablation public serve demo check build

fixture:      ## 生成离线评测语料
	python scripts/make_fixture.py --out data/fixture

test: fixture ## 运行测试套件（零依赖）
	python tests/run_tests.py

eval: fixture ## 离线评测
	python scripts/run_eval.py --profile offline

ablation: fixture ## 完整消融对照
	python scripts/run_eval.py --profile offline --ablation

public: ## 公开 SPAR 小样本评测（需要联网）
	python scripts/run_public.py --profile cloud --limit 10

serve: fixture ## 启动审计界面（离线语料）
	SN_CORPUS=data/fixture/corpus.jsonl python -m scholarnexus.server --profile offline

check:        ## 真实 API 连通性自检
	python scripts/run_real.py --check

demo:         ## 真实 API 单查询演示
	python scripts/run_real.py --demo

build: ## 构建 wheel
	python -m build
