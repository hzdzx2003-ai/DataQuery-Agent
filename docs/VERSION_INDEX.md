# 版本与数据索引

更新：2026-10-06。此表将代码、配置、评测范围和结果对应起来；各行是不同验证，不合并分母。

| 角色 | 版本 / 配置 | 范围与结果 | 证据入口 |
|---|---|---|---|
| 当前质量发布包 | `nl-v3-diagnostic100-20261005-1`；qwen3.7-max，thinking=true，budget4096 | 固定100题，93完整通过；70查询、13澄清、10拒绝 | [代码与命令](../releases/nl-v3-93/README.md) · [逐题判定](../releases/nl-v3-93/evaluation/judgments.json) |
| 固定后端 | `nl-v3-fixed-backend-1` | 保存计划在合成数据回放，70/70查询结果匹配 | [执行结果](../releases/nl-v3-93/evaluation/backend_results.json) · [参考结果](../releases/nl-v3-93/evaluation/expected_query_results.json) |
| 整体升级历史对照 | 历史Plus → 后续Max，代码与模型均有变化 | 同57题完整通过41→54；严格口径相对提升31.7% | [范围、公式及判定敏感性](EVALUATION_202610.md) |
| 性能实验 | `nl-v3-nothinking100-1`；Max，thinking=false | 同100题91完整通过，平均模型任务耗时5.09秒 | [实验数据](../experiments/no-thinking-100/README.md) |
| 开/关思考配对实验 | Max，固定20题 | 两组均17/20；平均任务耗时13.81→5.81秒 | [计时方法](EVALUATION_202610.md) |
| 历史演示与基础评测 | 根目录Streamlit、evaluation v2.0.1 | 24题评测基础；5题开发查询5/5匹配 | [历史报告](EVALUATION_REPORT.md) · [验证记录](VERIFIED_RESULTS.md) |

## 数据核对入口

- [100题及Gold](../releases/nl-v3-93/SINGLE_TASK_GOLD_REVIEWED_V1.json)
- [100题保存输出](../releases/nl-v3-93/evaluation/decisions.json)
- [完整、部分、失败的逐题判定](../releases/nl-v3-93/evaluation/judgments.json)
- [发布文件指纹](../releases/nl-v3-93/MANIFEST.json)
- [早期证据指纹索引](../evaluation/portfolio-evidence-20261006-v1.json)
- [产品迭代过程](ITERATION_HISTORY.md)

完整通过计数来自项目维护者对固定Gold的逐题复核，部分正确不计通过；离线验证程序复算计数、文件一致性、查询槽位和保存的数值结果。质量发布包、性能实验、历史演示各自对应以上版本，历史描述不自动延伸为当前状态。
