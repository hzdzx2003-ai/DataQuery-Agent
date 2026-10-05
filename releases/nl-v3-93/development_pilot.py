"""12-case diagnostic preparation/collection with injected clients.

No network client or credential loader. Gold is retained solely in the local
author file. Transport callbacks receive only explicitly constructed messages.
"""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from capabilities import load_capabilities, build_understanding_prompt
from conversation import ENVELOPE_INSTRUCTIONS
from json_resolver import parse_response, CorrectionFeedback
from paired_offline import OfflineBudget, run_pair
from semantic_review import REVIEW_PROMPT

HERE = Path(__file__).resolve().parent
CASES = HERE / 'development_cases_v1.json'


def question_set(path=CASES):
    bundle = json.loads(Path(path).read_text(encoding='utf-8'))
    cases = bundle['cases']
    if len(cases) != 12 or len({c['id'] for c in cases}) != 12:
        raise ValueError('pilot requires 12 unique cases')
    if not all(isinstance(c['question'], str) and c['question'].strip() for c in cases):
        raise ValueError('invalid pilot questions')
    # Explicit projection: never serialize category, Gold or requirements to
    # either client, even if the authoring schema later gains extra metadata.
    return [{'id': c['id'], 'question': c['question']} for c in cases]


def parser_messages(prompt, question, correction=''):
    messages = [{'role': 'system', 'content': prompt},
                {'role': 'user', 'content': question}]
    if correction:
        if isinstance(correction,CorrectionFeedback) and correction.previous_response is not None:
            messages.append({'role':'assistant','content':correction.previous_response})
        messages.append({'role': 'user', 'content': str(correction)})
    return messages


def reviewer_messages(prompt, question, capabilities, result):
    return [{'role': 'system', 'content': prompt}, {'role': 'user', 'content':
        json.dumps({'question': question, 'business_capabilities': capabilities,
                    'interpretation': result}, ensure_ascii=False)}]


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def prepare(path=CASES):
    capabilities = load_capabilities()
    prompt = build_understanding_prompt(capabilities) + ENVELOPE_INSTRUCTIONS
    return {'version': 'nl-v3-pilot-preparation-1', 'status': 'prepared_not_authorized',
        'case_file_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        'maximum_requests': 36, 'review_system_prompt': REVIEW_PROMPT,
        'parser_requests': [{'id': c['id'], 'messages': parser_messages(prompt, c['question'])}
                            for c in question_set(path)],
        'review_payload_note': 'Same original question, capabilities and parser interpretation; no Gold.'}


def collect_offline(parser_transport, review_transport, path=CASES):
    """Injected callbacks(messages)->raw text. Not an external-call CLI.

    Caller supplies fake transports until separate live authorization exists.
    Returned raw responses are evidence for diagnosis, never a computed score.
    """
    return collect_development(parser_transport, review_transport, path, mode='offline')


def collect_development(parser_transport, review_transport, path=CASES, *, mode, on_exchange=None, on_row=None):
    """mode labels evidence; it does not authorize external requests.

    Only an explicitly authorized caller may select live and supply HTTP clients.
    Both modes preserve raw responses and never compute a model score here.
    """
    if mode not in {'offline', 'live'}:
        raise ValueError('unknown evidence mode')
    capabilities = load_capabilities()
    budget = OfflineBudget(36)
    rows, exchanges = [], []

    def call(stage, transport, messages):
        event = {'stage': stage, 'case_id': current_id, 'messages': messages}
        exchanges.append(event)
        started = perf_counter()
        try:
            raw = transport(messages)
        except BaseException:
            event['status'] = 'transport_failure'
            if on_exchange is not None:
                on_exchange(dict(event))
            raise
        finally:
            event['callback_seconds'] = perf_counter() - started
        event.update(status='returned', raw_response=raw)
        if on_exchange is not None:
            on_exchange(dict(event))
        return raw

    for case in question_set(path):
        current_id = case['id']
        parser = lambda p, q, correction: call('parse', parser_transport, parser_messages(p, q, correction))
        reviewer = lambda p, q, cap, result: parse_response(call(
            'review', review_transport, reviewer_messages(p, q, cap, result)))
        row = run_pair(case['question'], capabilities, parser, reviewer, budget)
        row['evidence'] = ('offline_injected_callbacks_not_accuracy' if mode=='offline'
                           else 'live_developer_diagnostic_not_generalization')
        rows.append({'id': current_id, **row})
        if on_row is not None:
            on_row(rows[-1])
        if budget.stopped:
            break
    transport_records = {'parser': getattr(parser_transport, 'records', None),
                         'reviewer': getattr(review_transport, 'records', None)}
    return {'version': 'nl-v3-development-collection-1',
        'status': 'aborted' if budget.stopped else 'completed_' + mode,
        'evidence_boundary': ('Injected offline callbacks, not provider results or accuracy'
                             if mode == 'offline' else '12 developer-visible diagnostic questions; no generalization claim'),
        'rows': rows, 'exchanges': exchanges, 'callback_attempts': len(budget.attempts),
        'expected_cases': 12, 'completed_cases': len(rows),
        'transport_records': transport_records, 'usage': None,
        'external_calls': 0 if mode == 'offline' else None,
        'external_attempts': 0 if mode == 'offline' else len(budget.attempts),
        'score': None}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description='Prepare reviewable pilot messages without any calls')
    cli.add_argument('--prepare-output', type=Path, required=True)
    args = cli.parse_args()
    prepared = prepare()
    write_new(args.prepare_output, prepared)
    print(json.dumps({'status': prepared['status'], 'questions': 12,
                      'output': str(args.prepare_output.resolve()), 'external_calls': 0}))
