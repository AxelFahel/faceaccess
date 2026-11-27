"""Inspect/restart this local Windows backend while preserving its configuration.

Only FaceAccess settings are saved in .runtime.env (ignored by Git).
No secret values are printed. Run: python scripts/local_runtime.py inspect|restart PID
"""
import ast
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def process_environment(pid):
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("This helper requires 64-bit Windows.")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())

    def read(address, size):
        buf = ctypes.create_string_buffer(size)
        if not kernel.ReadProcessMemory(handle, address, buf, size, None):
            raise ctypes.WinError(ctypes.get_last_error())
        return buf.raw

    try:
        info = (ctypes.c_void_p * 6)()
        query = ctypes.WinDLL("ntdll").NtQueryInformationProcess
        query.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.ULONG, ctypes.c_void_p]
        if query(handle, 0, info, ctypes.sizeof(info), None) != 0:
            raise RuntimeError("Cannot read backend process configuration.")
        parameters = int.from_bytes(read(info[1] + 0x20, 8), "little")
        environment = int.from_bytes(read(parameters + 0x80, 8), "little")
        data = bytearray()
        for offset in range(0, 262144, 2):
            data.extend(read(environment + offset, 2))
            if data[-4:] == b"\0\0\0\0":
                break
        else:
            raise RuntimeError("Environment exceeded safe read limit.")
        return dict(line.split("=", 1) for line in data.decode("utf-16-le").split("\0") if "=" in line and not line.startswith("="))
    finally:
        kernel.CloseHandle(handle)


def main():
    mode, pid = sys.argv[1], int(sys.argv[2])
    environment = process_environment(pid)
    tree = ast.parse((ROOT / "app/core/config.py").read_text(encoding="utf-8"))
    fields = {node.target.id.upper() for node in ast.walk(tree) if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)}
    settings = {key: value for key, value in environment.items() if key.upper() in fields}
    required = {"DATABASE_URL", "JWT_SECRET", "BIOMETRIC_KEYS", "DATA_ENCRYPTION_KEY", "AUDIT_HMAC_KEY"}
    if not required <= {key.upper() for key in settings}:
        raise RuntimeError("Incomplete configuration; backend will not be restarted.")
    saved = ROOT / ".runtime.env"
    saved.write_text(json.dumps(settings), encoding="utf-8")
    print("Saved FaceAccess configuration without displaying secrets.")
    print("Model cache:", settings.get("UNIFACE_CACHE_DIR", str(Path.home() / ".uniface/models")))
    print("Engine:", settings.get("BIOMETRIC_ENGINE", "uniface"))
    if mode == "restart":
        # Explicit PID supplied after checking that this process owns the local API port.
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=True, capture_output=True)
        time.sleep(1)
        with (ROOT / "runtime.log").open("ab") as output:
            child = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=ROOT, env={**os.environ, **settings}, stdout=output, stderr=output,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            )
        print("Backend restarted, PID:", child.pid)


if __name__ == "__main__":
    main()
