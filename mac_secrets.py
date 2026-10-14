"""Use only the native macOS Keychain backend; no plaintext fallback."""
import base64
import hashlib
from pathlib import Path

from localization import tr

SERVICE = 'org.shiguang.desktop'


def _account(root, name):
    return hashlib.sha256((str(Path(root).resolve()) + '|' + name).encode('utf-8')).hexdigest()


def _backend():
    from keyring.backends.macOS import Keyring
    return Keyring()


def read(root, name):
    try:
        value = _backend().get_password(SERVICE, _account(root, name))
        return base64.b64decode(value, validate=True) if value is not None else None
    except Exception:
        raise ValueError(tr('无法访问系统钥匙串，请解锁后重试。')) from None


def write(root, name, value):
    try:
        _backend().set_password(SERVICE, _account(root, name), base64.b64encode(value).decode('ascii'))
    except Exception:
        raise ValueError(tr('无法访问系统钥匙串，密钥尚未保存。')) from None


def delete(root, name):
    try:
        backend = _backend()
        account = _account(root, name)
        if backend.get_password(SERVICE, account) is not None:
            backend.delete_password(SERVICE, account)
    except Exception:
        raise ValueError(tr('无法访问系统钥匙串，密钥尚未删除。')) from None
