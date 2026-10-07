"""Best-effort runtime, toolchain, and hardware metadata probes."""

import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))


def _git_sha():
    """Best-effort harness git SHA; 'unknown' outside a git checkout."""
    try:
        import subprocess

        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        sha = (out.stdout or "").strip()
        if out.returncode == 0 and len(sha) == 40:
            return sha
    except Exception:
        pass
    return "unknown"


def _tool_version(binary, *version_args):
    """Best-effort '<binary> <version>' string or 'unknown'."""
    try:
        import shutil
        import subprocess

        if shutil.which(binary) is None:
            return "unknown (binary not found)"
        out = subprocess.run(
            [binary] + list(version_args), capture_output=True, text=True, timeout=15
        )
        line = ((out.stdout or "") + "\n" + (out.stderr or "")).strip()
        return line.splitlines()[0][:120] if line else "unknown"
    except Exception:
        return "unknown"


def collect_toolchain():
    """Toolchain versions for rebuildability. Never raises; unknowns kept."""
    try:
        import sqlite3

        sqlite_v = sqlite3.sqlite_version
    except Exception:
        sqlite_v = "unknown"
    return {
        "python": platform.python_version(),
        "node": _tool_version("node", "--version"),
        "rustc": _tool_version("rustc", "--version"),
        "tsc": _tool_version("tsc", "--version"),
        "sqlite": sqlite_v,
        "postgres": _tool_version("psql", "--version"),
    }


def _hardware_cpu():
    """Best-effort CPU label; "unknown", never "". SPEC 32."""
    try:
        label = str(platform.processor() or platform.machine() or "").strip()
        if label:
            return label[:120]
    except Exception:
        pass
    return "unknown"


def _hardware_cpu_count():
    """Best-effort CPU count as string; "unknown", never "". SPEC 32."""
    try:
        count = os.cpu_count()
        if isinstance(count, int) and count > 0:
            return str(count)
    except Exception:
        pass
    return "unknown"


def _ram_gb_float():
    """Best-effort total RAM in GB as float, or None. SPEC 32."""
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if pages and page_size:
            return float(pages) * float(page_size) / (1024.0**3)
    except Exception:
        pass
    try:
        import subprocess

        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=10
        )
        val = (out.stdout or "").strip()
        if out.returncode == 0 and val.isdigit():
            return float(val) / (1024.0**3)
    except Exception:
        pass
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return float(line.split()[1]) / (1024.0**2)
    except Exception:
        pass
    return None


def _hardware_ram_gb():
    """Best-effort RAM label in GB; "unknown", never "". SPEC 32."""
    try:
        ram = _ram_gb_float()
        if ram is not None and ram > 0:
            text = f"{ram:.1f}"
            if text.endswith(".0"):
                text = text[:-2]
            return text
    except Exception:
        pass
    return "unknown"


def _hardware_gpu():
    """Best-effort GPU label: darwin sysctl or nvidia-smi, else unknown."""
    try:
        import subprocess

        if sys.platform == "darwin":
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            label = (out.stdout or "").strip()
            if out.returncode == 0 and label:
                return label[:120]
        import shutil

        if shutil.which("nvidia-smi") is not None:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            lines = (out.stdout or "").strip().splitlines()
            if out.returncode == 0 and lines and lines[0].strip():
                return lines[0].strip()[:120]
    except Exception:
        pass
    return "unknown"


def _device_class(machine, ram_gb, gpu):
    """Coarse device bucket; "unknown" when parts unknown. SPEC 32."""
    try:
        arch = str(machine or "").strip().lower()
        if arch in ("arm64", "aarch64", "arm"):
            arch_token = "arm64"
        elif arch in ("x86_64", "amd64", "x64", "i386", "i686"):
            arch_token = "x64"
        elif arch and arch != "unknown":
            arch_token = "".join(c for c in arch if c.isalnum())[:16] or "unknown"
        else:
            return "unknown"
        gpu_token = str(gpu or "").strip().lower()
        for slug in ("a100", "h100", "v100", "a10", "t4", "l4"):
            if slug in gpu_token:
                return f"cloud-gpu-{slug}"
        if "tesla" in gpu_token or "nvidia" in gpu_token:
            return "cloud-gpu-nvidia"
        ram = float(ram_gb)
        if not ram > 0:
            return "unknown"
        if ram <= 8.5:
            ram_token = "8gb"
        elif ram <= 17:
            ram_token = "16gb"
        elif ram <= 40:
            ram_token = "32gb"
        else:
            ram_token = "64gb"
        return f"laptop-{arch_token}-{ram_token}"
    except Exception:
        return "unknown"


def collect_hardware():
    """Best-effort hardware object; unknowns are explicit, never guessed."""
    try:
        machine = platform.machine() or "unknown"
    except Exception:
        machine = "unknown"
    cpu = _hardware_cpu()
    cpu_count = _hardware_cpu_count()
    ram_gb = _hardware_ram_gb()
    gpu = _hardware_gpu()
    try:
        ram_num = _ram_gb_float()
    except Exception:
        ram_num = None
    device_class = _device_class(machine, ram_num if ram_num else ram_gb, gpu)
    hardware = {
        "cpu": cpu,
        "cpu_count": cpu_count,
        "ram_gb": ram_gb,
        "gpu": gpu,
        "device_class": device_class,
    }
    for key, val in hardware.items():
        if not isinstance(val, str) or not val.strip():
            hardware[key] = "unknown"
    return hardware
