"""Presentation adapter. Saved responses are never presented as a live query."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path


class ReleaseError(ValueError):
    pass


def default_release():
    here = Path(__file__).resolve().parent
    candidates = [here.parent / 'releases/nl-v3-93',
                  here.parent / 'public_release_20261006/releases/nl-v3-93']
    for path in candidates:
        if (path / 'MANIFEST.json').is_file():
            return path
    raise ReleaseError('未找到冻结版本，请将 UI 与 releases/nl-v3-93 放在同一项目中。')


class SavedCases:
    """Load only manifest-bound saved artifacts, without importing backend code."""

    def __init__(self, release=None):
        self.release = Path(release or default_release()).resolve()
        manifest = json.loads((self.release / 'MANIFEST.json').read_text(encoding='utf-8'))
        self.version = manifest['release']
        loaded = {}
        for name in ('decisions', 'backend_results'):
            relative = f'evaluation/{name}.json'
            data = (self.release / relative).read_bytes()
            if hashlib.sha256(data).hexdigest() != manifest['source_files'][relative]:
                raise ReleaseError('保存案例校验失败，请恢复原始发布文件。')
            loaded[name] = json.loads(data)['rows']
        self._cases = self._index(loaded['decisions'])
        self._results = self._index(loaded['backend_results'])
        if self._cases.keys() != self._results.keys():
            raise ReleaseError('问题与结果集合不一致。')

    @staticmethod
    def _index(rows):
        result = {row['id']: row for row in rows}
        if len(result) != len(rows):
            raise ReleaseError('保存案例编号重复。')
        return result

    def catalog(self):
        return [{'id': row['id'], 'question': row['question'],
                 'action': row['decision']['action']} for row in self._cases.values()]

    def open(self, case_id):
        case = deepcopy(self._cases[case_id])
        actual = deepcopy(self._results[case_id]['actual'])
        decision = case['decision']
        if decision['action'] != 'query_candidate' and actual['status'] == 'executed':
            raise ReleaseError('非查询状态存在执行结果。')
        return {'id': case_id, 'question': case['question'], 'decision': decision,
                'result': actual, 'mode': 'saved', 'version': self.version,
                'model_called': False, 'database_queried': False}

    def find_exact(self, question):
        # No fuzzy answer substitution: unmatched text must go to a real parser.
        matches = [r['id'] for r in self._cases.values() if r['question'] == question.strip()]
        return self.open(matches[0]) if len(matches) == 1 else None


def clarification_draft(original, answer):
    """A draft for re-parsing, NOT a validated plan or permission to execute."""
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError('请先补充待确认的条件。')
    return {'original_question': original, 'clarification_answer': answer.strip(),
            'requires_reparse': True, 'execution_allowed': False}
