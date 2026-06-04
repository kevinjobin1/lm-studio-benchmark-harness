"""
Hardware detection — unified static detection of CPU, GPU, RAM, OS, and architecture.

Captures:
- CPU: model name, cores (physical/logical), frequency
- GPU: model name, VRAM
- RAM: total, available
- OS: name, version, kernel
- Architecture: arm64, x86_64, etc.
- Apple Silicon specifics: thermal state, memory pressure, unified memory

Usage:
    from core.hardware import detect_hardware, HardwareInfo
    hw = detect_hardware()
    print(hw.to_dict())
"""

import os
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from packages.modellens_logging import get_logger

logger = get_logger(__name__)


@dataclass
class HardwareInfo:
    """Static hardware profile captured at benchmark start."""

    # ── Platform ──────────────────────────────────────────────────
    os_name: str = ""
    os_version: str = ""
    kernel: str = ""
    architecture: str = ""
    hostname: str = ""

    # ── CPU ───────────────────────────────────────────────────────
    cpu_model: str = ""
    cpu_cores_physical: int = 0
    cpu_cores_logical: int = 0
    cpu_freq_mhz: float = 0.0

    # ── Memory ────────────────────────────────────────────────────
    ram_total_mb: float = 0.0
    ram_available_mb: float = 0.0
    swap_total_mb: float = 0.0

    # ── GPU ───────────────────────────────────────────────────────
    gpu_model: str = ""
    gpu_available: bool = False
    gpu_vram_mb: float = 0.0
    gpu_count: int = 0

    # ── Apple Silicon ─────────────────────────────────────────────
    is_apple_silicon: bool = False
    unified_memory: bool = False

    # ── Metadata ──────────────────────────────────────────────────
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    raw: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Serialize to a flat dict for JSON results."""
        return {
            "os": {
                "name": self.os_name,
                "version": self.os_version,
                "kernel": self.kernel,
                "architecture": self.architecture,
                "hostname": self.hostname,
            },
            "cpu": {
                "model": self.cpu_model,
                "cores_physical": self.cpu_cores_physical,
                "cores_logical": self.cpu_cores_logical,
                "freq_mhz": self.cpu_freq_mhz,
            },
            "memory": {
                "ram_total_mb": self.ram_total_mb,
                "ram_available_mb": self.ram_available_mb,
                "swap_total_mb": self.swap_total_mb,
            },
            "gpu": {
                "model": self.gpu_model,
                "available": self.gpu_available,
                "vram_mb": self.gpu_vram_mb,
                "count": self.gpu_count,
            },
            "apple_silicon": self.is_apple_silicon,
            "unified_memory": self.unified_memory,
            "detected_at": self.detected_at,
        }

    def summary(self) -> str:
        """Human-readable one-line summary (e.g., 'Apple M3 Pro 18GB, macOS 15.6.1 ')."""
        parts = []
        if self.cpu_model:
            parts.append(self.cpu_model)
        if self.ram_total_mb:
            parts.append(f"{self.ram_total_mb / 1024:.0f}GB")
        if self.os_name:
            parts.append(f"{self.os_name} {self.os_version}")
        if self.is_apple_silicon:
            parts.append("Apple Silicon")
        return ", ".join(parts) if parts else "Unknown hardware"


# ── Detection functions ──────────────────────────────────────────────


def _macos_cpu_model() -> str:
    """Get CPU brand string on macOS via sysctl."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug("Could not detect macOS CPU model: %s", e)
        return ""


def _macos_cpu_freq() -> float:
    """Get CPU frequency in MHz on macOS."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.cpufrequency"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        hz = int(result.stdout.strip())
        return round(hz / 1_000_000, 1)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError) as e:
        logger.debug("Could not detect macOS CPU frequency: %s", e)
        return 0.0


def _macos_gpu_model() -> str:
    """Get GPU model on macOS via system_profiler."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.split("\n"):
            stripped = line.strip()
            if stripped.startswith("Chipset Model:"):
                return stripped.split(":", 1)[1].strip()
        return ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug("Could not detect macOS GPU model: %s", e)
        return ""


def _macos_gpu_vram() -> float:
    """Get discrete GPU VRAM in MB on macOS. Returns 0 for unified memory Macs."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.split("\n"):
            stripped = line.strip()
            if "VRAM" in stripped:
                # Parse "VRAM (Total): 4096 MB" or similar
                import re

                match = re.search(r"(\d+)\s*MB", stripped)
                if match:
                    return float(match.group(1))
        return 0.0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug("Could not detect macOS GPU VRAM: %s", e)
        return 0.0


def _linux_cpu_model() -> str:
    """Get CPU model on Linux via /proc/cpuinfo."""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        return ""
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.debug("Could not detect Linux CPU model: %s", e)
        return ""


def _linux_gpu_model() -> str:
    """Get GPU model on Linux via lspci."""
    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.split("\n"):
            if "VGA" in line or "3D" in line or "Display" in line:
                return line.split(":", 2)[-1].strip()
        return ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug("Could not detect Linux GPU model: %s", e)
        return ""


def detect_hardware() -> HardwareInfo:
    """Detect hardware profile. Cross-platform (macOS, Linux, Windows)."""

    hw = HardwareInfo()

    # ── Platform ──────────────────────────────────────────────────
    hw.os_name = platform.system()  # Darwin, Linux, Windows
    hw.os_version = platform.mac_ver()[0] if hw.os_name == "Darwin" else platform.version()
    hw.kernel = platform.release()
    hw.architecture = platform.machine()
    hw.hostname = platform.node()

    # ── Apple Silicon detection ───────────────────────────────────
    if hw.os_name == "Darwin" and hw.architecture in ("arm64", "aarch64"):
        hw.is_apple_silicon = True
        hw.unified_memory = True

    # ── CPU & Memory (consolidated psutil) ───────────────────────
    try:
        import psutil

        hw.cpu_cores_physical = psutil.cpu_count(logical=False)
        hw.cpu_cores_logical = psutil.cpu_count(logical=True)
        mem = psutil.virtual_memory()
        hw.ram_total_mb = round(mem.total / (1024 * 1024), 1)
        hw.ram_available_mb = round(mem.available / (1024 * 1024), 1)
        swap = psutil.swap_memory()
        hw.swap_total_mb = round(swap.total / (1024 * 1024), 1)
    except (ImportError, ModuleNotFoundError):
        pass  # psutil not installed — skip CPU/memory detection
    except Exception as e:
        logger.debug("Could not detect CPU/memory via psutil: %s", e)

    # ── GPU ───────────────────────────────────────────────────────
    if hw.os_name == "Darwin":
        hw.gpu_model = _macos_gpu_model()
        hw.gpu_available = bool(hw.gpu_model)
        if hw.unified_memory:
            hw.gpu_vram_mb = 0.0  # Unified — reported as RAM
        else:
            hw.gpu_vram_mb = _macos_gpu_vram()
    elif hw.os_name == "Linux":
        hw.gpu_model = _linux_gpu_model()
        hw.gpu_available = bool(hw.gpu_model)

    hw.gpu_count = 1 if hw.gpu_available else 0

    return hw


__all__ = ["HardwareInfo", "detect_hardware"]
