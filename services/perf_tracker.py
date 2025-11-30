"""Performance tracking for debug panel.

Captures timing information for all major operations during game startup
and gameplay, allowing identification of bottlenecks.

Usage:
    from services.perf_tracker import perf, get_perf_summary
    
    # Track a single operation
    with perf.track("voice_fetch"):
        voices = fetch_voices()
    
    # Track parallel operations
    perf.start_parallel("image_generation", count=4)
    # ... parallel operations ...
    perf.end_parallel("image_generation")
    
    # Get summary for debug panel
    summary = get_perf_summary()
"""

import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TimingEntry:
    """A single timing measurement."""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    is_parallel: bool = False
    parallel_count: int = 1
    status: str = "running"
    details: str = ""
    
    def complete(self, status: str = "success", details: str = ""):
        """Mark this entry as complete."""
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        if details:
            self.details = details


class PerformanceTracker:
    """Tracks timing of operations for performance analysis."""
    
    def __init__(self):
        self._entries: List[TimingEntry] = []
        self._active: Dict[str, TimingEntry] = {}
        self._session_start: Optional[float] = None
        self._session_id: Optional[str] = None
        
    def reset(self, session_id: str = ""):
        """Reset tracker for a new session."""
        self._entries = []
        self._active = {}
        self._session_start = time.perf_counter()
        self._session_id = session_id
        logger.info("[PERF] Tracker reset for session %s", session_id[:8] if session_id else "unknown")
    
    def start(self, name: str, is_parallel: bool = False, parallel_count: int = 1, details: str = "") -> TimingEntry:
        """Start timing an operation."""
        entry = TimingEntry(
            name=name,
            start_time=time.perf_counter(),
            is_parallel=is_parallel,
            parallel_count=parallel_count,
            details=details
        )
        self._active[name] = entry
        
        if is_parallel:
            logger.info("[PERF] ⏱️ Started: %s (parallel x%d)", name, parallel_count)
        else:
            logger.info("[PERF] ⏱️ Started: %s", name)
        
        return entry
    
    def end(self, name: str, status: str = "success", details: str = ""):
        """End timing an operation."""
        if name not in self._active:
            logger.warning("[PERF] Tried to end unknown operation: %s", name)
            return
        
        entry = self._active.pop(name)
        entry.complete(status, details)
        self._entries.append(entry)
        
        status_emoji = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
        
        if entry.is_parallel:
            logger.info(
                "[PERF] %s Completed: %s (parallel x%d) - %.0fms%s",
                status_emoji, name, entry.parallel_count, entry.duration_ms,
                f" ({details})" if details else ""
            )
        else:
            logger.info(
                "[PERF] %s Completed: %s - %.0fms%s",
                status_emoji, name, entry.duration_ms,
                f" ({details})" if details else ""
            )
    
    @contextmanager
    def track(self, name: str, details: str = ""):
        """Context manager for tracking an operation."""
        self.start(name, details=details)
        try:
            yield
            self.end(name, status="success")
        except Exception as e:
            self.end(name, status="error", details=str(e))
            raise
    
    def start_parallel(self, name: str, count: int, details: str = ""):
        """Start tracking a parallel operation."""
        self.start(name, is_parallel=True, parallel_count=count, details=details)
    
    def end_parallel(self, name: str, completed: int = 0, details: str = ""):
        """End a parallel operation with completion count."""
        if completed:
            details = f"{completed} completed" + (f", {details}" if details else "")
        self.end(name, status="success" if completed else "partial", details=details)
    
    def get_total_time_ms(self) -> float:
        """Get total elapsed time since session start."""
        if self._session_start is None:
            return 0
        return (time.perf_counter() - self._session_start) * 1000
    
    def get_summary(self) -> str:
        """Get a formatted summary of all timings."""
        if not self._entries and not self._active:
            return "No performance data captured yet."
        
        lines = []
        lines.append("=" * 60)
        lines.append("⏱️  PERFORMANCE SUMMARY")
        lines.append("=" * 60)
        
        if self._session_id:
            lines.append(f"Session: {self._session_id[:8]}...")
        
        total_ms = self.get_total_time_ms()
        lines.append(f"Total elapsed: {total_ms:.0f}ms ({total_ms/1000:.1f}s)")
        lines.append("")
        
        # Completed operations
        if self._entries:
            lines.append("📊 COMPLETED OPERATIONS:")
            lines.append("-" * 40)
            
            # Sort by duration (longest first)
            sorted_entries = sorted(self._entries, key=lambda e: e.duration_ms or 0, reverse=True)
            
            for entry in sorted_entries:
                status_icon = "✅" if entry.status == "success" else "❌" if entry.status == "error" else "⚠️"
                parallel_info = f" [parallel x{entry.parallel_count}]" if entry.is_parallel else ""
                
                # Calculate percentage of total time
                pct = (entry.duration_ms / total_ms * 100) if total_ms > 0 else 0
                
                # Bar visualization
                bar_len = int(pct / 5)  # 20 chars = 100%
                bar = "█" * bar_len + "░" * (20 - bar_len)
                
                lines.append(f"{status_icon} {entry.name}{parallel_info}")
                lines.append(f"   {bar} {entry.duration_ms:.0f}ms ({pct:.1f}%)")
                if entry.details:
                    lines.append(f"   └─ {entry.details}")
            
            lines.append("")
        
        # Active operations
        if self._active:
            lines.append("🔄 CURRENTLY RUNNING:")
            lines.append("-" * 40)
            
            for name, entry in self._active.items():
                elapsed = (time.perf_counter() - entry.start_time) * 1000
                parallel_info = f" [parallel x{entry.parallel_count}]" if entry.is_parallel else ""
                lines.append(f"⏳ {name}{parallel_info} - {elapsed:.0f}ms elapsed...")
            
            lines.append("")
        
        # Bottleneck analysis
        if self._entries:
            lines.append("🎯 BOTTLENECK ANALYSIS:")
            lines.append("-" * 40)
            
            # Find the slowest operation
            slowest = max(self._entries, key=lambda e: e.duration_ms or 0)
            lines.append(f"Slowest: {slowest.name} ({slowest.duration_ms:.0f}ms)")
            
            # Parallel vs sequential time
            parallel_time = sum(e.duration_ms for e in self._entries if e.is_parallel) or 0
            sequential_time = sum(e.duration_ms for e in self._entries if not e.is_parallel) or 0
            
            lines.append(f"Parallel operations: {parallel_time:.0f}ms")
            lines.append(f"Sequential operations: {sequential_time:.0f}ms")
            
            # Potential savings if everything was parallel
            if len(self._entries) > 1:
                all_parallel_estimate = max(e.duration_ms for e in self._entries) or 0
                savings = total_ms - all_parallel_estimate
                if savings > 0:
                    lines.append(f"💡 Potential savings with full parallelization: ~{savings:.0f}ms")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def get_entries(self) -> List[TimingEntry]:
        """Get all timing entries."""
        return self._entries.copy()


# Global tracker instance
perf = PerformanceTracker()


def get_perf_summary() -> str:
    """Get the current performance summary."""
    return perf.get_summary()


def reset_perf_tracker(session_id: str = ""):
    """Reset the performance tracker for a new session."""
    perf.reset(session_id)

