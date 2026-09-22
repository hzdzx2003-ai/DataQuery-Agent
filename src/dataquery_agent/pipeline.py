from __future__ import annotations

import sqlite3
import time
from dataclasses import asdict, dataclass, replace
from typing import Protocol

from .router import QueryRouter, RouteDecision, require_executable
from .sql_guard import ReadOnlySqlGuard, SqlGuardError


@dataclass(frozen=True)
class CorrectionFeedback:
    error_type: str
    message: str
    previous_sql: str


@dataclass(frozen=True)
class GenerationRequest:
    question: str
    route: RouteDecision
    attempt_number: int
    feedback: CorrectionFeedback | None = None


@dataclass(frozen=True)
class SqlCandidate:
    sql: str
    summary: str = ""
    model: str = ""
    generation_ms: int = 0


class SqlGenerator(Protocol):
    def generate(self, request: GenerationRequest) -> SqlCandidate: ...


@dataclass(frozen=True)
class AttemptTrace:
    attempt_number: int
    sql: str
    summary: str
    status: str
    error_type: str | None
    error_message: str | None
    execution_ms: int
    row_count: int | None
    columns: tuple[str, ...]
    model: str
    generation_ms: int
    failure_stage: str | None = None
    precheck_error: str | None = None
    execution_error: str | None = None
    recovered_later: bool = False


@dataclass(frozen=True)
class QueryRun:
    question: str
    route: RouteDecision
    status: str
    attempts: tuple[AttemptTrace, ...]
    columns: tuple[str, ...] = ()
    rows: tuple[tuple[object, ...], ...] = ()
    user_message: str = ""
    recovered: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class QueryPipeline:
    """Traceable route → generate → validate → execute → correct pipeline."""

    def __init__(
        self,
        router: QueryRouter,
        generator: SqlGenerator,
        guard: ReadOnlySqlGuard,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.router = router
        self.generator = generator
        self.guard = guard
        self.max_attempts = max_attempts

    def run(self, question: str) -> QueryRun:
        route = self.router.route(question)
        if route.action in {"clarify", "reject"}:
            return QueryRun(
                question=question,
                route=route,
                status=route.action,
                attempts=(),
                user_message=route.message,
            )
        require_executable(route)

        traces: list[AttemptTrace] = []
        feedback: CorrectionFeedback | None = None
        for attempt_number in range(1, self.max_attempts + 1):
            candidate = self.generator.generate(
                GenerationRequest(
                    question=question,
                    route=route,
                    attempt_number=attempt_number,
                    feedback=feedback,
                )
            )
            started = time.perf_counter()
            try:
                validated_sql = self.guard.validate(candidate.sql)
            except SqlGuardError as exc:
                elapsed = round((time.perf_counter() - started) * 1000)
                error_type = normalize_sql_error(str(exc))
                traces.append(
                    AttemptTrace(
                        attempt_number=attempt_number,
                        sql=candidate.sql,
                        summary=candidate.summary,
                        status="failed",
                        error_type=error_type,
                        error_message=str(exc),
                        execution_ms=elapsed,
                        row_count=None,
                        columns=(),
                        model=candidate.model,
                        generation_ms=candidate.generation_ms,
                        failure_stage="precheck",
                        precheck_error=str(exc),
                    )
                )
                feedback = CorrectionFeedback(
                    error_type=error_type,
                    message=safe_correction_message(error_type, str(exc)),
                    previous_sql=candidate.sql,
                )
                continue

            try:
                columns, rows = self.guard.execute(validated_sql)
            except (SqlGuardError, sqlite3.DatabaseError) as exc:
                elapsed = round((time.perf_counter() - started) * 1000)
                error_type = normalize_sql_error(str(exc))
                traces.append(
                    AttemptTrace(
                        attempt_number=attempt_number,
                        sql=candidate.sql,
                        summary=candidate.summary,
                        status="failed",
                        error_type=error_type,
                        error_message=str(exc),
                        execution_ms=elapsed,
                        row_count=None,
                        columns=(),
                        model=candidate.model,
                        generation_ms=candidate.generation_ms,
                        failure_stage="execution",
                        execution_error=str(exc),
                    )
                )
                feedback = CorrectionFeedback(
                    error_type=error_type,
                    message=safe_correction_message(error_type, str(exc)),
                    previous_sql=candidate.sql,
                )
                continue

            elapsed = round((time.perf_counter() - started) * 1000)
            traces.append(
                AttemptTrace(
                    attempt_number=attempt_number,
                    sql=candidate.sql,
                    summary=candidate.summary,
                    status="succeeded",
                    error_type=None,
                    error_message=None,
                    execution_ms=elapsed,
                    row_count=len(rows),
                    columns=tuple(columns),
                    model=candidate.model,
                    generation_ms=candidate.generation_ms,
                )
            )
            recovered = any(trace.status == "failed" for trace in traces[:-1])
            if recovered:
                traces = [
                    replace(trace, recovered_later=True) if trace.status == "failed" else trace
                    for trace in traces
                ]
            messages: list[str] = []
            if recovered:
                messages.append("第一次生成的查询未成功，系统已自动修正后完成。")
            if route.disclosures:
                messages.append("说明：" + " ".join(route.disclosures))
            return QueryRun(
                question=question,
                route=route,
                status="succeeded",
                attempts=tuple(traces),
                columns=tuple(columns),
                rows=tuple(tuple(row) for row in rows),
                user_message=" ".join(messages),
                recovered=recovered,
            )

        return QueryRun(
            question=question,
            route=route,
            status="failed",
            attempts=tuple(traces),
            user_message=(
                f"这个问题没有查出来：系统自动修正了 {self.max_attempts} 次仍未成功。"
                "你可以换个问法，例如明确指标和时间范围后再试。"
            ),
        )


def normalize_sql_error(message: str) -> str:
    lowered = message.lower()
    mappings = (
        ("unknown_table", ("no such table",)),
        ("unknown_column", ("no such column", "has no column named")),
        ("ambiguous_column", ("ambiguous column",)),
        ("invalid_join", ("join condition", "invalid join", "cannot join")),
        ("forbidden_operation", ("forbidden sql", "only select", "not allowed", "not authorized", "comments are not allowed", "only one sql")),
        ("syntax", ("syntax error", "incomplete input", "near ")),
        ("type_mismatch", ("datatype mismatch", "type mismatch")),
        ("empty_result", ("empty result", "no rows returned")),
        ("timeout", ("timed out", "timeout")),
    )
    for error_type, cues in mappings:
        if any(cue in lowered for cue in cues):
            return error_type
    return "other"


def safe_correction_message(error_type: str, original: str) -> str:
    guidance = {
        "unknown_table": "使用 Schema 中存在的表名，并保持原查询口径。",
        "unknown_column": "使用 Schema 中存在的字段和别名，并保持原查询口径。",
        "ambiguous_column": "为歧义字段补充正确的表别名。",
        "invalid_join": "修正连接键或连接条件，但不要改变业务指标、过滤条件或分组。",
        "forbidden_operation": "只生成一条无注释的 SELECT 或 WITH 查询。",
        "syntax": "修正 SQLite 语法，但不要改变业务指标、过滤条件或分组。",
        "type_mismatch": "修正字段类型处理，但不要改变业务口径。",
        "empty_result": "查询已成功执行但没有返回记录；不要仅因空结果改写 SQL。",
        "timeout": "简化查询结构，同时保持相同业务口径。",
        "other": "根据执行错误修正 SQL，但不要改变业务口径。",
    }[error_type]
    compact = " ".join(original.split())[:300]
    return f"{guidance} 执行反馈：{compact}"
