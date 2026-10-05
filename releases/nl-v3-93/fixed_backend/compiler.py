"""Allow-listed metric formulas and parameter bindings. Never accepts model SQL.

Input is one fully resolved query plan, not a question or Gold label. This module
does not decide whether language was understood correctly. No schema discovery,
network, credential access or SQL-generating model is used.
"""
from copy import deepcopy
from calendar import monthrange
from pathlib import Path
import sqlite3

from capabilities import load_capabilities
from query_plan import validate_query_plan
from single_task_evaluation import observed_slots


DIM = {
    'project': 'p.property_name', 'project_city': 'p.city',
    'project_district': "CASE p.district WHEN '浦东新区' THEN '浦东' WHEN '徐汇区' THEN '徐汇' ELSE p.district END",
    'project_type': 'p.property_type', 'floor': 'CAST(u.floor AS TEXT)',
    'unit_type': 'u.unit_type', 'tenant': 't.tenant_id',
    'tenant_registration_city': 't.registered_city', 'tenant_tier': 't.tenant_tier',
    'tenant_industry': 't.industry',
    'expense_category': "CASE e.expense_category WHEN 'property_management' THEN '物业管理' WHEN 'utilities' THEN '水电' WHEN 'maintenance' THEN '维修维护' WHEN 'marketing' THEN '营销' WHEN 'security' THEN '安保' END",
}
PAY = 'rent_payments r JOIN leases l ON l.lease_id=r.lease_id JOIN units u ON u.unit_id=l.unit_id JOIN properties p ON p.property_id=u.property_id JOIN tenants t ON t.tenant_id=l.tenant_id'
EXP = 'operating_expenses e JOIN properties p ON p.property_id=e.property_id'
UNIT = 'units u JOIN properties p ON p.property_id=u.property_id'
IDENTITIES = {'property': ('p.property_id', 'p.property_name'),
              'unit': ('u.unit_id', 'u.unit_number'),
              'tenant': ('t.tenant_id', 't.tenant_name'),
              'lease': ('l.lease_id', 'l.lease_id')}
KINDS = {'period': 'range', 'point': 'point', 'point_series': 'points',
         'current_records': 'not_applicable', 'lease_date_field': 'field_range'}


def validate_slots(slots):
    if slots.get('time', {}).get('mode') == 'period':
        start, end = slots['time']['start'], slots['time']['end']
        if start[8:] != '01' or int(end[8:]) != monthrange(int(end[:4]), int(end[5:7]))[1]:
            raise ValueError('monthly facts cannot answer partial-month allocation')
    raw = deepcopy(slots)
    mode = raw['time'].pop('mode')
    raw['time']['kind'] = KINDS[mode]
    checked = validate_query_plan(load_capabilities(), raw)
    if checked['status'] != 'validated_structure_not_execution':
        raise ValueError('unresolved or unsupported execution plan')
    result = observed_slots(checked)
    result['group_by'] = sorted(result['group_by'])
    return result


def slots_from_decision(decision):
    # Explicit new execution adapter; never reinterpret the old preview-only
    # execution_allowed=False as a legacy grant of database access.
    if decision.get('action') != 'query_candidate':
        raise ValueError('clarify/reject/parser errors cannot reach execution')
    requests = decision.get('requests', [])
    if len(requests) != 1 or requests[0].get('kind') != 'query':
        raise ValueError('single resolved query required')
    plans = requests[0].get('plans', [])
    if len(plans) != 1:
        raise ValueError('exactly one plan required')
    return validate_slots(observed_slots(plans[0]))


class Builder:
    def __init__(self):
        self.params = {}

    def bind(self, value):
        name = 'v' + str(len(self.params))
        self.params[name] = value
        return ':' + name

    def filters(self, slots):
        terms = []
        for f in slots['filters']:
            col = DIM[f['dimension']]
            terms.append(col + ' IN (' + ','.join(self.bind(v) for v in f['values']) + ')')
        return ' AND '.join(terms) or '1=1'

    def groups(self, slots, month=None, point=None):
        result = []
        for key in slots['group_by']:
            expression = month if key == 'month' else self.bind(point) if key == 'point_date' else DIM[key]
            if expression is None:
                raise ValueError('group has no source')
            result.append(expression + ' AS "' + key + '"')
        return ','.join(result) + (',' if result else '')

    def facts(self, slots, metric, point=None):
        time = slots['time']
        where = self.filters(slots)
        if metric in {'rent_due', 'rent_collected', 'collection_rate', 'overdue_balance'}:
            groups = self.groups(slots, month='substr(r.billing_month,1,7)')
            if metric == 'overdue_balance':
                where += ' AND r.due_date < ' + self.bind(time['date']) + ' AND r.amount_due > r.amount_paid'
                a, b = 'r.amount_due-r.amount_paid', '0'
            else:
                where += ' AND substr(r.billing_month,1,7) BETWEEN ' + self.bind(time['start'][:7]) + ' AND ' + self.bind(time['end'][:7])
                a = 'r.amount_due' if metric == 'rent_due' else 'r.amount_paid'
                b = 'r.amount_due' if metric == 'collection_rate' else '0'
            return f'SELECT {groups}{a} AS numerator,{b} AS denominator FROM {PAY} WHERE {where}'
        if metric in {'operating_expense', 'budget_variance'}:
            groups = self.groups(slots, month='substr(e.expense_month,1,7)')
            where += ' AND substr(e.expense_month,1,7) BETWEEN ' + self.bind(time['start'][:7]) + ' AND ' + self.bind(time['end'][:7])
            a = 'e.amount' if metric == 'operating_expense' else 'e.amount-e.budget_amount'
            return f'SELECT {groups}{a} AS numerator,0 AS denominator FROM {EXP} WHERE {where}'
        if metric == 'cash_noi_proxy':
            # UNION independent fact streams. Never multiply rent by expense rows.
            rent = self.facts(slots, 'rent_collected')
            expense = self.facts(slots, 'operating_expense')
            keys = ','.join('"'+g+'"' for g in slots['group_by'])
            prefix = keys + ',' if keys else ''
            return rent + f' UNION ALL SELECT {prefix}-numerator,denominator FROM ({expense})'
        if metric not in {'leased_area', 'occupancy_rate', 'avg_monthly_rent_per_sqm'}:
            raise ValueError('no formula for target')
        point = point or time['date']
        date = self.bind(point)
        active = f'a.unit_id=u.unit_id AND a.lease_start_date<={date} AND a.lease_end_date>={date}'
        exists = f'EXISTS (SELECT 1 FROM leases a WHERE {active})'
        groups = self.groups(slots, point=point)
        area = f'CASE WHEN {exists} THEN u.leasable_area_sqm ELSE 0 END'
        if metric == 'avg_monthly_rent_per_sqm':
            numerator = f'COALESCE((SELECT SUM(a.monthly_base_rent) FROM leases a WHERE {active}),0)'
            return f'SELECT {groups}{numerator} AS numerator,{area} AS denominator FROM {UNIT} WHERE {where}'
        if metric == 'leased_area':
            return f'SELECT {groups}{area} AS numerator,0 AS denominator FROM {UNIT} WHERE {where}'
        used = set(slots['group_by']) | {f['dimension'] for f in slots['filters']}
        if used & {'floor', 'unit_type'}:
            return f'SELECT {groups}{area} AS numerator,u.leasable_area_sqm AS denominator FROM {UNIT} WHERE {where}'
        # GLA belongs to properties, not lease/unit rows; count each property once.
        unit_part = f'SELECT {groups}{area} AS numerator,0 AS denominator FROM {UNIT} WHERE {where}'
        return unit_part + f' UNION ALL SELECT {groups}0,p.gross_leasable_area_sqm FROM properties p WHERE {where}'

    def list_sql(self, slots):
        target = slots['target']['id']
        groups = self.groups(slots)
        if target == 'property':
            source = 'properties p'
        elif target == 'unit':
            source = UNIT
        elif target == 'lease':
            source = 'leases l JOIN units u ON u.unit_id=l.unit_id JOIN properties p ON p.property_id=u.property_id JOIN tenants t ON t.tenant_id=l.tenant_id'
        else:
            used = set(slots['group_by']) | {f['dimension'] for f in slots['filters']}
            source = 'tenants t'
            if used & {'project', 'project_city'}:
                source += ' JOIN leases l ON l.tenant_id=t.tenant_id JOIN units u ON u.unit_id=l.unit_id JOIN properties p ON p.property_id=u.property_id'
        where = self.filters(slots)
        time = slots['time']
        if time['mode'] == 'lease_date_field':
            where += f" AND l.{time['field']} BETWEEN " + self.bind(time['start']) + ' AND ' + self.bind(time['end'])
        identity, label = IDENTITIES[target]
        extra = ',l.lease_start_date,l.lease_end_date' if target == 'lease' else ''
        return f'SELECT DISTINCT {groups}{identity} AS entity_id,{label} AS label{extra} FROM {source} WHERE {where}'


def compile_query(slots):
    slots = validate_slots(slots)
    b = Builder()
    groups = slots['group_by']
    keys = ','.join('"'+g+'"' for g in groups)
    if slots['target']['kind'] == 'list':
        base = b.list_sql(slots)
        tie = ([keys] if keys else []) + ['entity_id']
    else:
        metric = slots['target']['id']
        dates = slots['time'].get('dates', [None])
        facts = ' UNION ALL '.join(b.facts(slots, metric, d) for d in dates)
        formula = 'COALESCE(SUM(numerator),0)'
        if metric in {'collection_rate', 'occupancy_rate', 'avg_monthly_rent_per_sqm'}:
            formula = '1.0*COALESCE(SUM(numerator),0)/NULLIF(SUM(denominator),0)'
        base = f'SELECT {keys + "," if keys else ""}{formula} AS value FROM ({facts})'
        if groups:
            base += ' GROUP BY ' + keys
        tie = [keys] if keys else []
    order = slots['order_by']
    sorting = ','.join(tie)
    if order:
        column = 'value' if order['by'] == 'target_value' else order['by']
        sorting = f'({column} IS NULL) ASC,{column} {order["direction"].upper()}' + (','+sorting if sorting else '')
        if order.get('partition_by'):
            partition = ','.join('"'+g+'"' for g in order['partition_by'])
            sql = f'WITH base AS ({base}), ranked AS (SELECT *,ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {sorting}) AS _rank FROM base) SELECT * FROM ranked WHERE _rank <= {b.bind(order["limit"])} ORDER BY {partition},_rank'
            return sql, b.params
    sql = f'SELECT * FROM ({base})'
    if sorting:
        sql += ' ORDER BY ' + sorting
    if order and 'limit' in order:
        sql += ' LIMIT ' + b.bind(order['limit'])
    return sql, b.params


def open_readonly(path):
    path = Path(path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    conn.execute('PRAGMA query_only=ON')
    conn.row_factory = sqlite3.Row
    def authorize(action, arg1, arg2, database, source):
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
        return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY
    conn.set_authorizer(authorize)
    return conn


def execute_slots(conn, slots):
    sql, params = compile_query(slots)
    rows = [dict(row) for row in conn.execute(sql, params)]
    for row in rows:
        row.pop('_rank', None)
    return {'sql': sql, 'parameters': params, 'rows': rows}


def execute_decision(conn, decision):
    if decision.get('action') != 'query_candidate':
        return {'status': 'not_executed', 'action': decision.get('action'), 'rows': None}
    result = execute_slots(conn, slots_from_decision(decision))
    return {'status': 'executed', 'action': 'query', **result}
