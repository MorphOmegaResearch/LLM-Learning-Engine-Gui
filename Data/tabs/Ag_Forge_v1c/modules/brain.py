#!/usr/bin/env python3
"""
Financial Project Management System - CLI Workflow Edition
----------------------------------------------------------------
Complete system for managing financial projects with agent-assisted onboarding,
task tracking, script orchestration, and change management.

Enhanced with:
1. CLI-first workflow with argparse
2. Ollama model selection and self-assessment
3. Guided project setup with directory-aware context
4. Static manifest logging for reproducibility
5. Integrated task binding to Python-master scripts
"""
import json
import os
import sys
from pathlib import Path

# Ensure the project root is in the system path to allow cross-module imports
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import sqlite3
import hashlib
import re
import subprocess
import asyncio
import uuid
import argparse
import shlex
import readline
import signal
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
import threading
from queue import Queue
import time
import webbrowser
from collections import defaultdict
import textwrap
import toml
import yaml

# Import Ag_ForgeApp for agribusiness workflow
try:
    from modules.meta_learn_agriculture import KnowledgeForgeApp
except ImportError:
    KnowledgeForgeApp = None # Handle gracefully if Ag_Forge not available

# ============================================================================
# 1. CONFIGURATION & MANIFEST SYSTEM
# ============================================================================

class ConfigManager:
    """Configuration and manifest management"""
    
    def __init__(self, base_path: Optional[Path] = None):
        # Use project_root for portability
        self.base_path = base_path or project_root / ".financial_brain"
        self.base_path.mkdir(exist_ok=True)
        
        self.config_file = self.base_path / "config.toml"
        self.manifest_file = self.base_path / "manifest.json"
        self.model_cache_file = self.base_path / "models.json"
        
        # Default configuration
        self.default_config = {
            "model": {
                "default": "llama2",
                "fallback": "qwen2.5:0.5b",
                "temperature": 0.7,
                "num_gpu": 0
            },
            "project": {
                "base_dir": str(Path.home() / "FinancialProjects"),
                "auto_discover_scripts": True,
                "default_workflow": "financial_analysis"
            },
            "scripts": {
                "python_master_path": str(project_root / "modules" / "Python-master"),
                "bind_by_category": True,
                "auto_map_tasks": True
            },
            "cli": {
                "interactive": True,
                "color_output": True,
                "log_level": "INFO"
            }
        }
        
        self.load_config()
        self.load_manifest()
    
    def load_config(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = toml.load(f)
            except:
                self.config = self.default_config
        else:
            self.config = self.default_config
            self.save_config()
    
    def save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            toml.dump(self.config, f)
    
    def load_manifest(self):
        """Load system manifest"""
        if self.manifest_file.exists():
            try:
                with open(self.manifest_file, 'r') as f:
                    self.manifest = json.load(f)
            except:
                self.manifest = self.create_default_manifest()
        else:
            self.manifest = self.create_default_manifest()
            self.save_manifest()
    
    def save_manifest(self):
        """Save system manifest"""
        with open(self.manifest_file, 'w') as f:
            json.dump(self.manifest, f, indent=2)
    
    def create_default_manifest(self) -> Dict:
        """Create default system manifest"""
        return {
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "models_tested": [],
            "projects_created": [],
            "workflows_executed": [],
            "scripts_bound": {},
            "system_context": self.get_system_context()
        }
    
    def get_system_context(self) -> Dict:
        """Get system context information"""
        try:
            python_master_path = Path(self.config["scripts"]["python_master_path"])
            if python_master_path.exists():
                scripts_by_category = self.discover_scripts_by_category(python_master_path)
            else:
                scripts_by_category = {}
        except:
            scripts_by_category = {}
        
        return {
            "system": {
                "python_version": sys.version,
                "platform": sys.platform,
                "cwd": os.getcwd()
            },
            "directory_structure": scripts_by_category,
            "config": {
                "model_default": self.config["model"]["default"],
                "project_base": self.config["project"]["base_dir"]
            }
        }
    
    def discover_scripts_by_category(self, base_path: Path) -> Dict:
        """Discover scripts organized by category"""
        categories = {}
        
        if not base_path.exists():
            return categories
        
        for item in base_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                scripts = []
                for script in item.glob("*.py"):
                    if script.is_file():
                        scripts.append(script.name)
                
                if scripts:
                    categories[item.name] = sorted(scripts)
        
        return categories
    
    def update_manifest(self, updates: Dict):
        """Update manifest with new data"""
        self.manifest.update(updates)
        self.manifest["last_updated"] = datetime.now().isoformat()
        self.save_manifest()

class SessionManager:
    """Manages conversational sessions."""
    def __init__(self, config: ConfigManager):
        self.session_dir = config.base_path / "sessions"
        self.session_dir.mkdir(exist_ok=True)

    def new_session(self) -> Tuple[str, List]:
        """Creates a new session."""
        session_id = str(uuid.uuid4())
        history = []
        self.save_session(session_id, history)
        return session_id, history

    def load_session(self, session_id: str) -> Optional[List]:
        """Loads a session history from a file."""
        session_file = self.session_dir / f"{session_id}.json"
        if session_file.exists():
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def save_session(self, session_id: str, history: List):
        """Saves a session history to a file."""
        session_file = self.session_dir / f"{session_id}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)

def check_internet_connection(timeout: int = 3) -> bool:
    """Checks if the system has an active internet connection."""
    import socket
    try:
        # Try to connect to a reliable host (Google DNS)
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except socket.error:
        return False

def handle_conversational_onboarding(args, config: ConfigManager, sm: SessionManager):
    """Orchestrates the turn-based conversational onboarding with intelligent routing."""
    session_id = args.session_id
    history = []
    
    # 0. Intelligent Provider Routing
    has_internet = check_internet_connection()
    existing_sessions = list(sm.session_dir.glob("*.json"))
    
    if not session_id and not existing_sessions:
        if has_internet:
            print("🌐 Internet detected. Defaulting to Gemini for initial onboarding.")
            args.provider = 'gemini'
        else:
            print("🔌 No internet detected. Defaulting to Mock Architect (Agent Mode).")
            args.provider = 'gemini'
            args.agent_mode = True
    elif getattr(args, 'general_business', False) or (args.reply and "business" in args.reply.lower() and not session_id):
        if has_internet:
            print("🌐 Internet detected. Defaulting to Gemini for General Business query.")
            args.provider = 'gemini'
        else:
            print("💡 No internet. Routing General Business query to Ollama (Local Model).")
            args.provider = 'ollama'
            args.model = args.model or "qwen2.5:0.5b"
    
    # Standard session handling starts here
    if not session_id:
        session_id, history = sm.new_session()
        print(f"🌟 Starting new onboarding session: {session_id}")
    else:
        history = sm.load_session(session_id)
        if history is None:
            print(f"❌ Error: Session ID '{session_id}' not found.", file=sys.stderr)
            return
        print(f"🔄 Continuing session: {session_id}")

    # 1. Reconstruct and Update State
    current_state = {
        "project_name": None, 
        "business_focus": None, 
        "business_strategy": None, # Added
        "initial_investment": None
    }
    
    # Rebuild state from the beginning of history
    # This assumes a sequential filling of state: Name -> Focus -> Strategy -> Investment
    temp_state_rebuild = {"project_name": None, "business_focus": None, "business_strategy": None, "initial_investment": None}
    for turn in history:
        if turn["role"] == "user":
            if temp_state_rebuild["project_name"] is None:
                temp_state_rebuild["project_name"] = turn["content"]
            elif temp_state_rebuild["business_focus"] is None:
                temp_state_rebuild["business_focus"] = turn["content"]
            elif temp_state_rebuild["business_strategy"] is None:
                temp_state_rebuild["business_strategy"] = turn["content"]
            elif temp_state_rebuild["initial_investment"] is None:
                temp_state_rebuild["initial_investment"] = turn["content"]
    
    current_state.update(temp_state_rebuild)

    # Process the new reply for this turn
    if args.reply:
        # Update the FIRST MISSING field in current_state with the reply
        if current_state["project_name"] is None:
            current_state["project_name"] = args.reply
        elif current_state["business_focus"] is None:
            current_state["business_focus"] = args.reply
        elif current_state["business_strategy"] is None:
            current_state["business_strategy"] = args.reply
        elif current_state["initial_investment"] is None:
            current_state["initial_investment"] = args.reply
            
        history.append({"role": "user", "content": args.reply, "timestamp": datetime.now().isoformat()})
        sm.save_session(session_id, history)

    # 2. Build Prompt for Reviewer
    from modules.dev_tools.context_aggregator import aggregate_context, create_ai_review_prompt
    
    target_file = project_root / "modules" / "brain.py"
    context = aggregate_context(
        target_file_path_str=str(target_file),
        user_request="Onboarding turn-based review.",
        project_dir=project_root,
        enable_analysis=False
    )
    
    ai_prompt = create_ai_review_prompt(
        context,
        known_project_name=current_state["project_name"],
        known_business_focus=current_state["business_focus"],
        known_business_strategy=current_state["business_strategy"],
        known_initial_investment=current_state["initial_investment"]
    )

    if args.show_context:
        print("\n--- FULL AI PROMPT CONTEXT ---")
        print(ai_prompt)
        print("------------------------------")

    # 3. Hand off to Provider
    from modules.quick_clip.providers import get_provider
    gemini_provider = get_provider('gemini')
    
    try:
        result_message = gemini_provider.execute(ai_prompt, args)
        
        # Save the result to history if in agent mode
        reviewer_content = ""
        if args.agent_mode and "Reviewer Output:" in result_message:
            reviewer_content = result_message.split("---", 1)[-1].strip()
            history.append({"role": "reviewer", "content": reviewer_content, "timestamp": datetime.now().isoformat()})
            sm.save_session(session_id, history)
        
        # Automated Task Queueing Logic (Integration with Quick Clip)
        if "[[PLANNER_TASKS:" in result_message:
            try:
                from modules.quick_clip.clip_task_core import TaskManager
                tm = TaskManager()
                
                # Extract tasks from tag: [[PLANNER_TASKS: cat/s1.py, cat2/s2.py]]
                task_match = re.search(r"\[\[PLANNER_TASKS: (.*?)\]\]", result_message)
                if task_match:
                    tasks_str = task_match.group(1)
                    suggested_scripts = [s.strip() for s in tasks_str.split(",")]
                    
                    print(f"\n📦 AI Architect suggested {len(suggested_scripts)} tasks. Queueing in Planner...")
                    for script in suggested_scripts:
                        task_id = tm.add_task(
                            description=f"Execute {script} for project {current_state['project_name']}",
                            project=current_state['project_name'] or "AgriOnboarding",
                            tags=["ai-suggested", "agribusiness", script.split("/")[0]]
                        )
                        print(f"  ✓ Queued: {script} (ID: {task_id[:8]})")
            except Exception as e:
                print(f"⚠️ Warning: Could not queue tasks in planner: {e}")

        print(f"\n✅ {result_message}")
        print(f"\n[SESSION_ID]: {session_id}")
        
    except Exception as e:
        print(f"❌ Error during conversational turn: {e}", file=sys.stderr)

# ============================================================================
# 2. OLLAMA MODEL MANAGEMENT
# ============================================================================

class OllamaManager:
    """Ollama model management and interaction"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.available_models = []
        self.current_model = config.config["model"]["default"]
        
    def check_ollama_installed(self) -> bool:
        """Check if Ollama is installed and running"""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def get_available_models(self) -> List[str]:
        """Get list of available Ollama models"""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                models = []
                
                # Skip header line
                for line in lines[1:]:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 1:
                            model_name = parts[0]
                            models.append(model_name)
                
                self.available_models = models
                
                # Cache models
                cache_data = {
                    "timestamp": datetime.now().isoformat(),
                    "models": models
                }
                with open(self.config.model_cache_file, 'w') as f:
                    json.dump(cache_data, f)
                
                return models
            else:
                return []
                
        except Exception as e:
            print(f"Error getting models: {e}")
            return []
    
    def model_exists(self, model_name: str) -> bool:
        """Check if a specific model exists"""
        if not self.available_models:
            self.get_available_models()
        
        return any(model_name in model for model in self.available_models)
    
    def run_model_assessment(self, model_name: str) -> Dict:
        """Run self-assessment with specified model"""
        assessment = {
            "model": model_name,
            "timestamp": datetime.now().isoformat(),
            "checks": [],
            "recommendations": [],
            "status": "pending"
        }
        
        # Check 1: Model availability
        if self.model_exists(model_name):
            assessment["checks"].append({
                "name": "model_availability",
                "status": "pass",
                "message": f"Model '{model_name}' is available"
            })
        else:
            assessment["checks"].append({
                "name": "model_availability",
                "status": "fail",
                "message": f"Model '{model_name}' not found"
            })
            assessment["status"] = "failed"
            return assessment
        
        # Check 2: System context comprehension
        context = self.config.get_system_context()
        prompt = self.create_assessment_prompt(context)
        
        try:
            response = self.query_model(model_name, prompt, max_tokens=500)
            
            if response:
                assessment["checks"].append({
                    "name": "context_comprehension",
                    "status": "pass",
                    "message": "Model responded to system context"
                })
                
                # Parse recommendations from response
                recommendations = self.parse_recommendations(response)
                assessment["recommendations"] = recommendations
                assessment["status"] = "complete"
            else:
                assessment["checks"].append({
                    "name": "context_comprehension",
                    "status": "fail",
                    "message": "No response from model"
                })
                assessment["status"] = "partial"
                
        except Exception as e:
            assessment["checks"].append({
                "name": "model_query",
                "status": "error",
                "message": f"Error querying model: {str(e)}"
            })
            assessment["status"] = "error"
        
        return assessment
    
    def create_assessment_prompt(self, context: Dict) -> str:
        """Create self-assessment prompt"""
        prompt = f"""You are assessing a Financial Project Management System. Please analyze the following system context and provide recommendations:

SYSTEM CONTEXT:
{json.dumps(context, indent=2)}

Please provide:
1. Analysis of the available script categories for financial tasks
2. Recommendations for which script categories to prioritize
3. Suggestions for project structure based on the directory layout
4. Any potential issues or improvements

Format your response as:
ANALYSIS: [your analysis]
RECOMMENDATIONS: [numbered list]
ISSUES: [any identified issues]
IMPROVEMENTS: [suggested improvements]"""
        
        return prompt
    
    def query_model(self, model_name: str, prompt: str, **kwargs) -> Optional[str]:
        """Query Ollama model"""
        try:
            data = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {}
            }
            
            # Add options if provided
            if "temperature" in kwargs:
                data["options"]["temperature"] = kwargs["temperature"]
            if "num_gpu" in kwargs:
                data["options"]["num_gpu"] = kwargs["num_gpu"]
            if "max_tokens" in kwargs:
                data["options"]["num_predict"] = kwargs["max_tokens"]
            
            # Call Ollama API
            import requests
            
            response = requests.post(
                "http://localhost:11434/api/generate",
                json=data,
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                return None
                
        except Exception as e:
            print(f"Error querying model: {e}")
            return None
    
    def parse_recommendations(self, response: str) -> List[str]:
        """Parse recommendations from model response"""
        recommendations = []
        
        # Look for RECOMMENDATIONS section
        lines = response.split('\n')
        in_recommendations = False
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("RECOMMENDATIONS:"):
                in_recommendations = True
                continue
            
            if line.startswith("ISSUES:"):
                break
            
            if in_recommendations and line:
                # Remove numbering if present
                clean_line = re.sub(r'^\d+[\.\)]\s*', '', line)
                if clean_line:
                    recommendations.append(clean_line)
        
        return recommendations
    
    def guided_model_setup(self) -> str:
        """Interactive guided model setup"""
        print("\n" + "="*60)
        print("OLLAMA MODEL SETUP WIZARD")
        print("="*60)
        
        # Check Ollama installation
        if not self.check_ollama_installed():
            print("\n❌ Ollama is not installed or not running.")
            print("Please install Ollama from: https://ollama.ai/")
            print("Then run: ollama pull llama2")
            sys.exit(1)
        
        # Get available models
        print("\n🔍 Fetching available models...")
        models = self.get_available_models()
        
        if not models:
            print("\n❌ No models found. Please pull a model first:")
            print("  ollama pull llama2")
            print("  ollama pull qwen2.5:0.5b")
            sys.exit(1)
        
        # Display models
        print(f"\n📋 Found {len(models)} models:")
        for i, model in enumerate(models, 1):
            print(f"  {i}. {model}")
        
        # Model selection
        while True:
            try:
                choice = input("\nSelect a model (number or name, or 'q' to quit): ").strip()
                
                if choice.lower() == 'q':
                    sys.exit(0)
                
                # Try to parse as number
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(models):
                        selected_model = models[idx]
                        break
                    else:
                        print(f"❌ Please enter a number between 1 and {len(models)}")
                except ValueError:
                    # Try to match by name
                    matched_models = [m for m in models if choice.lower() in m.lower()]
                    if len(matched_models) == 1:
                        selected_model = matched_models[0]
                        break
                    elif len(matched_models) > 1:
                        print(f"❓ Multiple matches found:")
                        for i, m in enumerate(matched_models, 1):
                            print(f"  {i}. {m}")
                        continue
                    else:
                        print(f"❌ Model '{choice}' not found")
                        
            except (KeyboardInterrupt, EOFError):
                print("\n\nSetup cancelled.")
                sys.exit(0)
        
        # Run self-assessment
        print(f"\n🧠 Running self-assessment with '{selected_model}'...")
        assessment = self.run_model_assessment(selected_model)
        
        # Display results
        print(f"\n✅ Assessment completed: {assessment['status']}")
        
        if assessment['recommendations']:
            print("\n📋 Recommendations:")
            for i, rec in enumerate(assessment['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        # Update configuration
        self.config.config["model"]["default"] = selected_model
        self.config.save_config()
        
        # Update manifest
        self.config.manifest["models_tested"].append({
            "model": selected_model,
            "timestamp": datetime.now().isoformat(),
            "status": assessment['status']
        })
        self.config.save_manifest()
        
        print(f"\n✅ Model '{selected_model}' configured as default.")
        return selected_model

# ============================================================================
# 3. CLI WORKFLOW ENGINE
# ============================================================================

class CLIWorkflow:
    """CLI workflow engine with guided interactions"""
    
    def __init__(self, config: ConfigManager, ollama: OllamaManager):
        self.config = config
        self.ollama = ollama
        self.project_context = {}
        self.workflow_steps = []
        
    def print_header(self, title: str):
        """Print formatted header"""
        print("\n" + "="*60)
        print(f" {title}")
        print("="*60)
    
    def print_step(self, step_num: int, title: str, description: str = ""):
        """Print step information"""
        print(f"\n[{step_num}] {title}")
        if description:
            print(f"   {description}")
    
    def guided_project_setup(self) -> Dict:
        """Interactive guided project setup with step-by-step navigation."""
        self.print_header("PROJECT SETUP WIZARD")

        project_config = {}
        step = 1

        while step <= 4:
            try:
                if step == 1:
                    # --- Step 1: Project Basics ---
                    self.print_step(1, "Project Information")
                    
                    while 'name' not in project_config:
                        name = input("Project name (or 'cancel'): ").strip()
                        if name.lower() == 'cancel':
                            raise KeyboardInterrupt()
                        if not name:
                            print("❌ Project name is required.")
                        else:
                            project_config['name'] = name
                    
                    desc = input("Description (optional, or 'back', 'cancel'): ").strip()
                    if desc.lower() == 'cancel':
                        raise KeyboardInterrupt()
                    if desc.lower() == 'back':
                        project_config.pop('name', None) # Go back to entering name
                        continue # Restart this step
                    
                    project_config['description'] = desc
                    step += 1

                elif step == 2:
                    # --- Step 2: Project Type ---
                    self.print_step(2, "Project Type Selection")
                    project_types = {
                        "1": {"name": "Financial Analysis", "workflow": "financial_analysis"},
                        "2": {"name": "Investment Portfolio", "workflow": "portfolio_management"},
                        "3": {"name": "Loan & Debt Analysis", "workflow": "loan_analysis"},
                        "4": {"name": "Business Financial Planning", "workflow": "business_planning"},
                        "5": {"name": "Custom Workflow", "workflow": "custom"}
                    }
                    print("\nSelect project type:")
                    for key, value in project_types.items():
                        print(f"  {key}. {value['name']}")
                    
                    type_choice = input(f"\nType (1-{len(project_types)}) (or 'back', 'cancel'): ").strip().lower()

                    if type_choice == 'cancel':
                        raise KeyboardInterrupt()
                    if type_choice == 'back':
                        step -= 1
                        continue

                    if type_choice in project_types:
                        project_config['type'] = project_types[type_choice]['name']
                        project_config['workflow'] = project_types[type_choice]['workflow']
                        step += 1
                    else:
                        print(f"❌ Please enter a number 1-{len(project_types)}")

                elif step == 3:
                    # --- Step 3: Script Binding ---
                    self.print_step(3, "Script Category Binding")
                    python_master_path = Path(self.config.config["scripts"]["python_master_path"])
                    categories = self.config.discover_scripts_by_category(python_master_path)

                    if not categories:
                        print(f"⚠️ Python-master directory not found or empty: {python_master_path}")
                        project_config['bound_categories'] = []
                        step += 1
                        continue

                    print("\nAvailable script categories:")
                    cat_list = list(categories.keys())
                    for i, category in enumerate(cat_list, 1):
                        print(f"  {i}. {category} ({len(categories[category])} scripts)")
                    
                    bind_choice = input("\nBind scripts automatically? (y/n, or 'back', 'cancel'): ").strip().lower()

                    if bind_choice == 'cancel':
                        raise KeyboardInterrupt()
                    if bind_choice == 'back':
                        step -= 1
                        continue
                    
                    if bind_choice == 'y':
                        project_config['bound_categories'] = self.auto_bind_categories(categories, project_config.get('workflow', 'custom'))
                        print(f"\n✅ Auto-bound {len(project_config['bound_categories'])} categories.")
                    else:
                        project_config['bound_categories'] = []
                        print("Skipping automatic script binding.")
                    
                    step += 1

                elif step == 4:
                    # --- Step 4: Create Project Structure ---
                    self.print_step(4, "Creating Project Structure")
                    base_dir = Path(self.config.config["project"]["base_dir"])
                    base_dir.mkdir(exist_ok=True)
                    project_dir = base_dir / project_config['name'].lower().replace(' ', '_')
                    project_dir.mkdir(exist_ok=True)

                    (project_dir / "data").mkdir(exist_ok=True)
                    (project_dir / "scripts").mkdir(exist_ok=True)
                    (project_dir / "reports").mkdir(exist_ok=True)
                    (project_dir / "docs").mkdir(exist_ok=True)
                    
                    final_config = {
                        "name": project_config['name'],
                        "description": project_config['description'],
                        "type": project_config['type'],
                        "workflow": project_config['workflow'],
                        "created_at": datetime.now().isoformat(),
                        "directory": str(project_dir),
                        "bound_categories": project_config['bound_categories'],
                        "scripts": {
                            "python_master_path": self.config.config["scripts"]["python_master_path"],
                            "auto_discover": self.config.config["project"]["auto_discover_scripts"]
                        }
                    }
                    config_file = project_dir / "project.toml"
                    with open(config_file, 'w') as f:
                        toml.dump(final_config, f)
                    
                    readme_file = project_dir / "README.md"
                    with open(readme_file, 'w') as f:
                        f.write(self.generate_readme(final_config))

                    self.config.manifest["projects_created"].append({
                        "name": final_config['name'],
                        "type": final_config['type'],
                        "timestamp": datetime.now().isoformat(),
                        "directory": str(project_dir)
                    })
                    self.config.save_manifest()
                    print(f"\n✅ Project created at: {project_dir}")
                    
                    return final_config

            except KeyboardInterrupt:
                print("\n\n👋 Setup cancelled by user.")
                sys.exit(0)
        
        return {} # Should not be reached
    
    def auto_bind_categories(self, categories: Dict, workflow: str) -> List[str]:
        """Automatically bind relevant script categories based on workflow"""
        # Map workflow to likely categories
        workflow_to_categories = {
            "financial_analysis": ["financial", "maths", "statistics", "data_structures"],
            "portfolio_management": ["financial", "optimization", "linear_programming"],
            "loan_analysis": ["financial", "maths", "dynamic_programming"],
            "business_planning": ["financial", "project_euler", "scheduling"],
            "custom": list(categories.keys())[:3]  # First 3 categories
        }
        
        # Get relevant categories for this workflow
        relevant_categories = workflow_to_categories.get(workflow, [])
        
        # Filter to only categories that actually exist
        bound_categories = [cat for cat in relevant_categories if cat in categories]
        
        # If no matches, take first 3 available categories
        if not bound_categories and categories:
            bound_categories = list(categories.keys())[:3]
        
        return bound_categories
    
    def generate_readme(self, project_config: Dict) -> str:
        """Generate README for project"""
        return f"""# {project_config['name']}

{project_config['description']}

## Project Details
- **Type**: {project_config['type']}
- **Workflow**: {project_config['workflow']}
- **Created**: {project_config['created_at']}
- **Directory**: `{project_config['directory']}`

## Bound Script Categories
{chr(10).join(f"- {cat}" for cat in project_config.get('bound_categories', []))}

## Directory Structure
{project_config['directory']}/
├── data/ # Project data files
├── scripts/ # Custom scripts
├── reports/ # Generated reports
└── docs/ # Documentation
## Getting Started
1. Review the bound script categories
2. Add your financial data to the `data/` directory
3. Modify `project.toml` for additional configuration
4. Run analysis using the Financial Brain system

## Available Scripts
Scripts are available from: `{project_config['scripts']['python_master_path']}`

---
*This project was created with Financial Brain Project Management System*
"""
    
    def interactive_workflow(self, project_config: Dict):
        """Run interactive workflow for project"""
        self.print_header(f"WORKFLOW: {project_config['name']}")
        
        workflows = {
            "financial_analysis": self.financial_analysis_workflow,
            "portfolio_management": self.portfolio_management_workflow,
            "loan_analysis": self.loan_analysis_workflow,
            "business_planning": self.business_planning_workflow,
            "custom": self.custom_workflow
        }
        
        workflow_func = workflows.get(
            project_config["workflow"],
            self.custom_workflow
        )
        
        return workflow_func(project_config)
    
    def financial_analysis_workflow(self, project_config: Dict) -> Dict:
        """Financial analysis workflow"""
        results = {
            "workflow": "financial_analysis",
            "steps_completed": [],
            "data_sources": [],
            "analyses_performed": [],
            "reports_generated": []
        }
        
        print("\n📊 FINANCIAL ANALYSIS WORKFLOW")
        
        # Step 1: Data source setup
        self.print_step(1, "Data Sources", "Specify financial data sources")
        
        data_sources = []
        while True:
            source = input("\nAdd data source (file path or description, empty to finish): ").strip()
            if not source:
                break
            
            if Path(source).exists():
                data_sources.append({
                    "type": "file",
                    "path": source,
                    "name": Path(source).name
                })
                print(f"  ✓ Added file: {Path(source).name}")
            else:
                data_sources.append({
                    "type": "description",
                    "description": source
                })
                print(f"  ✓ Added description: {source[:50]}...")
        
        results["data_sources"] = data_sources
        
        # Step 2: Analysis types
        self.print_step(2, "Analysis Types", "Select analyses to perform")
        
        analysis_options = [
            ("Trend Analysis", "Analyze financial trends over time"),
            ("Ratio Analysis", "Calculate key financial ratios"),
            ("Cash Flow Analysis", "Analyze cash inflows and outflows"),
            ("Risk Assessment", "Assess financial risks"),
            ("Scenario Modeling", "Model different financial scenarios")
        ]
        
        print("\nSelect analyses (comma-separated numbers):")
        for i, (name, desc) in enumerate(analysis_options, 1):
            print(f"  {i}. {name}: {desc}")
        
        while True:
            choices = input("\nChoices (1-5, comma-separated): ").strip()
            try:
                selected_indices = [int(c.strip()) - 1 for c in choices.split(',')]
                selected_analyses = [analysis_options[i][0] for i in selected_indices 
                                   if 0 <= i < len(analysis_options)]
                
                if selected_analyses:
                    results["analyses_performed"] = selected_analyses
                    break
                else:
                    print("❌ Please select at least one analysis")
            except ValueError:
                print("❌ Please enter valid numbers")
        
        # Step 3: Report generation
        self.print_step(3, "Report Generation", "Generate analysis reports")
        
        print("\nGenerating reports...")
        
        # Create sample reports
        report_dir = Path(project_config["directory"]) / "reports"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        reports = [
            f"financial_analysis_summary_{timestamp}.md",
            f"data_sources_{timestamp}.json",
            f"analysis_results_{timestamp}.json"
        ]
        
        for report in reports:
            report_path = report_dir / report
            with open(report_path, 'w') as f:
                f.write(f"# Report: {report}\n\nGenerated: {datetime.now().isoformat()}\n")
            
            results["reports_generated"].append(str(report_path))
            print(f"  ✓ Created: {report}")
        
        # Step 4: Next steps
        self.print_step(4, "Next Steps", "Recommended actions")
        
        print("\n📋 Recommended next steps:")
        print("  1. Review generated reports")
        print("  2. Run specific financial scripts from bound categories")
        print("  3. Set up automated analysis schedules")
        print("  4. Integrate with external data sources")
        
        results["steps_completed"] = ["data_sources", "analysis_selection", "report_generation"]
        
        return results
    
    def portfolio_management_workflow(self, project_config: Dict) -> Dict:
        """Portfolio management workflow"""
        # Similar structure to financial_analysis_workflow
        # Implementation would be specific to portfolio management
        pass
    
    def loan_analysis_workflow(self, project_config: Dict) -> Dict:
        """Loan analysis workflow"""
        # Similar structure
        pass
    
    def business_planning_workflow(self, project_config: Dict) -> Dict:
        """Business planning workflow"""
        # Similar structure
        pass
    
    def custom_workflow(self, project_config: Dict) -> Dict:
        """Custom workflow"""
        print("\n🔧 CUSTOM WORKFLOW")
        print("\nDefine your custom workflow steps:")
        
        steps = []
        step_num = 1
        
        while True:
            step_name = input(f"\nStep {step_num} name (or 'done' to finish): ").strip()
            if step_name.lower() == 'done':
                break
            
            step_desc = input(f"Step {step_num} description: ").strip()
            
            steps.append({
                "number": step_num,
                "name": step_name,
                "description": step_desc
            })
            
            step_num += 1
        
        print(f"\n✅ Defined {len(steps)} custom workflow steps")
        return {"workflow": "custom", "steps": steps}

# ============================================================================
# 4. MAIN CLI INTERFACE
# ============================================================================

def setup_argparse() -> argparse.ArgumentParser:
    """Setup argparse for CLI interface"""
    parser = argparse.ArgumentParser(
        description="Financial Project Management System - CLI Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run self-assessment with specific model
  python3 brain.py -h qwen2.5:0.5b --self-assessment
  
  # Setup with guided wizard
  python3 brain.py --setup
  
  # List available models
  python3 brain.py --list-models
  
  # Create project with specific model
  python3 brain.py --model llama2 --create-project "My Financial Analysis"
  
  # Run workflow non-interactively
  python3 brain.py --project "MyProject" --workflow financial_analysis
        """
    )
    
    # Model selection
    model_group = parser.add_argument_group('Model Selection')
    model_group.add_argument(
        '-m', '--model',
        help='Specify Ollama model to use'
    )
    model_group.add_argument(
        '--provider',
        default='ollama',
        choices=['ollama', 'gemini'],
        help='The provider to use for the assessment (default: ollama).'
    )
    model_group.add_argument(
        '--model-help',
        dest='model_help',
        metavar='MODEL',
        nargs='?',
        const='list',
        help='Show help for specific model or list available models'
    )
    
    # Assessment & Setup
    setup_group = parser.add_argument_group('Setup & Assessment')
    setup_group.add_argument(
        '--self-assessment',
        action='store_true',
        help='Run comprehensive self-assessment'
    )
    setup_group.add_argument(
        '--mode',
        default=None,
        choices=['onboarding', 'debug'],
        help='The mode for the self-assessment (e.g., onboarding, debug).'
    )
    setup_group.add_argument(
        '--target-file',
        help='The specific file to target for a debug self-assessment.'
    )
    setup_group.add_argument(
        '--setup',
        action='store_true',
        help='Run interactive setup wizard'
    )
    setup_group.add_argument(
        '--agribusiness',
        action='store_true',
        help='Run the specialized agribusiness onboarding and setup wizard.'
    )
    setup_group.add_argument(
        '--general-business',
        action='store_true',
        help='Indicate a general business query to route to local models.'
    )
    setup_group.add_argument(
        '--list-models',
        action='store_true',
        help='List available Ollama models'
    )
    
    # Project Management
    project_group = parser.add_argument_group('Project Management')
    project_group.add_argument(
        '--create-project',
        metavar='NAME',
        help='Create new project with given name'
    )
    project_group.add_argument(
        '--project',
        help='Use existing project'
    )
    project_group.add_argument(
        '--workflow',
        choices=['financial_analysis', 'portfolio_management', 
                 'loan_analysis', 'business_planning', 'custom'],
        help='Run specific workflow'
    )
    
    # Script Management
    script_group = parser.add_argument_group('Script Management')
    script_group.add_argument(
        '--list-scripts',
        action='store_true',
        help='List available scripts by category'
    )
    script_group.add_argument(
        '--bind-scripts',
        metavar='CATEGORIES',
        help='Bind script categories to project (comma-separated)'
    )
    
    # Output & Configuration
    config_group = parser.add_argument_group('Output & Configuration')
    config_group.add_argument(
        '--agent-mode',
        action='store_true',
        help='Enable non-interactive mode for agent-driven scripting.'
    )
    config_group.add_argument(
        '--show-context',
        action='store_true',
        help='Display the full AI prompt context before execution.'
    )
    config_group.add_argument(
        '--session-id',
        help='The ID of an ongoing conversational session.'
    )
    config_group.add_argument(
        '--reply',
        help='The user/agent reply for the current turn of a conversation.'
    )
    config_group.add_argument(
        '--config-path',
        help='Alternative config path'
    )
    config_group.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    config_group.add_argument(
        '--verbose', '-v',
        action='count',
        default=0,
        help='Increase verbosity'
    )
    config_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-essential output'
    )
    
    return parser

def handle_model_help(args, ollama_manager: OllamaManager):
    """Handle model help request"""
    if args.model_help == 'list' or not args.model_help:
        print("\n📋 Available Ollama Models:")
        print("="*50)
        
        models = ollama_manager.get_available_models()
        
        if not models:
            print("No models found. Try: ollama pull llama2")
            return
        
        for model in models:
            print(f"  • {model}")
        
        print("\nTo use a model:")
        print("  python3 brain.py --model MODEL_NAME")
        print("\nFor model help:")
        print("  python3 brain.py -h MODEL_NAME")
    
    else:
        # Specific model help
        model_name = args.model_help
        if ollama_manager.model_exists(model_name):
            print(f"\n🧠 Model: {model_name}")
            print("="*50)
            print(f"\nTo use this model:")
            print(f"  python3 brain.py --model {model_name}")
            
            # Run quick assessment
            print(f"\nRunning quick assessment...")
            assessment = ollama_manager.run_model_assessment(model_name)
            
            print(f"\nAssessment Status: {assessment['status']}")
            
            if assessment['recommendations']:
                print("\nRecommendations for this model:")
                for rec in assessment['recommendations'][:3]:  # Show top 3
                    print(f"  • {rec}")
        else:
            print(f"❌ Model '{model_name}' not found")
            print("\nAvailable models:")
            models = ollama_manager.get_available_models()
            for model in models[:5]:  # Show first 5
                print(f"  • {model}")

def handle_self_assessment(args, config: ConfigManager, ollama_manager: OllamaManager):
    """Handle self-assessment request, now with provider logic."""
    if args.provider == 'gemini':
        print("\n🧠 Running Self-Assessment with provider: Gemini")
        print("="*60)
        try:
            from modules.dev_tools.context_aggregator import aggregate_context, create_ai_review_prompt
            from modules.quick_clip.providers import get_provider
            from modules.ag_onboarding import OnboardingReviewWorkflow # New import
        except ImportError as e:
            print(f"❌ Error: Could not import necessary modules for Gemini review: {e}", file=sys.stderr)
            return

        is_first_session = not config.manifest.get("projects_created")
        
        # Determine the user request based on the mode
        if args.mode == 'debug':
            if not args.target_file:
                print("❌ Error: The --target-file argument is required for debug mode.", file=sys.stderr)
                return
            from modules.dev_tools.debug_workflow import DebugReviewWorkflow
            debug_review = DebugReviewWorkflow(target_file=args.target_file, agent_mode=args.agent_mode)
            ai_prompt = debug_review.run() # The workflow now generates the full prompt
            
        elif is_first_session or args.mode == 'onboarding':
            onboarding_review = OnboardingReviewWorkflow(config, agent_mode=args.agent_mode)
            user_request = onboarding_review.run()
            # Still need to aggregate and create the final prompt
            target_file = project_root / "modules" / "brain.py"
            context = aggregate_context(
                target_file_path_str=str(target_file),
                user_request=user_request,
                project_dir=project_root,
                enable_analysis=False
            )
            ai_prompt = create_ai_review_prompt(context)
        else:
            # Default generic self-assessment
            user_request = "This is a request for a general self-assessment of the main orchestrator script ('brain.py')."
            target_file = project_root / "modules" / "brain.py"
            context = aggregate_context(
                target_file_path_str=str(target_file),
                user_request=user_request,
                project_dir=project_root,
                enable_analysis=False
            )
            ai_prompt = create_ai_review_prompt(context)

        print("\n[2/2] Handing off to Gemini provider...")
        gemini_provider = get_provider('gemini')
        if not gemini_provider:
            print("❌ Error: Gemini provider not found.", file=sys.stderr)
            return
            
        try:
            result_message = gemini_provider.execute(ai_prompt, args)
            print(f"\n✅ {result_message}")
            if not args.agent_mode:
                print("\n" + "="*60)
                print("➡️ Your turn: Please run the suggested `gemini-cli` command in a new terminal to complete the review.")
                print("="*60)
        except Exception as e:
            print(f"❌ An error occurred during Gemini provider execution: {e}", file=sys.stderr)

    else: # Default to original Ollama assessment
        model_name = args.model or config.config["model"]["default"]
        
        print(f"\n🧠 Running Self-Assessment with model: {model_name}")
        print("="*60)
        
        print("\n[1/3] System Check...")
        if not ollama_manager.check_ollama_installed():
            print("❌ Ollama not found")
            return
        print("✅ Ollama is installed")
        
        print("\n[2/3] Model Check...")
        if not ollama_manager.model_exists(model_name):
            print(f"❌ Model '{model_name}' not found")
            return
        print(f"✅ Model '{model_name}' is available")
        
        print("\n[3/3] Running Assessment...")
        assessment = ollama_manager.run_model_assessment(model_name)
        
        print(f"\n📊 Assessment Results:")
        print(f"  Status: {assessment['status']}")
        if assessment['checks']:
            print(f"\n  Checks Performed:")
            for check in assessment['checks']:
                status_icon = "✅" if check['status'] == 'pass' else "❌"
                print(f"    {status_icon} {check['name']}: {check['message']}")
        if assessment['recommendations']:
            print(f"\n  Recommendations:")
            for i, rec in enumerate(assessment['recommendations'], 1):
                print(f"    {i}. {rec}")
        
        config.update_manifest({"last_assessment": assessment})
        print(f"\n✅ Assessment complete. Results saved to manifest.")

def handle_setup(args, config: ConfigManager, ollama_manager: OllamaManager):
    """Handle setup wizard"""
    print("\n" + "="*60)
    print("FINANCIAL BRAIN - SETUP WIZARD")
    print("="*60)
    
    # Step 1: Model setup
    print("\n[1/4] Model Configuration")
    print("-"*30)
    
    if args.model:
        model_name = args.model
        if not ollama_manager.model_exists(model_name):
            print(f"❌ Model '{model_name}' not found")
            model_name = ollama_manager.guided_model_setup()
        else:
            print(f"✅ Using model: {model_name}")
    else:
        model_name = ollama_manager.guided_model_setup()
    
    # Step 2: Directory setup
    print("\n[2/4] Directory Configuration")
    print("-"*30)
    
    python_master_path = input(f"Path to Python-master directory [{config.config['scripts']['python_master_path']}]: ").strip()
    if python_master_path:
        config.config["scripts"]["python_master_path"] = python_master_path
    
    project_base = input(f"Base directory for projects [{config.config['project']['base_dir']}]: ").strip()
    if project_base:
        config.config["project"]["base_dir"] = project_base
    
    # Step 3: Discover scripts
    print("\n[3/4] Script Discovery")
    print("-"*30)
    
    python_master_dir = Path(config.config["scripts"]["python_master_path"])
    if python_master_dir.exists():
        categories = config.discover_scripts_by_category(python_master_dir)
        print(f"✅ Found {len(categories)} script categories:")
        for cat, scripts in list(categories.items())[:5]:  # Show first 5
            print(f"  • {cat}: {len(scripts)} scripts")
        
        if len(categories) > 5:
            print(f"  ... and {len(categories) - 5} more")
    else:
        print(f"⚠️ Directory not found: {python_master_dir}")
    
    # Step 4: Save configuration
    print("\n[4/4] Saving Configuration")
    print("-"*30)
    
    config.save_config()
    config.save_manifest()
    
    print("\n✅ Setup complete!")
    print(f"\nConfiguration saved to: {config.config_file}")
    print(f"Manifest saved to: {config.manifest_file}")
    
    # Offer to create first project
    create_project = input("\nCreate your first project? (y/n): ").strip().lower()
    if create_project == 'y':
        workflow = CLIWorkflow(config, ollama_manager)
        project_config = workflow.guided_project_setup()
        
        print(f"\n🎉 Setup complete! You can now run:")
        print(f"  python3 brain.py --project '{project_config['name']}' --workflow {project_config['workflow']}")

def main():
    """Main CLI entry point"""
    # Try to import the AgWorkflow for the new functionality
    try:
        from modules.ag_onboarding import AgWorkflow
    except ImportError:
        AgWorkflow = None

    # Parse arguments
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Initialize configuration
    config_path = Path(args.config_path) if args.config_path else None
    config = ConfigManager(config_path)
    
    # Ensure the correct Python-master path is always used
    config.config["scripts"]["python_master_path"] = str(project_root / "modules" / "Python-master")
    
    # Initialize Ollama manager
    ollama_manager = OllamaManager(config)
    
    # Handle model help request
    if args.model_help:
        handle_model_help(args, ollama_manager)
        return
    
    # Handle list models
    if args.list_models:
        models = ollama_manager.get_available_models()
        if models:
            print("Available models:")
            for model in models:
                print(f"  • {model}")
        else:
            print("No models found. Try: ollama pull llama2")
        return
    
    # Handle list scripts
    if args.list_scripts:
        python_master_path = Path(config.config["scripts"]["python_master_path"])
        if python_master_path.exists():
            categories = config.discover_scripts_by_category(python_master_path)
            print("Available script categories:")
            for category, scripts in categories.items():
                print(f"\n{category}:")
                for script in scripts[:10]:  # Show first 10 scripts
                    print(f"  • {script}")
                if len(scripts) > 10:
                    print(f"  ... and {len(scripts) - 10} more")
        else:
            print(f"Directory not found: {python_master_path}")
        return
    
    # Handle self-assessment
    if args.self_assessment:
        handle_self_assessment(args, config, ollama_manager)
        return
    
    # Handle agribusiness onboarding
    if args.agribusiness:
        sm = SessionManager(config)
        
        # Check if we should use the conversational flow (Architect)
        # Default to conversational if new session, session_id provided, or Gemini selected
        has_internet = check_internet_connection()
        existing_sessions = list(sm.session_dir.glob("*.json"))
        
        if args.provider == 'gemini' or args.session_id or (not existing_sessions and has_internet):
            handle_conversational_onboarding(args, config, sm)
            return

        # Fallback to the classic Interactive Wizard if specified or offline
        if AgWorkflow and KnowledgeForgeApp:
            print("Launching Classic Agribusiness Wizard (Offline/Fallback)...")
            app = KnowledgeForgeApp(base_path=project_root / "knowledge_forge_data") 
            ag_workflow = AgWorkflow(config, ollama_manager, app)
            ag_workflow.guided_project_setup()
        else:
            print("Error: Agribusiness workflow or Ag_ForgeApp module could not be loaded.", file=sys.stderr)
        return

    # Handle setup wizard
    if args.setup:
        handle_setup(args, config, ollama_manager)
        return
    
    # Handle project creation
    if args.create_project:
        workflow = CLIWorkflow(config, ollama_manager)
        
        # Quick project creation
        project_config = {
            "name": args.create_project,
            "description": "Created via CLI",
            "type": "Financial Analysis",
            "workflow": args.workflow or "financial_analysis"
        }
        
        # Create project directory
        base_dir = Path(config.config["project"]["base_dir"])
        base_dir.mkdir(exist_ok=True)
        
        project_dir = base_dir / args.create_project.lower().replace(' ', '_')
        project_dir.mkdir(exist_ok=True)
        
        # Save project config
        config_file = project_dir / "project.toml"
        with open(config_file, 'w') as f:
            toml.dump(project_config, f)
        
        print(f"✅ Project created: {project_dir}")
        
        # Offer to run workflow
        if args.workflow:
            run_now = input(f"\nRun '{args.workflow}' workflow now? (y/n): ").strip().lower()
            if run_now == 'y':
                results = workflow.interactive_workflow(project_config)
                print(f"\n✅ Workflow completed. Results: {len(results.get('steps_completed', []))} steps")
        return
    
    # Handle project workflow
    if args.project and args.workflow:
        workflow = CLIWorkflow(config, ollama_manager)
        
        # Load project config
        base_dir = Path(config.config["project"]["base_dir"])
        project_dir = base_dir / args.project.lower().replace(' ', '_')
        config_file = project_dir / "project.toml"
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                project_config = toml.load(f)
            
            print(f"🚀 Running '{args.workflow}' workflow for project: {args.project}")
            results = workflow.interactive_workflow(project_config)
            print(f"\n✅ Workflow completed successfully!")
        else:
            print(f"❌ Project not found: {args.project}")
            print(f"Looked for: {config_file}")
        return
    
    # Default: Show help if no arguments
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n" + "="*60)
        print("Quick Start:")
        print("  1. Run setup: python3 brain.py --setup")
        print("  2. Create project: python3 brain.py --create-project 'MyProject'")
        print("  3. Run workflow: python3 brain.py --project MyProject --workflow financial_analysis")
    else:
        # If arguments were provided but not handled, show help
        parser.print_help()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if __debug__:
            import traceback
            traceback.print_exc()
        sys.exit(1)