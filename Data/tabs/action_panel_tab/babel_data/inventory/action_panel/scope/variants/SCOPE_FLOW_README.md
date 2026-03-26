# scope_flow.py - Analysis & Workflow Tool

A CLI-focused variant of scope.py that provides automated code analysis, fixing workflows, and interactive diff review.

## Purpose

- **scope.py**: Widget inspector + grep_flight integration (interactive GUI)
- **scope_flow.py**: Code analysis + workflow automation + diff review (CLI-first)

## Key Features

### 1. Progressive Analysis
Multi-depth analysis with automatic issue detection:
- Import resolution
- Call chain tracking
- Pattern detection (tkinter, security, performance)
- Prioritized fix suggestions

### 2. Turn-Based Workflows
Step-by-step execution with pause/resume:
- `full_analysis` - Complete 15-step analysis and fixing
- `quick_fix` - Fast 3-step import/style/format fixes
- `tkinter_only` - Tkinter-specific pattern analysis

### 3. Live GUI Diff Review
Interactive side-by-side comparison:
- Color-coded diffs
- Accept/reject individual changes
- Change statistics
- Backup creation

### 4. Organization Schema
Project structure analysis:
- Module relationship graphs
- Import dependency tracking
- File size recommendations
- Function/class distribution

### 5. Tool Integration
Automated fixes using:
- `pylint` - Code quality scanning
- `pyflakes` - Syntax checking
- `autoflake` - Unused import cleanup
- `ruff` - Style fixes
- `black` - Code formatting
- `bandit` - Security scanning
- `mypy` - Type checking

## Usage

### Progressive Analysis
```bash
# Analyze file with depth-4 inspection
python3 scope_flow.py --analyze --file=myapp.py --depth=4

# Auto-fix detected issues
python3 scope_flow.py --auto-fix --file=myapp.py --backup
```

### Workflow Execution
```bash
# Quick fix (imports, style, format)
python3 scope_flow.py --workflow=quick_fix --file=myapp.py

# Full analysis (all steps, auto mode)
python3 scope_flow.py --workflow=full_analysis --file=myapp.py --auto

# Tkinter-specific analysis
python3 scope_flow.py --workflow=tkinter_only --file=my_gui.py
```

### Interactive Diff Review
```bash
# Launch GUI to review proposed changes
python3 scope_flow.py --gui-review --file=myapp.py
```

This opens a GUI with:
- Side-by-side before/after comparison
- Syntax-highlighted diffs
- Accept/reject buttons for each change
- Statistics panel

### Project Organization Analysis
```bash
# Analyze entire project structure
python3 scope_flow.py --organization --dir=./my_project
```

Shows:
- Module dependencies
- Import relationships
- File size distribution
- Recommendations for refactoring

### Turn-Based Interactive Mode
```bash
# Step through workflow interactively
python3 scope_flow.py --turnbased --interactive --file=myapp.py
```

Pauses at each step, shows:
- Current phase (discovery, analysis, fix, review, verify)
- Step description
- Tool being used
- Results and duration
- Prompt to continue

## Integration with grep_flight

scope_flow.py includes `GrepFlightIntegration` class for seamless workflow:

### From grep_flight → scope_flow
```bash
# In grep_flight, find a file with issues
# Right-click result → "Analyze with scope_flow"
# (requires IPC trigger - see below)
```

### From scope_flow → grep_flight
```python
# After analysis, send file to grep_flight for further searching
integration = GrepFlightIntegration()
integration.send_to_grep_flight("/path/to/file.py", stable=True)
```

## External Triggering (IPC)

scope_flow.py can be triggered externally via IPC for integration with other tools:

### Planned IPC Interface
```bash
# IPC FIFO path
/run/user/1000/scope_flow_ipc_${USER}.fifo

# Message format
ANALYZE|/path/to/file.py|depth=4
GUI_REVIEW|/path/to/file.py|modified=/tmp/modified.py
WORKFLOW|quick_fix|/path/to/file.py
```

### Use Cases
1. **From grep_flight**: Right-click search result → "Analyze & Fix"
2. **From Claude Code**: Proposed changes → spawn diff GUI → user accepts/rejects
3. **From Thunar**: Right-click Python file → "Run Analysis Workflow"

## CLI Arguments Reference

### Analysis Options
```
--analyze              Run progressive analysis on file
--depth DEPTH          Analysis depth (1-4, default: 3)
--file FILE            Target file for analysis
```

### Workflow Options
```
--workflow TYPE        Run specific workflow (full_analysis, quick_fix, tkinter_only)
--auto                 Run workflow without confirmation prompts
--turnbased            Execute workflow step-by-step
--interactive          Pause at each step for review
```

### Fix Options
```
--auto-fix             Auto-fix all detectable issues
--backup               Create backup before auto-fix
```

### GUI Options
```
--gui-review           Launch interactive diff review GUI
```

### Organization
```
--organization         Generate project organization schema
--dir DIR              Directory for schema analysis
```

## Output and Logs

### Analysis Logs
```bash
# Comprehensive analysis log
scope_analysis.log

# Individual tool outputs stored in result objects
# Access via Python API or --verbose flag
```

### Backup Files
When using `--backup`, creates:
```
original_file_20260114_123456.py.bak
```

## Workflow Details

### full_analysis Workflow
1. **Discovery**: Find all Python files
2. **Initial Scan**: Pylint code quality check
3. **Syntax Check**: Pyflakes syntax validation
4. **Security Scan**: Bandit vulnerability detection
5. **Type Check**: Mypy type checking
6. **Tkinter Analysis**: GUI pattern detection
7. **Import Cleanup**: Autoflake unused imports
8. **Code Style Fix**: Ruff style corrections
9. **Format Code**: Black formatting
10. **Indent Fix**: Reindent corrections
11. **GUI Layout Analysis**: Tkinter layout patterns
12. **Data Piping Analysis**: Data flow tracking
13. **Generate Report**: Comprehensive report
14. **Diff Review**: Show before/after changes
15. **Final Verification**: Verify all fixes applied

### quick_fix Workflow
1. **Import Cleanup**: Remove unused imports
2. **Code Style Fix**: Apply style corrections
3. **Format Code**: Black formatting

### tkinter_only Workflow
1. **GUI Pattern Detection**: Find tkinter-specific issues
2. **Layout Analysis**: Analyze pack/grid/place usage
3. **Widget Optimization**: Suggest widget improvements

## Examples

### Example 1: Analyze and Fix GUI Application
```bash
# Step 1: Analyze with high depth
python3 scope_flow.py --analyze --file=my_tkinter_app.py --depth=4

# Step 2: Review suggested fixes
# (Shows prioritized list of issues)

# Step 3: Run GUI review to see diffs
python3 scope_flow.py --gui-review --file=my_tkinter_app.py

# Step 4: Accept/reject changes in GUI
# Step 5: Save accepted changes
```

### Example 2: Quick Cleanup Before Commit
```bash
# One-liner: backup, fix, verify
python3 scope_flow.py --workflow=quick_fix --file=my_module.py --backup --auto
```

### Example 3: Interactive Full Analysis
```bash
# Step through comprehensive analysis
python3 scope_flow.py --workflow=full_analysis --file=app.py --turnbased --interactive

# At each step:
# - See what's being analyzed/fixed
# - Review results
# - Decide to continue or skip
```

### Example 4: Project Health Check
```bash
# Analyze entire project
python3 scope_flow.py --organization --dir=~/my_project

# Output shows:
# - Module dependencies
# - Circular imports (if any)
# - Large files needing refactoring
# - Orphaned modules
# - Recommended improvements
```

## Integration with Claude Code CLI

Planned integration allows Claude Code to use scope_flow for visual change approval:

```python
# Claude proposes changes to file.py
# Claude writes proposed changes to /tmp/proposed_file.py
# Claude triggers scope_flow via IPC:

echo "GUI_REVIEW|/original/file.py|modified=/tmp/proposed_file.py" > /run/user/1000/scope_flow_ipc_${USER}.fifo

# scope_flow spawns GUI showing:
# - Original code (left)
# - Claude's proposed code (right)
# - Diff highlighting
# - Accept/Reject buttons

# User accepts changes → scope_flow applies them
# User rejects → scope_flow notifies Claude Code
```

This creates a human-in-the-loop workflow where Claude can propose changes but you visually approve them before application.

## Requirements

### Required Python Packages
```bash
pip3 install tkinter  # Usually comes with Python
```

### Optional Analysis Tools
```bash
# Install for full functionality
pip3 install pylint pyflakes autoflake ruff black mypy bandit isort
```

Check availability:
```bash
python3 scope_flow.py --analyze --file=test.py
# Will report which tools are available
```

## Troubleshooting

### Issue: "Tool not available"
```bash
# Install missing tools
pip3 install <tool_name>

# Or run without that tool (will skip)
```

### Issue: GUI review not opening
```bash
# Check if tkinter is installed
python3 -c "import tkinter; print('OK')"

# If not, install:
sudo apt install python3-tk
```

### Issue: No suggested fixes
```bash
# File may be clean, or tools not installed
# Check tool availability:
python3 scope_flow.py --analyze --file=yourfile.py
```

## Comparison: scope.py vs scope_flow.py

| Feature | scope.py | scope_flow.py |
|---------|----------|---------------|
| Widget Inspection | ✓ Real-time hover | ✗ N/A |
| Click-to-target | ✓ grep_flight integration | ✗ N/A |
| Code Analysis | ✗ Basic only | ✓ Multi-depth |
| Auto-fix Tools | ✗ No | ✓ 8+ tools |
| Diff Review GUI | ✗ No | ✓ Yes |
| Workflows | ✗ No | ✓ 3 types |
| CLI-focused | ✗ GUI-first | ✓ CLI-first |
| Project Analysis | ✗ No | ✓ Organization schema |

## Future Enhancements

Planned features:
- IPC receiver for external triggering
- Integration with CI/CD pipelines
- Custom workflow definitions
- Pre-commit hook integration
- Incremental analysis (only changed files)
- Parallel analysis for large projects
- Export reports to HTML/JSON/PDF

## Support

For issues or questions:
1. Check logs in `scope_analysis.log`
2. Run with individual args to isolate issue
3. Verify tool availability with `--analyze`
4. Compare with original scope.py behavior

---

**Remember**: scope_flow.py is for **analysis and automation**. For **widget inspection**, use the original `scope.py`.
