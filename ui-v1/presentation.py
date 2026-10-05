"""Display-only units; never changes stored values or query plans."""
NAMES = {'rent_due':'应收租金', 'rent_collected':'实收租金',
         'collection_rate':'租金收缴率', 'leased_area':'已出租面积',
         'occupancy_rate':'出租率', 'operating_expense':'运营费用',
         'budget_variance':'运营费用预算差异', 'cash_noi_proxy':'现金净运营收益（简化口径）',
         'avg_monthly_rent_per_sqm':'每平方米月租金', 'overdue_balance':'逾期欠款'}
RATIOS = {'collection_rate', 'occupancy_rate'}
COLUMNS = {'entity_id':'记录编号', 'label':'名称', 'project':'项目', 'project_city':'项目城市',
           'tenant':'租户编号', 'tenant_registration_city':'租户注册城市',
           'tenant_industry':'租户行业', 'expense_category':'费用类别', 'floor':'楼层',
           'unit_type':'铺位类型', 'month':'账期月份', 'point_date':'统计日期',
           'lease_start_date':'起租日', 'lease_end_date':'到期日'}


def display_rows(decision, rows):
    return [{(metric_display(decision, value)[0] if key == 'value' else COLUMNS.get(key, key)):
             (metric_display(decision, value)[1] if key == 'value' else value)
             for key, value in row.items()} for row in rows]


def metric_display(decision, value):
    plans = [p for r in decision.get('requests', []) for p in r.get('plans', [])]
    target = plans[0].get('target', {}).get('id') if len(plans) == 1 else None
    name = NAMES.get(target, '指标值')
    if value is None:
        return name, '暂无数据'
    if target in RATIOS:
        return name, f'{value:.2%}'
    unit = '㎡' if target == 'leased_area' else '元/㎡/月' if target == 'avg_monthly_rent_per_sqm' else '元' if target in NAMES else ''
    return name, f'{value:,.2f} {unit}'.strip()
