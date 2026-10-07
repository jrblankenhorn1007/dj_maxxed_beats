"""Command lines and environments of the processes visible to this user.

POSIX uses /proc or `ps -axww` / `ps -axwwE`. Windows reads each process's
command line and environment block from its PEB (NtQueryInformationProcess +
ReadProcessMemory, x64 layout) -- the same information `ps -E` shows.
Processes that cannot be opened (other users, protected) are skipped.
"""

import ctypes
from pathlib import Path
import subprocess
import sys


def snapshot():
    """One string with the command line and environment of every process."""
    if sys.platform == "win32":
        return "\n".join(cmd + "\n" + env for _, cmd, env in _windows_processes())
    if Path("/proc").is_dir():
        chunks = []
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                for name in ("cmdline", "environ"):
                    try:
                        chunks.append((entry / name).read_bytes().decode("utf-8", "replace"))
                    except OSError:
                        pass
        return "\n".join(chunks)
    out = subprocess.run(["ps", "-axww", "-o", "pid=,command="],
                         capture_output=True, text=True).stdout
    env = subprocess.run(["ps", "-axwwE", "-o", "command="],
                         capture_output=True, text=True).stdout
    return out + "\n" + env


def command_lines():
    """Command lines of all visible processes, one per line."""
    if sys.platform == "win32":
        return "\n".join(cmd for _, cmd, _ in _windows_processes())
    return subprocess.run(["ps", "-axww", "-o", "command="], capture_output=True,
                          text=True).stdout


if sys.platform == "win32":
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _ntdll = ctypes.WinDLL("ntdll")
    _PROCESS_QUERY_INFORMATION = 0x0400
    _PROCESS_VM_READ = 0x0010

    class _BasicInformation(ctypes.Structure):
        _fields_ = [("ExitStatus", ctypes.c_void_p), ("PebBaseAddress", ctypes.c_void_p),
                    ("AffinityMask", ctypes.c_void_p), ("BasePriority", ctypes.c_void_p),
                    ("UniqueProcessId", ctypes.c_void_p),
                    ("InheritedFromUniqueProcessId", ctypes.c_void_p)]

    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.K32EnumProcesses.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD,
                                           ctypes.POINTER(wintypes.DWORD)]
    _ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p,
                                                 ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]

    def _read(handle, address, size):
        buffer = ctypes.create_string_buffer(size)
        done = ctypes.c_size_t(0)
        if not _kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buffer, size,
                                           ctypes.byref(done)):
            return None
        return buffer.raw[:done.value]

    def _pointer(data, offset):
        return int.from_bytes(data[offset:offset + 8], "little")

    def _process_strings(pid):
        handle = _kernel32.OpenProcess(_PROCESS_QUERY_INFORMATION | _PROCESS_VM_READ, False, pid)
        if not handle:
            return None
        try:
            info = _BasicInformation()
            if _ntdll.NtQueryInformationProcess(handle, 0, ctypes.byref(info), ctypes.sizeof(info),
                                                None) != 0 or not info.PebBaseAddress:
                return None
            peb = _read(handle, info.PebBaseAddress, 0x28)
            if not peb:
                return None
            params = _read(handle, _pointer(peb, 0x20), 0x400)
            if not params or len(params) < 0x3F8:
                return None
            length = int.from_bytes(params[0x70:0x72], "little")
            command = _read(handle, _pointer(params, 0x78), length) or b""
            environment = b""
            address, size = _pointer(params, 0x80), _pointer(params, 0x3F0)
            if address:
                if 0 < size <= 4 * 1024 * 1024:
                    environment = _read(handle, address, size) or b""
                if not environment:
                    chunks = []
                    for index in range(64):
                        chunk = _read(handle, address + index * 4096, 4096)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        if b"\x00\x00\x00\x00" in chunk:
                            break
                    environment = b"".join(chunks)
            return (command.decode("utf-16-le", "replace"),
                    environment.decode("utf-16-le", "replace").replace("\x00", "\n"))
        finally:
            _kernel32.CloseHandle(handle)

    def _windows_processes():
        count = 4096
        while True:
            pids = (wintypes.DWORD * count)()
            needed = wintypes.DWORD(0)
            if not _kernel32.K32EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(needed)):
                raise ctypes.WinError(ctypes.get_last_error())
            if needed.value < ctypes.sizeof(pids):
                break
            count *= 2
        result = []
        for pid in list(pids)[:needed.value // ctypes.sizeof(wintypes.DWORD)]:
            if pid:
                strings = _process_strings(pid)
                if strings is not None:
                    result.append((pid, strings[0], strings[1]))
        if not result:
            raise AssertionError("could not read any process command line")
        return result
