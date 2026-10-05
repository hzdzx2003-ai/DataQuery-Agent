"""Optional semantic-review seam, tested with fakes only, no live transport.

Review is fallible evidence, never proof of coverage or execution permission.
It cannot change a query plan or upgrade an existing rejection/clarification.
"""
from copy import deepcopy
from conversation import understand_offline


REVIEW_PROMPT='''�ȴ�ԭ��������г��û���ҵ�������ٶ��ո�������������
����Ƿ�©�����������޸�Ϊ��ѯ����Ĭѡ����Ҫ�ھ�������Ŀ���ɸѡ���ޱ�Ҫ����/�ܾ���
��Ҫ�ñ����Ƿ����ĳ���ʱ��жϡ���Ҫ��ԭ������������������ʵ����Ҫ����SQL���޸ļƻ���
���ؽ���verdict��issues�Ķ���verdictΪconsistent/issues/uncertain��
ÿ��issue����code��source_text��source_text������ԭ�����еķǿ�Ƭ�Ρ�
codeΪomitted_request/write_intent/basis_guess/target_mismatch/filter_mismatch/unnecessary_intervention��
consistentҪ��issuesΪ�գ�issuesҪ������һ��ò�׼��uncertain�����ٳ���֤��������ȷ��
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
            result['message']='ϵͳδ��������⸴�ˣ�����û�в�ѯ��\n'+result['message']
        return result
    result['semantic_review'].update(status='reviewed',**review)
    if review['verdict']!='consistent':
        # Preserve stricter original actions; do not convert rejection to query.
        if result['action']=='query_candidate': result['action']='interpretation_review'
        concerns='��'.join(i['source_text'] for i in review['issues'])
        result['message']='���⸴���д�ȷ��'+('��'+concerns if concerns else '��')+'\n'+result['message']
    return result
