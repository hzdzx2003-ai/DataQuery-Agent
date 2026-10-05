"""Offline structural planning slice. No SQL or execute permission."""
from capabilities import validate_target_and_filters
from time_scope import resolve_period, resolve_point
from copy import deepcopy
from datetime import date


def validate_query_plan(capabilities, plan):
    required = {'target', 'filters', 'time', 'group_by', 'order_by'}
    if not isinstance(plan, dict) or set(plan) != required:
        raise ValueError('query plan has missing or unexpected fields')
    checked = validate_target_and_filters(capabilities, plan['target'], plan['filters'])
    groups = plan['group_by']
    if (not isinstance(groups, list) or not all(isinstance(d, str) for d in groups)
            or len(groups) != len(set(groups))):
        raise ValueError('group_by must contain unique dimension IDs')
    if not set(groups) <= set(capabilities['context']['dimensions']) | {'month','point_date'}:
        raise ValueError('unknown grouping dimension')
    order = plan['order_by']
    if order is not None:
        if (not isinstance(order,dict) or not {'by','direction'} <= set(order)
                or set(order)-{'by','direction','limit','partition_by'}
                or order.get('by') not in {'target_value','month','point_date','lease_start_date','lease_end_date'} or order.get('direction') not in {'asc','desc'}):
            raise ValueError('invalid ranking structure')
        if order['by'] in {'lease_start_date','lease_end_date'} and checked['target'] != {'kind':'list','id':'lease'}:
            raise ValueError('lease date ordering requires a lease list')
        if order['by'] in {'month','point_date'} and (order['by'] not in groups or checked['target']['kind']!='metric'
                                                     or 'limit' in order or 'partition_by' in order):
            raise ValueError('chronological sort requires matching time grouping without top N')
        if 'limit' in order and (type(order['limit']) is not int or not 1<=order['limit']<=1000):
            raise ValueError('ranking limit must be an integer from1to1000')
        if 'partition_by' in order:
            partition=order['partition_by']
            if (not isinstance(partition,list) or not partition or not all(isinstance(d,str) for d in partition)
                    or len(partition)!=len(set(partition)) or not set(partition)<set(groups)):
                raise ValueError('ranking partition must be a nonempty proper subset of grouping dimensions')
            if checked['target']['kind']!='metric' or order['by']!='target_value' or 'limit' not in order:
                raise ValueError('partitioned top N requires a metric value and explicit limit')
    if checked.get('unimplemented_filter_dimensions'):
        labels=capabilities['context']['dimension_labels']
        pending=set(checked['unimplemented_filter_dimensions'])
        retained='；'.join(labels[f['dimension']]+'为'+'、'.join(f['values'])
                          for f in checked['filters'] if f['dimension'] in pending)
        return {'status':'not_implemented',**checked,'group_by':list(groups),
                'input_plan':deepcopy(plan), 'retained_input_verified':False,
                'filter_values_verified':False,
                'message':'已保留筛选条件：'+retained+'。该维度已登记，但筛选值目录和关联尚未接入，本次不会忽略条件后查询。'}
    if checked['target']['kind']=='list':
        return validate_list_plan(capabilities,checked,plan)
    if order is not None:
        if not groups:
            raise ValueError('ranking requires an explicit grouping dimension')
    metric = next(m for m in capabilities['metrics'] if m['id'] == checked['target']['id'])
    # Deliberately narrow, reviewable join capability, not a language whitelist.
    # Unknown combinations are implementation gaps, not a claim of absent data.
    supported_dimensions = set(capabilities['context']['metric_grouping_dimensions'][metric['id']])
    if metric['time_type']=='period':
        supported_dimensions.add('month')
    is_series=isinstance(plan['time'],dict) and plan['time'].get('kind')=='points'
    if is_series and metric['time_type']!='period':
        supported_dimensions.add('point_date')
        if 'point_date' not in groups:
            raise ValueError('point series requires explicit point_date grouping')
    elif 'point_date' in groups:
        raise ValueError('point_date grouping requires a point series')
    used_dimensions = set(groups) | {f['dimension'] for f in checked['filters']}
    if not used_dimensions <= supported_dimensions:
        return {'status':'not_implemented', 'message':'该指标与维度的组合尚未完成业务校验。',
                'input_plan':deepcopy(plan), 'retained_input_verified':False}
    period = (resolve_period(capabilities, plan['time']) if metric['time_type']=='period'
              else resolve_point(capabilities,metric['id'],plan['time']))
    if period['status'] != 'resolved':
        return {'status':period['status'], **checked, 'time':period,
                'group_by':list(groups), 'order_by':None if order is None else dict(order),
                'input_plan':deepcopy(plan), 'retained_input_verified':False,
                'message':period['message']}
    return {'status':'validated_structure_not_execution', **checked, 'time':period,
            'group_by':list(groups), 'order_by':None if order is None else dict(order),
            'dimension_basis':[capabilities['context']['dimension_basis'][d] for d in sorted(used_dimensions)
                               if d in capabilities['context']['dimension_basis']]
                              + ([capabilities['context']['dimension_basis']['occupancy_unit_scope']]
                                 if metric['id']=='occupancy_rate' and used_dimensions & {'floor','unit_type'} else [])
                              + (['月份按指标原账期或费用月份拆分；无指标排名时按月份先后展示。收缴率逐组总实收除总应收，不平均比率。'] if 'month' in groups else []),
            'basis':metric['default_assumption'], 'disclosure_required':metric['disclosure_required'],
            'coverage_verified':False,
            'limitation':'Requires intent completeness, ambiguity and safety routing before any execution.'}


def validate_list_plan(capabilities, checked, plan):
    """Current stored records only, not inferred active/historical state."""
    supported_groups=set(capabilities['context']['list_grouping_dimensions'][checked['target']['id']])
    order=plan['order_by']
    date_order=(checked['target']['id']=='lease' and order is not None
                and order['by'] in {'lease_start_date','lease_end_date'} and not plan['group_by'])
    if not set(plan['group_by']) <= supported_groups or (order is not None and not date_order):
        return {'status':'not_implemented','input_plan':deepcopy(plan),'retained_input_verified':False,'message':'清单的分组或排序尚未接入，条件已保留，不会擅自忽略。'}
    allowed=capabilities['context']['list_filter_dimensions'][checked['target']['id']]
    if any(f['dimension'] not in allowed for f in checked['filters']):
        return {'status':'not_implemented','input_plan':deepcopy(plan),'retained_input_verified':False,'message':'该清单筛选组合尚未接入。'}
    slot=plan['time']
    if not isinstance(slot,dict):
        raise ValueError('list time must be an object')
    resolved_time={'status':'resolved','mode':'current_records','basis':'读取现有记录清单，不默认只保留有效或已出租记录'}
    if slot.get('kind')=='field_range':
        if (set(slot)!={'kind','field','start','end'} or slot['field'] not in {'lease_start_date','lease_end_date'}):
            raise ValueError('invalid lease date range fields')
        if checked['target']['id']!='lease':
            raise ValueError('lease date range requires a lease list')
        if not all(isinstance(slot[k],str) for k in ('start','end')):
            raise ValueError('lease date bounds must be ISO strings')
        start,end=date.fromisoformat(slot['start']),date.fromisoformat(slot['end'])
        if start.isoformat()!=slot['start'] or end.isoformat()!=slot['end'] or start>end:
            raise ValueError('invalid lease date bounds')
        resolved_time={'status':'resolved','mode':'lease_date_field','field':slot['field'],
                       'start':slot['start'],'end':slot['end'],
                       'basis':'按现有租约记载的'+('开始日' if slot['field']=='lease_start_date' else '结束日')+'筛选，起止日期均包含；不推断历史有效状态，未来到期日不等于未来实际经营数据。'}
    elif slot not in ({'kind':'missing'},{'kind':'not_applicable'}):
        return {'status':'not_implemented','input_plan':deepcopy(plan),'retained_input_verified':False,'message':'清单中的时间条件需进一步实现，不会将它忽略并返回所有记录。'}
    return {'status':'validated_structure_not_execution',**checked,
        'time':resolved_time,
        'group_by':list(plan['group_by']), 'order_by':deepcopy(order),
        'record_semantics':{'identity_key':capabilities['context']['list_identity_keys'][checked['target']['id']],
                            'deduplicate_within':list(plan['group_by']),
                            'project_match':'any_selected_existing_lease' if checked['target']['id']=='tenant' else 'record_project',
                            'implicit_active_lease_filter':False},
        'basis':'仅应用明确列出的筛选条件，不推断状态过滤。分组只整理记录，不计算汇总指标。'
                + ('按tenant_id在每组内去重；没有分组时跨所有所选项目只列一次。项目筛选为存在任一所选项目的现有租约，不默认只看有效租约；同一租户可出现在不同项目组，但每组内不因多份租约重复。'
                   if checked['target']['id']=='tenant' else '按目标记录身份在每组内去重，不因关联产生重复记录。'),
        'dimension_basis':[capabilities['context']['dimension_basis'][d]
                           for d in sorted(set(plan['group_by']) | {f['dimension'] for f in checked['filters']})
                           if d in capabilities['context']['dimension_basis']],
        'disclosure_required':False,'coverage_verified':False,
        'limitation':'List plan only; explicit lease date fields supported, historical active-state reconstruction and execution not implemented.'}
