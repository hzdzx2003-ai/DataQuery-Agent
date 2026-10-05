"""Single-task collection and conservative preliminary scoring.

Manual semantic audit is required; no automatic acceptance or numeric answers.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import json
from capabilities import load_capabilities
from conversation import understand_offline
from json_resolver import JsonResolver
from paired_offline import OfflineBudget
from development_pilot import parser_messages,write_new,HERE
from scoring_slots import compare_slots


def observed_slots(plan):
    if plan.get('status')!='validated_structure_not_execution':
        raise ValueError('unvalidated plan')
    t=plan['time']
    if t.get('mode') in {'current_records','point_series','lease_date_field'}:
        fields={'current_records':('mode',),'point_series':('mode','dates'),
                'lease_date_field':('mode','field','start','end')}[t['mode']]
        time={k:deepcopy(t[k]) for k in fields}
    elif 'date' in t:time={'mode':'point','date':t['date']}
    else:time={'mode':'period','start':t['start'],'end':t['end']}
    result={k:deepcopy(plan[k]) for k in ('target','filters','group_by','order_by')}|{'time':time}
    order=result['order_by']
    # Pre-run rubric permits explicit chronological ascending or its default.
    if order is not None and set(order)=={'by','direction'} and order['by'] in {'month','point_date'} and order['direction']=='asc':
        result['order_by']=None
    return result


def project_equivalence(slots,projects):
    """Frozen current project catalog defines city/project intersection only."""
    p=deepcopy(slots);remaining=[];scope=set(projects);has_scope=False
    for f in p['filters']:
        if f['dimension']=='project':scope &= set(f['values']);has_scope=True
        elif f['dimension']=='project_city':
            scope &= {name for name,city in projects.items() if city in f['values']};has_scope=True
        else:remaining.append(f)
    if has_scope:remaining.append({'dimension':'project','operator':'in','values':sorted(scope)})
    p['filters']=remaining
    return p


def preliminary_score(gold,row,projects):
    decision=row['decision'];expected=gold['expected_action']
    expected_route={'query':'query_candidate','clarify':'clarify','reject':'reject'}[expected]
    route_pass=decision.get('action')==expected_route
    result={'id':gold['id'],'route_pass':route_pass,'slot_pass':None,
            'primary_pass':None,'status':'manual_audit_required',
            'manual_requirements':gold['raw_gold']}
    if expected=='query':
        plans=[p for d in decision.get('requests',[]) for p in d.get('plans',[])]
        # Actual decision envelope uses details, not raw resolver requests.
        if not plans:plans=[p for d in decision.get('details',[]) for p in d.get('plans',[])]
        try:
            if len(plans)!=1:raise ValueError('not one query plan')
            actual=project_equivalence(observed_slots(plans[0]),projects)
            target=project_equivalence(gold['slots'],projects)
            result.update(compare_slots(target,actual))
        except (ValueError,KeyError,TypeError):result.update(slot_pass=False,mismatches=['invalid_or_missing_plan'])
    if not route_pass or result['slot_pass'] is False:
        result.update(primary_pass=False,status='failed_mechanically')
    return result


def collect(cases,capabilities,transport,directory,maximum=200,*,basis_mode=False):
    if type(basis_mode) is not bool:raise ValueError('basis_mode must be bool')
    budget=OfflineBudget(maximum);rows=[]
    for case in cases:
        def client(prompt,question,correction):
            messages=parser_messages(prompt,question,correction)
            def request():
                n=len(budget.attempts)
                write_new(directory/f'request_{n:03}.json',{'id':case['id'],'messages':messages})
                raw=transport(messages)
                write_new(directory/f'response_{n:03}.json',{'id':case['id'],'raw':raw})
                return raw
            return budget.invoke('parse',request)
        resolver=JsonResolver(capabilities,client,max_attempts=2,basis_mode=basis_mode)
        decision=understand_offline(case['question'],capabilities,resolver)
        row={'id':case['id'],'question':case['question'],'decision':decision,'trace':resolver.trace}
        if basis_mode:row['basis_mode']=True
        rows.append(row);write_new(directory/f"case_{case['id']}.json",row)
        if budget.stopped:break
    result={'status':'aborted' if budget.stopped else 'completed','rows':rows,
            'external_attempts':len(budget.attempts),'maximum_requests':maximum,
            'transport_records':getattr(transport,'records',[])}
    if basis_mode:result['basis_mode']=True
    write_new(directory/'result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--gold',required=True)
    parser.add_argument('--run-directory',required=True);parser.add_argument('--env-file',required=True)
    parser.add_argument('--confirm',required=True)
    parser.add_argument('--network-recovery-from')
    args=parser.parse_args()
    if args.confirm!='single-task-100-max-200':raise RuntimeError('explicit scope confirmation required')
    gold_path=Path(args.gold);gold=json.loads(gold_path.read_text(encoding='utf-8'))
    if not gold.get('pre_run_review_complete') or len(gold['cases'])!=100:
        raise RuntimeError('reviewed complete Gold required')
    if len({c['id'] for c in gold['cases']})!=100:raise RuntimeError('case IDs not unique')
    cap=load_capabilities();directory=Path(args.run_directory).resolve()
    if directory.parent!=HERE.resolve() or directory.exists():raise RuntimeError('new immediate child run directory required')
    prior_attempts=0
    if args.network_recovery_from:
        old=Path(args.network_recovery_from).resolve()
        if old.parent!=HERE.resolve():raise RuntimeError('recovery source must be in development directory')
        previous=json.loads((old/'result.json').read_text(encoding='utf-8'))
        spec=json.loads((old/'run_spec.json').read_text(encoding='utf-8'))
        if (previous['status']!='aborted' or previous['external_attempts']!=1
                or len(previous['transport_records'])!=1 or previous['transport_records'][0]['status']!='failed'
                or list(old.glob('response_*.json'))
                or spec['gold_sha256']!=hashlib.sha256(gold_path.read_bytes()).hexdigest()):
            raise RuntimeError('recovery only for first transport failure with zero responses and same Gold')
        prior_attempts=1
    from run_live_pilot import configuration,MODEL,ENDPOINT
    from qwen_transport import QwenTransport
    transport=QwenTransport(ENDPOINT,MODEL,configuration(args.env_file))
    directory.mkdir(exist_ok=False)
    write_new(directory/'run_spec.json',{'version':'single-task-nl-v3-eval-1','model':MODEL,'endpoint':ENDPOINT,
        'max_requests':200-prior_attempts,'prior_failed_attempts':prior_attempts,'combined_cap':200,
        'gold_sha256':hashlib.sha256(gold_path.read_bytes()).hexdigest(),
        'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir()
                         if p.is_file() and p.suffix in {'.py','.json'} and not p.name.startswith('test_')},
        'scope':'Synthetic question and capabilities only, never Gold; understanding plans, noSQL/database'})
    # The provider receives question and capabilities, not any Gold labels.
    cases=[{'id':c['id'],'question':c['raw_gold']['question']} for c in gold['cases']]
    result=collect(cases,cap,transport,directory,maximum=200-prior_attempts)
    projects={p['name']:p['city'] for p in cap['context']['projects']}
    lookup={c['id']:c for c in gold['cases']}
    scores=[preliminary_score(lookup[r['id']],r,projects) for r in result['rows']]
    write_new(directory/'preliminary_score.json',{'rows':scores,'official_accuracy':None,
        'reason':'Manual basis/additional condition/clarification audit required; missing cases remain denominator100.'})
    print(json.dumps({'status':result['status'],'cases':len(result['rows']),
                      'attempts':result['external_attempts'],'accuracy':None}))


if __name__=='__main__':main()
