"""Optional semantic-review seam, tested with fakes only, no live transport.

Review is fallible evidence, never proof of coverage or execution permission.
It cannot change a query plan or upgrade an existing rejection/clarification.
"""
from copy import deepcopy
from conversation import understand_offline


REVIEW_PROMPT='''先从原问题独立列出用户的业务请求，再对照给出的理解结果。
检查是否漏掉请求、误认修改为查询、静默选择重要口径、错误目标或筛选、无必要澄清/拒绝。
不要用表达是否符合某个词表判断。不要把原解析器的自述当作事实。不要生成SQL或修改计划。
返回仅含verdict和issues的对象。verdict为consistent/issues/uncertain。
每个issue仅含code和source_text。source_text必须是原问题中的非空片段。
code为omitted_request/write_intent/basis_guess/target_mismatch/filter_mismatch/unnecessary_intervention。
consistent要求issues为空；issues要求至少一项。拿不准用uncertain，不假称已证明理解正确。
'''
ISSUES={'omitted_request','write_intent','basis_guess','target_mismatch','filter_mismatch','unnecessary_intervention'}


def validate_review(question,review):
    if not isinstance(review,dict) or set(review)!={'verdict','issues'}:
        raise ValueError('invalid review schema')
    verdict=review['verdict']; issues=review['issues']
    if verdict not in {'consistent','issues','uncertain'} or not isinstance(issues,list):
        raise ValueError('invalid review values')
    if len(issues)>20 or (verdict=='consistent' and issues) or (verdict=='issues' and not issues):
        raise ValueError('review verdict contradicts issues')
    for i in issues:
        if not isinstance(i,dict) or set(i)!={'code','source_text'} or i['code'] not in ISSUES:
            raise ValueError('invalid issue')
        if not isinstance(i['source_text'],str) or not i['source_text'].strip() or i['source_text'] not in question:
            raise ValueError('issue lacks question grounding')
    return deepcopy(review)


def reviewed_understanding(question,capabilities,resolver,reviewer=None):
    original=understand_offline(question,capabilities,resolver)
    return review_existing_result(question,capabilities,original,reviewer)


def review_existing_result(question,capabilities,original,reviewer=None):
    """Review a saved interpretation without reparsing or mutating arm A.

    Caller must supply the matching question/result; this seam does not attest
    provenance or grant execution permission. It is for offline paired tests.
    """
    if not isinstance(original,dict) or original.get('execution_allowed') is not False:
        raise ValueError('review requires a non-executable interpretation')
    result=deepcopy(original)
    result['semantic_review']={'status':'not_run','semantic_correctness_proven':False}
    if reviewer is None or result['action']=='parser_error':
        return result
    # A callback cannot mutate the original interpretation or capability object.
    try:
        review=validate_review(question,reviewer(REVIEW_PROMPT,question,deepcopy(capabilities),deepcopy(result)))
    except Exception:
        result['semantic_review']['status']='failed'
        if result['action']=='query_candidate':
            result['action']='interpretation_review'
            result['message']='系统未能完成理解复核，本次没有查询。\n'+result['message']
        return result
    result['semantic_review'].update(status='reviewed',**review)
    if review['verdict']!='consistent':
        # Preserve stricter original actions; do not convert rejection to query.
        if result['action']=='query_candidate': result['action']='interpretation_review'
        concerns='；'.join(i['source_text'] for i in review['issues'])
        result['message']='理解复核有待确认'+('：'+concerns if concerns else '。')+'\n'+result['message']
    return result
