# DataQuery Agent

一个面向商业地产运营场景的可评测 Text-to-SQL 原型。系统先判断业务指标是否明确，再生成、校验、执行并在必要时修正 SQL。

普通 Text-to-SQL 容易因指标口径歧义、字段幻觉和不友好的报错在业务场景中失效，本项目针对这三类问题设计可审计的处理链路。

## 当前状态

当前已完成数据与评测地基、离线行为路由、只读 SQL 防护、可追踪纠错链路和 development-only 端到端真实运行，并提供本地 Streamlit Demo。

- 6 张独立设计的商业地产业务表
- 确定性规则与固定随机种子结合的合成数据生成器
- 指标口径字典与歧义处理规则
- 24 条 v2 评测题，覆盖执行、披露、澄清和拒绝
- 数据质量、业务约束和 Gold SQL 自动校验（Gold SQL 是每道题人工核对的标准查询及结果）
- 四路行为判断：执行、披露后执行、澄清、拒绝
- 结构化中文澄清选项、口径披露和安全拒绝原因
- v2.0.1 评测：16 条开发题覆盖全部主要规则，8 条留出题（holdout，未运行、不报告成绩）保持冻结
- SQL 只读三层防护：语句预检、只读连接、SQLite authorizer
- Qwen 两题冒烟测试与一次有记录的提示词修正
- 5 条可执行开发题首次执行成功并严格匹配 v2.0.1 Gold
- 每次 SQL 尝试记录阶段、错误、恢复状态、结果和耗时
- 默认离线的 Streamlit Demo，以及需二次确认的可选 Live 模式

当前 5 条端到端真实运行均首次成功，因此多轮纠错只通过构造场景的自动化测试验证，尚无真实纠错成功率。8 条 holdout 仍保持隔离。

完整的验证范围、结果证据和未验证边界见[评测报告](docs/EVALUATION_REPORT.md)。

## 快速开始

核心验证仅需 Python 3.11+；运行 UI 需安装 `requirements.txt`。

```powershell
python scripts/generate_synthetic_data.py
python scripts/validate_phase1.py
python -m unittest discover -s tests -v
python scripts/evaluate_router.py
python scripts/route_query.py "上海上个月的收入是多少？"
```

启动默认离线 UI：

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Phase 2B 的模型测试默认不运行，需要本地私有 `.env`。已保存的去敏结果位于 `evaluation/results/`，不包含 API Key。

生成结果位于 `data/generated/`。SQLite 数据库不会提交到 Git，可随时由脚本重建；小型 CSV 数据可用于人工查看。

## 项目边界

本仓库是从空目录开始的独立实现。业务领域、表结构、字段、合成数据、指标字典、评测题和代码均为本项目重新设计，不包含任何第三方专有问数项目的代码、提示词、数据、截图或实验结果。

详见 [独立性与公开边界](docs/PROVENANCE.md) 和 [产品范围](docs/PRODUCT_SCOPE.md)。
