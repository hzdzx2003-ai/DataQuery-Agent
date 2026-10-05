"""Offline-only vertical slice with an injected understanding provider.

There is no model transport, database or execution API. Candidate decisions are
not permission to run a query. Structural coverage is not semantic completeness.
"""
from capabilities import build_understanding_prompt
from query_plan import validate_query_plan
from plan_view import render_plan, render_gap, render_compact_plan, render_choice
from grounding import project_filter_diagnostics
from clarification_policy import CLARIFICATION_POLICY
from basis_slots import render_known_basis
import json


ENVELOPE_INSTRUCTIONS = '''
返回对象仅含requests数组。每项含source_text、kind、plans；ambiguous/unresolved还可含clarification。
clarification={question:具体待确认问题,choices:[{label:口径说明,availability:supported或unavailable,reason:说明}]}。
supported候选如有对应plans项，增加plan_index（从0开始的整数）绑定该计划；显示给用户的具体口径、日期与筛选由绑定计划生成，不再自由编造另一套解释。unavailable候选不绑定计划。只有提问而无可校验计划时可以不绑定，但不能声称已确认可执行。
choices可为空（直接问阈值或内部定义），最多5项；unavailable选项不是查询计划，不得编造指标。
先问真正缺少的条件，保留已明确的项目与时间。不能把两个相同查询计划当成不同口径。
盈利候选不能拿收入充当利润；不支持的正式口径可列为unavailable，代理口径须明确不是正式口径。
所有source_text按原顺序拼接为完整问题（包括标点），一个独立业务请求一项。
kind为query、ambiguous、unresolved、unsupported、write之一。
plans为查询计划数组，query恰好1项，ambiguous为0或2至3项；有clarification时也可只保留1个已知方案。
unresolved为0或1项：如目标已知但内部筛选口径未知，可保留已知方案；该方案仅供澄清，不可执行。
unsupported与write的plans必须为空。未知条件必须保留在source_text并标unresolved，不能把它删掉后标query。
unsupported/write项只能含source_text、kind、plans，不加clarification或建议查询选项。
同一句并列多个目标时可沿连接词切分source_text，分别标query与unsupported；后项计划可继承前文明确的时间/筛选，但原文拼接必须不变。
unresolved若已知清单/指标目标和项目，保留1个已知计划，具体未定义筛选仍在clarification.question中询问。
澄清前先保留所有已确定槽位。目标和期间已知但窗口/阈值未知时，plans保留1个已知方案，未知时间用missing，未知筛选不造值但在问题中明确追问。不能只写plans=[]然后省略已知项目、时间、分组或排序。目标本身待选择时可保留真实不同候选，不能拿已确定的条件充当歧义。
“该交/该收”的合同或账单义为应收，“已经交/收进来”的义为实收；有明确义时直接使用该口径。用户明确表达选择未定或仅说租金收入时才澄清。不因现实中可以有另一种算法而无端追问。
注意量纲：月租总额、每份租约的平均月租与每平方米月租不是同一个量。只有单位/业务意思明确为面积单价时，才用目录每平方米月租及其面积加权默认；平均方法的默认不能替用户决定缺失的计量单位。单位本身未定时询问单位，不能直接假定每平方米。
所有输出只是理解，实际未查询：不得在clarification的question/label/reason中声称已查询、已返回数据或已执行支持部分。
计划仅含target、filters、time、group_by、order_by。
不分组时group_by写[]而不是null；没有额外筛选时filters写[]。不排序时order_by写null，三者的空值类型不要混用。
target={kind:metric或list,id:目录ID}；filters每项为{dimension,operator:in,values:值数组}。
time={kind:relative,period:previous_month、previous_year或previous_quarter}，或{kind:range,start:ISO日期,end:ISO日期}，或{kind:missing}。
明确问最近N个完整月时可用{kind:relative,period:last_complete_months,months:N}；不能把未指定窗口的最近自动当成3个月，也不能把截至今天的滚动天数替换为完整月。
时点指标可用time={kind:point,date:ISO日期}，未指定日期用missing并披露默认基准日；不要把期间问题偷偷改为时点。
同一时点指标的多个明确日期是一个趋势查询，用time={kind:points,dates:[ISO日期]}并在group_by加point_date；每个日期单独计算，按日期先后展示，order_by可为null。不能改为期间平均、仅取最后一天或只保留部分日期。
明确按月份/日期从早到晚排，order_by.by用month/point_date、direction用asc；从晚到早用desc。时间顺序不是target_value金额高低。没有明确排序时month/point_date趋势默认按日期先后，无需追问。
普通清单不涉时间可用time={kind:not_applicable}；涉及到期日/历史状态等条件必须保留，不能写成not_applicable绕过。
租约按开始日或结束日范围筛选用time={kind:field_range,field:lease_start_date或lease_end_date,start:ISO日期,end:ISO日期}，两端包含。这是现有租约字段，不是期间实际收入；未来到期日期允许，不默认过滤有效状态。仅说某月租约但未明确开始/结束/存续时需要澄清。
租约日期排序用order_by={by:lease_start_date或lease_end_date,direction:asc或desc,limit:可选整数}，不把日期排序改为金额排名；不要求group_by。
group_by为维度ID数组；期间指标按月趋势可加month，指按指标自己的账期/费用月份分组，不按到账日；时点指标不自动转成月度序列。order_by为null或{by:target_value,direction:asc或desc}；用户明确要求前N名时加limit:N（1至1000整数），未指定数量不添加limit。最低N名用asc，最高N名用desc。
不要为了满足格式而把独立请求揉成一项或删去无法支持的部分。
order_by默认跨所有分组全局排序；若用户要求每个月/每类各自取前N名，须保留partition_by维度数组（group_by的非空真子集）及limit，先按全部group_by汇总，再在每个partition内排名，不能改成全局前N名。
按租户汇总使用tenant身份维度，不是tenant_tier或姓名；跨项目按租户汇总只放tenant，项目各自的租户排名用group_by=[project,tenant]、partition_by=[project]。
排名输出前检查：比较对象是group_by，排名在哪个范围内是partition_by，数量是limit，三者不能互相替代。例如每种类型各选两项：group_by包含类型及对象、partition_by只有类型、limit为2；整体选两项则没有partition_by。不要把明确“每组各N”解释为整体N。
''' + CLARIFICATION_POLICY


def validate_envelope(question, value):
    if not isinstance(question, str) or not question.strip():
        raise ValueError('question is empty')
    if not isinstance(value, dict) or set(value) != {'requests'}:
        raise ValueError('invalid understanding envelope')
    requests = value['requests']
    if not isinstance(requests, list) or not 1 <= len(requests) <= 20:
        raise ValueError('invalid request count')
    for item in requests:
        if not isinstance(item, dict) or not {'source_text','kind','plans'} <= set(item) or set(item)-{'source_text','kind','plans','clarification'}:
            raise ValueError('invalid request fields')
        if not isinstance(item['source_text'], str) or not item['source_text'].strip():
            raise ValueError('empty request text')
        kind, plans = item['kind'], item['plans']
        if kind not in {'query','ambiguous','unresolved','unsupported','write'} or not isinstance(plans,list):
            raise ValueError('invalid request classification')
        clarification=item.get('clarification')
        if 'clarification' in item:
            if kind not in {'ambiguous','unresolved'} or not isinstance(clarification,dict) or set(clarification)!={'question','choices'}:
                raise ValueError('invalid clarification fields')
            q=clarification['question']
            choices=clarification['choices']
            if not isinstance(q,str) or not q.strip() or len(q)>1000 or not isinstance(choices,list) or len(choices)>5:
                raise ValueError('invalid clarification question/choices')
            labels=set()
            for choice in choices:
                if (not isinstance(choice,dict) or not {'label','availability','reason'}<=set(choice)
                        or set(choice)-{'label','availability','reason','plan_index'}):
                    raise ValueError('invalid choice fields')
                if choice['availability'] not in {'supported','unavailable'}:
                    raise ValueError('invalid choice availability')
                if 'plan_index' in choice and (choice['availability']!='supported'
                        or type(choice['plan_index']) is not int or not 0<=choice['plan_index']<len(plans)):
                    raise ValueError('invalid choice plan binding')
                if any(not isinstance(choice[k],str) or not choice[k].strip() or len(choice[k])>1000 for k in {'label','reason'}):
                    raise ValueError('invalid choice text')
                if choice['label'].strip() in labels:
                    raise ValueError('duplicate clarification choice')
                labels.add(choice['label'].strip())
        n=len(plans)
        allowed={0,1,2,3} if clarification else {0,2,3}
        if ((kind=='query' and n!=1) or (kind=='ambiguous' and n not in allowed)
                or (kind=='unresolved' and n not in {0,1})
                or (kind in {'unsupported','write'} and n!=0)):
            raise ValueError('candidate count inconsistent with kind')
        if any(not isinstance(p,dict) for p in plans):
            raise ValueError('plan must be an object')
        if kind=='ambiguous' and any(a==b for i,a in enumerate(plans) for b in plans[i+1:]):
            raise ValueError('duplicate alternatives are not genuine ambiguity')
    if ''.join(r['source_text'] for r in requests) != question:
        raise ValueError('request text coverage differs from question')
    return requests


def understand_offline(question, capabilities, resolver):
    """resolver(prompt, question) is injectable; no live implementation supplied."""
    try:
        value=resolver(build_understanding_prompt(capabilities)+ENVELOPE_INSTRUCTIONS,question)
        requests=validate_envelope(question,value)
        grounding=project_filter_diagnostics(capabilities,requests)
        details=[]
        for request_index,r in enumerate(requests):
            plans=[validate_query_plan(capabilities,p) for p in r['plans']]
            validate_distinct_alternatives(r['kind'], plans)
            detail={'source_text':r['source_text'],'kind':r['kind'],'plans':plans}
            checks=getattr(resolver,'basis_checks',[])
            if getattr(resolver,'basis_mode',False) and request_index<len(checks) and checks[request_index] is not None:
                detail['basis_check']=checks[request_index]
            if 'clarification' in r:
                detail['clarification']=r['clarification']
            if r['kind'] in {'ambiguous','unresolved'}:
                detail['retention_status']='plans_present_not_completeness_proof' if plans else 'source_only'
            details.append(detail)
    except (ValueError, TypeError, KeyError) as exc:
        return {'action':'parser_error','message':'系统未能完整处理你的问题，本次没有查询。',
                'diagnostic':type(exc).__name__, 'execution_allowed':False}
    kinds={r['kind'] for r in details}
    statuses={p['status'] for r in details for p in r['plans']}
    if 'write' in kinds:
        action='reject'; lead='这里只能查询，不能修改记录；本次整个请求均未执行。'
    elif 'unsupported' in kinds or any(p['status']=='outside_coverage'
            for r in details if r['kind']!='ambiguous' for p in r['plans']) or any(
            r['kind']=='ambiguous' and r['plans'] and all(p['status']=='outside_coverage' for p in r['plans'])
            for r in details):
        action='reject'; lead='请求中有当前数据无法完整回答的部分，本次没有部分执行。'
    elif kinds & {'ambiguous','unresolved'} or 'clarify' in statuses:
        action='clarify'; lead='需要确认以下未定条件；已提取的条件列在下方，本次不查询。'
        if 'not_implemented' in statuses:
            lead+='保留的方案同时有实现缺口；确认条件也不代表已经可以执行。'
    elif 'not_implemented' in statuses or any(r.get('basis_check',{}).get('requires_predicate_implementation') for r in details):
        action='implementation_gap'; lead='问题已保留，但这类查询尚未接好，不是要求你换成专业术语。'
    elif grounding:
        action='interpretation_review'; lead='系统对项目范围的理解前后不一致，需要重新核对；这不是要求你改用专业术语。本次未查询。'
    else:
        action='query_candidate'; lead='已形成待查询方案，尚未执行。'
    lines=[lead]
    for r in details:
        if r['kind']=='unsupported': explanation='当前能力目录无法支持此部分。'
        elif r['kind']=='write': explanation='修改操作不支持。'
        elif r['kind']=='unresolved': explanation='请补充尚未定义的对象或筛选规则；下面只保留已知方案，待条件明确后才能查询。'
        elif r['kind']=='ambiguous': explanation='存在多种解释，请确认业务口径。'
        else: explanation='查询方案已保留。'
        lines.append(f"关于“{r['source_text']}”：{explanation}")
        lines.extend(render_known_basis(r.get('basis_check',{})))
        if r.get('basis_check',{}).get('requires_predicate_implementation'):
            lines.append('已记录门槛或租期条件，但相应数值比较尚未接入查询计划；条件即使补齐也不能直接执行。')
        if r.get('retention_status')=='source_only':
            lines.append('原问题已保留，但尚未形成结构化查询条件；不能据此认为其他条件已完整提取。')
        if 'clarification' in r:
            c=r['clarification']
            lines.append(('原口径问题（本轮不请求选择）：' if action=='reject' else '请确认：')+c['question'])
            for choice in c['choices']:
                lines.append(render_choice(capabilities,choice,r['plans']))
        for p in r['plans']:
            if p['status']=='validated_structure_not_execution':
                lines.append(render_plan(capabilities,p))
            else:
                lines.append(render_gap(capabilities,p))
    summary=[{'query_candidate':'理解方案已准备好；尚未查询。',
              'clarify':'请先确认以下问题；尚未查询。',
              'reject':'本次整个请求未执行。',
              'implementation_gap':'理解已保留，但功能尚未接好；尚未查询。',
              'interpretation_review':'项目范围需重新核对；尚未查询。'}[action]]
    for r in details:
        summary.extend(render_known_basis(r.get('basis_check',{})))
        if r.get('basis_check',{}).get('requires_predicate_implementation'):
            summary.append('门槛或租期条件仍有实现缺口；不会忽略这些条件后查询。')
        if r['kind'] in {'unsupported','write'}:
            summary.append('不能提供：'+r['source_text'])
        elif 'clarification' in r:
            c=r['clarification']; summary.append(('原口径问题（本轮不请求选择）：' if action=='reject' else '请确认：')+c['question'])
            summary.extend(render_choice(capabilities,choice,r['plans']) for choice in c['choices'])
        elif r['kind'] in {'ambiguous','unresolved'}:
            summary.append('待确认口径或规则：'+r['source_text'])
        if r.get('retention_status')=='source_only':
            summary.append('保留的原问题：'+r['source_text'])
            summary.append('尚未形成结构化查询条件；未确认条件提取完整。')
        for p in r['plans']:
            summary.append(render_compact_plan(capabilities,p))
    return {'action':action,'message':'\n'.join(lines),'summary_message':'\n'.join(summary),'requests':details,
            'execution_allowed':False,'coverage':'text_partition_only_not_semantic_proof',
            'grounding_diagnostics':grounding}


def validate_distinct_alternatives(kind, plans):
    """Compare resolved business slots, not provenance/default wording.

    Pending implementation plans lack sufficient slots; do not assert their
    equivalence. Distinctness does not prove alternatives are relevant.
    """
    if kind != 'ambiguous':
        return
    seen=set()
    for p in plans:
        if p.get('status') != 'validated_structure_not_execution':
            continue
        t=p['time']
        temporal={k:t[k] for k in ('start','end','date','dates','mode','field') if k in t}
        filters=sorted((f['dimension'],f['operator'],tuple(sorted(f['values']))) for f in p['filters'])
        key=json.dumps({'target':p['target'],'filters':filters,'time':temporal,
                        'group':sorted(p['group_by']),'sort':p['order_by']},sort_keys=True)
        if key in seen:
            raise ValueError('alternatives resolve to the same business query; ask missing condition directly')
        seen.add(key)
