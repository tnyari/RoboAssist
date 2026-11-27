"""Opt-in process-tree CPU and working-set measurements for Windows runs."""

from __future__ import annotations

import ctypes
import math
import os
import sys
import time
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast


@dataclass(frozen=True)
class ProcessCounters:
    """Cumulative CPU time and current working set for one process identity."""

    identity: int
    cpu_seconds: float
    working_set_bytes: int


class ProcessSnapshotProvider(Protocol):
    def snapshot(self, root_pid: int) -> Mapping[int, ProcessCounters]: ...


@dataclass(frozen=True)
class ProcessUsageSample:
    monotonic_ns: int
    process_count: int
    working_set_bytes: int
    cpu_percent: float | None


@dataclass(frozen=True)
class ProcessUsageSummary:
    average_cpu_percent: float | None
    peak_working_set_bytes: int | None
    process_sample_count: int
    cpu_interval_count: int


class ProcessTreeSampler:
    """Sample the root process plus descendants without installing a dependency.

    CPU percentages are normalized to total logical machine capacity: a whole
    machine at full load is 100 percent. Call ``sample`` at a steady interval;
    the first sample is the CPU baseline and also contributes to peak memory.
    """

    def __init__(
        self,
        *,
        root_pid: int | None = None,
        logical_cpu_count: int | None = None,
        provider: ProcessSnapshotProvider | None = None,
    ) -> None:
        self.root_pid = os.getpid() if root_pid is None else root_pid
        cpu_count = os.cpu_count() if logical_cpu_count is None else logical_cpu_count
        if self.root_pid < 1:
            raise ValueError("root_pid must be positive")
        if cpu_count is None or cpu_count < 1:
            raise ValueError("logical_cpu_count must be positive")
        self.logical_cpu_count = cpu_count
        self._provider = provider or WindowsProcessSnapshotProvider()
        self._previous: dict[int, ProcessCounters] | None = None
        self._previous_ns: int | None = None
        self._observations = 0
        self._intervals = 0
        self._elapsed_seconds = 0.0
        self._cpu_seconds = 0.0
        self._peak_working_set_bytes: int | None = None

    def sample(self, monotonic_ns: int | None = None) -> ProcessUsageSample:
        """Take one process-tree snapshot; CPU is undefined for the baseline."""
        now_ns = time.monotonic_ns() if monotonic_ns is None else monotonic_ns
        if now_ns < 0:
            raise ValueError("monotonic_ns must be nonnegative")
        snapshot = dict(self._provider.snapshot(self.root_pid))
        if self.root_pid not in snapshot:
            raise RuntimeError("Root process was not present in the process-tree snapshot")
        for pid, counters in snapshot.items():
            if (
                pid < 1
                or counters.identity < 0
                or not math.isfinite(counters.cpu_seconds)
                or counters.cpu_seconds < 0
                or counters.working_set_bytes < 0
            ):
                raise ValueError("Process snapshot contains invalid counters")

        working_set = sum(item.working_set_bytes for item in snapshot.values())
        peak = self._peak_working_set_bytes
        self._peak_working_set_bytes = working_set if peak is None else max(peak, working_set)
        cpu_percent: float | None = None
        if self._previous is not None and self._previous_ns is not None:
            if now_ns <= self._previous_ns:
                raise ValueError("Process sample timestamps must increase")
            elapsed = (now_ns - self._previous_ns) / 1_000_000_000
            delta_cpu = 0.0
            for pid, current in snapshot.items():
                previous = self._previous.get(pid)
                if previous is None or previous.identity != current.identity:
                    delta_cpu += current.cpu_seconds
                elif current.cpu_seconds < previous.cpu_seconds:
                    raise ValueError("Process CPU time decreased for a stable process identity")
                else:
                    delta_cpu += current.cpu_seconds - previous.cpu_seconds
            cpu_percent = 100 * delta_cpu / (elapsed * self.logical_cpu_count)
            self._elapsed_seconds += elapsed
            self._cpu_seconds += delta_cpu
            self._intervals += 1

        self._previous = snapshot
        self._previous_ns = now_ns
        self._observations += 1
        return ProcessUsageSample(now_ns, len(snapshot), working_set, cpu_percent)

    @property
    def summary(self) -> ProcessUsageSummary:
        average = (
            100 * self._cpu_seconds / (self._elapsed_seconds * self.logical_cpu_count)
            if self._elapsed_seconds
            else None
        )
        return ProcessUsageSummary(
            average,
            self._peak_working_set_bytes,
            self._observations,
            self._intervals,
        )


class WindowsProcessSnapshotProvider:
    """Read descendants with Toolhelp and usage with kernel32/psapi."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("Process-tree sampling is available only on Windows")
        from ctypes import wintypes

        self._wintypes = wintypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._psapi = ctypes.WinDLL("psapi", use_last_error=True)

        class ProcessEntry32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        class FileTime(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        class ProcessMemoryCountersEx(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        self._process_entry_type = ProcessEntry32W
        self._file_time_type = FileTime
        self._memory_type = ProcessMemoryCountersEx
        self._configure_functions()

    def _configure_functions(self) -> None:
        wt = self._wintypes
        self._kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
        self._kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
        self._kernel32.Process32FirstW.argtypes = [
            wt.HANDLE,
            ctypes.POINTER(self._process_entry_type),
        ]
        self._kernel32.Process32FirstW.restype = wt.BOOL
        self._kernel32.Process32NextW.argtypes = [
            wt.HANDLE,
            ctypes.POINTER(self._process_entry_type),
        ]
        self._kernel32.Process32NextW.restype = wt.BOOL
        self._kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        self._kernel32.OpenProcess.restype = wt.HANDLE
        self._kernel32.GetProcessTimes.argtypes = [
            wt.HANDLE,
            ctypes.POINTER(self._file_time_type),
            ctypes.POINTER(self._file_time_type),
            ctypes.POINTER(self._file_time_type),
            ctypes.POINTER(self._file_time_type),
        ]
        self._kernel32.GetProcessTimes.restype = wt.BOOL
        self._kernel32.CloseHandle.argtypes = [wt.HANDLE]
        self._kernel32.CloseHandle.restype = wt.BOOL
        self._psapi.GetProcessMemoryInfo.argtypes = [
            wt.HANDLE,
            ctypes.POINTER(self._memory_type),
            wt.DWORD,
        ]
        self._psapi.GetProcessMemoryInfo.restype = wt.BOOL

    def _process_parents(self) -> dict[int, int]:
        invalid_handle = ctypes.c_void_p(-1).value
        snapshot = self._kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if not snapshot or snapshot == invalid_handle:
            code = ctypes.get_last_error()
            raise OSError(code, "Unable to enumerate Windows processes")
        parents: dict[int, int] = {}
        try:
            entry = self._process_entry_type()
            entry.dwSize = ctypes.sizeof(self._process_entry_type)
            if not self._kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
                code = ctypes.get_last_error()
                raise OSError(code, "Unable to read Windows process list")
            while True:
                parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
                if not self._kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
        finally:
            self._kernel32.CloseHandle(snapshot)
        return parents

    def _family(self, root_pid: int) -> set[int]:
        parents = self._process_parents()
        if root_pid not in parents:
            raise RuntimeError("Root process was not present in the Windows process list")
        children: dict[int, list[int]] = defaultdict(list)
        for pid, parent in parents.items():
            children[parent].append(pid)
        family = {root_pid}
        pending = [root_pid]
        while pending:
            for child in children[pending.pop()]:
                if child not in family:
                    family.add(child)
                    pending.append(child)
        return family

    @staticmethod
    def _file_time_value(value: ctypes.Structure) -> int:
        file_time = cast(Any, value)
        low = int(file_time.dwLowDateTime)
        high = int(file_time.dwHighDateTime)
        return (high << 32) | low

    def snapshot(self, root_pid: int) -> Mapping[int, ProcessCounters]:
        family = self._family(root_pid)
        result: dict[int, ProcessCounters] = {}
        access = 0x0400 | 0x0010  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        for pid in family:
            handle = self._kernel32.OpenProcess(access, False, pid)
            if not handle:
                code = ctypes.get_last_error()
                if code in (6, 87):  # The process exited between enumeration and OpenProcess.
                    continue
                raise OSError(code, "Unable to inspect a process in the benchmark tree")
            try:
                creation = self._file_time_type()
                exit_time = self._file_time_type()
                kernel_time = self._file_time_type()
                user_time = self._file_time_type()
                if not self._kernel32.GetProcessTimes(
                    handle,
                    ctypes.byref(creation),
                    ctypes.byref(exit_time),
                    ctypes.byref(kernel_time),
                    ctypes.byref(user_time),
                ):
                    code = ctypes.get_last_error()
                    if code in (6, 87):
                        continue
                    raise OSError(code, "Unable to read process CPU time")
                memory = self._memory_type()
                memory.cb = ctypes.sizeof(self._memory_type)
                if not self._psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
                    code = ctypes.get_last_error()
                    if code in (6, 87):
                        continue
                    raise OSError(code, "Unable to read process working set")
                cpu_ticks = self._file_time_value(kernel_time) + self._file_time_value(user_time)
                result[pid] = ProcessCounters(
                    self._file_time_value(creation),
                    cpu_ticks / 10_000_000,
                    int(memory.WorkingSetSize),
                )
            finally:
                self._kernel32.CloseHandle(handle)
        if root_pid not in result:
            raise RuntimeError("Root process disappeared while sampling its process tree")
        return result
