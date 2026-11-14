"""Encrypted model credential storage. HTTP callers only receive metadata."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import stat
import sys
from tempfile import NamedTemporaryFile
import threading


def linux_cipher():
    key_file = os.environ.get('AGENTLOOP_CREDENTIAL_KEY_FILE')
    if not key_file:
        return None
    from cryptography.fernet import Fernet

    try:
        fd = os.open(key_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise ValueError
            return Fernet(stream.read(128).strip())
    except (OSError, ValueError):
        raise ValueError('无法加载 Linux 凭据加密密钥；请检查文件格式、服务用户和文件权限') from None


def crypt(data, *, decrypt=False):
    if os.name != 'nt':
        raise ValueError('本机持久凭据目前需要 Windows 当前用户加密支持')
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    api = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    method = api.CryptUnprotectData if decrypt else api.CryptProtectData
    method.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    method.restype = wintypes.BOOL
    if not method(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ValueError('本机凭据加解密失败；请使用保存凭据时的 Windows 用户')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


class CredentialVault:
    def __init__(self, path):
        self.path = Path(path)
        self.cipher = None
        if sys.platform == 'linux':
            self.path = self.path.with_suffix('.fernet')
            self.cipher = linux_cipher()
        self.persist_supported = os.name == 'nt' or self.cipher is not None
        self.lock = threading.RLock()
        self.original = {}
        self.values = {}
        if self.path.exists():
            try:
                values = json.loads(self.transform(self.path.read_bytes(), decrypt=True))
                for name, value in values.items():
                    self.validate(name, value)
                self.values = values
            except Exception:
                raise ValueError('无法读取加密凭据；请检查服务账户、加密密钥与凭据文件') from None
            for name, value in self.values.items():
                self.original[name] = os.environ.get(name)
                os.environ[name] = value

    def transform(self, data, *, decrypt=False):
        if self.cipher is not None:
            return self.cipher.decrypt(data) if decrypt else self.cipher.encrypt(data)
        if not self.persist_supported:
            raise ValueError('此服务尚未配置凭据加密存储，请联系管理员配置或使用服务环境变量')
        return crypt(data, decrypt=decrypt)

    @staticmethod
    def validate(name, value):
        if not isinstance(name, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,80}_API_KEY', name):
            raise ValueError('只允许专用的 *_API_KEY 凭据名称')
        if not isinstance(value, str) or not 8 <= len(value) <= 4096 or not value.isascii() or any(c.isspace() for c in value):
            raise ValueError('API Key 格式无效：需要 8–4096 位、不含空白的 ASCII 字符串')

    def status(self, refs):
        with self.lock:
            return [{'ref': ref, 'configured': bool(os.environ.get(ref[4:])),
                     'source': 'local_encrypted' if ref[4:] in self.values else 'environment' if os.environ.get(ref[4:]) else 'missing',
                     'persist_supported': self.persist_supported} for ref in sorted(set(refs))]

    def update(self, ref, value=None, *, remove=False):
        name = ref[4:]
        if not ref.startswith('env:'):
            raise ValueError('无效凭据引用')
        self.validate(name, 'validation-only' if remove else value)
        with self.lock:
            values = dict(self.values)
            if remove: values.pop(name, None)
            else: values[name] = value
            encrypted = self.transform(json.dumps(values).encode())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = None
            try:
                with NamedTemporaryFile(dir=self.path.parent, prefix=self.path.name + '.', delete=False) as stream:
                    temp = Path(stream.name)
                    stream.write(encrypted)
                os.replace(temp, self.path)
            finally:
                if temp is not None:
                    temp.unlink(missing_ok=True)
            if name not in self.original: self.original[name] = os.environ.get(name)
            if remove:
                original = self.original.get(name)
                if original is None: os.environ.pop(name, None)
                else: os.environ[name] = original
            else: os.environ[name] = value
            self.values = values
            return self.status([ref])[0]
