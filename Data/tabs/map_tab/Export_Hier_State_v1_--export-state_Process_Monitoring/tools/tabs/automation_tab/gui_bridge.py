"""
GUI Bridge (Phase 2.8C - Advanced)

Connects AI Model (or any AI) to control the GUI for testing and training.

Architecture:
1. Screenshot capture → Send to AI Model
2. AI Model analyzes and decides action
3. Execute action via pyautogui
4. Record interaction for training data
5. Repeat until task complete

This creates training data for your own coder model!

Safety:
- User must approve each session
- Time limits enforced
- ESC key emergency stop
- Preview before any destructive action
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import json
import base64
import io
import time
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
import threading

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class GUIBridge:
    """
    Bridge between AI Model API and GUI automation

    Flow:
    1. Take screenshot
    2. Send to AI Model with task description
    3. AI Model returns action (click, type, etc.)
    4. Execute action
    5. Record for training
    """

    def __init__(self, session_name: str = "test_session", api_key: Optional[str] = None, variant_type: str = "gui_tester"):
        self.session_name = session_name
        self.session_dir = Path(__file__).parent / "sessions" / session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.variant_type = variant_type  # For type-aware scoring

        self.session_data = {
            'session_id': session_name,
            'started_at': datetime.now().isoformat(),
            'task': None,
            'steps': [],
            'status': 'initialized',
            'user_terminated': False,  # Track if user stopped it
            'failure_reason': None,  # Why it failed
            'quality_score': 0.0,  # 0-1: How good was this session?
            'quality_grade': 'F',  # Letter grade
            'component_scores': {},  # Individual metric scores
            'dangerous_actions': [],  # Track dangerous clicks
            'variant_type': variant_type,  # Store for later analysis
            'performance_metrics': {
                'tasks_completed': 0,
                'success_rate': 0.0,
                'novel_solutions': 0,
                'total_time_seconds': 0
            }
        }

        self.active = False
        self.paused = False  # For pause/resume control
        self.step_count = 0
        self.mid_session_instruction = None  # For user instructions during automation

        # Safety
        self.max_steps = 20  # Prevent infinite loops
        self.step_delay = 2.0  # Seconds between actions (slower for visibility)
        self.trust_level = 5  # Default high trust for AI Model API

        # Safety bounds system
        try:
            from safety_bounds import SafetyBounds, get_screen_dimensions
            width, height = get_screen_dimensions()
            self.safety = SafetyBounds(width, height)
        except ImportError:
            print("⚠️ Safety bounds not available - running without safety checks")
            self.safety = None

        # Quality scoring system
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from quality_scoring import calculate_session_quality
            self.quality_scorer = calculate_session_quality
        except ImportError:
            print("⚠️ Quality scoring not available - using fallback")
            self.quality_scorer = None

        # API client
        self.api_key = api_key
        self.client = None
        if api_key and ANTHROPIC_AVAILABLE:
            self.client = anthropic.Anthropic(api_key=api_key)

    def start_session(self, task_description: str):
        """Start a new automation session"""
        self.active = True
        self.session_data['task'] = task_description
        self.session_data['status'] = 'active'
        self.save_session()

    def stop_session(self, user_terminated=False, failure_reason=None):
        """Stop the session"""
        self.active = False

        if user_terminated:
            self.session_data['status'] = 'user_terminated'
            self.session_data['user_terminated'] = True
            self.session_data['failure_reason'] = failure_reason or "User stopped session early"
            self.session_data['quality_score'] = 0.0  # Failed session = 0 quality
        elif failure_reason:
            self.session_data['status'] = 'failed'
            self.session_data['failure_reason'] = failure_reason
            self.session_data['quality_score'] = 0.0
        else:
            self.session_data['status'] = 'completed'
            # Calculate quality score based on success
            self.session_data['quality_score'] = self._calculate_quality_score()

        self.session_data['completed_at'] = datetime.now().isoformat()
        self.save_session()

    def _calculate_quality_score(self):
        """Calculate type-aware quality score for this session"""
        if self.quality_scorer:
            # Use type-aware scoring
            user_feedback = {
                'user_terminated': self.session_data.get('user_terminated', False),
                'failure_reason': self.session_data.get('failure_reason')
            }

            try:
                metrics = self.quality_scorer(
                    self.session_data,
                    self.variant_type,
                    user_feedback
                )

                # Update session data with detailed scores
                self.session_data['quality_score'] = metrics.overall_score
                self.session_data['quality_grade'] = metrics.grade
                self.session_data['component_scores'] = metrics.component_scores
                self.session_data['quality_passed'] = metrics.passed

                return metrics.overall_score

            except Exception as e:
                print(f"⚠️ Quality scoring failed: {e}")
                # Fall through to fallback

        # Fallback: simple scoring
        if not self.session_data['steps']:
            return 0.0

        score = 0.0

        # Did it complete successfully?
        if self.session_data['status'] == 'completed':
            score += 0.5

        # Success rate of actions
        success_count = sum(1 for s in self.session_data['steps'] if s.get('success', False))
        if self.session_data['steps']:
            score += 0.3 * (success_count / len(self.session_data['steps']))

        # No dangerous actions?
        if not self.session_data.get('dangerous_actions'):
            score += 0.2

        return min(1.0, score)

    def save_session(self):
        """Save session data to disk"""
        session_file = self.session_dir / "session.json"
        with open(session_file, 'w') as f:
            json.dump(self.session_data, f, indent=2)

    def capture_screenshot(self) -> Optional[Image.Image]:
        """Capture current screen"""
        if not PYAUTOGUI_AVAILABLE or not PIL_AVAILABLE:
            return None

        try:
            screenshot = pyautogui.screenshot()
            return screenshot
        except Exception as e:
            print(f"Screenshot failed: {e}")
            return None

    def save_screenshot(self, screenshot: Image.Image, step_num: int) -> str:
        """Save screenshot to disk"""
        filename = f"step_{step_num:03d}_screenshot.png"
        filepath = self.session_dir / filename
        screenshot.save(filepath)
        return str(filepath)

    def image_to_base64(self, image: Image.Image) -> str:
        """Convert image to base64 for API"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str

    def get_claude_action(self, screenshot: Image.Image, task: str, context: str = "") -> Optional[str]:
        """
        Get action from AI Model API based on screenshot

        Args:
            screenshot: Current screen state
            task: Overall task description
            context: Additional context about current state

        Returns:
            Action string (e.g., "CLICK(300, 200)")
        """
        if not self.client:
            return None

        try:
            # Convert screenshot to base64
            img_base64 = self.image_to_base64(screenshot)

            # Build prompt
            prompt = f"""You are controlling a GUI. Complete this task: {task}

{f"Additional context: {context}" if context else ""}

Respond with EXACTLY ONE action command. NO explanations, NO descriptions, ONLY the command:

MOVE(x, y) - Move mouse to coordinates (no click)
CLICK(x, y) - Click at coordinates
TYPE("text") - Type text
KEY(key_name) - Press key
WAIT(seconds) - Wait
DONE - Task complete
FAIL("reason") - Cannot complete

CRITICAL: Your response MUST be ONLY one of these commands. Nothing else.
Example good responses:
- CLICK(500, 300)
- TYPE("hello")
- DONE

Example BAD responses (DO NOT DO THIS):
- "I can see the desktop. CLICK(500, 300)"  ❌
- "Let me click here: CLICK(500, 300)"  ❌

Step {self.step_count + 1}/{self.max_steps}. What is your SINGLE action command?"""

            # Call AI Model API
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",  # Latest model
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }]
            )

            # Extract action
            action_text = message.content[0].text.strip()
            return action_text

        except Exception as e:
            print(f"AI Model API error: {e}")
            return None

    def parse_action(self, action_text: str) -> Optional[Dict]:
        """
        Parse action from AI Model's response

        Expected formats:
        - CLICK(x, y) - Click at coordinates
        - TYPE("text") - Type text
        - KEY(key_name) - Press key
        - WAIT(seconds) - Wait
        - DONE - Task complete
        - FAIL(reason) - Task failed
        """
        action_text = action_text.strip()

        if action_text.startswith("CLICK("):
            # Extract coordinates
            coords = action_text[6:-1].split(",")
            if len(coords) == 2:
                try:
                    x, y = int(coords[0].strip()), int(coords[1].strip())
                    return {'type': 'click', 'x': x, 'y': y}
                except:
                    pass

        elif action_text.startswith("TYPE("):
            # Extract text
            text = action_text[5:-1].strip('"')
            return {'type': 'type', 'text': text}

        elif action_text.startswith("KEY("):
            # Extract key name
            key = action_text[4:-1].strip('"')
            return {'type': 'key', 'key': key}

        elif action_text.startswith("WAIT("):
            # Extract seconds
            try:
                seconds = float(action_text[5:-1])
                return {'type': 'wait', 'seconds': seconds}
            except:
                pass

        elif action_text == "DONE":
            return {'type': 'done'}

        elif action_text.startswith("FAIL("):
            reason = action_text[5:-1].strip('"')
            return {'type': 'fail', 'reason': reason}

        return None

    def execute_action(self, action: Dict) -> bool:
        """Execute an action with safety checks"""
        if not PYAUTOGUI_AVAILABLE:
            print("PyAutoGUI not available")
            return False

        # Safety check before execution
        if self.safety:
            is_safe, reason = self.safety.check_action_safety(
                action,
                self.trust_level,
                self.session_data.get('task', '')
            )

            if not is_safe:
                print(f"🛡️ BLOCKED: {reason}")
                # Log as dangerous action
                self.session_data['dangerous_actions'].append({
                    'action': action,
                    'reason': reason,
                    'step': self.step_count,
                    'timestamp': datetime.now().isoformat()
                })
                return False

            # Log warnings for caution-level actions
            if "⚠️" in reason:
                print(f"⚠️ WARNING: {reason}")

        try:
            action_type = action.get('type')

            if action_type == 'click':
                x, y = action['x'], action['y']
                pyautogui.click(x, y)
                print(f"✓ Clicked at ({x}, {y})")
                return True

            elif action_type == 'type':
                text = action['text']
                pyautogui.write(text, interval=0.05)
                print(f"✓ Typed: {text}")
                return True

            elif action_type == 'key':
                key = action['key']
                pyautogui.press(key)
                print(f"✓ Pressed key: {key}")
                return True

            elif action_type == 'wait':
                seconds = action['seconds']
                time.sleep(seconds)
                print(f"✓ Waited {seconds}s")
                return True

            elif action_type == 'done':
                print("✓ Task completed")
                return True

            elif action_type == 'fail':
                reason = action.get('reason', 'Unknown')
                print(f"✗ Failed: {reason}")
                return False

        except Exception as e:
            print(f"✗ Action failed: {e}")
            return False

        return False

    def record_step(self, screenshot_path: str, action: Dict, success: bool, notes: str = ""):
        """Record a step for training data"""
        step = {
            'step_number': self.step_count,
            'timestamp': datetime.now().isoformat(),
            'screenshot': screenshot_path,
            'action': action,
            'success': success,
            'notes': notes
        }

        self.session_data['steps'].append(step)
        self.save_session()

    def get_training_data(self) -> Dict:
        """
        Export session as training data

        Format suitable for fine-tuning:
        - Screenshots as context
        - Actions as labels
        - Natural language description
        """
        training_data = {
            'task_description': self.session_data['task'],
            'success': self.session_data['status'] == 'completed',
            'steps': []
        }

        for step in self.session_data['steps']:
            training_step = {
                'image': step['screenshot'],
                'action': step['action'],
                'description': self._action_to_natural_language(step['action'])
            }
            training_data['steps'].append(training_step)

        return training_data

    def _action_to_natural_language(self, action: Dict) -> str:
        """Convert action to natural language for training"""
        action_type = action.get('type')

        if action_type == 'click':
            return f"Click at position ({action['x']}, {action['y']})"

        elif action_type == 'type':
            return f"Type the text: {action['text']}"

        elif action_type == 'key':
            return f"Press the {action['key']} key"

        elif action_type == 'wait':
            return f"Wait for {action['seconds']} seconds"

        elif action_type == 'done':
            return "Task completed successfully"

        elif action_type == 'fail':
            return f"Task failed: {action.get('reason', 'Unknown')}"

        return "Unknown action"

    def run_live_session(self, callback=None):
        """
        Run a live session with AI Model controlling the GUI

        Args:
            callback: Function to call with status updates
        """
        start_time = time.time()

        for step in range(self.max_steps):
            if not self.active:
                break

            # Check for pause
            while self.paused and self.active:
                time.sleep(0.5)  # Wait while paused

            if not self.active:  # Might have stopped during pause
                break

            self.step_count = step

            # Check for mid-session instruction
            additional_context = ""
            if self.mid_session_instruction:
                additional_context = f"\n\nUSER INSTRUCTION: {self.mid_session_instruction}"
                self.mid_session_instruction = None  # Clear after reading

            # Update status
            if callback:
                callback(f"Step {step + 1}/{self.max_steps}: Taking screenshot...")

            # Capture screenshot
            screenshot = self.capture_screenshot()
            if not screenshot:
                if callback:
                    callback("❌ Failed to capture screenshot")
                break

            # Save screenshot
            screenshot_path = self.save_screenshot(screenshot, step)

            # Get action from AI Model
            if callback:
                callback(f"🤖 AI Model is analyzing...")

            action_text = self.get_claude_action(
                screenshot,
                self.session_data['task'],
                context=f"Step {step + 1} of task{additional_context}"
            )

            if not action_text:
                if callback:
                    callback("❌ Failed to get action from AI Model")
                break

            if callback:
                callback(f"AI Model decided: {action_text}")

            # Parse action
            action = self.parse_action(action_text)
            if not action:
                if callback:
                    callback(f"⚠️ Could not parse action: {action_text}")
                continue

            # Check if done or failed
            if action['type'] == 'done':
                if callback:
                    callback("✅ Task completed!")
                self.session_data['performance_metrics']['tasks_completed'] += 1
                break

            if action['type'] == 'fail':
                reason = action.get('reason', 'Unknown')
                if callback:
                    callback(f"❌ Task failed: {reason}")
                break

            # Execute action
            if callback:
                callback(f"Executing: {self._action_to_natural_language(action)}")

            success = self.execute_action(action)

            # Record step
            self.record_step(screenshot_path, action, success)

            if not success:
                if callback:
                    callback(f"⚠️ Action failed")

            # Delay before next action
            time.sleep(self.step_delay)

        # Calculate metrics
        elapsed = time.time() - start_time
        self.session_data['performance_metrics']['total_time_seconds'] = elapsed

        if self.step_count > 0:
            success_count = sum(1 for s in self.session_data['steps'] if s['success'])
            self.session_data['performance_metrics']['success_rate'] = success_count / self.step_count

        self.stop_session()

        if callback:
            callback(f"\n📊 Session complete!")
            callback(f"Steps: {self.step_count}")
            callback(f"Time: {elapsed:.1f}s")
            callback(f"Success rate: {self.session_data['performance_metrics']['success_rate']:.1%}")


class GUIBridgeUI(tk.Toplevel):
    """
    UI for controlling AI Model-powered GUI automation

    This is where you connect me to test your GUI!
    """

    def __init__(self, parent=None):
        if parent:
            super().__init__(parent)
        else:
            self.root = tk.Tk()
            self.root.withdraw()
            tk.Toplevel.__init__(self, self.root)

        self.title("🤖 GUI Bridge - AI GUI Control")
        self.geometry("800x700")
        self.configure(bg='#1a1a1a')

        self.bridge: Optional[GUIBridge] = None
        self.control_panel = None  # Emergency control panel
        self.running = False

        self.create_ui()

    def create_ui(self):
        """Create the GUI Bridge UI"""

        # Header
        header = tk.Frame(self, bg='#0066cc', height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🤖 CLAUDE BRIDGE",
            font=("Arial", 16, "bold"),
            bg='#0066cc',
            fg='white'
        ).pack(side=tk.LEFT, padx=20)

        tk.Label(
            header,
            text="Connect AI Model to control your GUI",
            font=("Arial", 10),
            bg='#0066cc',
            fg='white'
        ).pack(side=tk.LEFT)

        # Main content
        content = tk.Frame(self, bg='#1a1a1a')
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Task input
        task_frame = tk.LabelFrame(
            content,
            text="📋 Task Description",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 10, "bold"),
            padx=15,
            pady=15
        )
        task_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            task_frame,
            text="What should AI Model do?",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 10)
        ).pack(anchor=tk.W, pady=(0, 5))

        self.task_text = tk.Text(
            task_frame,
            height=4,
            bg='#0a0a0a',
            fg='white',
            font=("Arial", 10),
            insertbackground='white'
        )
        self.task_text.pack(fill=tk.X)
        self.task_text.insert(1.0, "Example: Navigate to Models tab, select a model, and open the chat interface")

        # Connection method
        method_frame = tk.LabelFrame(
            content,
            text="🔌 Connection Method",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 10, "bold"),
            padx=15,
            pady=15
        )
        method_frame.pack(fill=tk.X, pady=(0, 15))

        self.method_var = tk.StringVar(value="simulation")

        tk.Radiobutton(
            method_frame,
            text="Simulation Mode (No actual API calls)",
            variable=self.method_var,
            value="simulation",
            bg='#2d2d2d',
            fg='white',
            selectcolor='#1a1a1a',
            font=("Arial", 10)
        ).pack(anchor=tk.W)

        tk.Radiobutton(
            method_frame,
            text="AI Model API (Requires API key)",
            variable=self.method_var,
            value="api",
            bg='#2d2d2d',
            fg='white',
            selectcolor='#1a1a1a',
            font=("Arial", 10)
        ).pack(anchor=tk.W)

        tk.Radiobutton(
            method_frame,
            text="Local Model (Through custom_code_tab chat)",
            variable=self.method_var,
            value="local",
            bg='#2d2d2d',
            fg='white',
            selectcolor='#1a1a1a',
            font=("Arial", 10)
        ).pack(anchor=tk.W)

        # API key entry (shows when API selected)
        self.api_frame = tk.Frame(method_frame, bg='#2d2d2d')
        self.api_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(
            self.api_frame,
            text="API Key:",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 9)
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.api_key_entry = tk.Entry(
            self.api_frame,
            show="*",
            bg='#0a0a0a',
            fg='white',
            font=("Arial", 9),
            width=40
        )
        self.api_key_entry.pack(side=tk.LEFT)

        # Action log
        log_frame = tk.LabelFrame(
            content,
            text="📝 Action Log",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 10, "bold"),
            padx=15,
            pady=15
        )
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            bg='#0a0a0a',
            fg='#00ff00',
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

        # Control buttons
        button_frame = tk.Frame(content, bg='#1a1a1a')
        button_frame.pack(fill=tk.X)

        self.start_btn = tk.Button(
            button_frame,
            text="🚀 Start Session",
            command=self.start_session,
            bg='#0066cc',
            fg='white',
            font=("Arial", 11, "bold"),
            height=2,
            cursor='hand2'
        )
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.stop_btn = tk.Button(
            button_frame,
            text="⏹️ Stop",
            command=self.stop_session,
            bg='#cc0000',
            fg='white',
            font=("Arial", 11, "bold"),
            height=2,
            cursor='hand2',
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        tk.Button(
            button_frame,
            text="💾 Export Training Data",
            command=self.export_training_data,
            bg='#228822',
            fg='white',
            font=("Arial", 11),
            height=2,
            cursor='hand2'
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Welcome message
        self.log("🤖 GUI Bridge initialized")
        self.log("⚠️ This is EXPERIMENTAL - use in development version only!")
        self.log("")
        self.log("How it works:")
        self.log("1. Enter what you want AI Model to do")
        self.log("2. Click Start Session")
        self.log("3. AI Model sees your screen and controls the mouse/keyboard")
        self.log("4. All actions are recorded as training data")
        self.log("5. Use training data to train your own coder!")
        self.log("")
        self.log("Safety: Press ESC anytime to stop")

    def log(self, message: str):
        """Add message to log"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def start_session(self):
        """Start automation session"""
        task = self.task_text.get("1.0", tk.END).strip()
        if not task:
            messagebox.showwarning("No Task", "Please enter a task description")
            return

        method = self.method_var.get()

        # Safety confirmation
        response = messagebox.askyesno(
            "Start Session",
            f"Start automation session?\n\n"
            f"Task: {task}\n"
            f"Method: {method}\n\n"
            f"AI Model will control your mouse and keyboard.\n"
            f"Press ESC to stop anytime.\n\n"
            f"Continue?"
        )

        if not response:
            return

        # Create bridge
        session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Get API key if API mode
        api_key = None
        if method == "api":
            api_key = self.api_key_entry.get().strip()

            # Try environment variable if no key entered
            if not api_key:
                import os
                api_key = os.environ.get('ANTHROPIC_API_KEY')

            if not api_key:
                messagebox.showwarning(
                    "No API Key",
                    "Please enter an API key or set ANTHROPIC_API_KEY environment variable"
                )
                return

        self.bridge = GUIBridge(session_name, api_key=api_key)
        self.bridge.start_session(task)

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        # Create emergency control panel
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent))
            from emergency_controls import EmergencyControlPanel

            # Determine agent name and trust level
            agent_name = "AI Model Sonnet 4" if method == "api" else "Local Model"
            trust_level = 5 if method == "api" else 1  # Trust AI Model fully, others minimally

            self.log("🛡️ Initializing emergency control panel...")
            self.control_panel = EmergencyControlPanel(self, agent_name, trust_level)

            # Wire up callbacks
            self.control_panel.on_pause = self.handle_pause
            self.control_panel.on_stop = self.handle_emergency_stop
            self.control_panel.on_instruction = self.handle_mid_session_instruction

            # Update control panel status
            self.control_panel.update_status("🟢 RUNNING", '#00ff00')
            self.control_panel.log_chat("AGENT", f"Starting task: {task[:50]}...")

            self.log("✅ Emergency control panel active!")

        except ImportError as e:
            self.log(f"⚠️ Emergency controls not available (import error): {e}")
        except Exception as e:
            self.log(f"❌ Emergency control panel failed to start: {type(e).__name__}: {e}")
            import traceback
            self.log(traceback.format_exc())

        self.log("")
        self.log(f"▶️ Session started: {session_name}")
        self.log(f"📋 Task: {task}")
        self.log(f"🔌 Method: {method}")
        self.log("")

        if method == "simulation":
            self.log("⚠️ Simulation mode - no actual actions will be performed")
            self.run_simulation()
        elif method == "api":
            self.log("🚀 LIVE API MODE - AI Model is taking control!")
            self.log("Press ESC to stop immediately")
            self.log("🛡️ Emergency control panel is active (top-right)")
            self.log("")
            # Run in thread so UI doesn't freeze
            thread = threading.Thread(target=self.run_live_api)
            thread.daemon = True
            thread.start()
        else:
            self.log("❌ Local model mode not yet implemented")
            self.stop_session()

    def run_simulation(self):
        """Run a simulated session"""
        self.log("🎬 Running simulation...")
        self.log("")

        # Simulate some actions
        simulated_actions = [
            "Taking screenshot of current screen...",
            "AI Model: I can see the application window",
            "AI Model: I'll click on the Models tab",
            "CLICK(150, 50) - Clicking Models tab",
            "✓ Action executed successfully",
            "",
            "Taking screenshot...",
            "AI Model: I can see the Models tab is now open",
            "AI Model: I'll select the first model in the list",
            "CLICK(300, 200) - Clicking first model",
            "✓ Action executed successfully",
            "",
            "Taking screenshot...",
            "AI Model: The model is now selected",
            "AI Model: Task completed successfully",
            "DONE",
            "",
            "✅ Session completed!",
            f"📊 Recorded 3 steps for training data",
            f"📁 Session saved to: {self.bridge.session_dir if self.bridge else 'unknown'}"
        ]

        def simulate_step(index=0):
            if not self.running or index >= len(simulated_actions):
                if self.running:
                    self.stop_session()
                return

            self.log(simulated_actions[index])
            self.after(800, lambda: simulate_step(index + 1))

        simulate_step()

    def run_live_api(self):
        """Run LIVE API session with AI Model"""
        try:
            # Run session with callback for UI updates
            def callback_wrapper(msg):
                """Forward to both log and control panel"""
                self.log(msg)
                if self.control_panel and "AI Model decided:" in msg:
                    # Extract action from message
                    action = msg.split("AI Model decided:")[-1].strip()
                    self.control_panel.log_chat("AGENT", action)
                elif self.control_panel and "✅" in msg:
                    self.control_panel.log_chat("AGENT", msg)

            self.bridge.run_live_session(callback=callback_wrapper)
        except Exception as e:
            self.log(f"❌ Session error: {e}")
            if self.control_panel:
                self.control_panel.log_chat("SYSTEM", f"Error: {str(e)[:50]}")
        finally:
            self.after(0, self.stop_session)  # Update UI from main thread

    def handle_pause(self, paused: bool):
        """Handle pause/resume from emergency controls"""
        if self.bridge:
            self.bridge.paused = paused
            if paused:
                self.log("⏸️ Session PAUSED by user")
            else:
                self.log("▶️ Session RESUMED")

    def handle_emergency_stop(self):
        """Handle emergency stop from control panel"""
        self.log("🛑 EMERGENCY STOP activated!")
        if self.bridge:
            self.bridge.active = False
            self.bridge.stop_session(user_terminated=True, failure_reason="User emergency stop - clicked dangerous things or behaving incorrectly")
        self.stop_session()

    def handle_mid_session_instruction(self, instruction: str):
        """Handle mid-session instruction from user"""
        self.log(f"📝 User instruction: {instruction}")
        if self.bridge:
            self.bridge.mid_session_instruction = instruction
            if self.control_panel:
                self.control_panel.log_chat("SYSTEM", "Instruction forwarded to agent")

    def stop_session(self):
        """Stop automation session"""
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

        if self.bridge:
            self.bridge.stop_session()
            self.log("")
            self.log("⏹️ Session stopped")

        # Close control panel
        if self.control_panel:
            try:
                self.control_panel.destroy()
            except:
                pass
            self.control_panel = None

    def export_training_data(self):
        """Export session as training data"""
        if not self.bridge:
            messagebox.showwarning("No Session", "No session to export")
            return

        training_data = self.bridge.get_training_data()
        export_file = self.bridge.session_dir / "training_data.json"

        with open(export_file, 'w') as f:
            json.dump(training_data, f, indent=2)

        self.log("")
        self.log(f"💾 Training data exported to: {export_file}")
        messagebox.showinfo("Exported", f"Training data saved:\n{export_file}")


# Testing
if __name__ == "__main__":
    print("Starting GUI Bridge UI...")
    ui = GUIBridgeUI()
    ui.mainloop()
