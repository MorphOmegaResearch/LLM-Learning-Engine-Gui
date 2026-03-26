# Debug Guide - Process Monitoring & Brain Visualization

## Overview
The Process Monitoring suite now includes comprehensive debugging capabilities for matplotlib-based visualizations.

## Matplotlib Debug Features

### 1. **Performance Monitoring**
- **FPS Tracking**: Real-time frames per second measurement
- **Render Timing**: Min/Max/Average render times
- **Artist Count**: Number of plot elements being rendered
- **Memory Usage**: Approximate figure memory consumption

### 2. **Event Logging**
All matplotlib events are captured and logged:
- Mouse clicks (button_press_event, button_release_event)
- Mouse movement (motion_notify_event)
- Scroll/zoom (scroll_event)
- Node picking (pick_event)
- Keyboard (key_press_event, key_release_event)

### 3. **Visual Debug Overlay**
Shows on-screen in real-time:
- Current FPS
- Draw count
- Camera elevation/azimuth (3D views)

### 4. **Performance Diagnostics**
Run `diagnose_performance()` to get:
- Total artist count breakdown by type
- Backend capabilities (blitting support)
- Memory usage estimates
- Performance bottleneck identification

### 5. **Optimization Suggestions**
Automatically suggests:
- Reducing artist count if too high (>100)
- Increasing update interval if FPS is low (<30)
- Using bulk rendering (LineCollection, PathCollection)
- Disabling anti-aliasing

## Configuration

### Enable Debug Mode

**Option 1: Config File** (Recommended)
Edit `monitor_config.json`:
```json
{
    "user_prefs": {
        "brain_map": {
            "enable_debug": true,
            "show_fps_overlay": true
        }
    }
}
```

**Option 2: Command Line**
When testing standalone:
```bash
python3 process_brain_viz.py  # Debug enabled by default in test mode
```

**Option 3: Programmatic**
```python
viz = ProcessBrainVisualization(parent, get_category, enable_debug=True)
```

## Using Debug Features

### In GUI (secure_view.py)

1. **Enable via config** (see above)
2. Launch secure_view: `python3 secure_view.py`
3. Navigate to "Brain Map" tab
4. You'll see:
   - **"Debug Overlay" checkbox**: Toggle FPS overlay
   - **"Diagnose" button**: Run full diagnostics

### Debug Overlay Display

When enabled, top-left corner shows:
```
FPS: 45.2
Draws: 1234
Elev: 20.0°
Azim: 45.0°
```

### Running Diagnostics

Click "Diagnose" button or check console logs every 60 frames:
```
2026-01-26 22:15:30 - brain_viz - INFO - Render Performance: FPS=48.3, Avg=20.7ms, Min=18.2ms, Max=45.1ms
2026-01-26 22:15:30 - brain_viz - INFO - === Performance Diagnostics ===
2026-01-26 22:15:30 - brain_viz - INFO - Artist count: 127
2026-01-26 22:15:30 - brain_viz - INFO -   Line3D: 45
2026-01-26 22:15:30 - brain_viz - INFO -   Path3DCollection: 82
2026-01-26 22:15:30 - brain_viz - INFO - Backend supports blitting: True
```

### Log Files

Debug logs are written to:
- `logs/gui_YYYYMMDD_HHMMSS.log` - Main GUI log with brain map events
- `logs/brain_viz_YYYYMMDD_HHMMSS.log` - Dedicated brain visualization log (if separate logger created)

## Interpreting Performance Metrics

### FPS (Frames Per Second)
- **60+ FPS**: Excellent, smooth
- **30-60 FPS**: Good, acceptable
- **15-30 FPS**: Sluggish, consider optimization
- **<15 FPS**: Poor, needs optimization

### Artist Count
- **<50**: Very light, good performance
- **50-100**: Moderate, acceptable
- **100-200**: Heavy, may slow down
- **>200**: Very heavy, likely to lag

### Common Bottlenecks

1. **Too many artists**
   - Solution: Combine multiple plot calls into one
   - Use `ax.scatter()` once instead of multiple calls
   - Use collections (LineCollection, PathCollection)

2. **High update frequency**
   - Solution: Increase `update_interval_ms` in config
   - Default: 2000ms (2 seconds)
   - Recommended range: 1000-5000ms

3. **Complex rendering**
   - Solution: Disable anti-aliasing: `antialiased=False`
   - Reduce marker sizes
   - Hide edges when not needed

## Matplotlib Backend Information

The debugger automatically logs backend info:
```
Matplotlib Backend: TkAgg
Matplotlib Version: 3.5.1
Interactive Mode: True
3D Projection: True
```

### Supported Backends
- **TkAgg**: Best for Tkinter integration (our use case)
- **Qt5Agg**: Alternative for Qt applications
- **Agg**: Non-interactive, for saving figures

## Advanced Debugging

### Enable Matplotlib Internal Logging

```python
debugger.enable_matplotlib_logging(level=logging.DEBUG)
```

This enables matplotlib's own internal debug output for deep troubleshooting.

### Event Log Inspection

```python
# Get last 10 pick events
pick_events = debugger.get_recent_events('pick_event', limit=10)

# Get all recent events
all_events = debugger.get_recent_events(limit=50)
```

### Manual Performance Check

```python
# Get current FPS
fps = debugger.get_fps()

# Log axes state
debugger.log_axes_state()

# Log 3D view state
debugger.log_view_state()
```

## Troubleshooting

### Debug Overlay Not Showing
1. Check `show_debug` is True
2. Verify debugger is initialized: `self.debugger is not None`
3. Check logs for "Brain visualization debugger enabled"

### Low FPS / Lag
1. Click "Diagnose" to identify bottleneck
2. Check artist count (aim for <100)
3. Increase update interval
4. Disable unused features (edges, labels)

### Events Not Logging
1. Check `enable_events=True` in debugger init
2. Check log level is DEBUG or INFO
3. Verify log file is being written to

### Memory Issues
1. Run diagnostics to check figure memory
2. Reduce number of nodes/edges displayed
3. Clear old data periodically

## Example: Full Debug Session

```python
# 1. Create visualization with debug
viz = ProcessBrainVisualization(root, get_category, enable_debug=True)

# 2. Enable overlay
viz.show_debug.set(True)

# 3. Run diagnostics
viz.run_diagnostics()

# 4. Check logs
# logs/gui_*.log will contain:
#   - FPS every 60 frames
#   - Artist count
#   - Performance suggestions
#   - Event log (clicks, picks, drags)
```

## Performance Optimization Checklist

- [ ] FPS > 30
- [ ] Artist count < 100
- [ ] Update interval appropriate (2000ms+)
- [ ] No memory leaks (constant memory usage)
- [ ] Events respond quickly (<100ms)
- [ ] No console errors or warnings

## Getting Help

If you encounter issues:
1. Enable debug mode
2. Run diagnostics
3. Check latest log file in `logs/`
4. Look for ERROR or WARNING messages
5. Check performance metrics (FPS, artist count)
6. Review optimization suggestions

---

**Last Updated**: 2026-01-26
**Version**: 1.0
**Author**: Process Monitoring Development Team
