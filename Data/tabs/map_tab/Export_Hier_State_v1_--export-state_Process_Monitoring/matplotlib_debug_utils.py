#!/usr/bin/env python3
"""
matplotlib_debug_utils.py - Debugging utilities for matplotlib visualizations

Provides tools to debug performance, events, and rendering issues in matplotlib.
"""

import matplotlib
import matplotlib.pyplot as plt
import time
from unified_logger import get_logger
from collections import deque
from datetime import datetime

class MatplotlibDebugger:
    """Debug helper for matplotlib figures"""

    def __init__(self, fig, ax, logger=None, enable_fps=True, enable_events=True):
        """
        Initialize matplotlib debugger

        Args:
            fig: matplotlib Figure
            ax: matplotlib Axes (can be 3D)
            logger: logging.Logger instance (optional)
            enable_fps: Track FPS and render performance
            enable_events: Log mouse/keyboard events
        """
        self.fig = fig
        self.ax = ax
        self.logger = logger or get_logger("viz_debug")

        # Performance tracking
        self.enable_fps = enable_fps
        self.frame_times = deque(maxlen=60)  # Last 60 frames
        self.last_render_time = None
        self.draw_count = 0
        
        # Expectations
        self.fps_expectation = 0
        self.performance_bugs = [] # List of {type, detail, timestamp}

        # Event tracking
        self.enable_events = enable_events
        self.event_log = deque(maxlen=100)

        # State tracking
        self.last_view = None

        # Setup
        self.log_backend_info()
        if enable_events:
            self.setup_event_logging()

    def log_backend_info(self):
        """Log matplotlib backend and configuration"""
        backend = matplotlib.get_backend()
        self.logger.info(f"Matplotlib Backend: {backend}")
        self.logger.info(f"Matplotlib Version: {matplotlib.__version__}")
        self.logger.info(f"Interactive Mode: {matplotlib.is_interactive()}")

        # Check if 3D
        is_3d = hasattr(self.ax, 'get_proj')
        self.logger.info(f"3D Projection: {is_3d}")

    def setup_event_logging(self):
        """Setup event listeners for debugging"""
        events = [
            'button_press_event',
            'button_release_event',
            'motion_notify_event',
            'scroll_event',
            'pick_event',
            'key_press_event',
            'key_release_event'
        ]

        for event in events:
            self.fig.canvas.mpl_connect(event, self._log_event)

    def _log_event(self, event):
        """Log matplotlib event"""
        if not self.enable_events:
            return

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Build event info
        info = {
            'time': timestamp,
            'type': event.name,
            'inaxes': event.inaxes == self.ax if hasattr(event, 'inaxes') else None
        }

        # Add event-specific data
        if hasattr(event, 'button'):
            info['button'] = event.button
        if hasattr(event, 'x') and hasattr(event, 'y'):
            info['pos'] = (event.x, event.y)
        if hasattr(event, 'xdata') and hasattr(event, 'ydata'):
            info['data'] = (event.xdata, event.ydata)
        if hasattr(event, 'key'):
            info['key'] = event.key
        if hasattr(event, 'ind'):
            info['picked_indices'] = event.ind

        self.event_log.append(info)

        # Log important events
        if event.name in ['pick_event', 'button_press_event']:
            self.logger.debug(f"Event: {event.name} - {info}")

    def start_render(self):
        """Mark start of render cycle"""
        if self.enable_fps:
            self.last_render_time = time.perf_counter()

    def end_render(self):
        """Mark end of render cycle and calculate FPS"""
        if self.enable_fps and self.last_render_time:
            render_time = time.perf_counter() - self.last_render_time
            self.frame_times.append(render_time)
            self.draw_count += 1

            # Log every 60 frames
            if self.draw_count % 60 == 0:
                self._log_performance()

    def _log_performance(self):
        """Log performance metrics"""
        if not self.frame_times:
            return

        avg_time = sum(self.frame_times) / len(self.frame_times)
        fps = 1.0 / avg_time if avg_time > 0 else 0
        min_time = min(self.frame_times)
        max_time = max(self.frame_times)

        self.logger.info(f"Render Performance: FPS={fps:.1f}, "
                        f"Avg={avg_time*1000:.1f}ms, "
                        f"Min={min_time*1000:.1f}ms, "
                        f"Max={max_time*1000:.1f}ms")

    def set_fps_expectation(self, fps):
        """Set the expected FPS for comparison"""
        self.fps_expectation = fps
        self.logger.info(f"FPS Expectation set to {fps}")

    def verify_expectations(self):
        """Compare actual performance against expectations and return findings"""
        current_fps = self.get_fps()
        findings = []

        if self.fps_expectation > 0:
            # Tolerance: 20% drop before flagging as a 'Bug'
            threshold = self.fps_expectation * 0.8
            if current_fps < threshold and self.draw_count > 60:
                bug = {
                    'type': 'FPS_MISMATCH',
                    'expected': self.fps_expectation,
                    'actual': round(current_fps, 1),
                    'timestamp': datetime.now().strftime("%H:%M:%S")
                }
                self.performance_bugs.append(bug)
                findings.append(bug)
                self.logger.warning(f"Performance Expectation Failed: Expected {self.fps_expectation}, got {current_fps:.1f}")

        return findings

    def get_fps(self):
        """Get current FPS"""
        if not self.frame_times:
            return 0
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0

    def log_view_state(self):
        """Log current 3D view state"""
        if hasattr(self.ax, 'elev') and hasattr(self.ax, 'azim'):
            view = (self.ax.elev, self.ax.azim)

            # Only log if changed
            if view != self.last_view:
                self.logger.debug(f"View changed: elev={self.ax.elev:.1f}, azim={self.ax.azim:.1f}")
                self.last_view = view

    def log_axes_state(self):
        """Log axes limits and properties"""
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        info = f"Axes State: xlim={xlim}, ylim={ylim}"

        if hasattr(self.ax, 'get_zlim'):
            zlim = self.ax.get_zlim()
            info += f", zlim={zlim}"

        self.logger.debug(info)

    def get_recent_events(self, event_type=None, limit=10):
        """Get recent events from log"""
        events = list(self.event_log)

        if event_type:
            events = [e for e in events if e['type'] == event_type]

        return events[-limit:]

    def clear_event_log(self):
        """Clear event log"""
        self.event_log.clear()

    def create_debug_overlay(self):
        """Create FPS/debug info overlay on figure"""
        if not hasattr(self, '_debug_text'):
            self._debug_text = self.fig.text(0.02, 0.98, '',
                                            transform=self.fig.transFigure,
                                            verticalalignment='top',
                                            fontsize=8,
                                            family='monospace',
                                            color='yellow',
                                            bbox=dict(boxstyle='round',
                                                     facecolor='black',
                                                     alpha=0.7))

        # Update text
        fps = self.get_fps()
        info = f"FPS: {fps:.1f}\n"
        info += f"Draws: {self.draw_count}\n"

        if hasattr(self.ax, 'elev'):
            info += f"Elev: {self.ax.elev:.1f}°\n"
            info += f"Azim: {self.ax.azim:.1f}°"

        self._debug_text.set_text(info)

    def enable_matplotlib_logging(self, level="DEBUG"):
        """Enable matplotlib's internal logging"""
        import logging
        mpl_logger = logging.getLogger('matplotlib')
        # Use level from string or default
        lvl = getattr(logging, level.upper()) if isinstance(level, str) else level
        mpl_logger.setLevel(lvl)

        # Add handler if none exists
        if not mpl_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
            mpl_logger.addHandler(handler)

        self.logger.info("Matplotlib internal logging enabled")

    def diagnose_performance(self):
        """Run performance diagnostics"""
        self.logger.info("=== Performance Diagnostics ===")

        # Check artist count
        artists = self.ax.get_children()
        self.logger.info(f"Artist count: {len(artists)}")

        # Count by type
        artist_types = {}
        for artist in artists:
            atype = type(artist).__name__
            artist_types[atype] = artist_types.get(atype, 0) + 1

        for atype, count in sorted(artist_types.items(), key=lambda x: -x[1]):
            self.logger.info(f"  {atype}: {count}")

        # Check if using blitting (fast redraw)
        backend = matplotlib.get_backend()
        supports_blit = 'Agg' in backend or 'TkAgg' in backend
        self.logger.info(f"Backend supports blitting: {supports_blit}")

        # Memory usage (approximate)
        try:
            import sys
            fig_size = sys.getsizeof(self.fig)
            self.logger.info(f"Figure memory (approx): {fig_size / 1024:.1f} KB")
        except:
            pass

    def suggest_optimizations(self):
        """Suggest performance optimizations"""
        suggestions = []

        fps = self.get_fps()
        if fps < 30:
            suggestions.append("FPS is low (<30). Consider:")
            suggestions.append("  - Reduce number of artists (plot fewer points/lines)")
            suggestions.append("  - Increase update interval")
            suggestions.append("  - Use simpler markers or no markers")
            suggestions.append("  - Disable anti-aliasing (set antialiased=False)")

        artists = self.ax.get_children()
        if len(artists) > 100:
            suggestions.append(f"High artist count ({len(artists)}). Consider:")
            suggestions.append("  - Combine multiple scatter/plot calls into one")
            suggestions.append("  - Use LineCollection or PathCollection for bulk data")

        if suggestions:
            self.logger.warning("=== Optimization Suggestions ===")
            for s in suggestions:
                self.logger.warning(s)
        else:
            self.logger.info("Performance looks good!")

        return suggestions


# Convenience function
def create_debugger(fig, ax, logger=None, show_overlay=True):
    """
    Create a matplotlib debugger with sensible defaults

    Args:
        fig: matplotlib Figure
        ax: matplotlib Axes
        logger: logging.Logger (optional)
        show_overlay: Show FPS overlay on figure

    Returns:
        MatplotlibDebugger instance
    """
    debugger = MatplotlibDebugger(fig, ax, logger=logger)

    if show_overlay:
        # Hook into draw to update overlay
        original_draw = fig.canvas.draw

        def debug_draw():
            debugger.start_render()
            original_draw()
            debugger.end_render()
            debugger.create_debug_overlay()

        fig.canvas.draw = debug_draw

    return debugger


# ─────────────────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import numpy as np

    # Setup logging using unified logger
    get_logger("viz_debug_test", console_output=True)

    # Create simple 3D plot
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Create debugger
    debugger = create_debugger(fig, ax, show_overlay=True)

    # Plot some data
    t = np.linspace(0, 10, 100)
    x = np.sin(t)
    y = np.cos(t)
    z = t
    ax.plot(x, y, z)

    debugger.logger.info("Test plot created. Interact with the plot to see debug info.")
    debugger.diagnose_performance()
    debugger.suggest_optimizations()

    plt.show()
