# Auto-Onboarding Concept: Parse --help → Generate Profiles

## Vision

Your panel system could automatically discover tools and generate profile entries by parsing `--help` output.

## Example: scope_flow.py Discovery

### Step 1: Detect New Tool

System scans `variants/` directory:
```bash
find ./scope/variants -name "*.py" -type f
# Found: scope_flow.py
```

### Step 2: Parse --help Output

```bash
python3 scope_flow.py --help
```

**Output:**
```
usage: scope_flow.py [-h] [--analyze] [--workflow {full_analysis,quick_fix,tkinter_only}]
                     [--auto] [--turnbased] [--interactive] [--gui-review]
                     [--organization] [--auto-fix] [--file FILE] [--dir DIR]
                     [--depth DEPTH] [--backup]

Enhanced Tkinter Inspector with Analysis Workflows

options:
  --analyze             Run progressive analysis on file
  --workflow TYPE       Run specific workflow
  --gui-review          Open live GUI review
  --organization        Generate organization schema
  --auto-fix            Auto-fix all detectable issues
  --file FILE           File to analyze/fix
  --dir DIR             Directory for schema analysis
  --depth DEPTH         Analysis depth (1-4, default: 3)
  --backup              Create backup before auto-fix
```

### Step 3: Extract Structured Data

Parse with regex patterns:

```python
import re
import subprocess

def parse_help_output(tool_path):
    """Parse --help output into structured data"""
    result = subprocess.run(
        [tool_path, '--help'],
        capture_output=True,
        text=True
    )

    help_text = result.stdout

    # Extract description
    description_match = re.search(r'(?:usage:.*?\n\n)(.+?)(?:\n\noptions:)',
                                  help_text, re.DOTALL)
    description = description_match.group(1).strip() if description_match else ""

    # Extract arguments
    args = []
    arg_pattern = r'  (--[\w-]+)(?: (\w+))?\s+(.+?)(?=\n  --|$)'

    for match in re.finditer(arg_pattern, help_text, re.DOTALL):
        flag, param, desc = match.groups()

        args.append({
            'flag': flag,
            'param': param,
            'description': desc.replace('\n', ' ').strip(),
            'required': param is not None and param.isupper()
        })

    return {
        'tool_path': tool_path,
        'description': description,
        'arguments': args
    }
```

**Extracted Data:**
```python
{
  'tool_path': 'scope_flow.py',
  'description': 'Enhanced Tkinter Inspector with Analysis Workflows',
  'arguments': [
    {
      'flag': '--analyze',
      'param': None,
      'description': 'Run progressive analysis on file',
      'required': False
    },
    {
      'flag': '--workflow',
      'param': 'TYPE',
      'description': 'Run specific workflow',
      'required': False,
      'choices': ['full_analysis', 'quick_fix', 'tkinter_only']
    },
    {
      'flag': '--gui-review',
      'param': None,
      'description': 'Open live GUI review',
      'required': False
    },
    {
      'flag': '--file',
      'param': 'FILE',
      'description': 'File to analyze/fix',
      'required': True  # For most workflows
    }
    # ... etc
  ]
}
```

### Step 4: Generate Profile Entries

```python
def generate_profile_actions(parsed_data):
    """Generate workflow_actions from parsed help data"""
    actions = []

    # Map flags to action types
    flag_mappings = {
        '--analyze': {
            'name': '🔬 Progressive Analysis',
            'type': 'workflow_suite',
            'output_to': 'results',
            'expectations': 'analysis_report'
        },
        '--workflow': {
            'name': '⚡ Workflow Execution',
            'type': 'workflow_suite',
            'output_to': 'results',
            'expectations': 'workflow_report',
            'variants': {
                'quick_fix': '⚡ Quick Fix',
                'full_analysis': '🎯 Full Analysis',
                'tkinter_only': '🎨 Tkinter Analysis'
            }
        },
        '--gui-review': {
            'name': '📋 Diff Review GUI',
            'type': 'workflow_suite',
            'output_to': 'diff_queue',
            'expectations': 'interactive_review'
        },
        '--auto-fix': {
            'name': '🔧 Auto-Fix',
            'type': 'workflow_suite',
            'output_to': 'results',
            'expectations': 'auto_fix'
        },
        '--organization': {
            'name': '📊 Project Schema',
            'type': 'workflow_suite',
            'output_to': 'results',
            'expectations': 'organization_report',
            'target_mode': 'dir_required'
        }
    }

    for arg in parsed_data['arguments']:
        flag = arg['flag']

        # Skip utility flags
        if flag in ['--help', '--version', '--file', '--dir', '--depth', '--backup']:
            continue

        if flag in flag_mappings:
            mapping = flag_mappings[flag]

            # Handle variants (like --workflow with multiple types)
            if 'variants' in mapping:
                for variant_key, variant_name in mapping['variants'].items():
                    action = {
                        'name': variant_name,
                        'type': mapping['type'],
                        'source': parsed_data['tool_path'],
                        'target_mode': 'file_required',
                        'output_to': mapping['output_to'],
                        'expectations': f"{variant_key}_workflow",
                        'command': parsed_data['tool_path'],
                        'args': f"{flag}={variant_key} --file={{target}}"
                    }
                    actions.append(action)
            else:
                # Determine target mode
                needs_file = any(a['flag'] == '--file' for a in parsed_data['arguments'])
                needs_dir = any(a['flag'] == '--dir' for a in parsed_data['arguments'])

                target_mode = 'auto'
                args_str = flag

                if needs_file and flag != '--organization':
                    target_mode = 'file_required'
                    args_str += ' --file={target}'
                elif needs_dir or flag == '--organization':
                    target_mode = 'dir_required'
                    args_str += ' --dir={target}'

                # Add optional flags
                if flag in ['--auto-fix', '--analyze']:
                    args_str += ' --backup'  # Safe default

                action = {
                    'name': mapping['name'],
                    'type': mapping['type'],
                    'source': parsed_data['tool_path'],
                    'target_mode': target_mode,
                    'output_to': mapping['output_to'],
                    'expectations': mapping['expectations'],
                    'command': parsed_data['tool_path'],
                    'args': args_str
                }
                actions.append(action)

    return actions
```

**Generated Actions:**
```python
[
  {
    'name': '🔬 Progressive Analysis',
    'type': 'workflow_suite',
    'source': 'scope_flow.py',
    'target_mode': 'file_required',
    'output_to': 'results',
    'expectations': 'analysis_report',
    'command': 'scope_flow.py',
    'args': '--analyze --file={target} --backup'
  },
  {
    'name': '⚡ Quick Fix',
    'type': 'workflow_suite',
    'source': 'scope_flow.py',
    'target_mode': 'file_required',
    'output_to': 'results',
    'expectations': 'quick_fix_workflow',
    'command': 'scope_flow.py',
    'args': '--workflow=quick_fix --file={target}'
  },
  # ... more actions
]
```

### Step 5: Present to User

GUI shows discovered tool:

```
┌─────────────────────────────────────────────────────┐
│ New Tool Detected: scope_flow.py                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│ Enhanced Tkinter Inspector with Analysis Workflows  │
│                                                      │
│ Found 6 workflow actions:                           │
│   ☐ 🔬 Progressive Analysis                         │
│   ☐ ⚡ Quick Fix                                     │
│   ☐ 🎯 Full Analysis                                │
│   ☐ 🎨 Tkinter Analysis                             │
│   ☐ 📋 Diff Review GUI                              │
│   ☐ 🔧 Auto-Fix                                     │
│                                                      │
│ Add to profile: [Scope ▼]                           │
│                                                      │
│ [Select All] [Preview] [Cancel] [Add to Profile]    │
└─────────────────────────────────────────────────────┘
```

User clicks "Add to Profile" → Actions automatically added to workflow_profiles.json

---

## Complete Auto-Onboarding System

### Architecture

```python
class ToolDiscovery:
    """Discovers and registers tools from variants directory"""

    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.discovered_tools = {}

    def scan_directory(self, subdir='variants'):
        """Scan for Python tools"""
        variant_dir = self.base_dir / subdir

        for py_file in variant_dir.glob('*.py'):
            if py_file.name.startswith('_'):
                continue

            tool_info = self.analyze_tool(py_file)
            if tool_info:
                self.discovered_tools[py_file.name] = tool_info

        return self.discovered_tools

    def analyze_tool(self, tool_path):
        """Analyze tool via --help"""
        try:
            result = subprocess.run(
                ['python3', str(tool_path), '--help'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return None

            return parse_help_output(str(tool_path))

        except Exception as e:
            print(f"Failed to analyze {tool_path}: {e}")
            return None

    def generate_profile_entries(self, tool_name):
        """Generate complete profile entries for a tool"""
        tool_info = self.discovered_tools.get(tool_name)
        if not tool_info:
            return None

        actions = generate_profile_actions(tool_info)

        return {
            'tool_name': tool_name,
            'description': tool_info['description'],
            'actions': actions,
            'tool_locations': {
                action['name']: action['source']
                for action in actions
            }
        }


class ProfileManager:
    """Manages workflow_profiles.json"""

    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.profiles = self.load()

    def load(self):
        """Load existing profiles"""
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def add_actions_to_profile(self, profile_name, new_actions):
        """Add actions to existing profile"""
        if profile_name not in self.profiles['profiles']:
            return False

        profile = self.profiles['profiles'][profile_name]

        # Find placeholder slots
        placeholders = [
            i for i, action in enumerate(profile['workflow_actions'])
            if action.get('type') == 'placeholder'
        ]

        # Replace placeholders with new actions
        for i, action in zip(placeholders, new_actions):
            profile['workflow_actions'][i] = action

        # Update tool_locations
        for action in new_actions:
            profile['tool_locations'][action['name']] = action['source']

        # Update timestamp
        profile['last_updated'] = datetime.now().isoformat()

        return True

    def save(self):
        """Save profiles back to file"""
        with open(self.config_path, 'w') as f:
            json.dump(self.profiles, f, indent=2)


# Usage
discovery = ToolDiscovery('/path/to/scope')
discovery.scan_directory('variants')

# Found: scope_flow.py
profile_entries = discovery.generate_profile_entries('scope_flow.py')

# Present to user (GUI or CLI)
print(f"Found tool: {profile_entries['tool_name']}")
print(f"Description: {profile_entries['description']}")
print(f"Actions: {len(profile_entries['actions'])}")

# User confirms → Add to profile
manager = ProfileManager('.docv2_workspace/config/workflow_profiles.json')
manager.add_actions_to_profile('Scope', profile_entries['actions'])
manager.save()
```

---

## Benefits

1. **Zero Manual Configuration**
   - Drop tool in variants/
   - System auto-discovers
   - Profile entries generated

2. **Consistent Structure**
   - All tools follow same pattern
   - Predictable behavior
   - Easy maintenance

3. **Extensibility**
   - Add new tools without touching code
   - Variants directory is self-contained
   - Version management via directory structure

4. **User Control**
   - Preview before adding
   - Select which actions to add
   - Choose target profile

5. **Future-Proof**
   - Tools document themselves via --help
   - No hardcoded mappings needed
   - Works with any CLI tool

---

## Advanced: Argument Templates

For complex arguments, define templates:

```python
arg_templates = {
    '--depth': {
        'type': 'int',
        'default': 4,
        'range': (1, 4),
        'ui_widget': 'slider'
    },
    '--workflow': {
        'type': 'choice',
        'choices': ['full_analysis', 'quick_fix', 'tkinter_only'],
        'ui_widget': 'dropdown'
    },
    '--backup': {
        'type': 'bool',
        'default': True,
        'ui_widget': 'checkbox'
    }
}
```

GUI generates appropriate widgets:
- `--depth` → Slider (1-4)
- `--workflow` → Dropdown menu
- `--backup` → Checkbox

---

## Integration with Existing System

Your panel system would add:

1. **Discovery Menu Item**
   ```
   Tools → Discover New Tools
   ```

2. **Auto-Scan on Startup**
   ```python
   # On panel launch
   discovery.scan_directory('variants')

   if discovery.discovered_tools:
       notify_user("New tools found. Click to review.")
   ```

3. **Profile Editor**
   - Drag-and-drop actions
   - Reorder buttons
   - Edit arguments
   - Test invocation

4. **Version Tracking**
   ```json
   "tool_versions": {
     "scope_flow.py": {
       "version": "1.0",
       "last_scanned": "2026-01-14",
       "args_hash": "abc123"
     }
   }
   ```

   If args change → Prompt to update profile

---

## Summary

**Current State**: Manual JSON editing

**Future State**: Drop tool → Auto-discover → One-click add

**Implementation**: ~200 lines of Python for discovery + UI integration

This makes your panel system **truly extensible** - any tool with `--help` output can be instantly integrated!
