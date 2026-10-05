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
    'measurement_unit':'金额的计量对象是每平方米、每份租约还是每个铺位？',
    'aggregation_basis':'希望合并总额后计算整体比例，还是对各组比例做简单平均？',
    'threshold_value':'筛选门槛的具体数值是多少？',
    'threshold_unit':'门槛使用什么计量单位？',
    'threshold_operator':'门槛是高于还是低于指定值，是否包含等于该值？',
    'duration_basis':'时长按原约定总租期，还是截至基准日的剩余租期判断？',
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
            questions.append('平均月租希望按面积加权计算，还是另有平均方式？当前目录只支持面积加权。')
        else:questions.append(QUESTIONS[name])
    return questions


def render_known_basis(checked):
    """Show reported known facts, not a claim that their semantics were proved."""
    names={'measurement_unit':'计量对象','aggregation_basis':'计算方式',
           'threshold_value':'门槛数值','threshold_unit':'门槛单位',
           'threshold_operator':'比较边界','duration_basis':'租期基准'}
    values={'per_sqm':'每平方米','per_lease':'每份租约','per_unit':'每个铺位',
            'area_weighted':'面积加权','ratio_of_totals':'合并总额后计算比例',
            'mean_of_ratios':'各组比例简单平均','CNY':'元','year':'年','month':'月','day':'天',
            'gt':'严格大于（不含等于）','gte':'大于或等于','lt':'严格小于（不含等于）',
            'lte':'小于或等于','original_term':'原约定总租期','remaining_term':'基准日剩余租期'}
    result=[]
    for name,slot in checked.get('slots',{}).items():
        if slot['state']=='unresolved':continue
        label=values.get(slot['value'],str(slot['value']))
        origin='目录默认，可确认' if slot['state']=='permitted_default' else '从原文提取，请核对'
        result.append(f'{names[name]}：{label}（{origin}）。')
    return result


BASIS_INSTRUCTIONS='''
【可选口径检查模式：先判断业务含义，再选目录指标】
每个非unsupported/write请求额外提供basis_slots对象；无相关事项时为{}。
每个槽位为{state:explicit或permitted_default或unresolved,value:值或null,source_quote:原文片段或空字符串}。
explicit需要原文片段，但仅引用“平均月租”不能证明平方米单位；引用“平均数”不能证明合并总额比率。
unresolved的value必须null，不用目录唯一指标倒推用户意图；明确未知后即使已有计划也不能直接查询。
measurement_unit值per_sqm/per_lease/per_unit；每平方米月租指标必须提供此槽和aggregation_basis。
aggregation_basis值area_weighted/ratio_of_totals/mean_of_ratios；收缴率必须提供此槽。
仅目录允许的面积加权和合并总额比率可用permitted_default，但用户提出平均方式分歧时标unresolved。
单位不可default。普通未提出平均方式分歧的收缴率可以默认整体比例，不额外问用户。
金额/期限筛选用threshold_value(非负数)、threshold_unit(CNY/year/month/day)、threshold_operator(gt/gte/lt/lte)。
只要涉及门槛，三项必须完整报告；用户已明确的照录，未知的标unresolved，不能造数或改问前N。
期限筛选另外提供duration_basis(original_term/remaining_term)，含义分别为原约定总租期/基准日剩余租期。
涉及长期定义时不能仅报告年数而遗漏时长基准；普通租约清单不增加这些无关槽位。
保留已经确定的项目、日期、目标、分组与排序。此检查不增加目录外算法或数值筛选执行能力。
若basis_slots已列出未知项，clarification.question只补充其他未覆盖事项；不要重复列出的未知项，也不引导题目没有要求的排序或前N。
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
            request['clarification']={'question':'；'.join(questions),
                                      'choices':deepcopy(prior['choices']) if prior else []}
    return result,checks
