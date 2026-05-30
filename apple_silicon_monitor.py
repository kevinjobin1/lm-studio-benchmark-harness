#!/usr/bin/env python3
"""
Apple Silicon Hardware Monitor
Tracks memory pressure, thermal state, and performance metrics
"""

import psutil
import time
import subprocess
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import deque


@dataclass
class HardwareSnapshot:
    """Snapshot of hardware state."""
    timestamp: float
    cpu_percent: float
    memory_used_mb: float
    memory_available_mb: float
    memory_percent: float
    swap_used_mb: float
    swap_percent: float
    cpu_temp_c: Optional[float]
    thermal_pressure: Optional[str]
    gpu_percent: Optional[float]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "cpu_percent": self.cpu_percent,
            "memory_used_mb": self.memory_used_mb,
            "memory_available_mb": self.memory_available_mb,
            "memory_percent": self.memory_percent,
            "swap_used_mb": self.swap_used_mb,
            "swap_percent": self.swap_percent,
            "cpu_temp_c": self.cpu_temp,
            "thermal_pressure": self.thermal_pressure,
            "gpu_percent": self.gpu_percent
        }


class AppleSiliconMonitor:
    """Monitor Apple Silicon hardware metrics."""
    
    def __init__(self, sample_interval: float = 1.0, history_size: int = 60):
        self.sample_interval = sample_interval
        self.history = deque(maxlen=history_size)
        self.is_apple_silicon = self._detect_apple_silicon()
    
    def _detect_apple_silicon(self) -> bool:
        """Detect if running on Apple Silicon."""
        import platform
        return platform.machine() in ["arm64", "aarch64"]
    
    def get_cpu_temp(self) -> Optional[float]:
        """Get CPU temperature (Apple Silicon only)."""
        if not self.is_apple_silicon:
            return None
        
        try:
            # Use powermetrics on macOS
            result = subprocess.run(
                ["sudo", "powermetrics", "--samplers", "cpu_power", "-i", "1", "-n", "1"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Parse output for temperature
            # This is a simplified version - actual parsing would be more complex
            return None  # Placeholder
        except:
            return None
    
    def get_thermal_pressure(self) -> Optional[str]:
        """Get thermal pressure state (Apple Silicon only)."""
        if not self.is_apple_silicon:
            return None
        
        try:
            # Use system_profiler on macOS
            result = subprocess.run(
                ["system_profiler", "SPPowerDataType"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Parse for thermal pressure
            if "Nominal" in result.stdout:
                return "nominal"
            elif "Moderate" in result.stdout:
                return "moderate"
            elif "Heavy" in result.stdout:
                return "heavy"
            elif "Critical" in result.stdout:
                return "critical"
            return None
        except:
            return None
    
    def get_gpu_usage(self) -> Optional[float]:
        """Get GPU usage percentage (Apple Silicon only)."""
        if not self.is_apple_silicon:
            return None
        
        try:
            # This would require specialized tools on macOS
            # Placeholder for now
            return None
        except:
            return None
    
    def take_snapshot(self) -> HardwareSnapshot:
        """Take a snapshot of current hardware state."""
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return HardwareSnapshot(
            timestamp=time.time(),
            cpu_percent=psutil.cpu_percent(interval=0.1),
            memory_used_mb=memory.used / (1024 ** 2),
            memory_available_mb=memory.available / (1024 ** 2),
            memory_percent=memory.percent,
            swap_used_mb=swap.used / (1024 ** 2),
            swap_percent=swap.percent,
            cpu_temp_c=self.get_cpu_temp(),
            thermal_pressure=self.get_thermal_pressure(),
            gpu_percent=self.get_gpu_usage()
        )
    
    def start_monitoring(self, duration: float) -> List[HardwareSnapshot]:
        """Monitor hardware for specified duration."""
        snapshots = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            snapshot = self.take_snapshot()
            snapshots.append(snapshot)
            self.history.append(snapshot)
            time.sleep(self.sample_interval)
        
        return snapshots
    
    def get_aggregate_metrics(self, snapshots: List[HardwareSnapshot]) -> Dict:
        """Calculate aggregate metrics from snapshots."""
        if not snapshots:
            return {}
        
        cpu_values = [s.cpu_percent for s in snapshots]
        memory_values = [s.memory_used_mb for s in snapshots]
        swap_values = [s.swap_used_mb for s in snapshots]
        
        # Detect thermal throttling
        thermal_states = [s.thermal_pressure for s in snapshots if s.thermal_pressure]
        thermal_throttling = any(state in ["moderate", "heavy", "critical"] for state in thermal_states)
        
        return {
            "cpu_avg": sum(cpu_values) / len(cpu_values),
            "cpu_max": max(cpu_values),
            "cpu_min": min(cpu_values),
            "memory_avg_mb": sum(memory_values) / len(memory_values),
            "memory_peak_mb": max(memory_values),
            "memory_min_mb": min(memory_values),
            "swap_avg_mb": sum(swap_values) / len(swap_values) if swap_values else 0,
            "swap_peak_mb": max(swap_values) if swap_values else 0,
            "thermal_throttling": thermal_throttling,
            "thermal_pressure_states": thermal_states,
            "sample_count": len(snapshots)
        }
    
    def detect_memory_pressure(self) -> str:
        """Detect current memory pressure state."""
        memory = psutil.virtual_memory()
        
        if memory.percent < 70:
            return "low"
        elif memory.percent < 85:
            return "moderate"
        else:
            return "high"
    
    def detect_speed_decay(self, baseline_speed: float, current_speed: float, threshold: float = 0.2) -> bool:
        """Detect if speed has decayed significantly from baseline."""
        if baseline_speed == 0:
            return False
        
        decay = (baseline_speed - current_speed) / baseline_speed
        return decay > threshold


if __name__ == "__main__":
    # Test monitoring
    monitor = AppleSiliconMonitor()
    
    print(f"Apple Silicon: {monitor.is_apple_silicon}")
    print(f"Memory pressure: {monitor.detect_memory_pressure()}")
    
    snapshot = monitor.take_snapshot()
    print(f"\nCurrent snapshot:")
    print(f"  CPU: {snapshot.cpu_percent}%")
    print(f"  Memory: {snapshot.memory_used_mb:.1f} MB ({snapshot.memory_percent:.1f}%)")
    print(f"  Swap: {snapshot.swap_used_mb:.1f} MB ({snapshot.swap_percent:.1f}%)")
    print(f"  Thermal: {snapshot.thermal_pressure}")
