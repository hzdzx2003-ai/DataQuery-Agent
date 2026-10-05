# DataQuery NL-v3 · 93/100评测版本

面向商业地产业务人员的单任务自然语言问数：理解表达、校验业务结构、必要时澄清，由固定指标公式与参数化SQL执行。此目录为独立发布包，不替换仓库根目录的历史Streamlit演示。

## 成果与版本

| 验证 | 结果 |
|---|---:|
| 固定100题完整任务通过 | 93/100 |
| 70道明确查询计划 | 70/70 |
| 后端数值及清单回放 | 70/70 |

解析版本 `nl-v3-diagnostic100-20261005-1`：qwen3.7-max，思考开启、预算4096；后端 `nl-v3-fixed-backend-1`。100题包括70查询、20澄清、10拒绝。原始人工复核判定为93完整、2部分、5失败，部分不给完整分。后端在保存的模型计划上回放合成数据；本包提供逐题输出及判定，便于检查评测方法，不需要API Key。

## 快速验证

Python 3.11+，仅使用标准库。在本目录运行：

```shell
python -B verify_release.py
python -B -m unittest discover -p "test_*.py"
```

第一条命令校验发布指纹、100题对应关系、原判定计数、70个查询槽位与SQL编译，以及保存结果与参考结果的一致性。它不是用程序重新作出人工语义判定。

可选：在本目录生成完全虚构的数据，再执行只读回放（不连接业务数据库）：

```shell
python scripts/generate_synthetic_data.py
python -B verify_release.py --synthetic-db data/generated/commercial_real_estate.sqlite3
```

生成器会重建本目录 `data/generated` 下同名演示数据库；不要向该目录放入自己的数据。默认验证不执行SQL、不调用模型。

## 文件导航

- `json_resolver.py`、`conversation.py`：模型输出契约、理解与动作决策。
- `query_plan.py`、`time_scope.py`：目标、筛选、时间、分组和排序校验。
- `business_context.json`、`metric_definitions.json`：业务能力和指标口径。
- `fixed_backend/compiler.py`：固定表达式白名单与绑定参数。
- `fixed_backend/reference.py`：独立代码路径的参考计算器。
- `SINGLE_TASK_GOLD_REVIEWED_V1.json`：100题及完整Gold。
- `evaluation/decisions.json`：保存的100题模型处理结果。
- `evaluation/judgments.json`：逐题判定及理由。
- `evaluation/backend_results.json`、`expected_query_results.json`：执行回放及参考值。
- `MANIFEST.json`：发布文件及原始结果指纹。

解析与后端核心文件保持已测快照字节；发布入口和便携文档为新增。已知案例用于版本复核；[整体评测与性能实验](../../docs/EVALUATION_202610.md)分别报告质量配置与低延迟配置。本包不包含凭据、HTTP原始交换或个人目录。
