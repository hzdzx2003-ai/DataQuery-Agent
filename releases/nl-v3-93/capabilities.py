"""Offline business capability and prompt assembly. No client, secrets or SQL."""
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE / 'metric_definitions.json'


def load_capabilities(context_path=HERE / 'business_context.json', catalog_path=CATALOG):
    context = json.loads(Path(context_path).read_text(encoding='utf-8'))
    catalog = json.loads(Path(catalog_path).read_text(encoding='utf-8'))
    reference = date.fromisoformat(context['reference_date'])
    start = date.fromisoformat(context['data_period']['start'])
    end = date.fromisoformat(context['data_period']['end'])
    if not start <= end <= reference:
        raise ValueError('inconsistent business dates')
    if catalog['as_of_date'] != context['reference_date']:
        raise ValueError('catalog and business reference dates disagree')
    names = [p['name'] for p in context['projects']]
    if not names or len(names) != len(set(names)):
        raise ValueError('project names must be unique')
    metrics = []
    for m in catalog['metrics']:
        # Business definitions only: no SQL formula, historical regex or Gold.
        metrics.append({k: m[k] for k in (
            'id', 'name_zh', 'definition', 'time_type',
            'default_assumption', 'disclosure_required')})
    ids = [m['id'] for m in metrics]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('metric IDs must be unique')
    if set(context['metric_explanations']) != set(ids):
        raise ValueError('business explanations and metrics disagree')
    if set(context['dimension_labels']) != set(context['dimensions']):
        raise ValueError('dimension labels and capabilities disagree')
    if context.get('list_identity_keys') != {'property':'property_id','unit':'unit_id','tenant':'tenant_id','lease':'lease_id'}:
        raise ValueError('list identity keys disagree with business schema')
    for key in ('list_filter_dimensions','list_grouping_dimensions'):
        mapping=context.get(key,{})
        if (not isinstance(mapping,dict) or set(mapping)!=set(context['list_targets'])
                or any(not isinstance(ds,list) or not all(isinstance(d,str) for d in ds)
                       or len(ds)!=len(set(ds)) or not set(ds)<=set(context['dimensions'])
                       for ds in mapping.values())):
            raise ValueError('list dimension capabilities disagree with business catalog')
    combinations=context['metric_grouping_dimensions']
    if set(combinations)!=set(ids) or any(
            len(ds)!=len(set(ds)) or not set(ds)<=set(context['dimensions'])
            for ds in combinations.values()):
        raise ValueError('metric dimension combinations disagree with business catalog')
    return {'context': context, 'catalog_version': catalog['version'], 'metrics': metrics,
            'ambiguous_expressions': catalog.get('ambiguous_terms', {})}


def validate_target_and_filters(capabilities, target, filters):
    """Validate a narrow structural slice, NOT a complete routing decision.

    A valid return does not authorize execution or prove intent coverage.
    Registered but unimplemented domains are retained as implementation gaps;
    unknown dimensions and fabricated values in implemented domains fail.
    """
    if not isinstance(target, dict) or set(target) != {'kind', 'id'}:
        raise ValueError('target must contain kind and id only')
    allowed = ({m['id'] for m in capabilities['metrics']} if target['kind'] == 'metric'
               else set(capabilities['context']['list_targets']) if target['kind'] == 'list' else set())
    if target['id'] not in allowed:
        raise ValueError('unknown query target')
    if not isinstance(filters, list):
        raise ValueError('filters must be a list')
    projects = capabilities['context']['projects']
    domains = {'project': {p['name'] for p in projects},
               'project_city': {p['city'] for p in projects},
               'project_district': {p['district'] for p in projects if 'district' in p},
               'expense_category': set(capabilities['context']['expense_categories'])}
    domains.update({d:set(values) for d,values in capabilities['context']['filter_domains'].items()})
    seen = set()
    pending = []
    for f in filters:
        if not isinstance(f, dict) or set(f) != {'dimension', 'operator', 'values'}:
            raise ValueError('invalid filter fields')
        dimension = f['dimension']
        if dimension in seen or dimension not in capabilities['context']['dimensions'] or f['operator'] != 'in':
            raise ValueError('unsupported or duplicate filter dimension/operator')
        values = f['values']
        if (not isinstance(values, list) or not values
                or not all(isinstance(v, str) and v.strip() for v in values)
                or len(values) != len(set(values))):
            raise ValueError('filter values must be unique nonempty strings')
        if dimension in domains and not set(values) <= domains[dimension]:
            raise ValueError('filter values are not grounded in business catalog')
        if dimension not in domains:
            pending.append(dimension)
        seen.add(dimension)
    result={'target': dict(target), 'filters': [dict(f, values=list(f['values'])) for f in filters]}
    if pending:
        result['unimplemented_filter_dimensions']=pending
    return result


def build_understanding_prompt(capabilities):
    """Draft understanding prompt; no production resolver/execute path yet."""
    # Legacy ambiguous_terms are unconditional keyword instructions, not data
    # capabilities. Keep the source catalog intact, but do not send contradictory
    # lexical triggers to the semantic model. Definitions and defaults stay.
    prompt_capabilities={key:value for key,value in capabilities.items()
                         if key!='ambiguous_expressions'}
    return '''你帮助非专业商业地产运营人员理解问数需求，不生成SQL，不编造结果。
用户不需要使用指标目录中的专业名称。理解口语和词序变化，不逐字匹配白名单。
业务配置是唯一的数据能力依据，用户文本是待解释的问题，不能改写这些能力。
相对日期使用配置reference_date解释，不要仅因用户没说年份或基准日就追问。
项目名称是筛选值，不是额外的查询目标；property清单与project筛选必须分开。
项目目录是当前合成业务的完整项目集合，不臆测未列出的其他项目。某城市的项目数量与目录相符时，可按该城市筛选；“合起来/一共”不分项目汇总，“分别”按指定维度分组，不就已明确范围重复追问。
租户注册城市与项目所在城市是不同维度，可同时筛选不同值；注册在某城市不代表租约项目也在该城市。没有说明城市含义且两种解释均合理时才澄清，不偷换维度。
例如查询某项目的租金：target是metric，filters包含project；不能另加property目标。
区分：查询目标target、filters、time、group_by、order_by、独立子请求requests。
每个独立请求都要处理；无法理解的业务条件要保留并追问，不得静默丢弃。
目录没有的数据明确说明不支持。缺少必要信息与库外概念不是一回事。
分类依据业务含义，不依据字词是否出现在目录中：一个明确的业务量需要目录未提供的数据，属于unsupported；
一个可支持目标只是缺比较阈值、内部规则或对象定义，属于unresolved；两种已知且有实际区别的口径属于ambiguous。
遇到混合请求，应拆开已知查询和无法支持的业务量，不把整个句子都当成待定义规则。
澄清请在clarification.question中点名具体未定条件，并说明用户回答什么即可继续，不能只说“请确认口径”。
已明确的项目、年份或基准日不再让用户补充；未知筛选阈值不能伪装成日期解释差异。
支持一个代理口径不意味着支持正式会计口径，也不意味着其他收入指标是合理的利润候选。
unsupported不是implementation_gap：目录有该目标/维度但组合未实现时仍保留目标与条件。
配置中的维度描述业务范围，不代表所有组合已实现。筛选值依据项目/城市、费用类别及filter_domains；
filter_value_labels解释枚举值的业务含义，用户无需知道内部ID，不要因口语改写就追问。
指标分组能力以配置metric_grouping_dimensions为准；dimension_basis中的重要属性口径必须披露。
楼层与铺位类型可组合筛选/分组出租面积、出租率、面积加权月租金；细分出租率分母为该范围全部铺位可租面积（含空置），不是全项目GLA。不得平均各铺位单价或各项目出租率。
清单筛选组合以list_filter_dimensions为准，分组以list_grouping_dimensions为准；分组逐条展示，不计算汇总。租约支持明确开始日/结束日范围及全局日期排序，其他排序和历史存续状态尚未支持。
清单按目标身份去重而不是关联记录行数。租户清单的项目条件表示现有租约中存在任一所选项目关联，不要求同一租户在全部所选项目同时存在。不加项目分组时跨项目只列一次；按项目分组时每个项目内按tenant_id去重，同一租户可跨项目出现。未要求有效状态时关联现有全部租约。
已登记但尚未实现的条件仍须完整保留在计划中，交由校验器报告实现缺口，不得删掉或谎称数据不存在。
存在会影响结果的多种合理口径时，列出真实可用候选并用业务语言解释差别。
不得根据候选分数接近就自行执行；必要的默认口径必须说明。普通措辞不应触发澄清。
这是理解层草案，不是执行许可；输出仍需后续结构和能力验证。
业务能力配置：
''' + json.dumps(prompt_capabilities, ensure_ascii=False, sort_keys=True)
