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
        result={'mode':'point_series','dates':sorted(dates),'basis':'逐个指定时点独立计算，按日期先后展示；不是期间平均或累计值。','defaulted':False}
        if failed:
            return dict(result,status=failed['status'],message=failed['message'])
        return dict(result,status='resolved')
    context=capabilities['context']
    reference=date.fromisoformat(context['reference_date'])
    if slot == {'kind':'missing'}:
        point=reference
        basis=f'未指定时点，按业务基准日{reference.isoformat()}统计'
        defaulted=True
    elif set(slot)=={'kind','date'} and slot['kind']=='point':
        point=date.fromisoformat(slot['date'])
        basis='用户指定的统计时点'
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
            return {'status':'not_implemented','message':'该指标的时点能力尚未配置。'}
        coverage = ('当前仅支持基准日'+reference.isoformat() if policy['mode']=='reference_only'
                    else '时点覆盖'+policy['start']+'至'+reference.isoformat())
        return {'status':'clarify', 'message':
                f'已保留原期间{start.isoformat()}至{end.isoformat()}；这个指标按时点统计，请确认其中哪一天或哪些明确时点。'
                +coverage+'；未把期间改为基准日或期末，也未计算期间平均。'}
    else:
        return {'status':'clarify','message':'这个指标按某一天统计，请确认统计时点；不会自动把一段时间改成期末。'}
    policy=context['point_time_capabilities'].get(metric_id)
    if policy is None:
        return {'status':'not_implemented','message':'该指标的时点能力尚未配置。'}
    result={'date':point.isoformat(),'basis':basis,'defaulted':defaulted}
    if point>reference:
        return dict(result,status='outside_coverage',message='该时点晚于业务基准日，不能当作已有数据或预测结果。')
    if policy['mode']=='reference_only' and point!=reference:
        return dict(result,status='not_implemented',message='当前只确认了基准日欠款余额，历史余额重建尚未接入，不能用当前余额替代。')
    if policy['mode']=='lease_dates' and point<date.fromisoformat(policy['start']):
        return dict(result,status='outside_coverage',message='该时点早于当前租约时点查询覆盖范围。')
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
        return {'status': 'clarify', 'message': '你想看哪段时间的数据？'}
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
            return {'status': 'not_implemented', 'message': '此时间类型尚未接入。'}
        basis = f'按业务基准日{reference.isoformat()}解释相对时间'
        if slot['period']=='last_complete_months':
            basis+='；使用最近'+str(slot['months'])+'个完整自然月，不包含基准日所在未完月份'
    elif kind == 'range':
        if set(slot) != {'kind', 'start', 'end'}:
            raise ValueError('range requires start and end only')
        start, end = date.fromisoformat(slot['start']), date.fromisoformat(slot['end'])
        basis = '用户明确的起止日期'
    else:
        raise ValueError('unknown time slot kind')
    if start > end:
        raise ValueError('time range is reversed')
    coverage = capabilities['context']['data_period']
    first, last = date.fromisoformat(coverage['start']), date.fromisoformat(coverage['end'])
    result = {'start': start.isoformat(), 'end': end.isoformat(), 'basis': basis}
    if start < first or end > last:
        return dict(result, status='outside_coverage',
                    message=f'目前数据覆盖{first.isoformat()}至{last.isoformat()}，不能完整回答这段时间。')
    return dict(result, status='resolved')
