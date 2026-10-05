"""Small injected-callback experiment harness; no transport or authorization.

Counts callback attempts, NOT verified external requests. Use fakes only until
a separately authorized transport exists. No scoring or selection of best arm.
"""
from copy import deepcopy
from conversation import understand_offline
from json_resolver import JsonResolver
from semantic_review import review_existing_result


class OfflineBudget:
    def __init__(self, limit):
        if type(limit) is not int or limit < 1:
            raise ValueError('positive integer budget required')
        self.limit = limit
        self.attempts = []
        self.stopped = False

    def invoke(self, stage, callback, *args):
        if self.stopped or len(self.attempts) >= self.limit:
            self.stopped = True
            raise RuntimeError('offline callback budget unavailable')
        event = {'stage': stage, 'status': 'started'}
        self.attempts.append(event)
        try:
            value = callback(*args)
        except BaseException:
            event['status'] = 'callback_failed'
            self.stopped = True
            raise
        event['status'] = 'returned'
        return value


def run_pair(question, capabilities, parser_client, reviewer, budget):
    if budget.stopped:
        raise RuntimeError('offline run stopped')
    start = len(budget.attempts)
    resolver = JsonResolver(capabilities, lambda *args: budget.invoke('parse', parser_client, *args))
    direct = understand_offline(question, capabilities, resolver)
    # Adapter can convert a callback exception into a parser_error; the shared
    # stopped state still prevents review or subsequent cases from consuming.
    reviewed = None
    if not budget.stopped:
        reviewed = review_existing_result(question, capabilities, direct,
            None if reviewer is None else lambda *args: budget.invoke('review', reviewer, *args))
    return {'question': question, 'direct': direct, 'reviewed': reviewed,
            'parser_trace': deepcopy(resolver.trace),
            'callback_attempts': deepcopy(budget.attempts[start:]),
            'stopped': budget.stopped, 'evidence': 'offline_injected_callbacks_not_accuracy'}
