# Phase 2A 行为路由

> 历史演示版本文档。下文保留该阶段原始表述；最新版代码、结果与范围见[版本与数据索引](VERSION_INDEX.md)，演进关系见[迭代历史](ITERATION_HISTORY.md)。


Phase 2A 在调用大模型或生成 SQL 之前运行。它是一个确定性的业务预检层，不消耗模型 Token；真正的数据库安全边界由独立 SQL 只读校验和只读连接承担。

## 四种结果

| Action | 含义 | 后续动作 |
|---|---|---|
| `execute` | 指标、对象和口径已经明确 | 允许进入后续 SQL 生成 |
| `execute_with_disclosure` | 存在可安全采用的默认口径 | 允许继续，但必须向用户展示口径说明 |
| `clarify` | 不同选择会实质改变问题含义 | 返回中文问题和结构化选项，不生成 SQL |
| `reject` | 写操作、预测或数据范围不支持 | 返回业务化原因，不生成 SQL |

## 决策顺序

1. 危险写操作和明确不支持能力优先拒绝。
2. 检查收入、利润、NOI、最好、最近、大客户等业务歧义。
3. 使用 `data/metric_catalog.json` 匹配受支持指标。
4. 根据 `data/behavior_policy.json` 判断是否附带口径披露。
5. 非指标型但对象明确的租约、租户、铺位、项目查询可继续。
6. 只有同时具备清单意图和受支持实体时，非指标查询才可继续；其余未知请求要求补充信息。

即使路由允许执行，下游仍必须经过 `ReadOnlySqlGuard`：只允许单条 `SELECT/WITH`，拒绝注释、多语句、写入和数据库管理关键字，并通过 SQLite 只读连接与 authorizer 再次限制。

路由结果是结构化对象，包含 `action`、`reason_code`、`message`、`metric_ids`、`options` 和 `disclosures`，便于后续 API、界面和评测复用。

## 防止评测泄漏

- v1.0.0 因审阅发现题面措辞进入早期规则，已归档并停止用于路由留出评测。
- v2.0.1 包含 16 条 development 题和 8 条保持冻结且未改动的 holdout 题。
- 每条主要路由规则至少由一条 development 题覆盖；holdout 不进入路由断言和实现调优。
- 长触发短语若只出现在 holdout 而未出现在 development，结构校验会失败。

## 本地验证

```powershell
python -m unittest discover -s tests -v
python scripts/evaluate_router.py
python scripts/route_query.py "上海上个月的收入是多少？"
```
