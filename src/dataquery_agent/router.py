from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


Action = Literal["execute", "execute_with_disclosure", "clarify", "reject"]


@dataclass(frozen=True)
class ClarificationOption:
    id: str
    label: str
    type: Literal["choice", "input", "action"] = "choice"


@dataclass(frozen=True)
class RouteDecision:
    action: Action
    reason_code: str
    message: str
    metric_ids: tuple[str, ...] = ()
    options: tuple[ClarificationOption, ...] = ()
    disclosures: tuple[str, ...] = ()
    matched_terms: tuple[str, ...] = ()
    policy_version: str = ""
    catalog_version: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def require_executable(decision: RouteDecision) -> RouteDecision:
    """Hard boundary preventing clarify/reject decisions from reaching SQL generation."""
    if decision.action not in {"execute", "execute_with_disclosure"}:
        raise ValueError(f"Decision {decision.action!r} is not executable")
    return decision


class QueryRouter:
    """Deterministic Phase 2A guardrail before any LLM or SQL generation."""

    def __init__(self, metric_catalog_path: Path, policy_path: Path) -> None:
        self.catalog = json.loads(metric_catalog_path.read_text(encoding="utf-8"))
        self.policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.metrics = {metric["id"]: metric for metric in self.catalog["metrics"]}
        self.metric_terms = self._build_metric_terms()

    @classmethod
    def from_project_root(cls, project_root: Path) -> "QueryRouter":
        return cls(
            project_root / "data" / "metric_catalog.json",
            project_root / "data" / "behavior_policy.json",
        )

    def route(self, question: str) -> RouteDecision:
        normalized = self._normalize(question)
        if not normalized:
            return self._clarify("empty_question")

        rejection = self._match_rejection(normalized)
        if rejection:
            return rejection

        metric_ids, matched_terms = self._match_metrics(normalized)
        clarification = self._match_clarification(normalized, metric_ids)
        if clarification:
            return clarification

        if metric_ids:
            disclosures = self._required_disclosures(normalized, metric_ids)
            if disclosures:
                return RouteDecision(
                    action="execute_with_disclosure",
                    reason_code="metric_default_disclosed",
                    message="可以查询；执行时会明确说明采用的指标口径。",
                    metric_ids=metric_ids,
                    disclosures=disclosures,
                    matched_terms=matched_terms,
                    **self._versions(),
                )
            return RouteDecision(
                action="execute",
                reason_code="supported_metric",
                message="问题口径明确，可以进入 SQL 生成。",
                metric_ids=metric_ids,
                matched_terms=matched_terms,
                **self._versions(),
            )

        has_entity = any(term in normalized for term in self.policy["supported_entity_terms"])
        has_list_intent = any(term in normalized for term in self.policy["list_intent_terms"])
        has_metric_shape = any(term in normalized for term in self.policy["metric_shape_terms"])
        if has_entity and has_list_intent and not has_metric_shape:
            return RouteDecision(
                action="execute",
                reason_code="supported_entity_query",
                message="问题对象和范围明确，可以进入 SQL 生成。",
                **self._versions(),
            )

        return self._clarify("unknown_request")

    def _build_metric_terms(self) -> tuple[tuple[str, str], ...]:
        terms: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for metric_id, metric in self.metrics.items():
            for name in [metric["name_zh"], *metric.get("synonyms", [])]:
                item = (self._normalize(name), metric_id)
                if item not in seen:
                    seen.add(item)
                    terms.append(item)
        return tuple(sorted(terms, key=lambda item: (-len(item[0]), item[0], item[1])))

    def _match_rejection(self, question: str) -> RouteDecision | None:
        if self._is_dangerous_write(question):
            return self._reject("dangerous_write")
        for rule in self.policy["unsupported_basis_rules"]:
            if all(any(term in question for term in group) for group in rule["all_term_groups"]):
                return RouteDecision(
                    action="reject",
                    reason_code=rule["id"],
                    message=rule["message"],
                    **self._versions(),
                )
        unsupported = tuple(
            term for term in self.policy["unsupported_metric_terms"] if term in question
        )
        if unsupported:
            return RouteDecision(
                action="reject",
                reason_code="unsupported_metric",
                message=self.policy["unsupported_metric_message"],
                matched_terms=unsupported,
                **self._versions(),
            )
        for rule in self.policy["rejection_rules"]:
            if any(term in question for term in rule["terms"]):
                return RouteDecision(
                    action="reject",
                    reason_code=rule["id"],
                    message=rule["message"],
                    **self._versions(),
                )
        return None

    def _match_clarification(
        self, question: str, metric_ids: tuple[str, ...]
    ) -> RouteDecision | None:
        rules = self.policy["clarification_rules"]
        if any(term in question for term in rules["profit_scope"]["terms"]):
            return self._clarify("profit_scope")
        if (
            any(term in question for term in rules["best_performance"]["terms"])
            and not metric_ids
        ):
            return self._clarify("best_performance")
        if (
            any(term in question for term in rules["arrears_priority"]["subject_terms"])
            and any(term in question for term in rules["arrears_priority"]["severity_terms"])
        ):
            return self._clarify("arrears_priority")
        if (
            any(term in question for term in rules["key_customer"]["subject_terms"])
            and any(term in question for term in rules["key_customer"]["degree_terms"])
        ):
            return self._clarify("key_customer")
        if self._has_ambiguous_tenant_city(question):
            return self._clarify("tenant_city_dimension")
        if self._has_unspecified_recent_window(question):
            return self._clarify("recent_window")
        if "noi" in question and not any(
            term in question for term in ("现金noi", "现金净运营收益", "现金净运营收入")
        ):
            return self._clarify("noi_scope")
        if (
            any(term in question for term in rules["income_scope"]["terms"])
            and not set(metric_ids) & {"rent_due", "rent_collected", "cash_noi_proxy"}
        ):
            return self._clarify("income_scope")
        return None

    def _match_metrics(self, question: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        matched: list[str] = []
        matched_terms: list[str] = []
        occupied: set[int] = set()
        for term, metric_id in self.metric_terms:
            for occurrence in re.finditer(re.escape(term), question):
                span = set(range(occurrence.start(), occurrence.end()))
                if span & occupied:
                    continue
                occupied.update(span)
                if metric_id not in matched:
                    matched.append(metric_id)
                if term not in matched_terms:
                    matched_terms.append(term)
        return tuple(matched), tuple(matched_terms)

    def _required_disclosures(
        self, question: str, metric_ids: tuple[str, ...]
    ) -> tuple[str, ...]:
        messages: list[str] = []
        for metric_id in metric_ids:
            metric = self.metrics[metric_id]
            if not metric.get("disclosure_required"):
                continue
            if metric_id == "occupancy_rate" and self._occupancy_is_explicit(question):
                continue
            disclosure = self.policy["disclosures"].get(metric_id)
            if disclosure and disclosure not in messages:
                messages.append(disclosure)
        return tuple(messages)

    @staticmethod
    def _occupancy_is_explicit(question: str) -> bool:
        has_area_basis = "按面积" in question or "面积出租率" in question
        has_point_in_time = "截至" in question or bool(
            re.search(r"\d{4}年\d{1,2}月\d{1,2}日", question)
        )
        return has_area_basis and has_point_in_time

    def _clarify(self, rule_id: str) -> RouteDecision:
        rule = self.policy["clarification_rules"][rule_id]
        options = tuple(
            ClarificationOption(
                id=option["id"],
                label=option["label"],
                type=option.get("type", "choice"),
            )
            for option in rule.get("options", [])
        )
        return RouteDecision(
            action="clarify",
            reason_code=rule_id,
            message=rule["message"],
            options=options,
            **self._versions(),
        )

    def _reject(self, rule_id: str) -> RouteDecision:
        rule = next(rule for rule in self.policy["rejection_rules"] if rule["id"] == rule_id)
        return RouteDecision(
            action="reject",
            reason_code=rule_id,
            message=rule["message"],
            **self._versions(),
        )

    def _versions(self) -> dict[str, str]:
        return {
            "policy_version": self.policy["version"],
            "catalog_version": self.catalog.get("version", "unversioned"),
        }

    def _is_dangerous_write(self, question: str) -> bool:
        if any(
            keyword in question
            for keyword in (
                "delete",
                "drop",
                "truncate",
                "alter",
                "insert",
                "update",
                "replace",
                "attach",
                "detach",
                "pragma",
            )
        ):
            return True
        destructive = r"(删除|删掉|抹掉|清除|移除|清空)"
        mutation = r"(改成|改为|调整为|更新为|修改为|设为|设置为)"
        creation = r"(新增|添加|插入|创建).{0,12}(记录|数据|租约|账单|行|表)"
        query_adjustment = r"(查询条件|统计口径|查询口径|汇总方式|展示方式|分组方式|按季度汇总|按月汇总|按月份|按面积)"
        data_object_mutation = r"(记录|数据|表|租约|账单|月租金|金额|状态|日期|费用).{0,12}" + mutation
        mutation_before_object = mutation + r".{0,12}(记录|数据|表|租约|账单|月租金|金额|状态|日期|费用)"
        explicit_field_assignment = r"(修改|调整|更新).{0,12}(月租金|金额|状态|日期|费用).{0,4}(为|成)"
        mutates_data = bool(
            re.search(data_object_mutation, question)
            or re.search(mutation_before_object, question)
            or re.search(explicit_field_assignment, question)
        )
        if re.search(query_adjustment, question) and not mutates_data:
            return False
        return bool(re.search(destructive, question) or mutates_data or re.search(creation, question))

    def _has_ambiguous_tenant_city(self, question: str) -> bool:
        if "租户" not in question:
            return False
        if "项目所在城市" in question or "注册城市" in question:
            return False
        return any(city in question for city in self.policy["city_terms"])

    @staticmethod
    def _has_unspecified_recent_window(question: str) -> bool:
        if "最近" not in question or re.search(r"离.{0,4}最近", question):
            return False
        number = r"(?:\d+|[一二两三四五六七八九十百]+|半|一)"
        if re.search(rf"最近{number}(?:天|日|周|个月|月|季度|年)", question):
            return False
        return True

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text).lower()
        normalized = normalized.translate(str.maketrans({"刪": "删", "調": "调", "為": "为"}))
        return "".join(
            char
            for char in normalized
            if not char.isspace() and unicodedata.category(char) != "Cf"
        )
