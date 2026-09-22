from __future__ import annotations

import json
from pathlib import Path

from .model_client import OpenAICompatibleClient, parse_json_object
from .pipeline import GenerationRequest, SqlCandidate


class QwenSqlGenerator:
    """OpenAI-compatible adapter for the tested Phase 3 generator protocol."""

    def __init__(
        self,
        client: OpenAICompatibleClient,
        project_root: Path,
        max_tokens: int = 1200,
    ) -> None:
        self.client = client
        self.project_root = project_root
        self.max_tokens = max_tokens
        self.schema = (project_root / "data" / "schema.sql").read_text(encoding="utf-8")
        self.catalog = json.loads(
            (project_root / "data" / "metric_catalog.json").read_text(encoding="utf-8")
        )

    def generate(self, request: GenerationRequest) -> SqlCandidate:
        relevant_metrics = [
            metric
            for metric in self.catalog["metrics"]
            if metric["id"] in request.route.metric_ids
        ]
        payload: dict[str, object] = {
            "question": request.question,
            "attempt_number": request.attempt_number,
            "fixed_as_of_date": self.catalog["as_of_date"],
            "route": request.route.to_dict(),
            "relevant_metrics": relevant_metrics,
            "field_conventions": {
                "date_storage": "所有日期字段使用 YYYY-MM-DD 文本格式",
                "month_storage": "billing_month 与 expense_month 使用每月第一天，例如 2026-08-01",
                "money": "金额字段为人民币数值",
            },
            "schema": self.schema,
        }
        if request.feedback:
            payload["correction"] = {
                "error_type": request.feedback.error_type,
                "message": request.feedback.message,
                "previous_sql": request.feedback.previous_sql,
                "constraint": "只修正错误，不改变问题的指标、时间、过滤、分组或排序口径。",
            }
        response = self.client.chat(
            system=(
                "你是商业地产数据分析助手。只为 SQLite 生成一条只读 SELECT 或 WITH 查询。"
                "只能使用给定 Schema 和指标定义，不得编造表、字段或指标，不得使用 SELECT *。"
                "只返回 JSON 对象：{\"sql\":\"...\",\"summary\":\"一句中文口径说明\"}。"
            ),
            user=json.dumps(payload, ensure_ascii=False),
            max_tokens=self.max_tokens,
        )
        parsed = parse_json_object(response.content)
        sql = parsed.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            raise ValueError("Model output did not contain non-empty SQL")
        summary = parsed.get("summary", "")
        return SqlCandidate(
            sql=sql.strip(),
            summary=summary if isinstance(summary, str) else "",
            model=response.model,
            generation_ms=response.latency_ms,
        )
