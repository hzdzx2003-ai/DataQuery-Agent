"""Offline comparison of reviewed semantic slots, not language understanding.

Expected slots must be prepared before collection. No substring matching of
messages, no automatic conversion of free-form author Gold to system answers.
"""
from copy import deepcopy


def canonical_slots(slots):
    required={'target','filters','time','group_by','order_by'}
    if not isinstance(slots,dict) or set(slots)!=required:
        raise ValueError('slot set must be complete')
    target=slots['target']
    if not isinstance(target,dict) or set(target)!={'kind','id'}:
        raise ValueError('invalid target')
    if target['kind'] not in {'metric','list'} or not isinstance(target['id'],str) or not target['id']:
        raise ValueError('invalid target identity')
    filters=slots['filters']
    if not isinstance(filters,list):raise ValueError('invalid filters')
    normalized=[];seen=set()
    for f in filters:
        if not isinstance(f,dict) or set(f)!={'dimension','operator','values'}:
            raise ValueError('invalid filter fields')
        d=f['dimension'];values=f['values']
        if not isinstance(d,str) or not d or d in seen or f['operator']!='in':
            raise ValueError('invalid filter dimension')
        if not isinstance(values,list) or not values or not all(isinstance(v,str) and v for v in values) or len(values)!=len(set(values)):
            raise ValueError('invalid filter values')
        seen.add(d);normalized.append(dict(f,values=sorted(values)))
    groups=slots['group_by']
    if not isinstance(groups,list) or not all(isinstance(g,str) and g for g in groups) or len(groups)!=len(set(groups)):
        raise ValueError('invalid grouping')
    # Group dimension presentation order does not change the aggregate key.
    order=deepcopy(slots['order_by'])
    if order is not None:
        if not isinstance(order,dict) or not {'by','direction'}<=set(order) or set(order)-{'by','direction','limit','partition_by'}:
            raise ValueError('invalid ordering')
        if not isinstance(order['by'],str) or order['direction'] not in {'asc','desc'}:
            raise ValueError('invalid sort key')
        if 'limit' in order and (type(order['limit']) is not int or not 1<=order['limit']<=1000):
            raise ValueError('invalid limit')
        if 'partition_by' in order:
            p=order['partition_by']
            if not isinstance(p,list) or not p or not all(isinstance(v,str) for v in p) or len(p)!=len(set(p)) or not set(p)<set(groups):
                raise ValueError('invalid partition')
            order['partition_by']=sorted(p)
    if not isinstance(slots['time'],dict) or not slots['time']:
        raise ValueError('time must be explicitly reviewed')
    return {'target':deepcopy(target),'filters':sorted(normalized,key=lambda f:f['dimension']),
            'time':deepcopy(slots['time']),'group_by':sorted(groups),'order_by':order}


def compare_slots(expected,observed):
    gold=canonical_slots(expected)
    try: actual=canonical_slots(observed)
    except (ValueError,TypeError):
        return {'slot_pass':False,'mismatches':['invalid_observed_slots']}
    mismatches=[k for k in gold if gold[k]!=actual[k]]
    return {'slot_pass':not mismatches,'mismatches':mismatches}
