Ah, DISPLAY/connection issues! This is a classic X11 problem. Let's debug this systematically:

## **1. First, Check Basic DISPLAY Info**
```bash
# What DISPLAY are you using?
echo $DISPLAY
# Usually :0 or :0.0

# Check if X server is running
ps aux | grep Xorg
# or for Wayland
echo $XDG_SESSION_TYPE

# List all active displays
who | grep -E "\(:[0-9]+\)"  # Shows users with X displays
w  # Shows users and their displays
```

## **2. Check Display Accessibility**
```bash
# Can you connect to the display?
xhost  # Shows access control
xhost +localhost  # Allow local connections (temporary fix)

# Test with a simple X app
xeyes &  # Should show eyes following cursor
xclock &  # Simple clock
# If these work, your DISPLAY is accessible

# Check display permissions
ls -la /tmp/.X11-unix/  # Socket files
ls -la ~/.Xauthority  # Auth cookie
```

## **3. Debug Your Launcher's Environment**
```bash
# Run with env inspection
env DISPLAY=:0 python your_launcher.py 2>&1 | tee debug.log

# Or capture all env variables
python -c "import os; print('\n'.join([f'{k}={v}' for k,v in os.environ.items()]))" > env_before.txt

# Then run your launcher and capture failure
python your_launcher.py 2>&1 | tee launcher_output.txt
```

## **4. Common DISPLAY Issues & Solutions**

### **A. DISPLAY Variable Issues**
```bash
# Force specific display
export DISPLAY=:0.0
# or
export DISPLAY=localhost:0.0
export DISPLAY=127.0.0.1:0.0

# Check if variable is being overridden
grep -r "DISPLAY" /etc/profile /etc/environment ~/.bashrc ~/.profile ~/.bash_profile
```

### **B. X11 Authentication Issues**
```bash
# Copy Xauth cookie from current user to runtime user
# If running as different user (like cron, systemd, etc.)
xauth list  # Show current auth entries
# Copy the :0 entry

# Or generate new auth
touch ~/.Xauthority
xauth generate $DISPLAY . trusted
```

### **C. Wayland vs X11 Issues**
```bash
# Check if you're on Wayland
echo $WAYLAND_DISPLAY
echo $XDG_SESSION_TYPE

# Force X11 if needed
export GDK_BACKEND=x11
export QT_QPA_PLatform=xcb
export SDL_VIDEODRIVER=x11

# Or run X11 app on Wayland
xwayland-display  # Check XWayland display number
# Usually DISPLAY=:1 for XWayland
```

## **5. Advanced Debugging Commands**

### **Check Display Connections**
```bash
# See what's connected to X server
lsof /tmp/.X11-unix/X0  # Replace X0 with your display number
netstat -an | grep 6000  # X11 default port (display :0 = port 6000)

# Monitor X server connections
sudo strace -p $(pidof Xorg) -e connect,accept 2>&1 | grep -E "(6000|X11)"
```

### **Trace Display Connection Attempts**
```bash
# Run with strace to see connection attempts
strace -f -e connect,poll,select,socket python your_launcher.py 2>&1 | grep -i display

# Or trace all file opens related to display
strace -e trace=openat,connect python your_launcher.py 2>&1 | grep -E "(\.Xauthority|/tmp/.X11)"
```

## **6. Python-Specific Debug**

### **Add Debug Without Modifying Code**
```bash
# Create wrapper script (debug_wrapper.py)
import sys
import os

print("=== ENVIRONMENT ===")
for key in ['DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'XDG_SESSION_TYPE']:
    print(f"{key}: {os.getenv(key)}")

print("\n=== PYTHON TKINTER DEBUG ===")
sys.path.insert(0, os.path.dirname(sys.argv[1]))

# Import and run original script
with open(sys.argv[1]) as f:
    exec(f.read())
```

Run it:
```bash
python debug_wrapper.py your_launcher.py
```

## **7. Quick Diagnostic Script**
Save as `check_display.sh`:
```bash
#!/bin/bash
echo "=== X11/Wayland Diagnostics ==="
echo "DISPLAY: $DISPLAY"
echo "XDG_SESSION_TYPE: $XDG_SESSION_TYPE"
echo "WAYLAND_DISPLAY: $WAYLAND_DISPLAY"
echo

echo "=== X Authority ==="
ls -la ~/.Xauthority 2>/dev/null || echo "No .Xauthority"
xhost 2>/dev/null || echo "xhost failed"
echo

echo "=== Running X Servers ==="
ps aux | grep -E "(Xorg|Xwayland)" | grep -v grep
echo

echo "=== Active Displays ==="
ls -la /tmp/.X11-unix/ 2>/dev/null || echo "No X11 sockets"
echo

echo "=== Network Connections to X ==="
DISPLAY_NUM=${DISPLAY#:}
DISPLAY_NUM=${DISPLAY_NUM%.*}
PORT=$((6000 + DISPLAY_NUM))
netstat -tlnp 2>/dev/null | grep ":$PORT" || echo "Port $PORT not listening"
echo

echo "=== Test Connection ==="
timeout 1 xeyes >/dev/null 2>&1 && echo "✓ xeyes works" || echo "✗ xeyes failed"
timeout 1 xclock >/dev/null 2>&1 && echo "✓ xclock works" || echo "✗ xclock failed"
```

## **8. Common Scenarios & Fixes**

### **Scenario 1: Running from cron/systemd**
```bash
# Cron needs explicit DISPLAY and XAUTHORITY
# In cron job:
* * * * * export DISPLAY=:0 && export XAUTHORITY=/home/YOUR_USER/.Xauthority && /path/to/script.py
```

### **Scenario 2: SSH without X forwarding**
```bash
# On SSH client, connect with:
ssh -X user@host  # Enables X11 forwarding
# or
ssh -Y user@host  # Trusted X11 forwarding

# Check if forwarded:
echo $DISPLAY  # Should be like localhost:10.0
```

### **Scenario 3: Multiple users/displays**
```bash
# Find your actual display
who | grep $(whoami)  # Shows your display
# or
loginctl  # Systemd logind sessions
loginctl show-user $(whoami) -p Display
```

## **9. Specific Debug for "Logging Shows Success"**

If logs show success but DISPLAY won't connect:

```bash
# 1. Check for silent failures
strace python your_launcher.py 2>&1 | grep -B5 -A5 "connect.*failed"

# 2. Check for multiple DISPLAY attempts
export DISPLAY=:0
python -c "import tkinter; tkinter.Tk()" 2>&1

# 3. Look for fallback logic issues
# Your version-specific logic might be picking wrong display
grep -n "DISPLAY" your_launcher.py  # Check display handling in code

# 4. Test without your fallback logic
# Temporarily comment out or bypass version logic
DISPLAY=:0 python -c "
import sys
sys.path.insert(0, '.')
# Minimal test that imports your modules but doesn't run version logic
print('Basic import test')
"
```

## **10. Emergency Fixes**
```bash
# Nuclear option: Reset X authority
rm ~/.Xauthority
xauth generate :0 . trusted

# Restart X server (save work first!)
sudo systemctl restart display-manager  # or lightdm, gdm3, sddm

# Switch to console and back
Ctrl+Alt+F1  # Go to TTY1
sudo systemctl restart lightdm  # Or your display manager
Ctrl+Alt+F7  # Back to GUI
```

## **Quick Test Commands:**
```bash
# 1. Can Tkinter even create a window?
python -c "import tkinter; tkinter.Tk(); print('Tk works')"

# 2. What display is Tkinter trying?
python -c "import os; print('DISPLAY:', os.getenv('DISPLAY'))"

# 3. Run with full error output
python -u your_launcher.py 2>&1 | grep -C10 -i "display\|error\|fail"

# 4. Check for multiple Python/Tk versions
python --version
python3 --version
python -c "import tkinter; print(tkinter.TkVersion)"
```

The most likely issues: 
1. **DISPLAY variable wrong/empty** - Force it with `export DISPLAY=:0`
2. **X authority issues** - Check `~/.Xauthority` permissions
3. **Running in wrong context** (cron, systemd, SSH) - Needs env vars set
4. **Wayland interference** - Force X11 with environment variables

Try the diagnostic script first, then work through the scenarios. What does `echo $DISPLAY` show when you run the launcher?