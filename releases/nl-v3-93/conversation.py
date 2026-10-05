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
���ض������requests���顣ÿ�source_text��kind��plans��ambiguous/unresolved���ɺ�clarification��
clarification={question:�����ȷ������,choices:[{label:�ھ�˵��,availability:supported��unavailable,reason:˵��}]}��
supported��ѡ���ж�Ӧplans�����plan_index����0��ʼ���������󶨸üƻ�����ʾ���û��ľ���ھ���������ɸѡ�ɰ󶨼ƻ����ɣ��������ɱ�����һ�׽��͡�unavailable��ѡ���󶨼ƻ���ֻ�����ʶ��޿�У��ƻ�ʱ���Բ��󶨣�������������ȷ�Ͽ�ִ�С�
choices��Ϊ�գ�ֱ������ֵ���ڲ����壩�����5�unavailableѡ��ǲ�ѯ�ƻ������ñ���ָ�ꡣ
��������ȱ�ٵ���������������ȷ����Ŀ��ʱ�䡣���ܰ�������ͬ��ѯ�ƻ����ɲ�ͬ�ھ���
ӯ����ѡ����������䵱���󣻲�֧�ֵ���ʽ�ھ�����Ϊunavailable�������ھ�����ȷ������ʽ�ھ���
����source_text��ԭ˳��ƴ��Ϊ�������⣨������㣩��һ������ҵ������һ�
kindΪquery��ambiguous��unresolved��unsupported��write֮һ��
plansΪ��ѯ�ƻ����飬queryǡ��1�ambiguousΪ0��2��3���clarificationʱҲ��ֻ����1����֪������
unresolvedΪ0��1���Ŀ����֪���ڲ�ɸѡ�ھ�δ֪���ɱ�����֪�������÷����������壬����ִ�С�
unsupported��write��plans����Ϊ�ա�δ֪�������뱣����source_text����unresolved�����ܰ���ɾ�����query��
unsupported/write��ֻ�ܺ�source_text��kind��plans������clarification�����ѯѡ�
ͬһ�䲢�ж��Ŀ��ʱ�������Ӵ��з�source_text���ֱ��query��unsupported������ƻ��ɼ̳�ǰ����ȷ��ʱ��/ɸѡ����ԭ��ƴ�ӱ��벻�䡣
unresolved����֪�嵥/ָ��Ŀ�����Ŀ������1����֪�ƻ�������δ����ɸѡ����clarification.question��ѯ�ʡ�
����ǰ�ȱ���������ȷ����λ��Ŀ����ڼ���֪������/��ֵδ֪ʱ��plans����1����֪������δ֪ʱ����missing��δ֪ɸѡ����ֵ������������ȷ׷�ʡ�����ֻдplans=[]Ȼ��ʡ����֪��Ŀ��ʱ�䡢���������Ŀ�걾����ѡ��ʱ�ɱ�����ʵ��ͬ��ѡ����������ȷ���������䵱���塣
���ý�/���ա��ĺ�ͬ���˵���ΪӦ�գ����Ѿ���/�ս���������Ϊʵ�գ�����ȷ��ʱֱ��ʹ�øÿھ����û���ȷ����ѡ��δ�����˵�������ʱ�ų��塣������ʵ�п�������һ���㷨���޶�׷�ʡ�
ע�����٣������ܶÿ����Լ��ƽ��������ÿƽ�������ⲻ��ͬһ������ֻ�е�λ/ҵ����˼��ȷΪ�������ʱ������Ŀ¼ÿƽ�������⼰�������ȨĬ�ϣ�ƽ��������Ĭ�ϲ������û�����ȱʧ�ļ�����λ����λ����δ��ʱѯ�ʵ�λ������ֱ�Ӽٶ�ÿƽ���ס�
�������ֻ�����⣬ʵ��δ��ѯ��������clarification��question/label/reason�������Ѳ�ѯ���ѷ������ݻ���ִ��֧�ֲ��֡�
�ƻ�����target��filters��time��group_by��order_by��
������ʱgroup_byд[]������null��û�ж���ɸѡʱfiltersд[]��������ʱorder_byдnull�����ߵĿ�ֵ���Ͳ�Ҫ���á�
target={kind:metric��list,id:Ŀ¼ID}��filtersÿ��Ϊ{dimension,operator:in,values:ֵ����}��
time={kind:relative,period:previous_month��previous_year��previous_quarter}����{kind:range,start:ISO����,end:ISO����}����{kind:missing}��
��ȷ�����N��������ʱ����{kind:relative,period:last_complete_months,months:N}�����ܰ�δָ�����ڵ�����Զ�����3���£�Ҳ���ܰѽ�������Ĺ��������滻Ϊ�����¡�
ʱ��ָ�����time={kind:point,date:ISO����}��δָ��������missing����¶Ĭ�ϻ�׼�գ���Ҫ���ڼ�����͵͵��Ϊʱ�㡣
ͬһʱ��ָ��Ķ����ȷ������һ�����Ʋ�ѯ����time={kind:points,dates:[ISO����]}����group_by��point_date��ÿ�����ڵ������㣬�������Ⱥ�չʾ��order_by��Ϊnull�����ܸ�Ϊ�ڼ�ƽ������ȡ���һ���ֻ�����������ڡ�
��ȷ���·�/���ڴ��絽���ţ�order_by.by��month/point_date��direction��asc������������desc��ʱ��˳����target_value���ߵ͡�û����ȷ����ʱmonth/point_date����Ĭ�ϰ������Ⱥ�����׷�ʡ�
��ͨ�嵥����ʱ�����time={kind:not_applicable}���漰������/��ʷ״̬���������뱣��������д��not_applicable�ƹ���
��Լ����ʼ�ջ�����շ�Χɸѡ��time={kind:field_range,field:lease_start_date��lease_end_date,start:ISO����,end:ISO����}�����˰���������������Լ�ֶΣ������ڼ�ʵ�����룻δ������������������Ĭ�Ϲ�����Ч״̬����˵ĳ����Լ��δ��ȷ��ʼ/����/����ʱ��Ҫ���塣
��Լ����������order_by={by:lease_start_date��lease_end_date,direction:asc��desc,limit:��ѡ����}���������������Ϊ�����������Ҫ��group_by��
group_byΪά��ID���飻�ڼ�ָ�갴�����ƿɼ�month��ָ��ָ���Լ�������/�����·ݷ��飬���������գ�ʱ��ָ�겻�Զ�ת���¶����С�order_byΪnull��{by:target_value,direction:asc��desc}���û���ȷҪ��ǰN��ʱ��limit:N��1��1000��������δָ������������limit�����N����asc�����N����desc��
��ҪΪ�������ʽ���Ѷ����������һ���ɾȥ�޷�֧�ֵĲ��֡�
order_byĬ�Ͽ����з���ȫ���������û�Ҫ��ÿ����/ÿ�����ȡǰN�����뱣��partition_byά�����飨group_by�ķǿ����Ӽ�����limit���Ȱ�ȫ��group_by���ܣ�����ÿ��partition�����������ܸĳ�ȫ��ǰN����
���⻧����ʹ��tenant����ά�ȣ�����tenant_tier������������Ŀ���⻧����ֻ��tenant����Ŀ���Ե��⻧������group_by=[project,tenant]��partition_by=[project]��
�������ǰ��飺�Ƚ϶�����group_by���������ĸ���Χ����partition_by��������limit�����߲��ܻ������������ÿ�����͸�ѡ���group_by�������ͼ�����partition_byֻ�����͡�limitΪ2������ѡ������û��partition_by����Ҫ����ȷ��ÿ���N������Ϊ����N��
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
        return {'action':'parser_error','message':'ϵͳδ����������������⣬����û�в�ѯ��',
                'diagnostic':type(exc).__name__, 'execution_allowed':False}
    kinds={r['kind'] for r in details}
    statuses={p['status'] for r in details for p in r['plans']}
    if 'write' in kinds:
        action='reject'; lead='����ֻ�ܲ�ѯ�������޸ļ�¼���������������δִ�С�'
    elif 'unsupported' in kinds or any(p['status']=='outside_coverage'
            for r in details if r['kind']!='ambiguous' for p in r['plans']) or any(
            r['kind']=='ambiguous' and r['plans'] and all(p['status']=='outside_coverage' for p in r['plans'])
            for r in details):
        action='reject'; lead='�������е�ǰ�����޷������ش�Ĳ��֣�����û�в���ִ�С�'
    elif kinds & {'ambiguous','unresolved'} or 'clarify' in statuses:
        action='clarify'; lead='��Ҫȷ������δ������������ȡ�����������·������β���ѯ��'
        if 'not_implemented' in statuses:
            lead+='�����ķ���ͬʱ��ʵ��ȱ�ڣ�ȷ������Ҳ�������Ѿ�����ִ�С�'
    elif 'not_implemented' in statuses or any(r.get('basis_check',{}).get('requires_predicate_implementation') for r in details):
        action='implementation_gap'; lead='�����ѱ������������ѯ��δ�Ӻã�����Ҫ���㻻��רҵ���'
    elif grounding:
        action='interpretation_review'; lead='ϵͳ����Ŀ��Χ������ǰ��һ�£���Ҫ���º˶ԣ��ⲻ��Ҫ�������רҵ�������δ��ѯ��'
    else:
        action='query_candidate'; lead='���γɴ���ѯ��������δִ�С�'
    lines=[lead]
    for r in details:
        if r['kind']=='unsupported': explanation='��ǰ����Ŀ¼�޷�֧�ִ˲��֡�'
        elif r['kind']=='write': explanation='�޸Ĳ�����֧�֡�'
        elif r['kind']=='unresolved': explanation='�벹����δ����Ķ����ɸѡ��������ֻ������֪��������������ȷ����ܲ�ѯ��'
        elif r['kind']=='ambiguous': explanation='���ڶ��ֽ��ͣ���ȷ��ҵ��ھ���'
        else: explanation='��ѯ�����ѱ�����'
        lines.append(f"���ڡ�{r['source_text']}����{explanation}")
        lines.extend(render_known_basis(r.get('basis_check',{})))
        if r.get('basis_check',{}).get('requires_predicate_implementation'):
            lines.append('�Ѽ�¼�ż�����������������Ӧ��ֵ�Ƚ���δ�����ѯ�ƻ���������ʹ����Ҳ����ֱ��ִ�С�')
        if r.get('retention_status')=='source_only':
            lines.append('ԭ�����ѱ���������δ�γɽṹ����ѯ���������ܾݴ���Ϊ����������������ȡ��')
        if 'clarification' in r:
            c=r['clarification']
            lines.append(('ԭ�ھ����⣨���ֲ�����ѡ�񣩣�' if action=='reject' else '��ȷ�ϣ�')+c['question'])
            for choice in c['choices']:
                lines.append(render_choice(capabilities,choice,r['plans']))
        for p in r['plans']:
            if p['status']=='validated_structure_not_execution':
                lines.append(render_plan(capabilities,p))
            else:
                lines.append(render_gap(capabilities,p))
    summary=[{'query_candidate':'���ⷽ����׼���ã���δ��ѯ��',
              'clarify':'����ȷ���������⣻��δ��ѯ��',
              'reject':'������������δִ�С�',
              'implementation_gap':'�����ѱ�������������δ�Ӻã���δ��ѯ��',
              'interpretation_review':'��Ŀ��Χ�����º˶ԣ���δ��ѯ��'}[action]]
    for r in details:
        summary.extend(render_known_basis(r.get('basis_check',{})))
        if r.get('basis_check',{}).get('requires_predicate_implementation'):
            summary.append('�ż���������������ʵ��ȱ�ڣ����������Щ�������ѯ��')
        if r['kind'] in {'unsupported','write'}:
            summary.append('�����ṩ��'+r['source_text'])
        elif 'clarification' in r:
            c=r['clarification']; summary.append(('ԭ�ھ����⣨���ֲ�����ѡ�񣩣�' if action=='reject' else '��ȷ�ϣ�')+c['question'])
            summary.extend(render_choice(capabilities,choice,r['plans']) for choice in c['choices'])
        elif r['kind'] in {'ambiguous','unresolved'}:
            summary.append('��ȷ�Ͽھ������'+r['source_text'])
        if r.get('retention_status')=='source_only':
            summary.append('������ԭ���⣺'+r['source_text'])
            summary.append('��δ�γɽṹ����ѯ������δȷ��������ȡ������')
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
