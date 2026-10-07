"""Credential-free saved-case UI; frozen backend artifacts remain untouched."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import streamlit as st
from adapter import SavedCases, clarification_draft
from presentation import metric_display, display_rows, summary_lines

st.set_page_config(page_title='DataQuery · 商业地产问数', page_icon='◈', layout='wide')
st.markdown('''<style>
/* Leave surfaces and text to Streamlit's active theme, including its controls. */
.block-container {max-width:1180px;padding-top:2.5rem}
h1,h2,h3 {letter-spacing:-.025em}
[data-testid="stMetric"] {padding:1.2rem;border-radius:12px;border:1px solid currentColor}
.eyebrow {font-size:12px;letter-spacing:.18em;color:inherit;font-weight:700}
[data-testid="stMarkdownContainer"] h2.case-library-title {font-size:1.8rem !important;font-weight:700 !important;line-height:1.3 !important;margin:0 0 .5rem !important;padding:0 !important}
[data-testid="stMarkdownContainer"] h3.case-section-title {font-size:1.2rem !important;font-weight:600 !important;line-height:1.4 !important;margin:.6rem 0 .5rem !important;padding:0 !important}
[data-testid="stMarkdownContainer"] h4.case-card-title {font-size:1rem !important;font-weight:600 !important;line-height:1.4 !important;margin:0 0 .5rem !important;padding:0 !important}
</style>''', unsafe_allow_html=True)

try:
    store = SavedCases()
except (OSError, ValueError, KeyError):
    st.error('演示文件不可用或校验未通过。请恢复完整发布包后重试。')
    st.stop()

catalog = store.catalog()
labels = {'query_candidate': '数据查询', 'clarify': '口径确认', 'reject': '数据范围说明'}

def open_case(ident):
    st.session_state['record'] = store.open(ident)
    st.session_state.pop('clarification_draft', None)

def clear_result():
    st.session_state.pop('record', None)
    st.session_state.pop('clarification_draft', None)

with st.sidebar:
    st.title('◈ DataQuery')
    st.caption('商业地产 · 业务问数工作台')
    st.divider()
    st.markdown('**数据与能力**')
    st.caption('合成商业地产数据 · 基准日 2026-09-01\n\n固定指标公式 · 参数化查询 · 只读边界')
    st.caption('回放使用已保存的模型理解及结果，不调用模型或数据库。')

st.markdown('<div class="eyebrow">DATAQUERY · 商业地产问数</div>', unsafe_allow_html=True)
st.title('商业地产经营问数')
st.write('通过自然语言查询租金、出租情况与运营费用，查看统计口径和数据结果。')

with st.container(border=True):
    st.markdown('<h2 class="case-library-title">案例库</h2>', unsafe_allow_html=True)
    st.caption('查看推荐案例，或按处理类型筛选。以下内容为已保存的演示记录。')
    st.markdown('<h3 class="case-section-title">推荐案例</h3>', unsafe_allow_html=True)
    recommended = [
        ('query_candidate', '数据查询', '条件明确时，返回汇总指标、分组结果或明细清单。'),
        ('clarify', '口径确认', '时间、指标定义或筛选条件未明确时，先确认再查询。'),
        ('reject', '数据范围说明', '请求涉及当前未覆盖的数据时，说明缺失内容与查询限制。')]
    for column, (action, title, description) in zip(st.columns(3), recommended):
        sample = next(r for r in catalog if r['action'] == action)
        with column:
            with st.container(border=True):
                st.markdown('<h4 class="case-card-title">'+title+'</h4>', unsafe_allow_html=True)
                st.caption(description)
                st.write(sample['question'])
                st.button('查看案例', key='recommend_'+action, on_click=open_case, args=(sample['id'],), width='stretch')
    st.divider()
    st.markdown('<h3 class="case-section-title">全部案例</h3>', unsafe_allow_html=True)
    st.caption(f'共 {len(catalog)} 个案例 · 按处理类型筛选，选择问题后查看详情。')
    type_column, question_column = st.columns([1, 3])
    with type_column:
        category = st.selectbox('处理类型', ['全部类型', *labels.values()], key='category', on_change=clear_result)
    rows = [r for r in catalog if category == '全部类型' or labels.get(r['action']) == category]
    with question_column:
        chosen = st.selectbox('案例问题', [r['id'] for r in rows], key='case_picker',
                              format_func=lambda ident: next(r['question'] for r in rows if r['id'] == ident), on_change=clear_result)
    st.button('查看案例详情', key='open_case', on_click=open_case, args=(chosen,), type='primary')

with st.container(border=True):
    st.markdown('<h2 class="case-library-title">自定义查询</h2>', unsafe_allow_html=True)
    st.caption('输入查询需求，可指定项目、时间范围及关注的数据。')
    st.text_area('查询问题', key='own_question', placeholder='例如：澄明广场上个月应该收多少租金？')
    st.button('开始查询', key='live_submit', disabled=True)
    st.caption('实时查询暂未启用。输入内容仅保留在当前页面，不会发送或执行。')

record = st.session_state.get('record')
if not record:
    st.stop()

decision, result = record['decision'], record['result']
st.divider()
st.caption(f"保存案例 {record['id']} · 非实时查询")
st.subheader(record['question'])
summary, output = st.columns([1, 1.6], gap='large')
with summary:
    st.markdown('### 查询条件与统计口径')
    for line in summary_lines(decision):
        st.text(line)
with output:
    st.markdown('### 处理结果')
    if result['status'] == 'executed':
        values = result.get('rows') or []
        st.caption('保存的固定后端结果 · 合成数据')
        if len(values) == 1 and set(values[0]) == {'value'}:
            value = values[0]['value']
            title, formatted = metric_display(decision, value)
            st.metric(title, formatted)
        elif values:
            st.dataframe(display_rows(decision, values), width='stretch', hide_index=True)
            st.caption(f'共 {len(values)} 条结果；下载文件保留原始数值与字段。')
        else:
            st.info('查询结果为空，没有符合条件的记录。')
        st.download_button('下载结果 JSON', json.dumps(values, ensure_ascii=False, indent=2),
                           file_name=record['id']+'_result.json', mime='application/json')
    elif decision['action'] == 'clarify':
        st.warning('补充必要条件后才能查询。')
        for request in decision.get('requests', []):
            clarification = request.get('clarification', {})
            if clarification:
                st.write(clarification['question'])
                for choice in clarification.get('choices', []):
                    st.write('• '+choice['label'])
        with st.form('clarification_'+record['id']):
            answer = st.text_input('补充说明')
            if st.form_submit_button('保留补充说明', key='save_clarification'):
                if answer.strip():
                    st.session_state['clarification_draft'] = clarification_draft(record['question'], answer)
                else:
                    st.warning('请填写待确认的条件。')
        if st.session_state.get('clarification_draft'):
            st.info('补充说明已保留在当前会话。离线回放不重新解析，也不会执行候选方案。')
            st.json(st.session_state['clarification_draft'])
    else:
        st.info('本次没有执行查询。请查看左侧的能力边界或处理说明。')
with st.expander('查看技术详情与版本'):
    st.caption(record['version'])
    if result.get('sql'):
        st.code(result['sql'], language='sql')
        st.json(result.get('parameters', []))
    st.json(decision)
