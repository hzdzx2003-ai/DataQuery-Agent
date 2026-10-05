"""Credential-free saved-case UI; frozen backend artifacts remain untouched."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import streamlit as st
from adapter import SavedCases, clarification_draft
from presentation import metric_display, display_rows

st.set_page_config(page_title='DataQuery · 商业地产问数', page_icon='◈', layout='wide')
st.markdown('''<style>
.stApp {background:#f5f6f2;color:#18322d}
.block-container {max-width:1180px;padding-top:2.5rem}
h1,h2,h3 {letter-spacing:-.025em}
[data-testid="stSidebar"] {background:#e8eee8}
[data-testid="stMetric"] {background:white;padding:1.2rem;border-radius:12px}
.eyebrow {font-size:12px;letter-spacing:.18em;color:#54796e;font-weight:700}
</style>''', unsafe_allow_html=True)

try:
    store = SavedCases()
except (OSError, ValueError, KeyError):
    st.error('演示文件不可用或校验未通过。请恢复完整发布包后重试。')
    st.stop()

catalog = store.catalog()
labels = {'query_candidate': '查询结果', 'clarify': '必要澄清', 'reject': '范围边界'}
with st.sidebar:
    st.title('◈ DataQuery')
    st.caption('商业地产 · 业务问数工作台')
    mode = st.radio('运行方式', ['保存案例回放', '实时提问（未启用）'])
    st.divider()
    st.markdown('**数据与能力**')
    st.caption('合成商业地产数据 · 基准日 2026-09-01\n\n固定指标公式 · 参数化查询 · 只读边界')
    st.caption('回放使用已保存的模型理解及结果，不调用模型或数据库。')

st.markdown('<div class="eyebrow">DATAQUERY / BUSINESS WORKSPACE</div>', unsafe_allow_html=True)
st.title('用业务语言，找到你要的数据')
st.write('从一个问题开始，看清系统理解了什么，以及数据采用什么口径。')

if mode != '保存案例回放':
    st.info('实时连接尚未启用。当前版本可离线查看完整案例；不会把保存答案当作实时回答。')
    st.text_area('你的问题', placeholder='例如：上个月每个项目应该收多少租金？', disabled=True)
    st.stop()

left, right = st.columns([1, 3])
with left:
    category = st.selectbox('案例类型', ['全部', '查询结果', '必要澄清', '范围边界'])
rows = [r for r in catalog if category == '全部' or labels.get(r['action'], '其他') == category]
with right:
    chosen = st.selectbox('选择一个保存案例', [r['id'] for r in rows],
                          format_func=lambda ident: next(r['question'] for r in rows if r['id'] == ident))
if st.session_state.get('selected_case') != chosen:
    for key in ('record', 'unmatched', 'clarification_draft'):
        st.session_state.pop(key, None)
    st.session_state['selected_case'] = chosen
with st.form('question_form'):
    question = st.text_area('问题', value=next(r['question'] for r in rows if r['id'] == chosen), key='question_'+chosen)
    submitted = st.form_submit_button('查看理解与结果', type='primary')
if submitted:
    st.session_state['record'] = store.find_exact(question)
    st.session_state['unmatched'] = st.session_state['record'] is None
    st.session_state.pop('clarification_draft', None)
if st.session_state.get('unmatched'):
    st.warning('这不是已保存案例的原问题。请恢复原问题回放；新问题需要启用实时解析。')
    st.stop()
record = st.session_state.get('record')
if not record:
    st.info('选择案例后点击“查看理解与结果”。支持查看汇总、分组、清单及需要澄清的问题。')
    st.stop()

decision, result = record['decision'], record['result']
st.divider()
st.caption(f"保存案例 {record['id']} · 非实时查询")
st.subheader(record['question'])
summary, output = st.columns([1, 1.6], gap='large')
with summary:
    st.markdown('### 01 / 理解与口径')
    st.text(decision.get('summary_message', decision.get('message', '暂无摘要')))
with output:
    st.markdown('### 02 / 结果')
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
            if st.form_submit_button('保留补充说明'):
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
