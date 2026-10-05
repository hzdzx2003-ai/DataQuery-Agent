"""Limited contradiction diagnostics, NOT natural-language completeness proof.

Literal catalog values are compared, never inserted into a plan automatically.
Negation, aliases and context references require further interpretation.
"""


def project_filter_diagnostics(capabilities, requests):
    catalog=capabilities['context']['projects']
    names={p['name'] for p in catalog}
    diagnostics=[]
    for index,r in enumerate(requests):
        if r['kind']!='query':
            continue
        mentioned={n for n in names if n in r['source_text']}
        for candidate,p in enumerate(r['plans']):
            selected={v for f in p['filters'] if f['dimension']=='project' for v in f['values']}
            # Compare bounded catalog scopes, not just the chosen filter key.
            # An exact city/district intersection may encode the named scope.
            # Never infer a city from a tenant registration-city filter.
            scope=set(names); scoped=False
            fields={'project':'name','project_city':'city','project_district':'district'}
            for f in p['filters']:
                if f['dimension'] in fields:
                    scoped=True;field=fields[f['dimension']]
                    scope &= {row['name'] for row in catalog if row.get(field) in f['values']}
            # Whole-catalog expansion is equivalent to the default unfiltered
            # scope. City expansion must equal the catalog set for city values
            # actually present in source; arbitrary subsets remain flagged.
            cities={p['city'] for p in capabilities['context']['projects'] if p['city'] in r['source_text']}
            city_names={p['name'] for p in capabilities['context']['projects'] if p['city'] in cities}
            expansion=not mentioned and (selected==names or bool(cities) and selected==city_names)
            mismatch=(not scoped or scope!=mentioned) if mentioned else bool(selected) and not expansion
            if mismatch:
                diagnostics.append({'request_index':index,'candidate_index':candidate,
                    'code':'project_scope_needs_review',
                    'mentioned':sorted(mentioned),'planned':sorted(selected),'resolved_project_scope':sorted(scope),
                    'note':'Literal name/plan mismatch only; no automatic insertion or intent verdict.'})
    return diagnostics
