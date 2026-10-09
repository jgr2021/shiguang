"""Codex metadata and CLI selection; never read or export authentication tokens."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
from functools import lru_cache

from localization import tr


@lru_cache(maxsize=20)
def _is_cli(path, modified):
    try:
        # Codex Desktop's executable has the same basename. Never launch it as a CLI.
        candidate = Path(path)
        if candidate.parent.name.lower() == 'app' and ('windowsapps' in str(candidate).lower() or (candidate.parent / 'resources' / 'app.asar').exists()):
            return False
        result = subprocess.run([path, '--version'], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return result.returncode == 0 and result.stdout.strip().startswith(b'codex-cli ')
    except (OSError, subprocess.TimeoutExpired):
        return False


def find_codex(explicit=''):
    def usable(path):
        path = Path(path).expanduser().resolve()
        return str(path) if path.is_file() and path.suffix.lower() == '.exe' and _is_cli(str(path), path.stat().st_mtime_ns) else None
    if explicit:
        return usable(explicit)
    # Prefer the actual CLI bundled with Desktop; Windows which() searches CWD first.
    base = Path(os.environ.get('LOCALAPPDATA', '')) / 'OpenAI' / 'Codex' / 'bin'
    candidates = list(base.glob('*/codex.exe')) if base.is_dir() else []
    for path in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        found = usable(path)
        if found: return found
    npm = Path(os.environ.get('APPDATA', '')) / 'npm' / 'node_modules' / '@openai'
    candidates = list(npm.glob('**/codex.exe')) if npm.is_dir() else []
    for directory in os.environ.get('PATH', '').split(os.pathsep):
        if directory.strip('"'):
            candidates.append(Path(directory.strip('"')) / 'codex.exe')
    for path in candidates:
        found = usable(path)
        if found: return found
    return None


def model_arguments(config):
    args = []
    if config.get('model'):
        args += ['--model', config['model']]
    effort = config.get('reasoning_effort', 'auto')
    if effort != 'auto':
        args += ['-c', 'model_reasoning_effort=' + json.dumps(effort)]
    return args


class MetadataClient:
    """Bounded stdio RPC session for metadata only. No thread/turn execution."""
    def __init__(self, binary):
        self.process = subprocess.Popen([binary, 'app-server', '--listen', 'stdio://'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.queue = queue.Queue(maxsize=100)
        self.seq = 0
        def reader():
            try:
                while True:
                    line = self.process.stdout.readline(4 * 1024 * 1024 + 1)
                    if not line or len(line) > 4 * 1024 * 1024:
                        break
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if 'id' in event:
                        try:
                            self.queue.put_nowait(event)
                        except queue.Full:
                            break
            except (OSError, ValueError):
                pass
        threading.Thread(target=reader, daemon=True).start()

    def send(self, data):
        self.process.stdin.write(json.dumps(data) + '\n')
        self.process.stdin.flush()

    def call(self, method, params=None, timeout=20):
        self.seq += 1
        identifier = self.seq
        self.send({'id': identifier, 'method': method, 'params': params or {}})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                event = self.queue.get(timeout=min(1, max(.01, deadline - time.monotonic())))
            except queue.Empty:
                if self.process.poll() is not None:
                    raise ValueError(tr('Codex 命令行程序提前退出（代码 {0}），未完成 {1}。请确认选择的是 Codex CLI。', self.process.returncode, method))
                continue
            if event.get('method'):
                # No approval, credential refresh or tool request is handled by this metadata client.
                self.send({'id': event['id'], 'error': {'code': -32601, 'message': 'Metadata-only client'}})
                continue
            if event.get('id') == identifier:
                if 'error' in event:
                    raise ValueError(tr('Codex 未能读取此项信息，请更新 Codex 并确认登录。'))
                return event.get('result') or {}
        raise ValueError(tr('读取 Codex 的 {0} 等待超过 {1} 秒，请重试。', method, timeout))

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for pipe in (self.process.stdin, self.process.stdout):
            try:
                pipe.close()
            except (OSError, ValueError):
                pass


def inspect_codex(explicit=''):
    binary = find_codex(explicit)
    if not binary:
        raise ValueError(tr('未找到 Codex。请安装 Codex，或选择 codex.exe 的位置。'))
    client = MetadataClient(binary)
    try:
        client.call('initialize', {'clientInfo': {'name': 'shiguang', 'title': 'Shiguang', 'version': '1.7.0'}})
        client.send({'method': 'initialized', 'params': {}})
        account = client.call('account/read', {'refreshToken': False}).get('account') or {}
        models, cursor = [], None
        for _ in range(10):
            page = client.call('model/list', {'limit': 100, 'includeHidden': False, 'cursor': cursor})
            for item in page.get('data', []):
                slug = item.get('model') or item.get('id')
                if slug and not item.get('hidden'):
                    models.append({'model': slug, 'name': item.get('displayName') or slug, 'efforts': [x['reasoningEffort'] for x in item.get('supportedReasoningEfforts', []) if x.get('reasoningEffort')], 'default': item.get('defaultReasoningEffort')})
            cursor = page.get('nextCursor')
            if not cursor:
                break
        limits = None
        try:
            if account.get('type') in {'chatgpt', 'chatgptAuthTokens'}:
                raw = client.call('account/rateLimits/read', timeout=12)
                limits = raw.get('rateLimitsByLimitId') or ({'codex': raw['rateLimits']} if raw.get('rateLimits') else None)
        except ValueError:
            pass
        return {'binary': binary, 'account_type': account.get('type'), 'plan': account.get('planType'), 'models': models, 'limits': limits}
    finally:
        client.close()


def login_codex(explicit=''):
    binary = find_codex(explicit)
    if not binary:
        raise ValueError(tr('未找到 Codex。请安装 Codex，或选择 codex.exe 的位置。'))
    # The user completes the provider's browser login. No auth file is read here.
    try:
        result = subprocess.run([binary, 'login'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired:
        raise ValueError(tr('登录等待已结束，请重试，或先在 Codex 中完成登录。')) from None
    if result.returncode:
        raise ValueError(tr('Codex 登录未完成，请在 Codex 中登录后重新读取状态。'))
    return inspect_codex(explicit)
