"""Deterministic user-facing view of checked plans; never invent result values."""


def render_choice(capabilities, choice, plans):
    """Bound choices use checked plan facts, never the model's second definition.

    Unbound legacy choices remain hypotheses, not proof of available capability.
    Raw labels/reasons stay in the decision and original response for review.
    """
    if 'plan_index' not in choice:
        suffix=('（当前不能提供）' if choice['availability']=='unavailable'
                else '（解释候选，尚未与查询计划绑定）')
        return choice['label']+suffix+'：'+choice['reason']
    index=choice['plan_index']; plan=plans[index]
    status=plan['status']
    suffix=('（待确认，结构已校验，尚未执行）' if status=='validated_structure_not_execution'
            else '（当前范围不能提供）' if status=='outside_coverage'
            else '（存在实现缺口）' if status=='not_implemented'
            else '（仍需补充条件）')
    return '选项'+str(index+1)+suffix+'：\n'+render_compact_plan(capabilities,plan)


def render_compact_plan(capabilities, plan):
    """Retain business slots/basis; remove repeated teaching/permission prose."""
    if plan.get('status')!='validated_structure_not_execution':
        return render_gap(capabilities,plan)
    lines=render_plan(capabilities,plan).splitlines()
    output=[]
    for line in lines:
        if line.startswith('候选：'):
            output.append(line.split('——',1)[0])
        elif line.startswith('这里只展示'):
            continue
        elif line=='排序：未指定排名顺序。':
            continue
        else:
            output.append(line)
    return '\n'.join(output)


def render_gap(capabilities, plan):
    """Show retained input without promoting it to a validated query."""
    if plan.get('status') not in {'not_implemented','clarify','outside_coverage'} or 'input_plan' not in plan:
        return plan['message']
    p=plan['input_plan']; context=capabilities['context']
    labels=dict(context['dimension_labels'],month='月份',point_date='统计时点')
    names={m['id']:m['name_zh'] for m in capabilities['metrics']}
    names.update(context['list_labels'])
    lines=[plan['message'],'保留的理解（尚未完成全部校验）：'+names[p['target']['id']]]
    if p['filters']:
        lines.append('筛选：'+'；'.join(labels[f['dimension']]+'为'+'、'.join(f['values']) for f in p['filters']))
    if p['group_by']:
        lines.append('分组：按'+'、'.join(labels[g] for g in p['group_by']))
    t=p['time']
    if isinstance(t,dict):
        if t.get('kind')=='points':
            lines.append('指定时点：'+'、'.join(t.get('dates',[])))
        elif t.get('kind')=='field_range':
            lines.append('租约日期条件：'+str(t.get('field'))+' '+str(t.get('start'))+'至'+str(t.get('end')))
        elif t.get('kind')=='range':
            lines.append('原时间条件：'+str(t.get('start'))+'至'+str(t.get('end'))+'（未确认数据覆盖）')
        elif t.get('kind')=='relative':
            lines.append('原时间条件：'+{'previous_month':'上个月','previous_year':'去年'}.get(t.get('period'),'待核对相对期间'))
        elif t.get('kind')=='point':
            lines.append('原时点条件：'+str(t.get('date'))+'（未确认数据覆盖）')
        elif t.get('kind')=='missing':
            lines.append('时间：待补充；其他已明确条件无需重新填写。')
    if p['order_by']:
        order=p['order_by']
        if order['by'] in {'lease_start_date','lease_end_date','month','point_date'}:
            lines.append('排序：按'+{'lease_start_date':'租约开始日','lease_end_date':'租约结束日','month':'月份','point_date':'统计时点'}[order['by']]+('由晚到早' if order['direction']=='desc' else '由早到晚'))
        else:
            lines.append('排序：按指标'+('从高到低' if order['direction']=='desc' else '从低到高'))
        if 'limit' in p['order_by']:
            lines.append('保留的数量限制：前'+str(p['order_by']['limit'])+'组（尚未完成全部校验）')
        if 'partition_by' in p['order_by']:
            lines.append('排名范围：每个'+ '、'.join(labels[d] for d in p['order_by']['partition_by'])+'内分别排名，不是整体排名。')
    lines.append('条件只是保留，不代表可执行；本次未查询。')
    return '\n'.join(lines)


def render_plan(capabilities, plan):
    if plan.get('status') != 'validated_structure_not_execution':
        raise ValueError('renderer requires a validated plan')
    context = capabilities['context']
    metric = next((m for m in capabilities['metrics'] if m['id'] == plan['target']['id']), None)
    is_list=plan['target']['kind']=='list'
    if is_list:
        name=context['list_labels'][plan['target']['id']]
        explanation='展示符合明确筛选条件的记录，不是汇总数值'
    elif metric is not None:
        name=metric['name_zh']
        explanation=context['metric_explanations'][metric['id']]
    else:
        raise ValueError('unknown target')
    labels = dict(context['dimension_labels'],month='月份',point_date='统计时点')
    time=plan['time']
    time_label=('、'.join(time['dates']) if time.get('mode')=='point_series' else
                '现有记录' if time.get('mode')=='current_records' else
                '截至'+time['date'] if 'date' in time else time['start']+'至'+time['end'])
    lines = [f"候选：{name}——{explanation}",
             f"时间：{time_label}（{time['basis']}）"]
    if plan['filters']:
        value_labels=context['filter_value_labels']
        filters = [f"{labels[f['dimension']]}为"+'、'.join(value_labels.get(f['dimension'],{}).get(v,v)
                   for v in f['values']) for f in plan['filters']]
        lines.append('筛选：'+'；且'.join(filters))
    else:
        lines.append('筛选：全部范围，未添加额外筛选条件。')
    if plan['group_by']:
        lines.append('分组：按'+'、'.join(labels[g] for g in plan['group_by'])+'分别展示。')
        if is_list:
            lines.append('展示：分组下逐条列出记录，不做数量或金额汇总。')
    else:
        lines.append('展示：逐条清单，不做汇总。' if is_list else '分组：不拆分，展示汇总指标。')
    if plan['order_by']:
        direction = '从高到低' if plan['order_by']['direction'] == 'desc' else '从低到高'
        order_label={'lease_start_date':'租约开始日','lease_end_date':'租约结束日','month':'月份','point_date':'统计时点'}.get(plan['order_by']['by'],'上述指标')
        if is_list or plan['order_by']['by'] in {'month','point_date'}:
            direction='由晚到早' if plan['order_by']['direction']=='desc' else '由早到晚'
        lines.append(f"排序：按{order_label}{direction}。")
        if 'partition_by' in plan['order_by']:
            lines.append('排名范围：每个'+'、'.join(labels[d] for d in plan['order_by']['partition_by'])+'内分别排名，不是整体排名。')
        if 'limit' in plan['order_by']:
            lines.append('数量：'+('每个排名范围内' if 'partition_by' in plan['order_by'] else '')+'排序后仅展示前'+str(plan['order_by']['limit'])+('条记录' if is_list else '组')+'；不足N时展示现有项，同值不扩展名额，具体取舍需执行层明确。')
    else:
        lines.append('排序：未指定排名顺序。')
    lines.append('口径说明：'+plan['basis'])
    if metric is not None and not is_list and metric['disclosure_required']:
        lines.append('指标定义：'+metric['definition'])
    if not is_list and plan['target']['id']=='collection_rate':
        lines.append('汇总口径：在当前筛选范围及每个分组内，先合计同账期实收与应收再相除；不平均各项目、租户或月份的比率。')
    lines.extend('分组口径：'+basis for basis in plan.get('dimension_basis',[]))
    lines.append('这里只展示理解方案，尚未执行查询，也没有生成数据结果。')
    return '\n'.join(lines)
