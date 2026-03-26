Here are **external-only** ways to debug/monitor Tkinter apps without touching source code:

## **1. Window & X11 Inspection**

### **Find Tkinter Windows**
```bash
# List all windows with titles
wmctrl -l
xlsclients  # List client applications
xprop -root _NET_CLIENT_LIST  # Get window IDs

# Find specific Tkinter window
xwininfo -root -tree | grep -i tk  # Search for Tk windows
xwininfo -root -tree | grep -B2 -A2 "Your App Name"
```

### **Inspect Window Properties**
```bash
# Get window ID first
WID=$(xdotool search --name "Your App Title" | head -1)

# Or click on window to get ID
xwininfo  # Then click on your Tkinter window

# Now inspect it
xprop -id $WID  # All properties
xprop -id $WID WM_CLASS  # Window class
xprop -id $WID WM_NAME   # Window title
xprop -id $WID _NET_WM_PID  # Process ID
```

## **2. Process Monitoring**

### **Monitor Python/Tkinter Process**
```bash
# Find the Python process
ps aux | grep -E "(python|tkinter)" | grep -v grep
pstree -p | grep -A5 -B5 python

# Monitor system calls
sudo strace -p $(pidof python)  # System calls
sudo ltrace -p $(pidof python)  # Library calls

# Monitor file access
sudo strace -e trace=file -p $(pidof python)

# Monitor network (if app has network)
sudo strace -e trace=network -p $(pidof python)
```

## **3. GUI Event Monitoring**

### **X11 Event Spy**
```bash
# Monitor ALL X events (heavy!)
xev

# Monitor events for specific window
xev -id $WID

# Monitor specific event types
xev -event mouse  # Mouse events only
xev -event key  # Keyboard events only
```

### **Input Device Monitoring**
```bash
# See input devices
xinput list
xinput test <device-id>

# Monitor keyboard
sudo showkey -k  # Raw keyboard input
evtest  # Input device events

# Monitor mouse
xinput test-xi2 --root  # All pointer events
```

## **4. Performance & Resource Monitoring**

### **CPU/Memory**
```bash
# Real-time monitoring
htop
top -p $(pidof python)

# Memory details
pmap -x $(pidof python)
cat /proc/$(pidof python)/status | grep -E "(Vm|RSS)"

# GPU (if using OpenGL in Tkinter)
glxinfo | grep -i render
nvidia-smi  # If NVIDIA
```

### **X11 Performance**
```bash
# X server info
xdpyinfo
xrandr --verbose

# Check for errors
x11perf  # X11 performance tests
xrestop  # X resource usage
```

## **5. Screenshot & Recording**

### **Visual Debugging**
```bash
# Take screenshots
scrot -u  # Active window
scrot -s  # Select area
import -window $WID screenshot.png  # Specific window

# Record interactions
ffmpeg -f x11grab -i :0.0+$(xwininfo -id $WID | grep Absolute | awk '{print $4}') output.mp4

# Take periodic screenshots for debugging
watch -n 1 scrot -u -q 100 '%Y-%m-%d-%H:%M:%S.png'
```

## **6. Network & IPC Monitoring**

### **Inter-Process Communication**
```bash
# Check if Tkinter is using D-Bus
dbus-monitor

# Monitor Unix sockets
sudo lsof -U -p $(pidof python)

# Network connections
sudo netstat -tupn | grep python
sudo ss -tupn | grep python
```

## **7. Toolkit-Specific Inspection**

### **Tkinter-Specific**
```bash
# Check Tk version externally
strings /proc/$(pidof python)/exe | grep -i tk

# Monitor Tk library calls
sudo ltrace -p $(pidof python) 2>&1 | grep -E "(Tk|Tcl|tkinter)"

# Check linked libraries
ldd /proc/$(pidof python)/exe
cat /proc/$(pidof python)/maps | grep -i tk
```

## **8. Automation & Testing**

### **External Control**
```bash
# Send events to window
xdotool windowactivate $WID
xdotool mousemove --window $WID 100 100 click 1
xdotool key --window $WID Tab
xdotool type --window $WID "test"

# Get widget under mouse
xdotool getmouselocation --shell

# Simulate complex interactions
xdotool key Ctrl+s  # Save
xdotool key Alt+F4  # Close
```

## **9. Advanced Debugging Tools**

### **Install Useful Tools**
```bash
sudo apt update
sudo apt install:
  gdb          # GNU Debugger (attach to process)
  x11-apps     # X utilities
  x11vnc       # For remote viewing
  devilspie    # Window matching/rules
  terminator   # Multiple terminals for monitoring
```

### **GDB Debugging**
```bash
# Attach to running Python process
sudo gdb -p $(pidof python)

# In GDB:
(gdb) bt  # Backtrace
(gdb) info threads  # Threads
(gdb) py-bt  # If python extensions loaded
(gdb) continue  # Resume execution
```

## **10. Quick Monitoring Scripts**

### **Create Monitoring Script** (`monitor_tkinter.sh`):
```bash
#!/bin/bash
# Monitor Tkinter app externally

APP_NAME="Your App Name"
PID=$(pgrep -f "$APP_NAME")

if [ -z "$PID" ]; then
    echo "App not running"
    exit 1
fi

echo "=== Monitoring Tkinter App ==="
echo "PID: $PID"

# Open multiple terminals for monitoring
terminator \
    -e "watch -n 1 'ps -p $PID -o pid,ppid,pcpu,pmem,cmd'" \
    -e "watch -n 1 'cat /proc/$PID/status | grep -E \"(Vm|RSS)\"'" \
    -e "xev -id \$(xdotool search --pid $PID | head -1)" \
    -e "sudo strace -p $PID 2>&1 | head -50" &
```

### **Window Change Monitor** (`window_monitor.sh`):
```bash
#!/bin/bash
# Monitor window property changes
WID=$(xdotool search --name "Your App" | head -1)
while true; do
    GEOM=$(xwininfo -id $WID | grep geometry)
    echo "$(date): $GEOM"
    sleep 0.5
done
```

## **Common Debug Commands Cheatsheet**

```bash
# 1. Quick window info
alias tkdebug='xwininfo | grep -E "(Window id|Absolute|Width|Height)"'

# 2. Monitor events (simplified)
alias tkevents='xev -id $(xdotool getactivewindow)'

# 3. Take debugging screenshot
alias tkshot='import -window $(xdotool getactivewindow) tkdebug_$(date +%s).png'

# 4. Check if responsive
alias tkping='xdotool getactivewindow windowmap windowunmap'

# 5. Memory watch
watch -n 1 "ps aux | grep -E '(python|tkinter)' | grep -v grep"
```

## **Best External Tools for Tkinter:**

1. **`xwininfo`** - Window geometry, hierarchy
2. **`xprop`** - Window properties (title, class, hints)
3. **`xev`** - Event monitoring
4. **`xdotool`** - Automation & control
5. **`strace`/`ltrace`** - System/library calls
6. **`wmctrl`** - Window manager info
7. **`scrot`/`import`** - Screenshots

Just run your Tkinter app normally, then use these external tools to inspect, monitor, and debug without any code changes. The key is finding the window ID first with `xdotool search` or `xwininfo`, then using that ID with other tools.