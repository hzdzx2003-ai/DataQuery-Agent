"""Deterministic user-facing view of checked plans; never invent result values."""


def render_choice(capabilities, choice, plans):
    """Bound choices use checked plan facts, never the model's second definition.

    Unbound legacy choices remain hypotheses, not proof of available capability.
    Raw labels/reasons stay in the decision and original response for review.
    """
    if 'plan_index' not in choice:
        suffix=('����ǰ�����ṩ��' if choice['availability']=='unavailable'
                else '�����ͺ�ѡ����δ���ѯ�ƻ��󶨣�')
        return choice['label']+suffix+'��'+choice['reason']
    index=choice['plan_index']; plan=plans[index]
    status=plan['status']
    suffix=('����ȷ�ϣ��ṹ��У�飬��δִ�У�' if status=='validated_structure_not_execution'
            else '����ǰ��Χ�����ṩ��' if status=='outside_coverage'
            else '������ʵ��ȱ�ڣ�' if status=='not_implemented'
            else '�����貹��������')
    return 'ѡ��'+str(index+1)+suffix+'��\n'+render_compact_plan(capabilities,plan)


def render_compact_plan(capabilities, plan):
    """Retain business slots/basis; remove repeated teaching/permission prose."""
    if plan.get('status')!='validated_structure_not_execution':
        return render_gap(capabilities,plan)
    lines=render_plan(capabilities,plan).splitlines()
    output=[]
    for line in lines:
        if line.startswith('��ѡ��'):
            output.append(line.split('����',1)[0])
        elif line.startswith('����ֻչʾ'):
            continue
        elif line=='����δָ������˳��':
            continue
        else:
            output.append(line)
    return '\n'.join(output)


def render_gap(capabilities, plan):
    """Show retained input without promoting it to a validated query."""
    if plan.get('status') not in {'not_implemented','clarify','outside_coverage'} or 'input_plan' not in plan:
        return plan['message']
    p=plan['input_plan']; context=capabilities['context']
    labels=dict(context['dimension_labels'],month='�·�',point_date='ͳ��ʱ��')
    names={m['id']:m['name_zh'] for m in capabilities['metrics']}
    names.update(context['list_labels'])
    lines=[plan['message'],'���������⣨��δ���ȫ��У�飩��'+names[p['target']['id']]]
    if p['filters']:
        lines.append('ɸѡ��'+'��'.join(labels[f['dimension']]+'Ϊ'+'��'.join(f['values']) for f in p['filters']))
    if p['group_by']:
        lines.append('���飺��'+'��'.join(labels[g] for g in p['group_by']))
    t=p['time']
    if isinstance(t,dict):
        if t.get('kind')=='points':
            lines.append('ָ��ʱ�㣺'+'��'.join(t.get('dates',[])))
        elif t.get('kind')=='field_range':
            lines.append('��Լ����������'+str(t.get('field'))+' '+str(t.get('start'))+'��'+str(t.get('end')))
        elif t.get('kind')=='range':
            lines.append('ԭʱ��������'+str(t.get('start'))+'��'+str(t.get('end'))+'��δȷ�����ݸ��ǣ�')
        elif t.get('kind')=='relative':
            lines.append('ԭʱ��������'+{'previous_month':'�ϸ���','previous_year':'ȥ��'}.get(t.get('period'),'���˶�����ڼ�'))
        elif t.get('kind')=='point':
            lines.append('ԭʱ��������'+str(t.get('date'))+'��δȷ�����ݸ��ǣ�')
        elif t.get('kind')=='missing':
            lines.append('ʱ�䣺�����䣻��������ȷ��������������д��')
    if p['order_by']:
        order=p['order_by']
        if order['by'] in {'lease_start_date','lease_end_date','month','point_date'}:
            lines.append('���򣺰�'+{'lease_start_date':'��Լ��ʼ��','lease_end_date':'��Լ������','month':'�·�','point_date':'ͳ��ʱ��'}[order['by']]+('��������' if order['direction']=='desc' else '���絽��'))
        else:
            lines.append('���򣺰�ָ��'+('�Ӹߵ���' if order['direction']=='desc' else '�ӵ͵���'))
        if 'limit' in p['order_by']:
            lines.append('�������������ƣ�ǰ'+str(p['order_by']['limit'])+'�飨��δ���ȫ��У�飩')
        if 'partition_by' in p['order_by']:
            lines.append('������Χ��ÿ��'+ '��'.join(labels[d] for d in p['order_by']['partition_by'])+'�ڷֱ���������������������')
    lines.append('����ֻ�Ǳ�������������ִ�У�����δ��ѯ��')
    return '\n'.join(lines)


def render_plan(capabilities, plan):
    if plan.get('status') != 'validated_structure_not_execution':
        raise ValueError('renderer requires a validated plan')
    context = capabilities['context']
    metric = next((m for m in capabilities['metrics'] if m['id'] == plan['target']['id']), None)
    is_list=plan['target']['kind']=='list'
    if is_list:
        name=context['list_labels'][plan['target']['id']]
        explanation='չʾ������ȷɸѡ�����ļ�¼�����ǻ�����ֵ'
    elif metric is not None:
        name=metric['name_zh']
        explanation=context['metric_explanations'][metric['id']]
    else:
        raise ValueError('unknown target')
    labels = dict(context['dimension_labels'],month='�·�',point_date='ͳ��ʱ��')
    time=plan['time']
    time_label=('��'.join(time['dates']) if time.get('mode')=='point_series' else
                '���м�¼' if time.get('mode')=='current_records' else
                '����'+time['date'] if 'date' in time else time['start']+'��'+time['end'])
    lines = [f"��ѡ��{name}����{explanation}",
             f"ʱ�䣺{time_label}��{time['basis']}��"]
    if plan['filters']:
        value_labels=context['filter_value_labels']
        filters = [f"{labels[f['dimension']]}Ϊ"+'��'.join(value_labels.get(f['dimension'],{}).get(v,v)
                   for v in f['values']) for f in plan['filters']]
        lines.append('ɸѡ��'+'����'.join(filters))
    else:
        lines.append('ɸѡ��ȫ����Χ��δ���Ӷ���ɸѡ������')
    if plan['group_by']:
        lines.append('���飺��'+'��'.join(labels[g] for g in plan['group_by'])+'�ֱ�չʾ��')
        if is_list:
            lines.append('չʾ�������������г���¼����������������ܡ�')
    else:
        lines.append('չʾ�������嵥���������ܡ�' if is_list else '���飺����֣�չʾ����ָ�ꡣ')
    if plan['order_by']:
        direction = '�Ӹߵ���' if plan['order_by']['direction'] == 'desc' else '�ӵ͵���'
        order_label={'lease_start_date':'��Լ��ʼ��','lease_end_date':'��Լ������','month':'�·�','point_date':'ͳ��ʱ��'}.get(plan['order_by']['by'],'����ָ��')
        if is_list or plan['order_by']['by'] in {'month','point_date'}:
            direction='��������' if plan['order_by']['direction']=='desc' else '���絽��'
        lines.append(f"���򣺰�{order_label}{direction}��")
        if 'partition_by' in plan['order_by']:
            lines.append('������Χ��ÿ��'+'��'.join(labels[d] for d in plan['order_by']['partition_by'])+'�ڷֱ���������������������')
        if 'limit' in plan['order_by']:
            lines.append('������'+('ÿ��������Χ��' if 'partition_by' in plan['order_by'] else '')+'������չʾǰ'+str(plan['order_by']['limit'])+('����¼' if is_list else '��')+'������Nʱչʾ�����ֵͬ����չ�������ȡ����ִ�в���ȷ��')
    else:
        lines.append('����δָ������˳��')
    lines.append('�ھ�˵����'+plan['basis'])
    if metric is not None and not is_list and metric['disclosure_required']:
        lines.append('ָ�궨�壺'+metric['definition'])
    if not is_list and plan['target']['id']=='collection_rate':
        lines.append('���ܿھ����ڵ�ǰɸѡ��Χ��ÿ�������ڣ��Ⱥϼ�ͬ����ʵ����Ӧ�����������ƽ������Ŀ���⻧���·ݵı��ʡ�')
    lines.extend('����ھ���'+basis for basis in plan.get('dimension_basis',[]))
    lines.append('����ֻչʾ���ⷽ������δִ�в�ѯ��Ҳû���������ݽ����')
    return '\n'.join(lines)
