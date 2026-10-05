"""Independent Python/Decimal result oracle from reviewed Gold and source rows.

Does not import the SQL compiler, resolver, model answers or generated SQL. A
second implementation by the same coordinator is not independent human review.
"""
from collections import defaultdict
from decimal import Decimal


def number(value):
    return Decimal(str(value))


class Reference:
    def __init__(self, tables):
        self.tables = tables
        self.properties = {r['property_id']: r for r in tables['properties']}
        self.units = {r['unit_id']: r for r in tables['units']}
        self.tenants = {r['tenant_id']: r for r in tables['tenants']}
        self.leases = {r['lease_id']: r for r in tables['leases']}

    def dims(self, p=None, u=None, t=None, month=None, expense=None, point=None):
        d = {}
        if p:
            d.update(project=p['property_name'], project_city=p['city'], project_type=p['property_type'],
                     project_district={'�����':'���', '�ֶ�����':'�ֶ�'}.get(p['district'], p['district']))
        if u:
            d.update(unit_type=u['unit_type'], floor=str(u['floor']))
        if t:
            d.update(tenant=t['tenant_id'], tenant_tier=t['tenant_tier'], tenant_industry=t['industry'],
                     tenant_registration_city=t['registered_city'])
        if month is not None:
            d['month'] = month[:7]
        if point is not None:
            d['point_date'] = point
        if expense:
            d['expense_category'] = dict(property_management='��ҵ����', utilities='ˮ��', maintenance='ά��ά��', marketing='Ӫ��', security='����')[expense]
        return d

    @staticmethod
    def matches(d, filters):
        return all(d[f['dimension']] in f['values'] for f in filters)

    def calculate(self, gold_slots):
        slots = gold_slots
        groups = sorted(slots['group_by'])
        filters, time = slots['filters'], slots['time']
        target = slots['target']['id']
        values = defaultdict(lambda: [Decimal(0), Decimal(0)])
        if not groups:
            values[()]  # empty summary: zero sum / null ratio

        def add(d, a, b=0):
            if self.matches(d, filters):
                key = tuple(d[g] for g in groups)
                values[key][0] += number(a)
                values[key][1] += number(b)

        if slots['target']['kind'] == 'list':
            rows = self.list_rows(slots, groups)
        else:
            if target in {'rent_due','rent_collected','collection_rate','overdue_balance','cash_noi_proxy'}:
                for r in self.tables['rent_payments']:
                    l = self.leases[r['lease_id']]
                    u = self.units[l['unit_id']]
                    p, t = self.properties[u['property_id']], self.tenants[l['tenant_id']]
                    if target == 'overdue_balance':
                        if not (r['due_date'] < time['date'] and r['amount_paid'] < r['amount_due']):
                            continue
                        a = number(r['amount_due']) - number(r['amount_paid'])
                    else:
                        if not time['start'][:7] <= r['billing_month'][:7] <= time['end'][:7]:
                            continue
                        a = r['amount_due'] if target == 'rent_due' else r['amount_paid']
                    add(self.dims(p,u,t,month=r['billing_month']), a, r['amount_due'] if target == 'collection_rate' else 0)
            if target in {'operating_expense','budget_variance','cash_noi_proxy'}:
                for e in self.tables['operating_expenses']:
                    if not time['start'][:7] <= e['expense_month'][:7] <= time['end'][:7]:
                        continue
                    a = number(e['amount'])
                    if target == 'budget_variance':
                        a -= number(e['budget_amount'])
                    if target == 'cash_noi_proxy':
                        a = -a
                    add(self.dims(self.properties[e['property_id']], month=e['expense_month'], expense=e['expense_category']), a)
            if target in {'leased_area','occupancy_rate','avg_monthly_rent_per_sqm'}:
                scoped = bool((set(groups) | {f['dimension'] for f in filters}) & {'floor','unit_type'})
                for day in time.get('dates', [time.get('date')]):
                    for u in self.units.values():
                        p = self.properties[u['property_id']]
                        active = [l for l in self.leases.values() if l['unit_id']==u['unit_id'] and l['lease_start_date'] <= day <= l['lease_end_date']]
                        area = number(u['leasable_area_sqm']) if active else Decimal(0)
                        a, b = area, 0
                        if target == 'occupancy_rate' and scoped:
                            b = u['leasable_area_sqm']
                        if target == 'avg_monthly_rent_per_sqm':
                            a = sum((number(l['monthly_base_rent']) for l in active), Decimal(0))
                            b = area
                        add(self.dims(p,u,point=day), a, b)
                    if target == 'occupancy_rate' and not scoped:
                        for p in self.properties.values():
                            add(self.dims(p,point=day), 0, p['gross_leasable_area_sqm'])
            ratios = {'collection_rate','occupancy_rate','avg_monthly_rent_per_sqm'}
            rows = []
            for key, (a,b) in values.items():
                value = a / b if target in ratios and b else None if target in ratios else a
                rows.append(dict(zip(groups,key)) | {'value': None if value is None else float(value)})
        return self.sort(rows, slots, groups)

    def list_rows(self, slots, groups):
        target, time, filters = slots['target']['id'], slots['time'], slots['filters']
        found = {}
        for r in self.tables[dict(property='properties',unit='units',tenant='tenants',lease='leases')[target]]:
            p = u = t = None
            if target == 'property':
                p = r
            elif target == 'unit':
                u, p = r, self.properties[r['property_id']]
            elif target == 'lease':
                u, t = self.units[r['unit_id']], self.tenants[r['tenant_id']]
                p = self.properties[u['property_id']]
                if time['mode']=='lease_date_field' and not time['start'] <= r[time['field']] <= time['end']:
                    continue
            else:
                t = r
            dims = [self.dims(p,u,t)]
            if target == 'tenant' and (set(groups)|{f['dimension'] for f in filters}) & {'project','project_city'}:
                dims = []
                for l in self.leases.values():
                    if l['tenant_id']==r['tenant_id']:
                        u = self.units[l['unit_id']]
                        dims.append(self.dims(self.properties[u['property_id']],u,r))
            identity = r[dict(property='property_id',unit='unit_id',tenant='tenant_id',lease='lease_id')[target]]
            label = r[dict(property='property_name',unit='unit_number',tenant='tenant_name',lease='lease_id')[target]]
            for d in dims:
                if not self.matches(d, filters):
                    continue
                key = tuple(d[g] for g in groups)+(identity,)
                item = dict(zip(groups,key)) | {'entity_id':identity,'label':label}
                if target=='lease':
                    item.update(lease_start_date=r['lease_start_date'],lease_end_date=r['lease_end_date'])
                found[key] = item
        return list(found.values())

    @staticmethod
    def sort(rows, slots, groups):
        identity = ['entity_id'] if slots['target']['kind']=='list' else []
        rows.sort(key=lambda r: tuple(r[g] for g in groups+identity))
        order = slots['order_by']
        if not order:
            return rows
        field = 'value' if order['by']=='target_value' else order['by']
        present = [r for r in rows if r[field] is not None]
        absent = [r for r in rows if r[field] is None]
        present.sort(key=lambda r:r[field], reverse=order['direction']=='desc')
        rows = present + absent
        if order.get('partition_by'):
            parts = defaultdict(list)
            for row in rows:
                parts[tuple(row[g] for g in order['partition_by'])].append(row)
            return [r for key in sorted(parts) for r in parts[key][:order['limit']]]
        return rows[:order['limit']] if 'limit' in order else rows
