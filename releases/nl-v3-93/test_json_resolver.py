import json
import unittest
from capabilities import load_capabilities
from conversation import understand_offline
from json_resolver import JsonResolver, parse_response, ResolverFailure, correction_hint


class JsonResolverTests(unittest.TestCase):
    def setUp(self):
        self.cap=load_capabilities()
        self.question='��Щ��¼ɾ����'
        self.payload={'requests':[{'source_text':self.question,'kind':'write','plans':[]}]}
        self.raw=json.dumps(self.payload,ensure_ascii=False)

    def client(self,outputs):
        calls=[]
        def fake(prompt,question,correction):
            calls.append(correction)
            value=outputs[len(calls)-1]
            if isinstance(value,Exception): raise value
            return value
        return fake,calls

    def test_valid_rejection_not_retried(self):
        client,calls=self.client([self.raw])
        resolver=JsonResolver(self.cap,client)
        r=understand_offline(self.question,self.cap,resolver)
        self.assertEqual(r['action'],'reject');self.assertEqual(len(calls),1)

    def test_malformed_then_valid(self):
        client,calls=self.client(['{',self.raw])
        resolver=JsonResolver(self.cap,client)
        self.assertEqual(resolver('prompt',self.question),self.payload)
        self.assertEqual([t['status'] for t in resolver.trace],['invalid_contract','accepted_contract'])
        self.assertTrue(calls[1])

    def test_exhaustion_safe_in_conversation(self):
        client,calls=self.client(['{}','{}'])
        resolver=JsonResolver(self.cap,client)
        r=understand_offline(self.question,self.cap,resolver)
        self.assertEqual(r['action'],'parser_error');self.assertEqual(len(calls),2)
        self.assertFalse(r['execution_allowed'])

    def test_transport_failure_no_retry_or_exception_leak(self):
        client,calls=self.client([OSError('SECRET_MARKER')])
        resolver=JsonResolver(self.cap,client)
        with self.assertRaises(ResolverFailure) as caught: resolver('p',self.question)
        self.assertNotIn('SECRET_MARKER',str(caught.exception))
        self.assertEqual(len(calls),1)

    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw in ['{"requests":[],"requests":[]}','{"x":NaN}','{"x":Infinity}']:
            with self.subTest(raw=raw),self.assertRaises(ValueError): parse_response(raw)

    def test_whole_fence_is_presentation_not_a_retry(self):
        client,calls=self.client(['```json\n'+self.raw+'\n```'])
        resolver=JsonResolver(self.cap,client)
        self.assertEqual(resolver('prompt',self.question),self.payload)
        self.assertEqual(len(calls),1)
        self.assertEqual(resolver.trace[0]['format_normalizations'],[
            {'field':'response_wrapper','from':'json_code_fence','to':'json_document'}])

    def test_fence_whitespace_crlf_and_no_language(self):
        for prefix in ['```json','```']:
            with self.subTest(prefix=prefix):
                self.assertEqual(parse_response(' \n'+prefix+'\r\n'+self.raw+'\r\n```\n'),self.payload)

    def test_never_extracts_json_from_prose_or_multiple_documents(self):
        fenced='```json\n'+self.raw+'\n```'
        for raw in ['���ͣ�'+fenced,fenced+'˵��',fenced+'\n'+fenced,
                    '```python\n'+self.raw+'\n```',self.raw+self.raw]:
            with self.subTest(raw=raw),self.assertRaises(ValueError): parse_response(raw)

    def test_fenced_bad_json_remains_invalid(self):
        for raw in ['{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}','{']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                parse_response('```json\n'+raw+'\n```')

    def test_fenced_business_contract_still_checked(self):
        client,calls=self.client(['```json\n{}\n```',self.raw])
        resolver=JsonResolver(self.cap,client)
        resolver('prompt',self.question)
        self.assertEqual(len(calls),2)
        self.assertEqual(resolver.trace[0]['status'],'invalid_contract')

    def test_missing_question_text_retries(self):
        client,calls=self.client([self.raw.replace(self.question,'ɾ��'),self.raw])
        resolver=JsonResolver(self.cap,client)
        resolver('p',self.question)
        self.assertEqual(len(calls),2)
        self.assertIn('ԭ����˳��ƴ��',calls[1])

    def test_correction_never_echoes_untrusted_exception_text(self):
        hint=correction_hint(ValueError('SECRET_PROVIDER_TEXT'))
        self.assertNotIn('SECRET_PROVIDER_TEXT',hint)
        self.assertIn('����',correction_hint(ValueError('ranking limit must be an integer from1to1000')))

    def test_invalid_budget(self):
        for n in [True,0,3]:
            with self.subTest(n=n),self.assertRaises(ValueError): JsonResolver(self.cap,None,n)

    def test_shape_corruption_is_contract_failure(self):
        invalid={'requests':[{'source_text':self.question,'kind':{},'plans':[]}]}
        client,calls=self.client([json.dumps(invalid),self.raw])
        resolver=JsonResolver(self.cap,client)
        resolver('p',self.question)
        self.assertEqual(len(calls),2)


if __name__=='__main__': unittest.main()
