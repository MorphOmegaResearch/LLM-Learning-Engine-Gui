#!/usr/bin/env python3
"""
Knowledge Forge AI Orchestrator
--------------------------------
Local AI assistant with Ollama integration for agricultural knowledge management.
Provides intelligent context management, task queuing, document generation,
and seamless integration with the main Knowledge Forge application.
"""

import json
import os
import sys
import subprocess
import threading
import queue
import asyncio
import tempfile
import webbrowser
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import uuid
import requests
import re
import shutil

# Try to import Ollama API client
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    # Create a stub for when ollama isn't installed
    class OllamaStub:
        class Client:
            def list(self):
                return {'models': []}
            
            def generate(self, model, prompt, **kwargs):
                return {'response': f"Ollama not available. Install via 'curl -fsSL https://ollama.com/install.sh | sh'"}
        
        def list(self):
            return {'models': []}
    
    ollama = OllamaStub()

# ---------------------------------------------------------------------------
# Configuration & Data Models
# ---------------------------------------------------------------------------

class ModelCapability(Enum):
    CHAT = "chat"
    TOOLS = "tool_calling"
    DOCUMENT_WRITING = "document_writing"
    CODE_GENERATION = "code_generation"
    ANALYSIS = "analysis"
    PLANNING = "planning"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass
class ModelProfile:
    name: str
    model_id: str  # Ollama model name
    capabilities: List[ModelCapability]
    context_size: int = 2048
    temperature: float = 0.7
    max_tokens: int = 512
    is_default: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ContextChunk:
    id: str
    content: str
    source: str  # 'chat', 'document', 'entity', 'task', 'research'
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 1.0

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    requires_confirmation: bool = False

@dataclass
class Task:
    id: str
    title: str
    description: str
    status: TaskStatus
    created_at: str
    updated_at: str
    assigned_to: Optional[str] = None  # Model profile name
    dependencies: List[str] = field(default_factory=list)
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    priority: int = 5  # 1-10, 10 being highest

@dataclass
class ConversationTurn:
    role: MessageRole
    content: str
    timestamp: str
    context_references: List[str] = field(default_factory=list)
    tool_calls: List[Dict] = field(default_factory=list)
    tool_results: List[Dict] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Core Orchestrator
# ---------------------------------------------------------------------------

class AIOrchestrator:
    """Main orchestrator for local AI integration"""
    
    def __init__(self, base_path: Path, session_token: str):
        self.base_path = base_path.resolve()
        self.session_token = session_token
        self.config_path = base_path / "orchestrator_config.json"
        self.context_path = base_path / "context_store"
        self.tasks_path = base_path / "tasks"
        
        # Initialize directories
        self.context_path.mkdir(exist_ok=True)
        self.tasks_path.mkdir(exist_ok=True)
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize components
        self.model_profiles: Dict[str, ModelProfile] = {}
        self.context_store: Dict[str, ContextChunk] = {}
        self.tasks: Dict[str, Task] = {}
        self.tools: Dict[str, ToolDefinition] = {}
        self.conversation_history: List[ConversationTurn] = []
        
        # Current state
        self.current_model: Optional[str] = None
        self.active_context_window: List[ContextChunk] = []
        self.context_window_size = 10
        
        # Threading
        self.task_queue = queue.Queue()
        self.task_worker = None
        self.stop_worker = threading.Event()
        
        # Initialize
        self._load_model_profiles()
        self._load_tasks()
        self._load_context_store()
        self._register_default_tools()
        
        # Start task worker
        self._start_task_worker()
    
    def _load_config(self) -> Dict:
        """Load or create configuration"""
        default_config = {
            "ollama_endpoint": "http://localhost:11434",
            "default_model": "qwen2.5:0.5b",
            "context_retention_days": 30,
            "auto_save_interval": 300,  # seconds
            "max_conversation_turns": 50,
            "tool_timeout": 30,
            "enable_auto_context": True,
            "enable_tool_calling": True,
            "knowledge_forge_path": str(self.base_path)
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except:
                return default_config
        else:
            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def _load_model_profiles(self):
        """Load available model profiles"""
        # Default profiles
        default_profiles = [
            ModelProfile(
                name="Qwen Quick Assistant",
                model_id="qwen2.5:0.5b",
                capabilities=[
                    ModelCapability.CHAT,
                    ModelCapability.TOOLS,
                    ModelCapability.DOCUMENT_WRITING
                ],
                context_size=2048,
                temperature=0.7,
                is_default=True
            ),
            ModelProfile(
                name="Code Specialist",
                model_id="codellama:7b",
                capabilities=[
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.ANALYSIS
                ],
                context_size=4096,
                temperature=0.3
            ),
            ModelProfile(
                name="Research Assistant",
                model_id="llama3.2:latest",
                capabilities=[
                    ModelCapability.ANALYSIS,
                    ModelCapability.PLANNING,
                    ModelCapability.DOCUMENT_WRITING
                ],
                context_size=8192,
                temperature=0.5
            )
        ]
        
        # Try to get actual Ollama models
        try:
            if OLLAMA_AVAILABLE:
                client = ollama.Client(host=self.config['ollama_endpoint'])
                available_models = client.list()
                
                for model in available_models.get('models', []):
                    profile = ModelProfile(
                        name=model['name'].replace(':', ' ').title(),
                        model_id=model['name'],
                        capabilities=[ModelCapability.CHAT],
                        context_size=model.get('size', 2048) // 1000000,  # Convert to MB
                        is_default=False
                    )
                    self.model_profiles[model['name']] = profile
            else:
                # Use defaults if Ollama not available
                for profile in default_profiles:
                    self.model_profiles[profile.model_id] = profile
        except:
            # Fall back to defaults
            for profile in default_profiles:
                self.model_profiles[profile.model_id] = profile
        
        # Set default model
        if self.config['default_model'] in self.model_profiles:
            self.current_model = self.config['default_model']
        elif self.model_profiles:
            self.current_model = next(iter(self.model_profiles.keys()))
    
    def _load_tasks(self):
        """Load tasks from storage"""
        task_files = self.tasks_path.glob("*.json")
        for task_file in task_files:
            try:
                with open(task_file, 'r') as f:
                    task_data = json.load(f)
                    task = Task(**task_data)
                    self.tasks[task.id] = task
            except:
                continue
    
    def _load_context_store(self):
        """Load context chunks from storage"""
        context_files = self.context_path.glob("*.json")
        for context_file in context_files:
            try:
                with open(context_file, 'r') as f:
                    data = json.load(f)
                    chunk = ContextChunk(**data)
                    self.context_store[chunk.id] = chunk
            except:
                continue
    
    def _register_default_tools(self):
        """Register default tools for the AI"""
        
        # File system tools
        self.register_tool(ToolDefinition(
            name="list_directory",
            description="List contents of a directory",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            },
            function=self.tool_list_directory,
            requires_confirmation=False
        ))
        
        self.register_tool(ToolDefinition(
            name="open_file",
            description="Open a file in default application",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            },
            function=self.tool_open_file,
            requires_confirmation=True
        ))
        
        self.register_tool(ToolDefinition(
            name="create_document",
            description="Create a new document with content",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Document title"},
                    "content": {"type": "string", "description": "Document content"},
                    "category": {"type": "string", "description": "Category/folder"}
                },
                "required": ["title", "content"]
            },
            function=self.tool_create_document,
            requires_confirmation=True
        ))
        
        self.register_tool(ToolDefinition(
            name="search_knowledge",
            description="Search knowledge base for information",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "category": {"type": "string", "description": "Category to search in"}
                },
                "required": ["query"]
            },
            function=self.tool_search_knowledge,
            requires_confirmation=False
        ))
        
        self.register_tool(ToolDefinition(
            name="execute_command",
            description="Execute a system command",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                    "working_dir": {"type": "string", "description": "Working directory"}
                },
                "required": ["command"]
            },
            function=self.tool_execute_command,
            requires_confirmation=True
        ))
        
        self.register_tool(ToolDefinition(
            name="fetch_webpage",
            description="Fetch content from a webpage",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Webpage URL"}
                },
                "required": ["url"]
            },
            function=self.tool_fetch_webpage,
            requires_confirmation=True
        ))
        
        self.register_tool(ToolDefinition(
            name="create_task",
            description="Create a new task for later execution",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task description"},
                    "priority": {"type": "integer", "description": "Priority (1-10)"}
                },
                "required": ["title", "description"]
            },
            function=self.tool_create_task,
            requires_confirmation=False
        ))
    
    def register_tool(self, tool: ToolDefinition):
        """Register a new tool"""
        self.tools[tool.name] = tool
    
    def _start_task_worker(self):
        """Start background task worker"""
        if self.task_worker is None or not self.task_worker.is_alive():
            self.task_worker = threading.Thread(
                target=self._process_task_queue,
                daemon=True
            )
            self.task_worker.start()

    def _is_path_safe(self, path: str) -> bool:
        """Check if path is within base_path"""
        try:
            target = Path(path).expanduser().resolve()
            return self.base_path in target.parents or target == self.base_path
        except:
            return False
    
    def _process_task_queue(self):
        """Process tasks from the queue"""
        while not self.stop_worker.is_set():
            try:
                task_id = self.task_queue.get(timeout=1)
                if task_id in self.tasks:
                    self._execute_task(task_id)
                self.task_queue.task_done()
            except queue.Empty:
                continue
    
    def _execute_task(self, task_id: str):
        """Execute a task"""
        task = self.tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.now().isoformat()
        self._save_task(task)
        
        try:
            # Task execution logic would go here
            # For now, just mark as completed
            task.status = TaskStatus.COMPLETED
            task.updated_at = datetime.now().isoformat()
            task.results = {"message": "Task completed successfully"}
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.updated_at = datetime.now().isoformat()
        
        self._save_task(task)
    
    # -----------------------------------------------------------------------
    # Tool Implementations
    # -----------------------------------------------------------------------
    
    def tool_list_directory(self, path: str) -> Dict:
        """List directory contents (Restricted)"""
        if not self._is_path_safe(path):
             return {"error": "Access Denied: Path outside knowledge base."}
        
        try:
            target_path = Path(path).expanduser()
            if not target_path.exists():
                return {"error": f"Path does not exist: {path}"}
            
            items = []
            for item in target_path.iterdir():
                items.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                    "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                })
            
            return {
                "path": str(target_path),
                "items": items,
                "count": len(items)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def tool_open_file(self, path: str) -> Dict:
        """Open file in default application (Restricted)"""
        if not self._is_path_safe(path):
             return {"error": "Access Denied: Path outside knowledge base."}
        
        try:
            target_path = Path(path).expanduser()
            if not target_path.exists():
                return {"error": f"File does not exist: {path}"}
            
            if sys.platform == "win32":
                os.startfile(target_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(target_path)])
            else:
                subprocess.run(["xdg-open", str(target_path)])
            
            return {"success": True, "file": str(target_path)}
        except Exception as e:
            return {"error": str(e)}
    
    def tool_create_document(self, title: str, content: str, category: Optional[str] = None) -> Dict:
        """Create a new document"""
        try:
            # Sanitize title for filename
            safe_title = re.sub(r'[^\w\-_\. ]', '_', title)
            safe_title = safe_title[:100]  # Limit length
            
            # Determine directory
            if category:
                doc_dir = self.base_path / "documents" / category
            else:
                doc_dir = self.base_path / "documents"
            
            doc_dir.mkdir(exist_ok=True, parents=True)
            
            # Create file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_title}_{timestamp}.md"
            filepath = doc_dir / filename
            
            # Write content with frontmatter
            frontmatter = f"""---
title: {title}
created: {datetime.now().isoformat()}
category: {category or 'general'}
---

{content}
"""
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(frontmatter)
            
            # Add to context store
            chunk_id = f"doc_{uuid.uuid4().hex[:8]}"
            self.add_context_chunk(
                content=content,
                source="document",
                metadata={
                    "title": title,
                    "path": str(filepath),
                    "category": category
                }
            )
            
            return {
                "success": True,
                "path": str(filepath),
                "title": title,
                "context_id": chunk_id
            }
        except Exception as e:
            return {"error": str(e)}
    
    def tool_search_knowledge(self, query: str, category: Optional[str] = None) -> Dict:
        """Search knowledge base"""
        try:
            results = []
            
            # Search context store
            for chunk_id, chunk in self.context_store.items():
                if query.lower() in chunk.content.lower():
                    if category and chunk.metadata.get('category') != category:
                        continue
                    
                    results.append({
                        "id": chunk_id,
                        "content_preview": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                        "source": chunk.source,
                        "relevance": chunk.relevance_score,
                        "metadata": chunk.metadata
                    })
            
            # Search document files
            search_dir = self.base_path / "documents"
            if category:
                search_dir = search_dir / category
            
            if search_dir.exists():
                for doc_file in search_dir.glob("**/*.md"):
                    try:
                        content = doc_file.read_text(encoding='utf-8')
                        if query.lower() in content.lower():
                            results.append({
                                "id": f"file_{doc_file.name}",
                                "content_preview": content[:200] + "..." if len(content) > 200 else content,
                                "source": "document_file",
                                "path": str(doc_file),
                                "relevance": 0.8  # Slightly lower than context store
                            })
                    except:
                        continue
            
            return {
                "query": query,
                "results": sorted(results, key=lambda x: x['relevance'], reverse=True)[:10],
                "count": len(results)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def tool_execute_command(self, command: str, working_dir: Optional[str] = None) -> Dict:
        """Execute a system command"""
        try:
            cwd = Path(working_dir).expanduser() if working_dir else self.base_path
            
            # Security check - prevent dangerous commands
            dangerous_patterns = [
                r"rm\s+-rf", r"dd\s+if=", r">\s+/dev/", 
                r":\(\)\{.*\}",  # Fork bomb pattern
                r"chmod\s+777", r"chown\s+root"
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, command, re.IGNORECASE):
                    return {"error": "Command contains potentially dangerous pattern"}
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.config.get("tool_timeout", 30)
            )
            
            return {
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out"}
        except Exception as e:
            return {"error": str(e)}
    
    def tool_fetch_webpage(self, url: str) -> Dict:
        """Fetch webpage content"""
        import urllib.robotparser
        from urllib.parse import urlparse
        
        try:
            # Check robots.txt
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            robots_url = f"{base_url}/robots.txt"
            
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                if not rp.can_fetch("*", url):
                    return {"error": "Access denied by robots.txt"}
            except:
                # If robots.txt fetch fails, we proceed with caution or assume allowed 
                # (standard behavior is usually permissive if no robots.txt found)
                pass

            # Simple fetch with requests
            headers = {'User-Agent': 'KnowledgeForgeBot/1.0 (Research Prototype)'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Extract text content (simplified)
            content = response.text[:5000]  # Limit size
            
            # Add to context store
            chunk_id = self.add_context_chunk(
                content=content[:1000],  # Store first 1000 chars
                source="webpage",
                metadata={
                    "url": url,
                    "status_code": response.status_code,
                    "content_type": response.headers.get('content-type')
                }
            )
            
            return {
                "url": url,
                "status_code": response.status_code,
                "content_length": len(content),
                "content_preview": content[:500],
                "context_id": chunk_id
            }
        except Exception as e:
            return {"error": str(e)}
    
    def tool_create_task(self, title: str, description: str, priority: int = 5) -> Dict:
        """Create a new task"""
        try:
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            task = Task(
                id=task_id,
                title=title,
                description=description,
                status=TaskStatus.PENDING,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                priority=priority
            )
            
            self.tasks[task_id] = task
            self._save_task(task)
            
            # Add to task queue
            self.task_queue.put(task_id)
            
            return {
                "task_id": task_id,
                "title": title,
                "status": task.status.value,
                "message": "Task created and queued"
            }
        except Exception as e:
            return {"error": str(e)}
    
    # -----------------------------------------------------------------------
    # Context Management
    # -----------------------------------------------------------------------
    
    def add_context_chunk(self, content: str, source: str, metadata: Optional[Dict] = None) -> str:
        """Add a chunk to context store"""
        chunk_id = f"ctx_{uuid.uuid4().hex[:8]}"
        chunk = ContextChunk(
            id=chunk_id,
            content=content,
            source=source,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {},
            relevance_score=1.0
        )
        
        self.context_store[chunk_id] = chunk
        
        # Save to disk
        chunk_file = self.context_path / f"{chunk_id}.json"
        with open(chunk_file, 'w') as f:
            json.dump(asdict(chunk), f, indent=2)
        
        # Update active context window
        self.active_context_window.insert(0, chunk)
        if len(self.active_context_window) > self.context_window_size:
            self.active_context_window.pop()
        
        return chunk_id
    
    def get_relevant_context(self, query: str, limit: int = 5) -> List[ContextChunk]:
        """Get context chunks relevant to query"""
        # Simple keyword matching for now
        # In production, could use embeddings
        query_words = set(query.lower().split())
        
        scored_chunks = []
        for chunk in self.context_store.values():
            content_words = set(chunk.content.lower().split())
            overlap = len(query_words.intersection(content_words))
            score = overlap / max(len(query_words), 1)
            
            if score > 0:
                chunk.relevance_score = score
                scored_chunks.append(chunk)
        
        # Sort by relevance and recency
        scored_chunks.sort(key=lambda x: (
            x.relevance_score,
            datetime.fromisoformat(x.timestamp).timestamp()
        ), reverse=True)
        
        return scored_chunks[:limit]
    
    def build_context_prompt(self, user_input: str, include_tools: bool = True) -> str:
        """Build a comprehensive context prompt"""
        system_prompt = f"""You are an agricultural knowledge assistant. Current time: {datetime.now().isoformat()}

KNOWLEDGE BASE CONTEXT:
{self._format_active_context()}

AVAILABLE TOOLS:
{self._format_tools() if include_tools else "No tools available"}

INSTRUCTIONS:
1. Answer questions using the provided context
2. Use tools when helpful (specify parameters)
3. Be concise and factual
4. Acknowledge uncertainty
5. Suggest next steps when appropriate

USER QUERY: {user_input}

RESPONSE FORMAT:
If using tools, format as: TOOL_CALL {{"name": "tool_name", "arguments": {{...}}}}
Otherwise, provide a helpful response."""

        return system_prompt
    
    def _format_active_context(self) -> str:
        """Format active context for prompt"""
        if not self.active_context_window:
            return "No active context."
        
        context_lines = []
        for i, chunk in enumerate(self.active_context_window):
            source_info = f"[{chunk.source.upper()}]"
            if 'title' in chunk.metadata:
                source_info += f" {chunk.metadata['title']}"
            
            context_lines.append(f"{i+1}. {source_info}: {chunk.content[:200]}...")
        
        return "\n".join(context_lines)
    
    def _format_tools(self) -> str:
        """Format tool descriptions for prompt"""
        tool_descriptions = []
        for name, tool in self.tools.items():
            param_desc = json.dumps(tool.parameters, indent=2)
            tool_descriptions.append(f"- {name}: {tool.description}\n  Parameters: {param_desc}")
        
        return "\n".join(tool_descriptions)
    
    # -----------------------------------------------------------------------
    # AI Interaction
    # -----------------------------------------------------------------------
    
    def generate_response(self, user_input: str, use_tools: bool = True) -> Dict:
        """Generate AI response with context"""
        if not self.current_model:
            return {"error": "No model selected"}
        
        try:
            # Build context-aware prompt
            prompt = self.build_context_prompt(user_input, include_tools=use_tools)
            
            # Add to conversation history
            user_turn = ConversationTurn(
                role=MessageRole.USER,
                content=user_input,
                timestamp=datetime.now().isoformat()
            )
            self.conversation_history.append(user_turn)
            
            # Get response from Ollama
            if OLLAMA_AVAILABLE:
                client = ollama.Client(host=self.config['ollama_endpoint'])
                response = client.generate(
                    model=self.current_model,
                    prompt=prompt,
                    options={
                        'temperature': self.model_profiles[self.current_model].temperature,
                        'num_predict': self.model_profiles[self.current_model].max_tokens
                    }
                )
                
                response_text = response['response']
            else:
                response_text = "Ollama not available. Please install Ollama first."
            
            # Parse for tool calls
            tool_calls = self._parse_tool_calls(response_text)
            
            # Execute tool calls if any
            tool_results = []
            if tool_calls and use_tools:
                for tool_call in tool_calls:
                    result = self._execute_tool_call(tool_call)
                    tool_results.append(result)
            
            # Add assistant response to history
            assistant_turn = ConversationTurn(
                role=MessageRole.ASSISTANT,
                content=response_text,
                timestamp=datetime.now().isoformat(),
                tool_calls=tool_calls,
                tool_results=tool_results
            )
            self.conversation_history.append(assistant_turn)
            
            # Add response to context store
            self.add_context_chunk(
                content=response_text,
                source="assistant_response",
                metadata={
                    "user_query": user_input,
                    "model": self.current_model,
                    "has_tools": bool(tool_calls)
                }
            )
            
            return {
                "response": response_text,
                "tool_calls": tool_calls,
                "tool_results": tool_results,
                "context_added": True
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _parse_tool_calls(self, response: str) -> List[Dict]:
        """Parse tool calls from response text"""
        tool_calls = []
        
        # Look for TOOL_CALL pattern
        pattern = r'TOOL_CALL\s*(\{.*?\})'
        matches = re.findall(pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                tool_call = json.loads(match)
                if isinstance(tool_call, dict) and 'name' in tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue
        
        return tool_calls
    
    def _execute_tool_call(self, tool_call: Dict) -> Dict:
        """Execute a tool call"""
        tool_name = tool_call.get('name')
        arguments = tool_call.get('arguments', {})
        
        if tool_name not in self.tools:
            return {
                "tool": tool_name,
                "error": f"Tool not found: {tool_name}"
            }
        
        tool = self.tools[tool_name]
        
        try:
            # Execute tool function
            result = tool.function(**arguments)
            
            # Add result to context store
            self.add_context_chunk(
                content=f"Tool {tool_name} executed with result: {json.dumps(result, indent=2)[:500]}",
                source="tool_result",
                metadata={
                    "tool": tool_name,
                    "arguments": arguments,
                    "success": 'error' not in result
                }
            )
            
            return {
                "tool": tool_name,
                "result": result,
                "success": True
            }
        except Exception as e:
            return {
                "tool": tool_name,
                "error": str(e),
                "success": False
            }
    
    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------
    
    def _save_task(self, task: Task):
        """Save task to disk"""
        task_file = self.tasks_path / f"{task.id}.json"
        with open(task_file, 'w') as f:
            json.dump(asdict(task), f, indent=2)
    
    def get_models(self) -> List[Dict]:
        """Get list of available models"""
        models = []
        for model_id, profile in self.model_profiles.items():
            models.append({
                "id": model_id,
                "name": profile.name,
                "capabilities": [c.value for c in profile.capabilities],
                "context_size": profile.context_size,
                "is_default": profile.is_default
            })
        return models
    
    def set_model(self, model_id: str):
        """Set current model"""
        if model_id in self.model_profiles:
            self.current_model = model_id
            self.config['default_model'] = model_id
            self._save_config()
            return True
        return False
    
    def get_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """Get tasks, optionally filtered by status"""
        if status:
            return [t for t in self.tasks.values() if t.status == status]
        return list(self.tasks.values())
    
    def _save_config(self):
        """Save configuration"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def install_model(self, model_name: str) -> Dict:
        """Install an Ollama model"""
        try:
            if not OLLAMA_AVAILABLE:
                return {"error": "Ollama not available"}
            
            # Execute ollama pull command
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Refresh model list
                self._load_model_profiles()
                return {
                    "success": True,
                    "model": model_name,
                    "output": result.stdout
                }
            else:
                return {
                    "error": f"Failed to install model: {result.stderr}"
                }
        except subprocess.TimeoutExpired:
            return {"error": "Installation timed out"}
        except Exception as e:
            return {"error": str(e)}
    
    def cleanup_context(self, days_old: int = 30):
        """Clean up old context chunks"""
        cutoff = datetime.now().timestamp() - (days_old * 24 * 3600)
        
        chunks_to_delete = []
        for chunk_id, chunk in self.context_store.items():
            chunk_time = datetime.fromisoformat(chunk.timestamp).timestamp()
            if chunk_time < cutoff:
                chunks_to_delete.append(chunk_id)
        
        for chunk_id in chunks_to_delete:
            # Remove from memory
            del self.context_store[chunk_id]
            
            # Remove from disk
            chunk_file = self.context_path / f"{chunk_id}.json"
            if chunk_file.exists():
                chunk_file.unlink()
        
        return len(chunks_to_delete)

# ---------------------------------------------------------------------------
# Tkinter GUI
# ---------------------------------------------------------------------------

class OrchestratorGUI:
    """Compact Tkinter interface for AI Orchestrator"""
    
    def __init__(self, orchestrator: AIOrchestrator):
        self.orchestrator = orchestrator
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("Knowledge Forge AI Assistant")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Configure styles
        self._configure_styles()
        
        # State
        self.current_context = []
        self.pending_tool_calls = []
        
        # Build UI
        self._build_ui()
        
        # Load initial data
        self._refresh_models()
        self._refresh_tasks()
    
    def _configure_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('Title.TLabel', font=('TkDefaultFont', 12, 'bold'))
        style.configure('Status.TLabel', font=('TkDefaultFont', 9, 'italic'))
        
        # Configure button colors
        style.configure('Primary.TButton', font=('TkDefaultFont', 10))
        style.map('Primary.TButton',
                 foreground=[('active', 'white'), ('!active', 'white')],
                 background=[('active', '#2E7D32'), ('!active', '#4CAF50')])
    
    def _build_ui(self):
        """Build the user interface"""
        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Chat Tab
        self.chat_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.chat_frame, text="Chat")
        self._build_chat_tab()
        
        # Tasks Tab
        self.tasks_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tasks_frame, text="Tasks")
        self._build_tasks_tab()
        
        # Context Tab
        self.context_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.context_frame, text="Context")
        self._build_context_tab()
        
        # Settings Tab
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")
        self._build_settings_tab()
        
        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _build_chat_tab(self):
        """Build chat interface"""
        # Model selection
        model_frame = ttk.Frame(self.chat_frame)
        model_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(model_frame, text="Model:").pack(side=tk.LEFT)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var, state="readonly")
        self.model_combo.pack(side=tk.LEFT, padx=(5, 10))
        self.model_combo.bind('<<ComboboxSelected>>', self._on_model_changed)
        
        ttk.Button(model_frame, text="Refresh", 
                  command=self._refresh_models).pack(side=tk.LEFT)
        
        # Context display
        context_frame = ttk.LabelFrame(self.chat_frame, text="Active Context", padding=5)
        context_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.context_text = scrolledtext.ScrolledText(context_frame, height=4, wrap=tk.WORD)
        self.context_text.pack(fill=tk.X)
        self.context_text.insert('1.0', "No context loaded.")
        self.context_text.config(state=tk.DISABLED)
        
        # Chat history
        history_frame = ttk.LabelFrame(self.chat_frame, text="Conversation", padding=5)
        history_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.history_text = scrolledtext.ScrolledText(
            history_frame, 
            wrap=tk.WORD,
            font=('TkDefaultFont', 10)
        )
        self.history_text.pack(fill=tk.BOTH, expand=True)
        self.history_text.config(state=tk.DISABLED)
        
        # User input
        input_frame = ttk.Frame(self.chat_frame)
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_var)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind('<Return>', lambda e: self._send_message())
        
        ttk.Button(input_frame, text="Send", 
                  command=self._send_message, style='Primary.TButton').pack(side=tk.RIGHT)
        
        # Tool options
        tool_frame = ttk.Frame(self.chat_frame)
        tool_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        self.use_tools_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(tool_frame, text="Enable tools", 
                       variable=self.use_tools_var).pack(side=tk.LEFT)
    
    def _build_tasks_tab(self):
        """Build tasks interface"""
        # Task controls
        control_frame = ttk.Frame(self.tasks_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Refresh", 
                  command=self._refresh_tasks).pack(side=tk.LEFT)
        ttk.Button(control_frame, text="New Task", 
                  command=self._create_task_dialog).pack(side=tk.LEFT, padx=(5, 0))
        
        # Task list
        list_frame = ttk.LabelFrame(self.tasks_frame, text="Tasks", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview for tasks
        columns = ("ID", "Title", "Status", "Priority", "Created")
        self.task_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        for col in columns:
            self.task_tree.heading(col, text=col)
            self.task_tree.column(col, width=100)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Task details
        detail_frame = ttk.LabelFrame(self.tasks_frame, text="Task Details", padding=5)
        detail_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.task_detail_text = scrolledtext.ScrolledText(detail_frame, height=6, wrap=tk.WORD)
        self.task_detail_text.pack(fill=tk.X)
        self.task_detail_text.config(state=tk.DISABLED)
        
        # Bind selection event
        self.task_tree.bind('<<TreeviewSelect>>', self._on_task_selected)
    
    def _build_context_tab(self):
        """Build context management interface"""
        # Context controls
        control_frame = ttk.Frame(self.context_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Refresh", 
                  command=self._refresh_context).pack(side=tk.LEFT)
        ttk.Button(control_frame, text="Clear Old", 
                  command=self._cleanup_context).pack(side=tk.LEFT, padx=(5, 0))
        
        # Context list
        list_frame = ttk.LabelFrame(self.context_frame, text="Context Chunks", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview for context
        columns = ("ID", "Source", "Preview", "Timestamp")
        self.context_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        for col in columns:
            self.context_tree.heading(col, text=col)
            self.context_tree.column(col, width=150)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.context_tree.yview)
        self.context_tree.configure(yscrollcommand=scrollbar.set)
        
        self.context_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Context details
        detail_frame = ttk.LabelFrame(self.context_frame, text="Context Detail", padding=5)
        detail_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.context_detail_text = scrolledtext.ScrolledText(detail_frame, height=8, wrap=tk.WORD)
        self.context_detail_text.pack(fill=tk.X)
        self.context_detail_text.config(state=tk.DISABLED)
        
        # Bind selection event
        self.context_tree.bind('<<TreeviewSelect>>', self._on_context_selected)
    
    def _build_settings_tab(self):
        """Build settings interface"""
        settings_frame = ttk.Frame(self.settings_frame, padding=20)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        # Ollama settings
        ollama_frame = ttk.LabelFrame(settings_frame, text="Ollama Settings", padding=10)
        ollama_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(ollama_frame, text="Endpoint:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.endpoint_var = tk.StringVar(value=self.orchestrator.config['ollama_endpoint'])
        ttk.Entry(ollama_frame, textvariable=self.endpoint_var, width=40).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Model installation
        install_frame = ttk.LabelFrame(settings_frame, text="Install Model", padding=10)
        install_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(install_frame, text="Model name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.install_var = tk.StringVar(value="qwen2.5:0.5b")
        ttk.Entry(install_frame, textvariable=self.install_var, width=30).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Button(install_frame, text="Install", 
                  command=self._install_model).grid(row=0, column=2, padx=(10, 0))
        
        # Context settings
        context_frame = ttk.LabelFrame(settings_frame, text="Context Settings", padding=10)
        context_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(context_frame, text="Retention days:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.retention_var = tk.IntVar(value=self.orchestrator.config['context_retention_days'])
        ttk.Spinbox(context_frame, from_=1, to=365, textvariable=self.retention_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(context_frame, text="Context window size:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.window_var = tk.IntVar(value=self.orchestrator.context_window_size)
        ttk.Spinbox(context_frame, from_=1, to=50, textvariable=self.window_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Save button
        ttk.Button(settings_frame, text="Save Settings", 
                  command=self._save_settings, style='Primary.TButton').pack(pady=10)
    
    def _refresh_models(self):
        """Refresh model list"""
        self.model_combo['values'] = list(self.orchestrator.model_profiles.keys())
        if self.orchestrator.current_model:
            self.model_combo.set(self.orchestrator.current_model)
    
    def _refresh_tasks(self):
        """Refresh task list"""
        # Clear existing items
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        
        # Add tasks
        for task in self.orchestrator.get_tasks():
            self.task_tree.insert("", tk.END, values=(
                task.id[:8] + "...",
                task.title[:30],
                task.status.value,
                task.priority,
                task.created_at[:10]
            ))
    
    def _refresh_context(self):
        """Refresh context list"""
        # Clear existing items
        for item in self.context_tree.get_children():
            self.context_tree.delete(item)
        
        # Add context chunks
        for chunk in list(self.orchestrator.context_store.values())[:50]:  # Show last 50
            preview = chunk.content[:50] + "..." if len(chunk.content) > 50 else chunk.content
            self.context_tree.insert("", tk.END, values=(
                chunk.id,
                chunk.source,
                preview,
                chunk.timestamp[:16]
            ))
    
    def _on_model_changed(self, event=None):
        """Handle model change"""
        model_id = self.model_var.get()
        if model_id:
            success = self.orchestrator.set_model(model_id)
            if success:
                self._update_status(f"Model changed to: {model_id}")
    
    def _send_message(self):
        """Send user message to AI"""
        message = self.input_var.get().strip()
        if not message:
            return
        
        # Add user message to history
        self._add_to_history(f"You: {message}", "user")
        
        # Clear input
        self.input_var.set("")
        
        # Disable input during processing
        self.input_entry.config(state=tk.DISABLED)
        
        # Run in thread to avoid blocking
        thread = threading.Thread(
            target=self._process_message,
            args=(message,),
            daemon=True
        )
        thread.start()
    
    def _process_message(self, message: str):
        """Process message in background thread"""
        try:
            # Get AI response
            use_tools = self.use_tools_var.get()
            response = self.orchestrator.generate_response(message, use_tools=use_tools)
            
            # Update UI in main thread
            self.root.after(0, self._handle_response, response)
            
        except Exception as e:
            self.root.after(0, self._show_error, f"Error: {str(e)}")
        
        finally:
            self.root.after(0, lambda: self.input_entry.config(state=tk.NORMAL))
    
    def _handle_response(self, response: Dict):
        """Handle AI response"""
        if 'error' in response:
            self._show_error(response['error'])
            return
        
        # Add AI response to history
        self._add_to_history(f"Assistant: {response['response']}", "assistant")
        
        # Show tool calls and results
        if response.get('tool_calls'):
            self._add_to_history("Tools called:", "system")
            for tool_call in response['tool_calls']:
                self._add_to_history(f"  - {tool_call.get('name')}", "system")
        
        if response.get('tool_results'):
            self._add_to_history("Tool results:", "system")
            for result in response['tool_results']:
                if result.get('success'):
                    self._add_to_history(f"  ✓ {result.get('tool')}: Success", "system")
                else:
                    self._add_to_history(f"  ✗ {result.get('tool')}: {result.get('error', 'Failed')}", "system")
        
        # Update context display
        self._update_context_display()
        
        # Refresh tasks if any were created
        if any('create_task' in str(r) for r in response.get('tool_calls', [])):
            self._refresh_tasks()
    
    def _add_to_history(self, text: str, sender: str):
        """Add message to chat history"""
        self.history_text.config(state=tk.NORMAL)
        
        # Color coding
        if sender == "user":
            prefix = ">>> "
            color = "blue"
        elif sender == "assistant":
            prefix = "<<< "
            color = "green"
        else:
            prefix = "--- "
            color = "gray"
        
        # Insert with timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.history_text.insert(tk.END, f"[{timestamp}] {prefix}{text}\n", sender)
        
        # Configure tags for colors
        self.history_text.tag_config("user", foreground="blue")
        self.history_text.tag_config("assistant", foreground="green")
        self.history_text.tag_config("system", foreground="gray")
        
        self.history_text.see(tk.END)
        self.history_text.config(state=tk.DISABLED)
    
    def _update_context_display(self):
        """Update context display"""
        self.context_text.config(state=tk.NORMAL)
        self.context_text.delete('1.0', tk.END)
        
        context_summary = []
        for chunk in self.orchestrator.active_context_window:
            source = chunk.source.upper()
            preview = chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
            context_summary.append(f"[{source}] {preview}")
        
        if context_summary:
            self.context_text.insert('1.0', "\n".join(context_summary))
        else:
            self.context_text.insert('1.0', "No active context.")
        
        self.context_text.config(state=tk.DISABLED)
    
    def _create_task_dialog(self):
        """Open dialog to create task"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Task")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Task form
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
        title_var = tk.StringVar()
        ttk.Entry(frame, textvariable=title_var, width=40).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        desc_text = scrolledtext.ScrolledText(frame, width=40, height=8)
        desc_text.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="Priority (1-10):").grid(row=2, column=0, sticky=tk.W, pady=5)
        priority_var = tk.IntVar(value=5)
        ttk.Spinbox(frame, from_=1, to=10, textvariable=priority_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Create", 
                  command=lambda: self._create_task_and_close(
                      dialog, title_var.get(), desc_text.get('1.0', tk.END).strip(), priority_var.get()
                  )).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Cancel", 
                  command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def _create_task_and_close(self, dialog, title: str, description: str, priority: int):
        """Create task and close dialog"""
        if title and description:
            result = self.orchestrator.tool_create_task(title, description, priority)
            if 'error' in result:
                messagebox.showerror("Error", result['error'])
            else:
                self._refresh_tasks()
                dialog.destroy()
    
    def _on_task_selected(self, event):
        """Handle task selection"""
        selection = self.task_tree.selection()
        if selection:
            # Get task details (simplified - in real app would fetch by ID)
            self.task_detail_text.config(state=tk.NORMAL)
            self.task_detail_text.delete('1.0', tk.END)
            self.task_detail_text.insert('1.0', "Task details would appear here.")
            self.task_detail_text.config(state=tk.DISABLED)
    
    def _on_context_selected(self, event):
        """Handle context selection"""
        selection = self.context_tree.selection()
        if selection:
            item = self.context_tree.item(selection[0])
            chunk_id = item['values'][0]
            
            if chunk_id in self.orchestrator.context_store:
                chunk = self.orchestrator.context_store[chunk_id]
                
                self.context_detail_text.config(state=tk.NORMAL)
                self.context_detail_text.delete('1.0', tk.END)
                
                details = f"""ID: {chunk.id}
Source: {chunk.source}
Timestamp: {chunk.timestamp}
Relevance: {chunk.relevance_score:.2f}

Content:
{chunk.content}
"""
                self.context_detail_text.insert('1.0', details)
                self.context_detail_text.config(state=tk.DISABLED)
    
    def _install_model(self):
        """Install selected model"""
        model_name = self.install_var.get().strip()
        if not model_name:
            messagebox.showwarning("Warning", "Please enter a model name")
            return
        
        # Show progress in status bar
        self._update_status(f"Installing {model_name}...")
        
        # Run installation in thread
        thread = threading.Thread(
            target=self._do_install_model,
            args=(model_name,),
            daemon=True
        )
        thread.start()
    
    def _do_install_model(self, model_name: str):
        """Install model in background"""
        try:
            result = self.orchestrator.install_model(model_name)
            
            if result.get('success'):
                self.root.after(0, self._update_status, f"Model {model_name} installed successfully")
                self.root.after(0, self._refresh_models)
            else:
                self.root.after(0, self._show_error, f"Failed to install model: {result.get('error')}")
                
        except Exception as e:
            self.root.after(0, self._show_error, f"Installation error: {str(e)}")
    
    def _cleanup_context(self):
        """Clean up old context"""
        days = self.retention_var.get()
        count = self.orchestrator.cleanup_context(days)
        self._refresh_context()
        self._update_status(f"Cleaned up {count} old context chunks")
    
    def _save_settings(self):
        """Save settings"""
        self.orchestrator.config['ollama_endpoint'] = self.endpoint_var.get()
        self.orchestrator.config['context_retention_days'] = self.retention_var.get()
        self.orchestrator.context_window_size = self.window_var.get()
        self.orchestrator._save_config()
        self._update_status("Settings saved")
    
    def _update_status(self, message: str):
        """Update status bar"""
        self.status_bar.config(text=message)
    
    def _show_error(self, message: str):
        """Show error message"""
        self._update_status(f"Error: {message}")
        self._add_to_history(f"ERROR: {message}", "system")
    
    def run(self):
        """Run the GUI"""
        self.root.mainloop()

# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Knowledge Forge AI Orchestrator")
    parser.add_argument("--base-dir", type=str, default=None,
                       help="Base directory for knowledge storage")
    parser.add_argument("--no-gui", action="store_true",
                       help="Run in CLI mode instead of GUI")
    parser.add_argument("--model", type=str,
                       help="Default model to use")
    parser.add_argument("--task", type=str,
                       help="Execute a specific task")
    parser.add_argument("--cleanup", action="store_true",
                       help="Clean up old context")
    parser.add_argument("--session-token", type=str, required=True,
                       help="Required session token for authentication")
    
    args = parser.parse_args()
    
    # Determine base directory
    if args.base_dir:
        base_path = Path(args.base_dir).expanduser()
    else:
        # Default to local directory (Portable Mode)
        base_path = Path(__file__).parent.resolve() / "orchestrator_data"
    
    base_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize orchestrator
    orchestrator = AIOrchestrator(base_path, args.session_token)
    
    # Set model if specified
    if args.model:
        success = orchestrator.set_model(args.model)
        if not success:
            print(f"Model not found: {args.model}")
            available = list(orchestrator.model_profiles.keys())
            print(f"Available models: {available}")
    
    # Handle CLI commands
    if args.task:
        # Execute task (simplified)
        print(f"Executing task: {args.task}")
        result = orchestrator.generate_response(args.task, use_tools=True)
        print("Response:", json.dumps(result, indent=2))
    elif args.cleanup:
        count = orchestrator.cleanup_context()
        print(f"Cleaned up {count} context chunks")
    elif args.no_gui:
        # Start interactive CLI
        print("Knowledge Forge AI Orchestrator (CLI Mode)")
        print(f"Base directory: {base_path}")
        print(f"Current model: {orchestrator.current_model}")
        print("Type 'quit' to exit, 'help' for commands")
        
        while True:
            try:
                user_input = input("\n> ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                elif user_input.lower() == 'help':
                    print("Commands: models, tasks, context, cleanup, switch <model>")
                elif user_input.lower() == 'models':
                    models = orchestrator.get_models()
                    for model in models:
                        print(f"- {model['id']}: {model['name']} ({model['context_size']}MB)")
                elif user_input.lower() == 'tasks':
                    tasks = orchestrator.get_tasks()
                    for task in tasks:
                        print(f"- {task.id}: {task.title} [{task.status.value}]")
                elif user_input.lower() == 'context':
                    print(f"Active context: {len(orchestrator.active_context_window)} chunks")
                    for chunk in orchestrator.active_context_window:
                        print(f"  [{chunk.source}] {chunk.content[:50]}...")
                elif user_input.lower() == 'cleanup':
                    count = orchestrator.cleanup_context()
                    print(f"Cleaned up {count} chunks")
                elif user_input.lower().startswith('switch '):
                    model_id = user_input[7:].strip()
                    success = orchestrator.set_model(model_id)
                    print(f"Switched to {model_id}: {success}")
                else:
                    # Process as AI query
                    response = orchestrator.generate_response(user_input, use_tools=True)
                    
                    if 'error' in response:
                        print(f"Error: {response['error']}")
                    else:
                        print(f"\nAssistant: {response['response']}")
                        
                        if response.get('tool_calls'):
                            print("\nTools called:")
                            for tool_call in response['tool_calls']:
                                print(f"  - {tool_call.get('name')}")
                        
                        if response.get('tool_results'):
                            print("\nTool results:")
                            for result in response['tool_results']:
                                if result.get('success'):
                                    print(f"  ✓ {result.get('tool')}")
                                else:
                                    print(f"  ✗ {result.get('tool')}: {result.get('error')}")
            
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    else:
        # Launch GUI
        if not OLLAMA_AVAILABLE:
            response = messagebox.askyesno(
                "Ollama Not Installed",
                "Ollama is required for AI features. Would you like to open the installation page?"
            )
            if response:
                webbrowser.open("https://ollama.com")
        
        gui = OrchestratorGUI(orchestrator)
        
        # Center window
        gui.root.update_idletasks()
        width = gui.root.winfo_width()
        height = gui.root.winfo_height()
        x = (gui.root.winfo_screenwidth() // 2) - (width // 2)
        y = (gui.root.winfo_screenheight() // 2) - (height // 2)
        gui.root.geometry(f'{width}x{height}+{x}+{y}')
        
        gui.run()

if __name__ == "__main__":
    main()