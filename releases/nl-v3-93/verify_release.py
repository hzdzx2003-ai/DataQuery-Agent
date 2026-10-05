"""Offline integrity/count/slot/SQL-compilation checks; optional synthetic replay."""
import argparse,hashlib,json,math
from collections import Counter
from pathlib import Path
from capabilities import load_capabilities
from single_task_evaluation import preliminary_score
from fixed_backend.compiler import slots_from_decision,compile_query,open_readonly,execute_decision
R=Path(__file__).resolve().parent
def read(p):return json.loads((R/p).read_text(encoding='utf-8'))
def same(a,b):
 if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
 if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
 if type(a) in (int,float) and type(b) in (int,float):return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-6)
 return type(a)==type(b) and a==b
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--synthetic-db',type=Path);args=parser.parse_args()
 manifest=read('MANIFEST.json')
 for name,digest in manifest['source_files'].items():
  if hashlib.sha256((R/name).read_bytes()).hexdigest()!=digest:raise ValueError('hash mismatch: '+name)
 gold=read('SINGLE_TASK_GOLD_REVIEWED_V1.json')['cases']
 decisions={r['id']:r for r in read('evaluation/decisions.json')['rows']}
 judgments={r['id']:r for r in read('evaluation/judgments.json')['rows']}
 results={r['id']:r for r in read('evaluation/backend_results.json')['rows']}
 expected=read('evaluation/expected_query_results.json')
 ids={g['id'] for g in gold};assert len(gold)==len(ids)==100 and ids==decisions.keys()==judgments.keys()==results.keys()
 projects={p['name']:p['city'] for p in load_capabilities()['context']['projects']}
 checked=0
 for g in gold:
  ident=g['id'];r=decisions[ident];assert r['question']==g['raw_gold']['question']
  if g['expected_action']=='query':
   assert preliminary_score(g,r,projects)['slot_pass'] is True,ident
   compile_query(slots_from_decision(r['decision']))
   assert same(results[ident]['actual']['rows'],expected[ident]),ident
   checked+=1
 counts=Counter(r['verdict'] for r in judgments.values())
 assert counts=={'full':93,'partial':2,'failed':5} and checked==70
 assert sum(r['primary_pass'] for r in judgments.values())==93
 actual_replay=None
 if args.synthetic_db:
  # Explicit opt-in for a generated fixture; default never opens a database.
  conn=open_readonly(args.synthetic_db.resolve())
  try:
   actual_replay=0
   for g in gold:
    actual=execute_decision(conn,decisions[g['id']]['decision'])
    assert same(actual,results[g['id']]['actual']),g['id']
    actual_replay+=1
  finally:conn.close()
 print(json.dumps({'hashes':'verified','cases':100,'manual_verdict_counts':dict(counts),'query_slots_compilation_and_saved_results':checked,'synthetic_replayed':actual_replay,'model_calls':0}))
if __name__=='__main__':main()
