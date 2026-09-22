from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from dataquery_agent import (  # noqa: E402
    OpenAICompatibleClient,
    QueryPipeline,
    QueryRouter,
    QwenSqlGenerator,
    ReadOnlySqlGuard,
)
from dataquery_agent.ui_support import attempts_for_display, format_display_rows, load_demo_records  # noqa: E402


st.set_page_config(page_title="DataQuery Agent", page_icon="◆", layout="wide")
st.markdown(
    """
    <style>
    .stApp {background: #f5f6f2; color: #17211b;}
    .block-container {max-width: 1180px; padding-top: 2.2rem;}
    .hero {padding: 28px 32px; border: 1px solid #dfe4dc; border-radius: 22px;
           background: linear-gradient(135deg,#ffffff 0%,#edf4ee 100%); margin-bottom: 22px;}
    .eyebrow {font-size: 12px; letter-spacing: .14em; color: #55705e; font-weight: 700;}
    .hero h1 {font-size: 42px; margin: 8px 0 6px; letter-spacing: -.03em;}
    .hero p {color: #667069; margin: 0; max-width: 760px;}
    .status {display:inline-block; padding:5px 10px; border-radius:99px;
             background:#e0eee3; color:#245a38; font-size:13px; font-weight:700;}
    [data-testid="stMetric"] {background:#fff; border:1px solid #e0e4de; padding:14px; border-radius:16px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="hero">
      <div class="eyebrow">COMMERCIAL REAL ESTATE · TEXT TO SQL</div>
      <h1>DataQuery Agent</h1>
      <p>先确认业务口径，再生成、校验和执行只读 SQL。默认展示已保存的去敏开发记录，不产生模型费用。</p>
    </section>
    """,
    unsafe_allow_html=True,
)

router = QueryRouter.from_project_root(ROOT)
guard = ReadOnlySqlGuard(ROOT / "data" / "generated" / "commercial_real_estate.sqlite3")
records = load_demo_records(ROOT)
_, city_rows = guard.execute("SELECT DISTINCT city FROM properties ORDER BY city")
available_cities = "、".join(str(row[0]) for row in city_rows)

with st.sidebar:
    st.header("运行方式")
    mode = st.radio("选择模式", ("已验证 Demo", "本地规则体验", "Live Qwen"))
    st.caption("Demo 与规则体验均不联网；Live 模式会发送 Schema、指标定义和当前问题。")
    st.divider()
    st.markdown("**当前验证边界**")
    st.write("5 条可执行 development 查询")
    st.write("8 条 holdout 尚未运行")
    st.write("只读 SQLite + 最多 3 次修正")


def render_route(route: dict[str, object], show_disclosures: bool = True) -> None:
    labels = {
        "execute": "可以查询",
        "execute_with_disclosure": "披露口径后查询",
        "clarify": "需要补充",
        "reject": "无法执行",
    }
    st.markdown(f'<span class="status">{labels.get(str(route.get("action")), "已判断")}</span>', unsafe_allow_html=True)
    if route.get("action") in {"clarify", "reject"}:
        st.info(str(route.get("message", "")))
    if show_disclosures:
        for disclosure in route.get("disclosures", []):
            st.warning(f"说明：{disclosure}")


def render_result(columns: list[str], rows: list[list[object]]) -> None:
    if rows:
        st.dataframe(pd.DataFrame(format_display_rows(rows), columns=columns), width="stretch", hide_index=True)
    else:
        message = "查询已完成，但当前条件下没有数据。"
        if available_cities:
            message += f" 当前数据覆盖的城市有：{available_cities}。"
        st.info(message)


if mode == "已验证 Demo":
    if not records:
        st.error("尚未找到已保存的 Phase 3 Demo 记录。")
    else:
        selected = st.selectbox(
            "选择一个演示问题",
            records,
            format_func=lambda record: f"{record.case_id} · {record.question}",
        )
        route = selected.trace["route"]
        render_route(route)
        st.caption(selected.evidence_label)
        if selected.status == "failed" or selected.trace.get("recovered"):
            st.info(str(selected.trace["user_message"]))
        if route.get("options"):
            st.markdown("**可选项：**")
            for option in route["options"]:
                st.write(f"- {option['label']}")
        left, middle, right = st.columns(3)
        status_labels = {"succeeded": "完成", "failed": "未完成", "clarify": "待补充", "reject": "已拒绝"}
        left.metric("执行状态", status_labels.get(selected.status, selected.status))
        middle.metric("尝试次数", len(selected.trace.get("attempts", [])))
        match_label = "是" if selected.strict_row_match is True else ("否" if selected.strict_row_match is False else "不适用")
        right.metric("结果通过离线核验", match_label)
        if selected.status == "succeeded":
            st.subheader("查询结果")
            render_result(selected.columns, selected.rows)
        if selected.final_sql:
            with st.expander("查看生成的 SQL"):
                st.code(selected.final_sql, language="sql")
        if selected.trace.get("attempts"):
            with st.expander("查看执行 Trace"):
                st.dataframe(pd.DataFrame(attempts_for_display(selected.trace)), width="stretch", hide_index=True)
                st.caption("Trace 已去敏，不包含 API Key、请求头或服务地址。")

elif mode == "本地规则体验":
    question = st.text_input("输入业务问题", placeholder="例如：上海上个月的收入是多少？")
    if st.button("判断是否可以查询", type="primary", disabled=not question.strip()):
        decision = router.route(question)
        render_route(decision.to_dict())
        if decision.options:
            st.markdown("**请选择或补充：**")
            for option in decision.options:
                st.write(f"- {option.label}")
        if decision.action in {"execute", "execute_with_disclosure"}:
            st.caption("该问题已通过本地口径判断。此模式不会调用模型或生成 SQL。")

else:
    st.warning("Live 模式会调用外部 Qwen API。请确认当前环境变量已安全配置。")
    question = st.text_input("输入要实际查询的问题", placeholder="例如：2026年8月每个项目的租金收缴率是多少？")
    consent = st.checkbox("我确认发送当前问题、Schema 和指标定义到已配置的 Qwen API")
    ready = bool(os.environ.get("LLM_API_KEY"))
    if not ready:
        st.info("尚未检测到 LLM_API_KEY。请在启动 Streamlit 前通过私有环境变量配置，不要粘贴到页面。")
    if st.button("执行只读查询", type="primary", disabled=not (question.strip() and consent and ready)):
        with st.spinner("正在生成并安全执行查询…"):
            pipeline = QueryPipeline(
                router,
                QwenSqlGenerator(OpenAICompatibleClient.from_environment(), ROOT),
                guard,
                max_attempts=3,
            )
            run = pipeline.run(question)
        render_route(run.route.to_dict(), show_disclosures=False)
        if run.user_message:
            st.info(run.user_message)
        if run.status == "succeeded":
            render_result(list(run.columns), [list(row) for row in run.rows])
        if run.attempts:
            with st.expander("查看 SQL 与执行 Trace"):
                st.code(run.attempts[-1].sql, language="sql")
                st.dataframe(pd.DataFrame(attempts_for_display(run.to_dict())), width="stretch", hide_index=True)

st.divider()
st.caption("个人作品集原型 · 合成商业地产数据 · development 结果不代表通用准确率")
