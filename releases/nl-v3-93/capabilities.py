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
    return '''�������רҵ��ҵ�ز���Ӫ��Ա�����������󣬲�����SQL������������
�û�����Ҫʹ��ָ��Ŀ¼�е�רҵ���ơ��������ʹ���仯��������ƥ���������
ҵ��������Ψһ�������������ݣ��û��ı��Ǵ����͵����⣬���ܸ�д��Щ������
�������ʹ������reference_date���ͣ���Ҫ�����û�û˵��ݻ��׼�վ�׷�ʡ�
��Ŀ������ɸѡֵ�����Ƕ���Ĳ�ѯĿ�ꣻproperty�嵥��projectɸѡ����ֿ���
��ĿĿ¼�ǵ�ǰ�ϳ�ҵ���������Ŀ���ϣ����ܲ�δ�г���������Ŀ��ĳ���е���Ŀ������Ŀ¼���ʱ���ɰ��ó���ɸѡ����������/һ����������Ŀ���ܣ����ֱ𡱰�ָ��ά�ȷ��飬��������ȷ��Χ�ظ�׷�ʡ�
�⻧ע���������Ŀ���ڳ����ǲ�ͬά�ȣ���ͬʱɸѡ��ֵͬ��ע����ĳ���в�������Լ��ĿҲ�ڸó��С�û��˵�����к��������ֽ��;�����ʱ�ų��壬��͵��ά�ȡ�
�����ѯĳ��Ŀ�����target��metric��filters����project����������propertyĿ�ꡣ
���֣���ѯĿ��target��filters��time��group_by��order_by������������requests��
ÿ����������Ҫ�������޷������ҵ������Ҫ������׷�ʣ����þ�Ĭ������
Ŀ¼û�е�������ȷ˵����֧�֡�ȱ�ٱ�Ҫ��Ϣ���������һ���¡�
��������ҵ���壬�������ִ��Ƿ������Ŀ¼�У�һ����ȷ��ҵ������ҪĿ¼δ�ṩ�����ݣ�����unsupported��
һ����֧��Ŀ��ֻ��ȱ�Ƚ���ֵ���ڲ����������壬����unresolved��������֪����ʵ������Ŀھ�����ambiguous��
�����������Ӧ����֪��ѯ���޷�֧�ֵ�ҵ�����������������Ӷ����ɴ��������
��������clarification.question�е�������δ����������˵���û��ش�ʲô���ɼ���������ֻ˵����ȷ�Ͽھ�����
����ȷ����Ŀ����ݻ��׼�ղ������û����䣻δ֪ɸѡ��ֵ����αװ�����ڽ��Ͳ��졣
֧��һ�������ھ�����ζ��֧����ʽ��ƿھ���Ҳ����ζ����������ָ���Ǻ����������ѡ��
unsupported����implementation_gap��Ŀ¼�и�Ŀ��/ά�ȵ����δʵ��ʱ�Ա���Ŀ����������
�����е�ά������ҵ��Χ�����������������ʵ�֡�ɸѡֵ������Ŀ/���С��������filter_domains��
filter_value_labels����ö��ֵ��ҵ���壬�û�����֪���ڲ�ID����Ҫ������д��׷�ʡ�
ָ���������������metric_grouping_dimensionsΪ׼��dimension_basis�е���Ҫ���Կھ�������¶��
¥������λ���Ϳ����ɸѡ/�����������������ʡ������Ȩ�����ϸ�ֳ����ʷ�ĸΪ�÷�Χȫ����λ��������������ã�������ȫ��ĿGLA������ƽ������λ���ۻ����Ŀ�����ʡ�
�嵥ɸѡ�����list_filter_dimensionsΪ׼��������list_grouping_dimensionsΪ׼����������չʾ����������ܡ���Լ֧����ȷ��ʼ��/�����շ�Χ��ȫ���������������������ʷ����״̬��δ֧�֡�
�嵥��Ŀ������ȥ�ض����ǹ�����¼�������⻧�嵥����Ŀ������ʾ������Լ�д�����һ��ѡ��Ŀ��������Ҫ��ͬһ�⻧��ȫ����ѡ��Ŀͬʱ���ڡ�������Ŀ����ʱ����Ŀֻ��һ�Σ�����Ŀ����ʱÿ����Ŀ�ڰ�tenant_idȥ�أ�ͬһ�⻧�ɿ���Ŀ���֡�δҪ����Ч״̬ʱ��������ȫ����Լ��
�ѵǼǵ���δʵ�ֵ������������������ڼƻ��У�����У��������ʵ��ȱ�ڣ�����ɾ����ѳ����ݲ����ڡ�
���ڻ�Ӱ�����Ķ��ֺ����ھ�ʱ���г���ʵ���ú�ѡ����ҵ�����Խ��Ͳ��
���ø��ݺ�ѡ�����ӽ�������ִ�У���Ҫ��Ĭ�Ͽھ�����˵������ͨ��ǲ�Ӧ�������塣
���������ݰ�������ִ�����ɣ������������ṹ��������֤��
ҵ���������ã�
''' + json.dumps(prompt_capabilities, ensure_ascii=False, sort_keys=True)
