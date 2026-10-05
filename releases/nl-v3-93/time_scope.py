"""Resolve semantic time slots, not Chinese wording. No execution permission.

The future language adapter maps paraphrases into these slots; it must preserve
ambiguity rather than invent a slot. Supported here: period metrics only.
"""
from datetime import date, timedelta


def resolve_point(capabilities, metric_id, slot):
    """Point dates use per-metric support, not the billing-period end date."""
    if not isinstance(slot, dict):
        raise ValueError('point time must be an object')
    if slot.get('kind')=='points':
        if set(slot)!={'kind','dates'}:
            raise ValueError('point series requires dates only')
        dates=slot['dates']
        if (not isinstance(dates,list) or not 1<=len(dates)<=120
                or not all(isinstance(d,str) for d in dates) or len(dates)!=len(set(dates))):
            raise ValueError('point series must contain unique ISO dates')
        if any(date.fromisoformat(d).isoformat()!=d for d in dates):
            raise ValueError('point series dates must be canonical ISO')
        points=[resolve_point(capabilities,metric_id,{'kind':'point','date':d}) for d in dates]
        failed=next((p for p in points if p['status']!='resolved'),None)
        result={'mode':'point_series','dates':sorted(dates),'basis':'���ָ��ʱ��������㣬�������Ⱥ�չʾ�������ڼ�ƽ�����ۼ�ֵ��','defaulted':False}
        if failed:
            return dict(result,status=failed['status'],message=failed['message'])
        return dict(result,status='resolved')
    context=capabilities['context']
    reference=date.fromisoformat(context['reference_date'])
    if slot == {'kind':'missing'}:
        point=reference
        basis=f'δָ��ʱ�㣬��ҵ���׼��{reference.isoformat()}ͳ��'
        defaulted=True
    elif set(slot)=={'kind','date'} and slot['kind']=='point':
        point=date.fromisoformat(slot['date'])
        basis='�û�ָ����ͳ��ʱ��'
        defaulted=False
    elif slot.get('kind') == 'range':
        if set(slot) != {'kind', 'start', 'end'}:
            raise ValueError('range requires start and end only')
        start, end = date.fromisoformat(slot['start']), date.fromisoformat(slot['end'])
        if start.isoformat() != slot['start'] or end.isoformat() != slot['end']:
            raise ValueError('range dates must be canonical ISO')
        if start > end:
            raise ValueError('time range is reversed')
        policy = context['point_time_capabilities'].get(metric_id)
        if policy is None:
            return {'status':'not_implemented','message':'��ָ���ʱ��������δ���á�'}
        coverage = ('��ǰ��֧�ֻ�׼��'+reference.isoformat() if policy['mode']=='reference_only'
                    else 'ʱ�㸲��'+policy['start']+'��'+reference.isoformat())
        return {'status':'clarify', 'message':
                f'�ѱ���ԭ�ڼ�{start.isoformat()}��{end.isoformat()}�����ָ�갴ʱ��ͳ�ƣ���ȷ��������һ�����Щ��ȷʱ�㡣'
                +coverage+'��δ���ڼ��Ϊ��׼�ջ���ĩ��Ҳδ�����ڼ�ƽ����'}
    else:
        return {'status':'clarify','message':'���ָ�갴ĳһ��ͳ�ƣ���ȷ��ͳ��ʱ�㣻�����Զ���һ��ʱ��ĳ���ĩ��'}
    policy=context['point_time_capabilities'].get(metric_id)
    if policy is None:
        return {'status':'not_implemented','message':'��ָ���ʱ��������δ���á�'}
    result={'date':point.isoformat(),'basis':basis,'defaulted':defaulted}
    if point>reference:
        return dict(result,status='outside_coverage',message='��ʱ������ҵ���׼�գ����ܵ����������ݻ�Ԥ������')
    if policy['mode']=='reference_only' and point!=reference:
        return dict(result,status='not_implemented',message='��ǰֻȷ���˻�׼��Ƿ������ʷ����ؽ���δ���룬�����õ�ǰ��������')
    if policy['mode']=='lease_dates' and point<date.fromisoformat(policy['start']):
        return dict(result,status='outside_coverage',message='��ʱ�����ڵ�ǰ��Լʱ���ѯ���Ƿ�Χ��')
    if policy['mode'] not in {'reference_only','lease_dates'}:
        raise ValueError('unknown point capability mode')
    return dict(result,status='resolved')


def resolve_period(capabilities, slot):
    if not isinstance(slot, dict):
        raise ValueError('time slot must be an object')
    kind = slot.get('kind')
    reference = date.fromisoformat(capabilities['context']['reference_date'])
    if kind == 'missing':
        if set(slot) != {'kind'}:
            raise ValueError('unexpected missing-time fields')
        return {'status': 'clarify', 'message': '���뿴�Ķ�ʱ������ݣ�'}
    if kind == 'relative':
        expected={'kind','period','months'} if slot.get('period')=='last_complete_months' else {'kind','period'}
        if set(slot) != expected:
            raise ValueError('relative time requires a period only')
        if slot['period'] == 'previous_month':
            end = reference.replace(day=1) - timedelta(days=1)
            start = end.replace(day=1)
        elif slot['period'] == 'previous_year':
            start, end = date(reference.year-1, 1, 1), date(reference.year-1, 12, 31)
        elif slot['period'] == 'previous_quarter':
            current_quarter_start=reference.replace(month=((reference.month-1)//3)*3+1,day=1)
            end=current_quarter_start-timedelta(days=1)
            start=end.replace(month=((end.month-1)//3)*3+1,day=1)
        elif slot['period'] == 'last_complete_months':
            months=slot['months']
            if type(months) is not int or not 1<=months<=120:
                raise ValueError('months must be an integer from1to120')
            end=reference.replace(day=1)-timedelta(days=1)
            month_index=end.year*12+end.month-1-(months-1)
            start=date(month_index//12,month_index%12+1,1)
        else:
            # Unimplemented is not evidence that the user's question is invalid.
            return {'status': 'not_implemented', 'message': '��ʱ��������δ���롣'}
        basis = f'��ҵ���׼��{reference.isoformat()}�������ʱ��'
        if slot['period']=='last_complete_months':
            basis+='��ʹ�����'+str(slot['months'])+'��������Ȼ�£���������׼������δ���·�'
    elif kind == 'range':
        if set(slot) != {'kind', 'start', 'end'}:
            raise ValueError('range requires start and end only')
        start, end = date.fromisoformat(slot['start']), date.fromisoformat(slot['end'])
        basis = '�û���ȷ����ֹ����'
    else:
        raise ValueError('unknown time slot kind')
    if start > end:
        raise ValueError('time range is reversed')
    coverage = capabilities['context']['data_period']
    first, last = date.fromisoformat(coverage['start']), date.fromisoformat(coverage['end'])
    result = {'start': start.isoformat(), 'end': end.isoformat(), 'basis': basis}
    if start < first or end > last:
        return dict(result, status='outside_coverage',
                    message=f'Ŀǰ���ݸ���{first.isoformat()}��{last.isoformat()}�����������ش����ʱ�䡣')
    return dict(result, status='resolved')
