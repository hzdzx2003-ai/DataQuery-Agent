"""Injected parsing boundary; no transport, credential loader or database opener."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
from adapter import default_release, ReleaseError


def frozen_modules():
    root = default_release().resolve()
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    for name, expected in manifest['source_files'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ReleaseError('冻结发布文件校验失败。')
        if name.endswith('.py'):
            module_name = name[:-3].replace('/', '.').replace('\\', '.')
            module = sys.modules.get(module_name)
            if module and getattr(module, '__file__', None) and Path(module.__file__).resolve() != (root / name).resolve():
                raise ReleaseError('检测到其他版本模块，请在独立进程中启动。')
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return (importlib.import_module('capabilities'), importlib.import_module('json_resolver'),
            importlib.import_module('conversation'))


def understand(question, client, *, basis_mode=False):
    """Client is supplied by caller. This adapter does not authorize live calls."""
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError('问题须为 1–4000 字符。')
    capabilities, resolver_module, conversation = frozen_modules()
    caps = capabilities.load_capabilities()
    resolver = resolver_module.JsonResolver(caps, client, max_attempts=2, basis_mode=basis_mode)
    decision = conversation.understand_offline(question, caps, resolver)
    # A structurally valid multi-request envelope is outside this UI's scope.
    if len(decision.get('requests', [])) > 1:
        return {'action':'unsupported_ui_scope', 'execution_allowed':False,
                'message':'当前界面仅处理单一查询任务，请一次提出一个问题。'}
    return decision


def execute_confirmed(decision, executor):
    """Executor must be explicitly supplied (e.g. a synthetic read-only fixture)."""
    if decision.get('action') != 'query_candidate':
        return {'status':'not_executed', 'action':decision.get('action'), 'rows':None}
    requests = decision.get('requests', [])
    if len(requests) != 1 or requests[0].get('kind') != 'query':
        raise ValueError('不是单一查询方案。')
    return executor(decision)
