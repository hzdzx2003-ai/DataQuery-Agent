"""Opt-in business-basis checks; not a natural-language truth verifier.

Opt-in prototype. Not connected to the default resolver. Quotes establish only
source membership; a model can still misclassify the meaning of a real quote.
"""
from copy import deepcopy
import math


ENUMS={
    'measurement_unit':{'per_sqm','per_lease','per_unit'},
    'aggregation_basis':{'area_weighted','ratio_of_totals','mean_of_ratios'},
    'threshold_unit':{'CNY','year','month','day'},
    'threshold_operator':{'gt','gte','lt','lte'},
    'duration_basis':{'original_term','remaining_term'},
}
FIELDS=set(ENUMS)|{'threshold_value'}
DEFAULTS={
    ('avg_monthly_rent_per_sqm','aggregation_basis'):'area_weighted',
    ('collection_rate','aggregation_basis'):'ratio_of_totals',
}
REQUIRED={
    'avg_monthly_rent_per_sqm':{'measurement_unit','aggregation_basis'},
    'collection_rate':{'aggregation_basis'},
}
QUESTIONS={
    'measurement_unit':'���ļ���������ÿƽ���ס�ÿ����Լ����ÿ����λ��',
    'aggregation_basis':'ϣ���ϲ��ܶ�����������������ǶԸ����������ƽ����',
    'threshold_value':'ɸѡ�ż��ľ�����ֵ�Ƕ��٣�',
    'threshold_unit':'�ż�ʹ��ʲô������λ��',
    'threshold_operator':'�ż��Ǹ��ڻ��ǵ���ָ��ֵ���Ƿ�������ڸ�ֵ��',
    'duration_basis':'ʱ����ԭԼ�������ڣ����ǽ�����׼�յ�ʣ�������жϣ�',
}


def check_basis_slots(source_text,target,slots):
    """Validate reported facts and expose unknowns without filling any slot.

    This does not inspect source keywords or assert that the model has reported
    every business condition. The caller must preserve normal plan validation.
    """
    if not isinstance(source_text,str) or not source_text.strip():
        raise ValueError('basis source must be nonempty text')
    if (target is not None and (not isinstance(target,dict)
            or set(target)!={'kind','id'} or target['kind'] not in {'metric','list'}
            or not isinstance(target['id'],str))):
        raise ValueError('basis target must be a query target or null')
    metric_id=target['id'] if target and target['kind']=='metric' else None
    if not isinstance(slots,dict) or set(slots)-FIELDS:
        raise ValueError('unknown basis slot')
    required=REQUIRED.get(metric_id,set())
    if not required<=set(slots):
        raise ValueError('missing applicable basis slots')
    # A reported threshold/duration needs the whole comparison contract. This
    # does not claim a missing threshold was detectable from natural language.
    threshold={'threshold_value','threshold_unit','threshold_operator'}
    if (set(slots)&threshold or 'duration_basis' in slots) and not threshold<=set(slots):
        raise ValueError('incomplete threshold basis slots')
    unit_slot=slots.get('threshold_unit')
    if (target=={'kind':'list','id':'lease'} and isinstance(unit_slot,dict)
            and unit_slot.get('value') in ('year','month','day') and 'duration_basis' not in slots):
        raise ValueError('duration comparison requires duration_basis')
    unknown=[]
    for name,slot in slots.items():
        if (not isinstance(slot,dict) or set(slot)!={'state','value','source_quote'}
                or slot['state'] not in {'explicit','permitted_default','unresolved'}
                or not isinstance(slot['source_quote'],str)):
            raise ValueError('invalid basis slot structure')
        state,value,quote=slot['state'],slot['value'],slot['source_quote']
        if len(quote)>1000 or (quote and quote not in source_text):
            raise ValueError('basis quote is not in source')
        if state=='unresolved':
            if value is not None:raise ValueError('unresolved basis cannot carry a selected value')
            unknown.append(name)
            continue
        if name=='threshold_value':
            if type(value) not in {int,float} or not math.isfinite(value) or value<0:
                raise ValueError('threshold value must be finite and nonnegative')
        elif not isinstance(value,str) or value not in ENUMS[name]:
            raise ValueError('invalid basis value')
        if state=='explicit' and not quote.strip():
            raise ValueError('explicit basis requires source quote')
        if state=='permitted_default' and DEFAULTS.get((metric_id,name))!=value:
            raise ValueError('basis default is not permitted')
    # Even explicit alternatives cannot silently become a different catalog
    # metric; retain these as unsupported representation needs, not new support.
    conflicts=[]
    unit=slots.get('measurement_unit',{})
    aggregation=slots.get('aggregation_basis',{})
    if metric_id=='avg_monthly_rent_per_sqm':
        if unit.get('value') not in {None,'per_sqm'}:conflicts.append('measurement_unit')
        if aggregation.get('value') not in {None,'area_weighted'}:conflicts.append('aggregation_basis')
    if metric_id=='collection_rate' and aggregation.get('value') not in {None,'ratio_of_totals'}:
        conflicts.append('aggregation_basis')
    return {'slots':deepcopy(slots),'unresolved':sorted(unknown),'metric_id':metric_id,
            'target_conflicts':conflicts,'requires_clarification':bool(unknown),
            'requires_plan_revision':bool(conflicts),
            'requires_predicate_implementation':bool(set(slots)&(threshold|{'duration_basis'})),
            'semantic_truth_verified':False,
            'limitation':'Model-reported meaning and completeness remain unverified.'}


def unresolved_questions(checked):
    """Wording only, based on validated unknowns; never guess missing facts."""
    questions=[]
    for name in checked['unresolved']:
        if name=='aggregation_basis' and checked.get('metric_id')=='avg_monthly_rent_per_sqm':
            questions.append('ƽ������ϣ���������Ȩ���㣬��������ƽ����ʽ����ǰĿ¼ֻ֧�������Ȩ��')
        else:questions.append(QUESTIONS[name])
    return questions


def render_known_basis(checked):
    """Show reported known facts, not a claim that their semantics were proved."""
    names={'measurement_unit':'��������','aggregation_basis':'���㷽ʽ',
           'threshold_value':'�ż���ֵ','threshold_unit':'�ż���λ',
           'threshold_operator':'�Ƚϱ߽�','duration_basis':'���ڻ�׼'}
    values={'per_sqm':'ÿƽ����','per_lease':'ÿ����Լ','per_unit':'ÿ����λ',
            'area_weighted':'�����Ȩ','ratio_of_totals':'�ϲ��ܶ��������',
            'mean_of_ratios':'���������ƽ��','CNY':'Ԫ','year':'��','month':'��','day':'��',
            'gt':'�ϸ���ڣ��������ڣ�','gte':'���ڻ����','lt':'�ϸ�С�ڣ��������ڣ�',
            'lte':'С�ڻ����','original_term':'ԭԼ��������','remaining_term':'��׼��ʣ������'}
    result=[]
    for name,slot in checked.get('slots',{}).items():
        if slot['state']=='unresolved':continue
        label=values.get(slot['value'],str(slot['value']))
        origin='Ŀ¼Ĭ�ϣ���ȷ��' if slot['state']=='permitted_default' else '��ԭ����ȡ����˶�'
        result.append(f'{names[name]}��{label}��{origin}����')
    return result


BASIS_INSTRUCTIONS='''
����ѡ�ھ����ģʽ�����ж�ҵ���壬��ѡĿ¼ָ�꡿
ÿ����unsupported/write��������ṩbasis_slots�������������ʱΪ{}��
ÿ����λΪ{state:explicit��permitted_default��unresolved,value:ֵ��null,source_quote:ԭ��Ƭ�λ���ַ���}��
explicit��Ҫԭ��Ƭ�Σ��������á�ƽ�����⡱����֤��ƽ���׵�λ�����á�ƽ����������֤���ϲ��ܶ���ʡ�
unresolved��value����null������Ŀ¼Ψһָ�굹���û���ͼ����ȷδ֪��ʹ���мƻ�Ҳ����ֱ�Ӳ�ѯ��
measurement_unitֵper_sqm/per_lease/per_unit��ÿƽ��������ָ������ṩ�˲ۺ�aggregation_basis��
aggregation_basisֵarea_weighted/ratio_of_totals/mean_of_ratios���ս��ʱ����ṩ�˲ۡ�
��Ŀ¼�����������Ȩ�ͺϲ��ܶ���ʿ���permitted_default�����û����ƽ����ʽ����ʱ��unresolved��
��λ����default����ͨδ���ƽ����ʽ������ս��ʿ���Ĭ��������������������û���
���/����ɸѡ��threshold_value(�Ǹ���)��threshold_unit(CNY/year/month/day)��threshold_operator(gt/gte/lt/lte)��
ֻҪ�漰�ż�����������������棻�û�����ȷ����¼��δ֪�ı�unresolved���������������ǰN��
����ɸѡ�����ṩduration_basis(original_term/remaining_term)������ֱ�ΪԭԼ��������/��׼��ʣ�����ڡ�
�漰���ڶ���ʱ���ܽ�������������©ʱ����׼����ͨ��Լ�嵥��������Щ�޹ز�λ��
�����Ѿ�ȷ������Ŀ�����ڡ�Ŀ�ꡢ���������򡣴˼�鲻����Ŀ¼���㷨����ֵɸѡִ��������
��basis_slots���г�δ֪�clarification.questionֻ��������δ���������Ҫ�ظ��г���δ֪�Ҳ��������Ŀû��Ҫ��������ǰN��
'''


def compile_basis_envelope(value):
    """Project the opt-in payload to the old envelope, preserving raw input.

    Unknowns become clarification, not contract retries. Conflicting selected
    target/value pairs require correction rather than silently changing intent.
    Return sidecar evidence separately; do not insert new query-plan fields.
    """
    if not isinstance(value,dict) or set(value)!={'requests'} or not isinstance(value['requests'],list):
        raise ValueError('invalid understanding envelope')
    result=deepcopy(value);checks=[]
    for request in result['requests']:
        if not isinstance(request,dict):raise ValueError('invalid request fields')
        kind=request.get('kind')
        if kind in ('unsupported','write'):
            if 'basis_slots' in request:raise ValueError('basis slots not applicable to rejected request')
            checks.append(None)
            continue
        if 'basis_slots' not in request:raise ValueError('basis mode requires basis_slots')
        slots=request.pop('basis_slots')
        plans=request.get('plans')
        if not isinstance(plans,list) or any(not isinstance(p,dict) for p in plans):
            raise ValueError('plan must be an object')
        targets=[p.get('target') for p in plans] or [None]
        validated=[check_basis_slots(request.get('source_text'),target,slots) for target in targets]
        if any(c['requires_plan_revision'] for c in validated):
            raise ValueError('basis value conflicts with catalog target')
        checked=validated[0]
        checks.append(checked)
        if checked['requires_clarification']:
            if kind=='query':request['kind']='unresolved'
            prior=request.get('clarification')
            if prior is not None and (not isinstance(prior,dict) or set(prior)!={'question','choices'}
                    or not isinstance(prior['question'],str) or not isinstance(prior['choices'],list)):
                raise ValueError('invalid clarification fields')
            # Keep additional model-identified unknowns, never discard them to
            # get a short, apparently complete question. Deduplicate exact text.
            questions=unresolved_questions(checked)
            if prior and prior['question'].strip() and prior['question'] not in questions:
                questions.append(prior['question'])
            request['clarification']={'question':'��'.join(questions),
                                      'choices':deepcopy(prior['choices']) if prior else []}
    return result,checks
