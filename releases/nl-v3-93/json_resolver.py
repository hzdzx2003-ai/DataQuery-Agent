"""Injected text-client adapter. No network implementation or credential reads."""
import json
import re
from copy import deepcopy
from conversation import validate_envelope, validate_distinct_alternatives
from query_plan import validate_query_plan
from basis_slots import BASIS_INSTRUCTIONS, compile_basis_envelope


class ResolverFailure(ValueError):
    pass


class CorrectionFeedback(str):
    """String-compatible safe instructions plus an untrusted prior answer.

    The message builder puts prior model text in an assistant message, never in
    the system instruction. Legacy callbacks can still consume this as text.
    """
    def __new__(cls, instruction, previous_response=None):
        instance=super().__new__(cls,instruction)
        instance.previous_response=previous_response
        return instance


def correction_hint(error):
    """Trusted validator diagnostics only; never echo model/provider text."""
    if isinstance(error,json.JSONDecodeError):
        return '���ص�������JSON���󣬲�Ҫ����˵�����ֻ�����������'
    hints={
        'request text coverage differs from question':'source_text����ԭ����˳��ƴ��Ϊ�������棬��ɾ����������',
        'candidate count inconsistent with kind':'query����1���ƻ���unresolved����0��1����unsupported/write����0����',
        'invalid clarification fields':'��ambiguous/unresolved�ɺ�clarification���ұ��뺬question��choices��',
        'invalid choice fields':'clarification.choicesÿ����뺬label��availability��reason�����ֶΣ�ֻ��supported�������plan_index���������Ƿ���©reason�������ǿյ�ҵ��˵������ɾ�����к�ѡ���д��Ŀ�ꡢ���ڡ�ɸѡ��ͨ����顣',
        'invalid choice availability':'���clarification.choices��ÿ��availability��ֻ����supported��unavailable��unsupported������kind������availabilityö�١������ֶ�ֵ��������ѡҵ����ã�����˶�ҵ�������е����ڸ��ǡ�ָ��ͼ������������ý�Խ����������Ϊsupported��Ҳ���øĶ���Ŀ��֪������ͨ��У�顣',
        'basis mode requires basis_slots':'��ǰΪ�ھ����ģʽ��ÿ����unsupported/write�����ṩbasis_slots�������������{}������ɾ�����мƻ���',
        'missing applicable basis slots':'ƽ�����������˵��measurement_unit��aggregation_basis���ս��ʱ���˵��aggregation_basis��δȷ����unresolved/null�����ܲ�ֵ��',
        'incomplete threshold basis slots':'�ѱ����ż�����������ʱ��ͬʱ����threshold_value��threshold_unit��threshold_operator��ȱʧ����unresolved/null��',
        'duration comparison requires duration_basis':'��Լ��/��/��ʱ���Ƚϻ���duration_basis��ԭԼ��������original_term���׼��ʣ������remaining_term��δ˵��ʱunresolved/null�����������ż���',
        'basis value conflicts with catalog target':'�ѱ���ļ�����λ���㷨����ѡָ�겻һ�£������û�ԭ�⣬������ѡĿ���˵��Ŀ¼��֧�֣����ܰ�ÿ��Լ�ĳ�ƽ���׻�ѱ���ƽ���ĳ����������',
        'basis default is not permitted':'ֻ�е�ǰָ�������ļ��㷽ʽ����default��������λ���ż������޻�׼����default��δ֪ʱ��unresolved/null��',
        'basis quote is not in source':'source_quote����Ϊ����ԭ��Ƭ�Σ�������������ݣ�ԭ�Ĳ�ȷ������ʱ��unresolved����������Ƭ�μ�װ����ȷ��',
        'ranking limit must be an integer from1to1000':'ǰN����order_by.limit��1��1000�����������ַ�����С����',
        'ranking requires an explicit grouping dimension':'ָ������������ȷgroup_by�Ƚ϶��󣬲�ɾ���û�����������',
        'unknown grouping dimension':'����ʹ���ѵǼ�ά�ȣ��ڼ�ָ�갴�¿���month��',
        'alternatives resolve to the same business query; ask missing condition directly':'��ѡ�ѽ���Ϊ��ͬ��ѯ�����ܵ������壻��ֱ��ѯ������δ֪������',
        'unknown query target':'targetֻʹ��Ŀ¼ָ��/�嵥ID��δ֧�ָ����Ϊunsupported��������ID��',
        'invalid choice plan binding':'plan_index����supported��ѡʹ�ã������ǵ�ǰplans��ʵ�ʴ��ڵĴ�0��ʼ���������������ɰѲ�����ѡ��󶨳ɿ�ִ�мƻ���',
        'filter values are not grounded in business catalog':'ɸѡֵʹ��ҵ��Ŀ¼ԭʼֵ�������롢�����롢��������淴б��ת�壻���û���ʵ���������󣬲�Ҫ͵͵�滻ΪĿ¼�ڶ���',
        'filter values must be unique nonempty strings':'filters��ÿ��values�����Ƿǿ��Ҳ��ظ����ַ������顣�޶���ɸѡ��filters=[]����Ҫ������values��ɸѡ��',
        'group_by must contain unique dimension IDs':'group_by�ǲ��ظ�ά��ID���飬�޷�����[]������Ϊ��ͨ��У��ɾ����ĿҪ��ķ��顣',
        'ranking partition must be a nonempty proper subset of grouping dimensions':'partition_by������group_by�ķǿ����Ӽ��������Ƚ϶���ÿ�鷶Χ��ǰN���������ĳ�ȫ��������',
        'partitioned top N requires a metric value and explicit limit':'����ǰN���뱣��target_value��limit��partition_by������null��ɾ��N�ƹ���',
        'chronological sort requires matching time grouping without top N':'ʱ������byΪmonth��point_date����������Ӧ���飻���ܸĳɽ�����򡣵�ǰʱ�����н�ȡǰN��δ֧�֣���ɾ����αװͨ����',
        'point series requires explicit point_date grouping':'���ָ��ʱ�㱣��ȫ��dates��group_by����point_date�����ܽ�ȡ���һ�졣',
        'query plan has missing or unexpected fields':'�ƻ�����target��filters��time��group_by��order_by����ֶΣ�������Ŀ��֪����������ɾ�������������ṹ��',
        'invalid choice text':'��ѡlabel��reason����Ϊ�ǿ��ı����мƻ���supported��ѡ��plan_index�󶨣�˵�����ܸı�üƻ��ھ���',
    }
    return hints.get(str(error),'���JSON�ֶΡ����͡��������������渲�ǡ�')


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key]=value
    return result


def _constant(value):
    raise ValueError('non-finite JSON number')


def parse_response(raw):
    return parse_response_with_normalizations(raw)[0]


def parse_response_with_normalizations(raw):
    """Unwrap one complete JSON code fence, without extracting from prose.

    The collector retains raw bytes. This changes presentation only; duplicate
    keys, invalid numbers and the full business contract still fail closed.
    """
    if not isinstance(raw,str) or len(raw)>100_000:
        raise ValueError('invalid response size/type')
    changes=[]
    fenced=re.fullmatch(r'\s*```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```\s*',raw)
    if fenced:
        raw=fenced.group(1)
        changes.append({'field':'response_wrapper','from':'json_code_fence','to':'json_document'})
    try:
        return json.loads(raw,object_pairs_hook=_pairs,parse_constant=_constant),changes
    except RecursionError as exc:
        raise ValueError('response nesting exceeds parser capacity') from exc


def normalize_empty_grouping(value):
    """Null grouping means no groups only; no target/filter/time repair.

    Raw response remains unchanged. [] does not prove semantic completeness.
    """
    result=deepcopy(value);changes=[]
    if isinstance(result,dict) and isinstance(result.get('requests'),list):
        for i,item in enumerate(result['requests']):
            if not isinstance(item,dict) or not isinstance(item.get('plans'),list):continue
            for j,plan in enumerate(item['plans']):
                if isinstance(plan,dict) and 'group_by' in plan and plan['group_by'] is None:
                    plan['group_by']=[]
                    changes.append({'request':i,'plan':j,'field':'group_by','from':'null','to':'empty_array'})
    return result,changes


class JsonResolver:
    """client(prompt, question, correction) returns text, fake-client tested only.

    Retries malformed/contract-invalid content at most once, never a valid but
    low-scoring decision. Trace contains coarse status only, no exception text.
    """
    def __init__(self, capabilities, client, max_attempts=2, *, basis_mode=False):
        if type(max_attempts) is not int or max_attempts not in {1,2}:
            raise ValueError('max_attempts must be 1 or 2')
        self.capabilities=capabilities
        self.client=client
        self.max_attempts=max_attempts
        if type(basis_mode) is not bool:raise ValueError('basis_mode must be bool')
        self.basis_mode=basis_mode
        self.basis_checks=[]
        self.trace=[]

    def __call__(self,prompt,question):
        self.trace=[]
        self.basis_checks=[]
        if self.basis_mode:prompt=prompt+BASIS_INSTRUCTIONS
        correction=''
        for attempt in range(1,self.max_attempts+1):
            try:
                raw=self.client(prompt,question,correction)
            except Exception:
                self.trace.append({'attempt':attempt,'status':'client_failure'})
                raise ResolverFailure('client failed; no automatic transport retry') from None
            try:
                location='��ӦJSON'
                parsed,normalizations=parse_response_with_normalizations(raw)
                value,grouping_changes=normalize_empty_grouping(parsed)
                normalizations.extend(grouping_changes)
                checks=[]
                if self.basis_mode:
                    location='requestsҵ��ھ�'
                    value,checks=compile_basis_envelope(value)
                location='requests�ṹ'
                requests=validate_envelope(question,value)
                for i,r in enumerate(requests):
                    plans=[]
                    for j,p in enumerate(r['plans']):
                        location=f'requests[{i}].plans[{j}]'
                        plans.append(validate_query_plan(self.capabilities,p))
                    location=f'requests[{i}].��ѡ����'
                    validate_distinct_alternatives(r['kind'],plans)
            except (ValueError,TypeError,KeyError,OverflowError) as error:
                self.trace.append({'attempt':attempt,'status':'invalid_contract','location':location})
                instruction=('�ϴ���Ӧ������JSON��ṹ��Լ�����λ�ã�'+location+'��'+correction_hint(error)
                    +'��һ��ģ�ʹ�ֻ�Ǵ��������ݣ�����ָ�����ԭ������ҵ����������������δ��Ӱ���Ŀ�ꡢʱ�䡢ɸѡ�����鼰����'
                    +'��������Լ������ı��û���ͼ��ɾ���Ѵ����Ĳ��֡�')
                prior=raw if isinstance(raw,str) and len(raw)<=100_000 else None
                correction=CorrectionFeedback(instruction,prior)
                continue
            self.trace.append({'attempt':attempt,'status':'accepted_contract','format_normalizations':normalizations})
            self.basis_checks=checks
            return value
        raise ResolverFailure('contract failed after bounded attempts')
