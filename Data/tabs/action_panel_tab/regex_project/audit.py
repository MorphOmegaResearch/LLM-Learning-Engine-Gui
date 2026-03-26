#!/usr/bin/env python3
"""
ORCHESTRATOR AUDIT - System analysis and gap identification
Analyzes orchestrator.py against patterns, suggests fixes, and validates integration
"""

import argparse
import json
import re
import sys
import os
import ast
import difflib
import subprocess
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Set, Optional, Any
from dataclasses import dataclass, asdict
import textwrap

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATHS = {
    "orchestrator": os.path.join(BASE_DIR, "orchestrator.py"),
    "master_regex": os.path.join(BASE_DIR, "master_regex.json"),
    "hierarchy": os.path.join(BASE_DIR, "english_hier.json"),
    "knowledge_base": os.path.join(BASE_DIR, "knowledge_base.json"),
    "candidates": os.path.join(BASE_DIR, "candidate_entities.json"),
    "logs": os.path.join(BASE_DIR, "audit_logs")
}

# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class PatternMatch:
    """Pattern matching result"""
    line_num: int
    line_text: str
    pattern_name: str
    pattern: str
    matched: bool
    confidence: float
    suggestion: Optional[str] = None

@dataclass
class CodeIssue:
    """Code issue detection"""
    severity: str  # "high", "medium", "low"
    category: str  # "syntax", "logic", "performance", "pattern", "integration"
    location: str  # "file:line:function"
    description: str
    suggestion: str
    confidence: float
    code_excerpt: Optional[str] = None
    fix_lines: Optional[List[str]] = None

@dataclass
class GapAnalysis:
    """Gap analysis result"""
    text: str
    unrecognized_tokens: List[str]
    pattern_coverage: Dict[str, float]  # pattern_category -> coverage_percentage
    suggested_patterns: List[Dict[str, str]]
    confidence_score: float
    recommendations: List[str]
    missing_hierarchy_levels: List[str]

@dataclass
class OrchestratorState:
    """Orchestrator runtime state"""
    class_initialized: bool = False
    components_loaded: List[str] = None
    missing_imports: List[str] = None
    runtime_errors: List[str] = None
    method_coverage: Dict[str, float] = None  # class -> method_coverage_percentage
    pattern_references: Dict[str, int] = None  # pattern_category -> reference_count
    
    def __post_init__(self):
        if self.components_loaded is None:
            self.components_loaded = []
        if self.missing_imports is None:
            self.missing_imports = []
        if self.runtime_errors is None:
            self.runtime_errors = []
        if self.method_coverage is None:
            self.method_coverage = {}
        if self.pattern_references is None:
            self.pattern_references = {}

@dataclass
class AuditResult:
    """Complete audit result"""
    timestamp: str
    input_text: str
    gap_analysis: Optional[GapAnalysis]
    code_issues: List[CodeIssue]
    orchestrator_state: OrchestratorState
    pattern_matches: List[PatternMatch]
    summary: Dict[str, Any]
    log_file: str
    diff_suggestions: List[Dict[str, Any]]

# ============================================================================
# Core Analyzers
# ============================================================================

class CodeAnalyzer:
    """Analyzes orchestrator.py code for issues"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.content = self._load_file()
        self.ast_tree = self._parse_ast()
        self.issues = []
        self.pattern_matches = []
        
    def _load_file(self) -> str:
        """Load file content"""
        try:
            with open(self.file_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {self.file_path}")
            return ""
    
    def _parse_ast(self):
        """Parse file into AST"""
        try:
            return ast.parse(self.content) if self.content else None
        except SyntaxError as e:
            print(f"Syntax error in {self.file_path}: {e}")
            return None
    
    def analyze(self) -> List[CodeIssue]:
        """Run comprehensive code analysis"""
        if not self.content or not self.ast_tree:
            return []
        
        self._check_imports()
        self._check_pattern_usage()
        self._check_method_coverage()
        self._check_error_handling()
        self._check_resource_management()
        self._check_docstrings()
        self._check_class_structure()
        self._check_json_operations()
        
        return self.issues
    
    def _check_imports(self):
        """Check for missing or problematic imports"""
        required_imports = {
            'InteractionResolver': 'interaction_resolver',
            'RealizationEngine': 'realization_engine',
            'KnowledgeManager': 'orchestrator (self)',
            'BackupManager': 'version_manager',
            'JournalSystem': 'version_manager',
            'ConversationalTrainer': 'conversational_trainer'
        }
        
        # Check if imports exist in AST
        imports_found = {}
        for node in ast.walk(self.ast_tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports_found[name.name] = True
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for name in node.names:
                    full_name = f"{module}.{name.name}" if module else name.name
                    imports_found[full_name] = True
        
        for import_name, source in required_imports.items():
            if import_name not in imports_found and f"orchestrator.{import_name}" not in imports_found:
                self.issues.append(CodeIssue(
                    severity="high" if source != 'orchestrator (self)' else "low",
                    category="integration",
                    location=f"{self.file_path}:0:imports",
                    description=f"Missing import: {import_name} from {source}",
                    suggestion=f"Add: from {source} import {import_name}",
                    confidence=0.9,
                    code_excerpt="# Missing import detected"
                ))
    
    def _check_pattern_usage(self):
        """Check pattern references in code"""
        # Common pattern categories to check
        pattern_categories = [
            "level_3_lexical", "level_4_syntax", "level_5_semantics",
            "level_6_pragmatics", "domain_technical", "domain_academic",
            "entities_properties", "entities_temporal"
        ]
        
        lines = self.content.split('\n')
        for i, line in enumerate(lines, 1):
            line_lower = line.lower()
            
            # Check for direct pattern category references
            for category in pattern_categories:
                if category in line_lower:
                    self.pattern_matches.append(PatternMatch(
                        line_num=i,
                        line_text=line.strip(),
                        pattern_name=category,
                        pattern=category,
                        matched=True,
                        confidence=1.0,
                        suggestion=f"Ensure {category} patterns are loaded in master_regex.json"
                    ))
            
            # Check for regex pattern usage
            regex_patterns = [
                (r're\.search\([^)]+\)', "re.search call"),
                (r're\.match\([^)]+\)', "re.match call"),
                (r're\.compile\([^)]+\)', "re.compile call"),
                (r're\.split\([^)]+\)', "re.split call"),
                (r're\.sub\([^)]+\)', "re.sub call"),
                (r're\.findall\([^)]+\)', "re.findall call"),
            ]
            
            for pattern, name in regex_patterns:
                if re.search(pattern, line):
                    self.pattern_matches.append(PatternMatch(
                        line_num=i,
                        line_text=line.strip(),
                        pattern_name=name,
                        pattern=pattern,
                        matched=True,
                        confidence=0.8,
                        suggestion="Consider consolidating regex patterns in master_regex.json"
                    ))
    
    def _check_method_coverage(self):
        """Check method implementation coverage"""
        class_methods = {
            "MetacognitiveOrchestrator": [
                "__init__", "process_interaction", "_execute_single_interaction",
                "_update_entity_stack", "_calculate_understanding_stats",
                "_query_memory", "_calculate_priority_weights",
                "_handle_proactive_curiosity", "_handle_teach"
            ],
            "KnowledgeManager": ["save_concept", "get_concept", "check_consistency"],
            "AutoIngestor": ["capture_unknowns", "get_top_candidate", "mark_learned"],
            "ThoughtEngine": ["resolve_unknowns"]
        }
        
        for class_name, methods in class_methods.items():
            found_methods = 0
            for node in ast.walk(self.ast_tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    method_names = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    for method in methods:
                        if method in method_names:
                            found_methods += 1
                        else:
                            self.issues.append(CodeIssue(
                                severity="medium",
                                category="logic",
                                location=f"{self.file_path}:{node.lineno}:{class_name}",
                                description=f"Missing method: {class_name}.{method}",
                                suggestion=f"Implement {method} method in {class_name} class",
                                confidence=0.7,
                                code_excerpt=f"class {class_name}:"
                            ))
            
            if methods:  # Avoid division by zero
                coverage = found_methods / len(methods)
                if coverage < 0.5:
                    self.issues.append(CodeIssue(
                        severity="low",
                        category="coverage",
                        location=f"{self.file_path}:0:{class_name}",
                        description=f"Low method coverage for {class_name}: {coverage:.0%}",
                        suggestion=f"Implement missing methods: {[m for m in methods if m not in method_names]}",
                        confidence=0.6
                    ))
    
    def _check_error_handling(self):
        """Check for proper error handling"""
        lines = self.content.split('\n')
        
        # Look for try-except blocks
        try_blocks = 0
        for i, line in enumerate(lines, 1):
            if 'try:' in line:
                try_blocks += 1
                
                # Check if there's a proper except block
                has_except = False
                for j in range(i, min(i + 10, len(lines))):
                    if 'except' in lines[j] or 'finally' in lines[j]:
                        has_except = True
                        break
                
                if not has_except:
                    self.issues.append(CodeIssue(
                        severity="medium",
                        category="error_handling",
                        location=f"{self.file_path}:{i}:try",
                        description="Try block without except/finally",
                        suggestion="Add proper exception handling with specific exceptions",
                        confidence=0.8,
                        code_excerpt=line.strip()
                    ))
    
    def _check_resource_management(self):
        """Check for resource management issues"""
        lines = self.content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for open files without context managers
            if 'open(' in line and 'with open(' not in line and 'with open(' not in lines[max(0, i-2):i]:
                self.issues.append(CodeIssue(
                    severity="medium",
                    category="performance",
                    location=f"{self.file_path}:{i}:open",
                    description="File open without context manager",
                    suggestion="Use 'with open(...) as f:' for automatic resource management",
                    confidence=0.9,
                    code_excerpt=line.strip()
                ))
    
    def _check_docstrings(self):
        """Check for missing docstrings"""
        for node in ast.walk(self.ast_tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                # Check if class/function has a docstring
                docstring = ast.get_docstring(node)
                if not docstring:
                    self.issues.append(CodeIssue(
                        severity="low",
                        category="documentation",
                        location=f"{self.file_path}:{node.lineno}:{node.name}",
                        description=f"Missing docstring for {type(node).__name__} '{node.name}'",
                        suggestion=f"Add a docstring describing the purpose and usage",
                        confidence=0.9
                    ))
    
    def _check_class_structure(self):
        """Check class structure and inheritance"""
        for node in ast.walk(self.ast_tree):
            if isinstance(node, ast.ClassDef):
                # Check if class has __init__ method
                has_init = any(isinstance(n, ast.FunctionDef) and n.name == '__init__' 
                              for n in node.body)
                
                if not has_init and node.name not in ['Enum', 'Exception']:
                    self.issues.append(CodeIssue(
                        severity="low",
                        category="structure",
                        location=f"{self.file_path}:{node.lineno}:{node.name}",
                        description=f"Class {node.name} missing __init__ method",
                        suggestion=f"Add __init__ method to initialize class properties",
                        confidence=0.7
                    ))
    
    def _check_json_operations(self):
        """Check JSON operations for potential issues"""
        lines = self.content.split('\n')
        
        json_patterns = [
            (r'json\.load\([^)]*open\([^)]+\)[^)]*\)', "json.load with open"),
            (r'json\.dump\([^)]*open\([^)]+\)[^)]*\)', "json.dump with open"),
        ]
        
        for i, line in enumerate(lines, 1):
            for pattern, description in json_patterns:
                if re.search(pattern, line):
                    # Check if it's in a try block or has error handling
                    context = '\n'.join(lines[max(0, i-3):min(len(lines), i+2)])
                    if 'try:' not in context and 'except' not in context:
                        self.issues.append(CodeIssue(
                            severity="low",
                            category="error_handling",
                            location=f"{self.file_path}:{i}:json",
                            description=f"JSON operation without error handling: {description}",
                            suggestion="Wrap JSON operations in try-except blocks",
                            confidence=0.6,
                            code_excerpt=line.strip()
                        ))

class PatternAnalyzer:
    """Analyzes pattern coverage and gaps"""
    
    def __init__(self, patterns_file: str, hierarchy_file: str):
        self.patterns_file = patterns_file
        self.hierarchy_file = hierarchy_file
        self.patterns = self._load_patterns()
        self.hierarchy = self._load_hierarchy()
        
    def _load_patterns(self) -> Dict:
        """Load patterns from JSON file"""
        try:
            with open(self.patterns_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading patterns from {self.patterns_file}: {e}")
            return {}
    
    def _load_hierarchy(self) -> Dict:
        """Load hierarchy from JSON file"""
        try:
            with open(self.hierarchy_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading hierarchy from {self.hierarchy_file}: {e}")
            return {}
    
    def analyze_text(self, text: str) -> GapAnalysis:
        """Analyze text for pattern coverage gaps"""
        if not text:
            return GapAnalysis(
                text=text,
                unrecognized_tokens=[],
                pattern_coverage={},
                suggested_patterns=[],
                confidence_score=0.0,
                recommendations=["Empty input"],
                missing_hierarchy_levels=[]
            )
        
        # Tokenize
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Analyze coverage by pattern category
        pattern_coverage = {}
        unrecognized_tokens = []
        
        for category, patterns in self.patterns.items():
            matched_tokens = set()
            total_tokens_in_category = 0
            
            for pattern_name, pattern in patterns.items():
                # Compile pattern
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    matches = compiled.findall(text)
                    if matches:
                        # Flatten matches
                        for match in matches:
                            if isinstance(match, tuple):
                                for item in match:
                                    if isinstance(item, str):
                                        matched_tokens.update(item.lower().split())
                            elif isinstance(match, str):
                                matched_tokens.update(match.lower().split())
                except re.error:
                    continue
            
            # Check which words are covered
            category_words = set(words)
            recognized = category_words.intersection(matched_tokens)
            
            if category_words:
                coverage = len(recognized) / len(category_words)
                pattern_coverage[category] = coverage
                
                # Find unrecognized tokens for this category
                unrecognized = category_words - matched_tokens
                unrecognized_tokens.extend(list(unrecognized))
        
        # Deduplicate unrecognized tokens
        unrecognized_tokens = list(set(unrecognized_tokens))
        
        # Generate suggested patterns
        suggested_patterns = self._suggest_patterns(unrecognized_tokens)
        
        # Calculate overall confidence
        confidence = sum(pattern_coverage.values()) / len(pattern_coverage) if pattern_coverage else 0
        
        # Check missing hierarchy levels
        missing_levels = self._check_missing_hierarchy_levels()
        
        # Generate recommendations
        recommendations = self._generate_recommendations(pattern_coverage, unrecognized_tokens)
        
        return GapAnalysis(
            text=text,
            unrecognized_tokens=unrecognized_tokens,
            pattern_coverage=pattern_coverage,
            suggested_patterns=suggested_patterns,
            confidence_score=confidence,
            recommendations=recommendations,
            missing_hierarchy_levels=missing_levels
        )
    
    def _suggest_patterns(self, tokens: List[str]) -> List[Dict[str, str]]:
        """Suggest patterns for unrecognized tokens"""
        suggestions = []
        
        for token in tokens[:10]:  # Limit to top 10
            suggestion = self._suggest_pattern_for_token(token)
            if suggestion:
                suggestions.append({
                    "token": token,
                    "pattern": suggestion["pattern"],
                    "category": suggestion["category"],
                    "confidence": suggestion["confidence"]
                })
        
        return suggestions
    
    def _suggest_pattern_for_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Suggest a pattern for a specific token"""
        token_lower = token.lower()
        
        # Check for morphological patterns
        if token_lower.endswith('ing'):
            return {
                "pattern": r'\b\w+ing\b',
                "category": "level_2_morphology",
                "confidence": 0.9
            }
        elif token_lower.endswith('ed'):
            return {
                "pattern": r'\b\w+ed\b',
                "category": "level_2_morphology",
                "confidence": 0.9
            }
        elif token_lower.endswith('ly'):
            return {
                "pattern": r'\b\w+ly\b',
                "category": "level_2_morphology",
                "confidence": 0.8
            }
        elif token_lower.endswith('s') and not token_lower.endswith('ss'):
            return {
                "pattern": r'\b\w+s\b',
                "category": "level_2_morphology",
                "confidence": 0.7
            }
        
        # Check for proper nouns (capitalized)
        if token and token[0].isupper():
            return {
                "pattern": r'\b[A-Z][a-z]+\b',
                "category": "level_1_graphology",
                "confidence": 0.8
            }
        
        # Check for numbers
        if any(c.isdigit() for c in token):
            if '$' in token or '£' in token or '€' in token:
                return {
                    "pattern": r'[\$£€]\d+(?:\.\d{2})?',
                    "category": "entities_numerical",
                    "confidence": 0.9
                }
            elif '%' in token:
                return {
                    "pattern": r'\d+\s?%',
                    "category": "entities_numerical",
                    "confidence": 0.9
                }
            else:
                return {
                    "pattern": r'\b\d+\b',
                    "category": "entities_numerical",
                    "confidence": 0.7
                }
        
        # Generic word pattern
        return {
            "pattern": fr'\b{re.escape(token)}\b',
            "category": "level_3_lexical",
            "confidence": 0.5
        }
    
    def _check_missing_hierarchy_levels(self) -> List[str]:
        """Check for hierarchy levels missing from patterns"""
        if not self.hierarchy or "hierarchy_levels" not in self.hierarchy:
            return []
        
        hierarchy_levels = [str(level.get("level", "")) for level in self.hierarchy.get("hierarchy_levels", [])]
        pattern_levels = list(self.patterns.keys())
        
        missing = []
        for level in hierarchy_levels:
            # Check if we have a corresponding pattern level
            found = False
            for pattern_level in pattern_levels:
                if level in pattern_level:
                    found = True
                    break
            
            if not found:
                missing.append(level)
        
        return missing
    
    def _generate_recommendations(self, coverage: Dict[str, float], tokens: List[str]) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # Low coverage categories
        for category, cov in coverage.items():
            if cov < 0.3:
                recommendations.append(f"Low coverage in {category}: {cov:.0%}. Consider adding more patterns.")
        
        # Unrecognized tokens
        if tokens:
            recommendations.append(f"Found {len(tokens)} unrecognized tokens. Consider adding patterns for: {', '.join(tokens[:5])}")
        
        # Check for missing hierarchy mapping
        if not self.patterns:
            recommendations.append("No patterns loaded. Check pattern file path and format.")
        
        return recommendations

class OrchestratorRunner:
    """Runs orchestrator and captures state"""
    
    def __init__(self, orchestrator_path: str, base_dir: str = None):
        self.orchestrator_path = orchestrator_path
        self.base_dir = base_dir or os.path.dirname(orchestrator_path)
        self.state = OrchestratorState()
    
    def run_analysis(self) -> OrchestratorState:
        """Run orchestrator analysis without executing full interaction"""
        try:
            # Check if file exists and is readable
            if not os.path.exists(self.orchestrator_path):
                self.state.runtime_errors.append(f"File not found: {self.orchestrator_path}")
                return self.state
            
            # Load and analyze the file
            with open(self.orchestrator_path, 'r') as f:
                content = f.read()
            
            # Check for imports
            self._analyze_imports(content)
            
            # Check for class definitions
            self._analyze_classes(content)
            
            # Check for pattern references
            self._analyze_pattern_references(content)
            
            # Try to import and instantiate
            self._try_instantiate()
            
        except Exception as e:
            self.state.runtime_errors.append(f"Analysis error: {str(e)}")
        
        return self.state
    
    def _analyze_imports(self, content: str):
        """Analyze imports in orchestrator"""
        import_patterns = [
            r'from\s+(\w+)\s+import',
            r'import\s+(\w+)'
        ]
        
        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if match not in self.state.components_loaded:
                    self.state.components_loaded.append(match)
    
    def _analyze_classes(self, content: str):
        """Analyze class definitions in orchestrator"""
        class_pattern = r'class\s+(\w+)(?:\(|:)'
        classes = re.findall(class_pattern, content)
        
        for class_name in classes:
            # Count methods in class
            method_pattern = rf'class\s+{class_name}.*?:\n(.*?)(?=\nclass|\Z)'
            class_match = re.search(method_pattern, content, re.DOTALL)
            
            if class_match:
                class_body = class_match.group(1)
                method_matches = re.findall(r'def\s+(\w+)', class_body)
                if method_matches:
                    self.state.method_coverage[class_name] = len(method_matches)
    
    def _analyze_pattern_references(self, content: str):
        """Analyze pattern references in orchestrator"""
        pattern_categories = [
            "level_1_graphology", "level_2_morphology", "level_3_lexical",
            "level_4_syntax", "level_5_semantics", "level_6_pragmatics",
            "domain_academic", "domain_technical", "domain_informal",
            "entities_temporal", "entities_numerical", "entities_properties"
        ]
        
        for category in pattern_categories:
            count = len(re.findall(category, content, re.IGNORECASE))
            if count > 0:
                self.state.pattern_references[category] = count
    
    def _try_instantiate(self):
        """Try to instantiate MetacognitiveOrchestrator"""
        # This is a simplified check - we're not actually running it
        # just checking if it can be imported
        try:
            # Add base directory to sys.path temporarily
            import sys
            sys.path.insert(0, self.base_dir)
            
            # Try to import the module
            module_name = os.path.splitext(os.path.basename(self.orchestrator_path))[0]
            spec = __import__(module_name, fromlist=['MetacognitiveOrchestrator'])
            
            # Check if class exists
            if hasattr(spec, 'MetacognitiveOrchestrator'):
                self.state.class_initialized = True
            else:
                self.state.runtime_errors.append("MetacognitiveOrchestrator class not found in module")
                
        except ImportError as e:
            self.state.runtime_errors.append(f"Import error: {str(e)}")
        except Exception as e:
            self.state.runtime_errors.append(f"Instantiation error: {str(e)}")

class DiffGenerator:
    """Generates diffs and suggestions"""
    
    @staticmethod
    def generate_code_diff(original: str, suggested: str, context_lines: int = 3) -> List[str]:
        """Generate unified diff between original and suggested code"""
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            suggested.splitlines(keepends=True),
            fromfile='original',
            tofile='suggested',
            n=context_lines
        )
        return list(diff)
    
    @staticmethod
    def suggest_pattern_additions(missing_tokens: List[str], 
                                 pattern_category: str = "level_3_lexical") -> str:
        """Generate suggested pattern additions for JSON"""
        suggestions = []
        
        for token in missing_tokens[:10]:  # Limit to 10
            # Clean the token
            clean_token = re.sub(r'[^\w\s]', '', token).lower()
            if len(clean_token) < 3:
                continue
                
            suggestions.append(f'    "{clean_token}": "\\\\b{clean_token}\\\\b"')
        
        if suggestions:
            suggestion_text = ',\n'.join(suggestions)
            return f'"{pattern_category}": {{\n{suggestion_text}\n}}'
        
        return ""
    
    @staticmethod
    def generate_fix_suggestion(issue: CodeIssue) -> Optional[str]:
        """Generate fix suggestion for a code issue"""
        if issue.fix_lines:
            return '\n'.join(issue.fix_lines)
        
        # Generate generic fix based on category
        if issue.category == "import":
            return f"# Add missing import\nimport {issue.suggestion.split()[-1]}"
        elif issue.category == "error_handling":
            return "# Add try-except block\n\ntry:\n    # Existing code\n    pass\nexcept Exception as e:\n    # Handle error\n    pass"
        elif issue.category == "documentation":
            return f'"""Add descriptive docstring here."""'
        
        return None

# ============================================================================
# Main Audit Engine
# ============================================================================

class OrchestratorAuditEngine:
    """Main audit engine orchestrating all analyses"""
    
    def __init__(self, config: Dict[str, str] = None):
        self.config = config or DEFAULT_PATHS
        self.results = []
        self.audit_log_dir = self.config.get("logs", "audit_logs")
        os.makedirs(self.audit_log_dir, exist_ok=True)
    
    def run_full_audit(self, 
                      text: str = None,
                      file_path: str = None,
                      depth: int = 1,
                      verbose: bool = False,
                      generate_diff: bool = False) -> AuditResult:
        """Run full audit pipeline"""
        timestamp = datetime.now().isoformat()
        log_file = os.path.join(self.audit_log_dir, f"audit_{timestamp.replace(':', '-')}.log")
        
        # Determine input text
        input_text = text
        if file_path and os.path.exists(file_path):
            with open(file_path, 'r') as f:
                input_text = f.read().strip()
        
        if not input_text:
            input_text = "Test input for pattern analysis"
        
        # Run analyses
        print(f"[AUDIT] Starting comprehensive audit...")
        
        # 1. Code Analysis
        print(f"[AUDIT] Analyzing orchestrator code...")
        code_analyzer = CodeAnalyzer(self.config["orchestrator"])
        code_issues = code_analyzer.analyze()
        pattern_matches = code_analyzer.pattern_matches
        
        # 2. Pattern Analysis
        print(f"[AUDIT] Analyzing pattern coverage...")
        pattern_analyzer = PatternAnalyzer(self.config["master_regex"], 
                                          self.config["hierarchy"])
        gap_analysis = pattern_analyzer.analyze_text(input_text)
        
        # 3. Orchestrator State Analysis
        print(f"[AUDIT] Analyzing orchestrator state...")
        orchestrator_runner = OrchestratorRunner(self.config["orchestrator"])
        orchestrator_state = orchestrator_runner.run_analysis()
        
        # 4. Generate diffs if requested
        diff_suggestions = []
        if generate_diff:
            print(f"[AUDIT] Generating diff suggestions...")
            diff_suggestions = self._generate_diffs(code_issues, gap_analysis)
        
        # 5. Create summary
        summary = self._create_summary(code_issues, gap_analysis, orchestrator_state, 
                                      pattern_matches, diff_suggestions)
        
        # 6. Create result
        result = AuditResult(
            timestamp=timestamp,
            input_text=input_text,
            gap_analysis=gap_analysis,
            code_issues=code_issues,
            orchestrator_state=orchestrator_state,
            pattern_matches=pattern_matches,
            summary=summary,
            log_file=log_file,
            diff_suggestions=diff_suggestions
        )
        
        # 7. Log results
        self._log_results(result, verbose)
        
        # 8. Save to log file
        self._save_to_log(result, log_file)
        
        return result
    
    def _generate_diffs(self, 
                       code_issues: List[CodeIssue],
                       gap_analysis: GapAnalysis) -> List[Dict[str, Any]]:
        """Generate diff suggestions"""
        diffs = []
        
        # Generate pattern diffs
        if gap_analysis.suggested_patterns:
            pattern_diff = DiffGenerator.suggest_pattern_additions(
                gap_analysis.unrecognized_tokens,
                "level_3_lexical"
            )
            if pattern_diff:
                diffs.append({
                    "type": "pattern_addition",
                    "file": "master_regex.json",
                    "description": "Add missing lexical patterns",
                    "diff": pattern_diff,
                    "confidence": 0.7
                })
        
        # Generate code fix diffs
        for issue in code_issues:
            if issue.severity in ["high", "medium"]:
                fix = DiffGenerator.generate_fix_suggestion(issue)
                if fix:
                    diffs.append({
                        "type": "code_fix",
                        "file": "orchestrator.py",
                        "location": issue.location,
                        "description": issue.description,
                        "diff": fix,
                        "confidence": issue.confidence
                    })
        
        return diffs
    
    def _create_summary(self,
                       code_issues: List[CodeIssue],
                       gap_analysis: GapAnalysis,
                       orchestrator_state: OrchestratorState,
                       pattern_matches: List[PatternMatch],
                       diff_suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create comprehensive summary"""
        # Count issues by severity
        issue_counts = {"high": 0, "medium": 0, "low": 0}
        for issue in code_issues:
            issue_counts[issue.severity] += 1
        
        # Calculate pattern coverage stats
        if gap_analysis.pattern_coverage:
            avg_coverage = sum(gap_analysis.pattern_coverage.values()) / len(gap_analysis.pattern_coverage)
        else:
            avg_coverage = 0
        
        # Calculate orchestrator health score
        health_score = 0
        if orchestrator_state.class_initialized:
            health_score += 30
        if not orchestrator_state.runtime_errors:
            health_score += 30
        if gap_analysis.confidence_score > 0.5:
            health_score += int(gap_analysis.confidence_score * 40)
        
        return {
            "issue_counts": issue_counts,
            "total_issues": len(code_issues),
            "pattern_coverage_avg": avg_coverage,
            "unrecognized_tokens": len(gap_analysis.unrecognized_tokens),
            "orchestrator_health": health_score,
            "components_loaded": len(orchestrator_state.components_loaded),
            "missing_imports": len(orchestrator_state.missing_imports),
            "runtime_errors": len(orchestrator_state.runtime_errors),
            "pattern_matches_found": len(pattern_matches),
            "diff_suggestions": len(diff_suggestions),
            "recommendations": gap_analysis.recommendations[:5]  # Top 5
        }
    
    def _log_results(self, result: AuditResult, verbose: bool):
        """Log results to console"""
        summary = result.summary
        
        print("\n" + "="*60)
        print("ORCHESTRATOR AUDIT SUMMARY")
        print("="*60)
        
        print(f"\n📊 OVERVIEW:")
        print(f"  Health Score: {summary['orchestrator_health']}/100")
        print(f"  Total Issues: {summary['total_issues']} "
              f"(High: {summary['issue_counts']['high']}, "
              f"Medium: {summary['issue_counts']['medium']}, "
              f"Low: {summary['issue_counts']['low']})")
        print(f"  Pattern Coverage: {summary['pattern_coverage_avg']:.0%}")
        print(f"  Unrecognized Tokens: {summary['unrecognized_tokens']}")
        
        print(f"\n⚙️  ORCHESTRATOR STATE:")
        print(f"  Initialized: {'✓' if result.orchestrator_state.class_initialized else '✗'}")
        print(f"  Components: {len(result.orchestrator_state.components_loaded)} loaded")
        print(f"  Runtime Errors: {len(result.orchestrator_state.runtime_errors)}")
        
        if verbose:
            print(f"\n🔍 DETAILED ISSUES:")
            for issue in result.code_issues:
                print(f"  [{issue.severity.upper()}] {issue.category}: {issue.description}")
                if issue.code_excerpt:
                    print(f"     Excerpt: {issue.code_excerpt[:100]}...")
                print(f"     Suggestion: {issue.suggestion}")
                print(f"     Confidence: {issue.confidence:.0%}")
        
        print(f"\n🎯 TOP RECOMMENDATIONS:")
        for i, rec in enumerate(summary.get("recommendations", [])[:3], 1):
            print(f"  {i}. {rec}")
        
        if result.diff_suggestions:
            print(f"\n🛠️  DIFF SUGGESTIONS ({len(result.diff_suggestions)}):")
            for diff in result.diff_suggestions[:3]:
                print(f"  - {diff['description']} (Confidence: {diff['confidence']:.0%})")
        
        print(f"\n📁 LOG FILE: {result.log_file}")
        print("="*60 + "\n")
    
    def _save_to_log(self, result: AuditResult, log_file: str):
        """Save audit results to log file"""
        # Convert to serializable dict
        log_data = {
            "timestamp": result.timestamp,
            "input_text": result.input_text,
            "summary": result.summary,
            "orchestrator_state": asdict(result.orchestrator_state),
            "gap_analysis": {
                "text": result.gap_analysis.text,
                "unrecognized_tokens": result.gap_analysis.unrecognized_tokens,
                "pattern_coverage": result.gap_analysis.pattern_coverage,
                "suggested_patterns": result.gap_analysis.suggested_patterns,
                "confidence_score": result.gap_analysis.confidence_score,
                "recommendations": result.gap_analysis.recommendations
            } if result.gap_analysis else None,
            "code_issues": [
                {
                    "severity": issue.severity,
                    "category": issue.category,
                    "location": issue.location,
                    "description": issue.description,
                    "suggestion": issue.suggestion,
                    "confidence": issue.confidence,
                    "code_excerpt": issue.code_excerpt
                }
                for issue in result.code_issues
            ],
            "pattern_matches": [
                {
                    "line_num": match.line_num,
                    "pattern_name": match.pattern_name,
                    "matched": match.matched,
                    "confidence": match.confidence,
                    "suggestion": match.suggestion
                }
                for match in result.pattern_matches
            ],
            "diff_suggestions": result.diff_suggestions
        }
        
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2, default=str)
        
        print(f"[AUDIT] Results saved to {log_file}")

# ============================================================================
# CLI Interface
# ============================================================================

# Mode descriptions for help output
MODE_DESCRIPTIONS = {
    "regex-diff": "Analyze text for pattern coverage gaps and suggest additions",
    "orchestrator": "Analyze orchestrator.py code for issues and integration",
    "full": "Comprehensive analysis combining regex + orchestrator + state",
    "test-all": "Run test suite across multiple domains and inputs"
}

def get_system_state():
    """Get current system state for state-aware help."""
    state_path = os.path.join(BASE_DIR, "session_state.json")
    state_info = {
        "confidence": "N/A",
        "turn_count": 0,
        "active_domain": "general",
        "boredom_score": "0%%",
        "conversation_state": "idle",
        "entity_stack_depth": 0,
        "last_audit": "Never"
    }
    try:
        if os.path.exists(state_path):
            with open(state_path, 'r') as f:
                state = json.load(f)
                state_info["confidence"] = f"{state.get('confidence_score', 1.0):.2f}"
                state_info["turn_count"] = state.get("turn_count", 0)
                state_info["active_domain"] = state.get("active_domain", "general")
                state_info["boredom_score"] = f"{state.get('boredom_score', 0) * 100:.0f}%%"
                state_info["entity_stack_depth"] = len(state.get("entity_stack", []))
                flow = state.get("conversation_flow", {})
                state_info["conversation_state"] = flow.get("state", "idle")

        # Check for last audit
        audit_dir = os.path.join(BASE_DIR, "audit_logs")
        if os.path.exists(audit_dir):
            logs = sorted([f for f in os.listdir(audit_dir) if f.endswith('.json')])
            if logs:
                state_info["last_audit"] = logs[-1].replace('.json', '').split('_')[-1][:10]
    except Exception:
        pass
    return state_info

def get_orchestrator_health():
    """Quick health check of orchestrator."""
    health = {"status": "Unknown", "components": 0, "issues": "N/A"}
    try:
        orch_path = os.path.join(BASE_DIR, "orchestrator.py")
        if os.path.exists(orch_path):
            with open(orch_path, 'r') as f:
                content = f.read()
            # Count classes
            classes = len(re.findall(r'class\s+\w+', content))
            # Count methods
            methods = len(re.findall(r'def\s+\w+', content))
            health["components"] = classes
            health["status"] = "Loaded"
            health["methods"] = methods
    except Exception:
        health["status"] = "Error"
    return health

def build_audit_epilog():
    """Build state-aware epilog with current system information."""
    state = get_system_state()
    health = get_orchestrator_health()

    mode_help = "\n".join([f"    {k:15} {v}" for k, v in MODE_DESCRIPTIONS.items()])

    return f"""
ANALYSIS MODES:
{mode_help}

CURRENT SYSTEM STATE:
    Confidence:       {state['confidence']}
    Turn Count:       {state['turn_count']}
    Active Domain:    {state['active_domain']}
    Boredom Score:    {state['boredom_score']}
    Conv. State:      {state['conversation_state']}
    Entity Stack:     {state['entity_stack_depth']} entities
    Last Audit:       {state['last_audit']}

ORCHESTRATOR HEALTH:
    Status:           {health['status']}
    Classes:          {health.get('components', 'N/A')}
    Methods:          {health.get('methods', 'N/A')}

MILESTONES (from MILESTONES.md):
    [x] Tier 1-4: Foundational -> Stateful (Complete)
    [x] Tier 5-7: Expert -> Self-Reflective (Complete)
    [ ] Tier 8:   Autonomous / Turing Proficiency (In Progress)
    [ ] M8.4:     Granular Inquiry (Pending)
    [ ] M8.5:     Turing Pass - TOP GOAL (Pending)

EXAMPLES:
    Pattern gap analysis:
      %(prog)s --regex-diff --text "what is quantum tunneling?"

    Orchestrator code audit:
      %(prog)s --orchestrator --verbose --generate-diff

    Full system audit with pinpoint:
      %(prog)s --full --text "machine learning" --pinpoint --thoughts

    Show current thoughts and gap summary:
      %(prog)s --regex-diff --text "neural networks" --gap-summary --show-state

    Comprehensive test suite:
      %(prog)s --test-all --depth 2

RELATED TASKS (from TASKS.md):
    Task 12.5: Semantic Link Profiler (--pinpoint flag)
    Task 5.1:  Multi-Layer Understanding Audit
    Task 3.2:  Meta-Intent: System State Inquiries (--show-state)
    Task 7.1:  Bi-directional Reference Marking
"""

def main():
    parser = argparse.ArgumentParser(
        description="ORCHESTRATOR AUDIT - Comprehensive system analysis and gap identification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=build_audit_epilog()
    )

    # -------------------------------------------------------------------------
    # Input Options
    # -------------------------------------------------------------------------
    input_group = parser.add_argument_group(
        'Input Options',
        'Specify text to analyze via argument or file'
    )
    input_group.add_argument(
        "--text", "-t",
        metavar="TEXT",
        help="Text to analyze for pattern coverage gaps"
    )
    input_group.add_argument(
        "--file", "-f",
        metavar="PATH",
        help="Read text from file instead of command line"
    )
    input_group.add_argument(
        "--input-file", "-i",
        metavar="PATH",
        help="Alternative input file path"
    )

    # -------------------------------------------------------------------------
    # Analysis Modes
    # -------------------------------------------------------------------------
    mode_group = parser.add_argument_group(
        'Analysis Modes',
        'Select which type of analysis to perform (see ANALYSIS MODES below)'
    )
    mode_group.add_argument(
        "--regex-diff",
        action="store_true",
        help="Analyze text for regex pattern gaps and suggest pattern additions"
    )
    mode_group.add_argument(
        "--orchestrator",
        action="store_true",
        help="Analyze orchestrator.py code for issues, imports, and structure"
    )
    mode_group.add_argument(
        "--full",
        action="store_true",
        help="Run comprehensive analysis (regex + orchestrator + state)"
    )
    mode_group.add_argument(
        "--test-all",
        action="store_true",
        help="Run test suite across multiple domains and sample inputs"
    )

    # -------------------------------------------------------------------------
    # Diagnostic Options (New - matches gap_analyzer.py)
    # -------------------------------------------------------------------------
    diag_group = parser.add_argument_group(
        'Diagnostic Options',
        'Developer tools for semantic profiling and system introspection'
    )
    diag_group.add_argument(
        "--pinpoint",
        action="store_true",
        help="[Task 12.5] Output unmapped semantic tokens with pattern suggestions"
    )
    diag_group.add_argument(
        "--thoughts",
        action="store_true",
        help="Show current thought process and internal reasoning chain"
    )
    diag_group.add_argument(
        "--gap-summary",
        action="store_true",
        dest="gap_summary",
        help="Show concise gap summary with learning priority levels"
    )
    diag_group.add_argument(
        "--show-state",
        action="store_true",
        dest="show_state",
        help="Display current orchestrator state (confidence, boredom, domain)"
    )

    # -------------------------------------------------------------------------
    # Analysis Parameters
    # -------------------------------------------------------------------------
    param_group = parser.add_argument_group(
        'Analysis Parameters',
        'Fine-tune analysis depth and fix generation'
    )
    param_group.add_argument(
        "--depth", "-d",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="Analysis depth: 1=quick, 2=standard, 3=deep (default: 1)"
    )
    param_group.add_argument(
        "--generate-diff", "-g",
        action="store_true",
        help="Generate diff suggestions for code and pattern fixes"
    )
    param_group.add_argument(
        "--fix-confidence",
        type=float,
        default=0.7,
        metavar="CONF",
        help="Minimum confidence (0.0-1.0) for suggested fixes (default: 0.7)"
    )

    # -------------------------------------------------------------------------
    # Output Options
    # -------------------------------------------------------------------------
    output_group = parser.add_argument_group(
        'Output Options',
        'Control output format, verbosity, and logging'
    )
    output_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including all issues and pattern matches"
    )
    output_group.add_argument(
        "--summary", "-s",
        action="store_true",
        help="Show executive summary only (health score, issue counts)"
    )
    output_group.add_argument(
        "--compare", "-c",
        choices=["latest", "previous", "all"],
        metavar="MODE",
        help="Compare with previous audit: latest|previous|all"
    )
    output_group.add_argument(
        "--log-dir",
        default="audit_logs",
        metavar="DIR",
        help="Directory for log files (default: audit_logs)"
    )
    output_group.add_argument(
        "--no-log",
        action="store_true",
        help="Don't save log file to disk"
    )

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    config_group = parser.add_argument_group(
        'Configuration',
        'Override default paths for orchestrator and pattern files'
    )
    config_group.add_argument(
        "--orchestrator-path",
        default=None,
        metavar="PATH",
        help="Path to orchestrator.py (default: auto-detect)"
    )
    config_group.add_argument(
        "--patterns-path",
        default=None,
        metavar="PATH",
        help="Path to master_regex.json (default: auto-detect)"
    )
    config_group.add_argument(
        "--hierarchy-path",
        default=None,
        metavar="PATH",
        help="Path to english_hier.json (default: auto-detect)"
    )
    config_group.add_argument(
        "--config-file",
        metavar="PATH",
        help="Load configuration from JSON file"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = DEFAULT_PATHS.copy()
    if args.config_file and os.path.exists(args.config_file):
        with open(args.config_file, 'r') as f:
            config.update(json.load(f))
    
    # Override with command line arguments (only if explicitly provided)
    if args.orchestrator_path is not None:
        config["orchestrator"] = args.orchestrator_path
    if args.patterns_path is not None:
        config["master_regex"] = args.patterns_path
    if args.hierarchy_path is not None:
        config["hierarchy"] = args.hierarchy_path
    if args.log_dir != "audit_logs":
        config["logs"] = args.log_dir
    
    # Validate paths
    missing_files = []
    for key, path in config.items():
        if key in ["orchestrator", "master_regex", "hierarchy"]:
            if not os.path.exists(path):
                missing_files.append(f"{key}: {path}")
    
    if missing_files:
        print("❌ Missing required files:")
        for file in missing_files:
            print(f"  - {file}")
        print("\nPlease check paths and run again.")
        return 1
    
    # Initialize audit engine
    audit_engine = OrchestratorAuditEngine(config)
    
    # Run based on mode
    if args.regex_diff:
        print("[MODE] Running regex diff analysis...")
        if not args.text and not args.file:
            print("❌ Error: --regex-diff requires --text or --file")
            return 1
        
        # Run pattern analysis
        pattern_analyzer = PatternAnalyzer(config["master_regex"], 
                                          config["hierarchy"])
        
        input_text = args.text
        if args.file:
            with open(args.file, 'r') as f:
                input_text = f.read().strip()
        
        gap_analysis = pattern_analyzer.analyze_text(input_text)
        
        # Display results
        print("\n" + "="*60)
        print("REGEX DIFF ANALYSIS")
        print("="*60)
        print(f"Input: {input_text}")
        print(f"Confidence: {gap_analysis.confidence_score:.0%}")
        print(f"Unrecognized Tokens: {len(gap_analysis.unrecognized_tokens)}")
        
        if gap_analysis.unrecognized_tokens:
            print("\n🔍 UNRECOGNIZED TOKENS:")
            for token in gap_analysis.unrecognized_tokens[:10]:
                print(f"  - '{token}'")
            
            print("\n🛠️  SUGGESTED PATTERN ADDITIONS:")
            pattern_diff = DiffGenerator.suggest_pattern_additions(
                gap_analysis.unrecognized_tokens
            )
            print(pattern_diff)
        
        print("\n📊 PATTERN COVERAGE:")
        for category, coverage in gap_analysis.pattern_coverage.items():
            print(f"  {category}: {coverage:.0%}")

        print("="*60)

        # --show-state: Display current orchestrator state
        if args.show_state:
            state = get_system_state()
            boredom = state['boredom_score'].replace("%%", "%")
            print("\n" + "=" * 20 + " CURRENT SYSTEM STATE " + "=" * 18)
            print(f"  Confidence Score:    {state['confidence']}")
            print(f"  Turn Count:          {state['turn_count']}")
            print(f"  Active Domain:       {state['active_domain']}")
            print(f"  Boredom Score:       {boredom}")
            print(f"  Conversation State:  {state['conversation_state']}")
            print(f"  Entity Stack Depth:  {state['entity_stack_depth']} entities")
            print(f"  Last Audit:          {state['last_audit']}")
            print("=" * 60)

        # --pinpoint: Semantic Link Profiler (Task 12.5)
        if args.pinpoint:
            print("\n" + "=" * 20 + " SEMANTIC LINK PROFILER " + "=" * 16)
            print(f"  Input: {input_text[:60]}{'...' if len(input_text) > 60 else ''}")

            # Filter noise words
            noise_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                           "being", "have", "has", "had", "do", "does", "did", "will",
                           "would", "could", "should", "may", "might", "must", "shall",
                           "can", "to", "of", "in", "for", "on", "with", "at", "by",
                           "from", "as", "into", "through", "during", "before", "after",
                           "and", "but", "if", "or", "because", "until", "while", "i",
                           "you", "he", "she", "it", "we", "they", "what", "which",
                           "who", "this", "that", "these", "those", "how", "why", "when"}

            semantic_gaps = [t for t in gap_analysis.unrecognized_tokens
                            if t.lower() not in noise_words and len(t) > 2]

            print(f"\n  UNMAPPED SEMANTIC TOKENS ({len(semantic_gaps)}):")
            if semantic_gaps:
                for token in semantic_gaps[:10]:
                    # Suggest pattern category
                    if token.endswith("ing"):
                        suggestion = "level_2_morphology:verb_progressive"
                    elif token.endswith("ly"):
                        suggestion = "level_2_morphology:adverb"
                    elif token.endswith("tion") or token.endswith("sion"):
                        suggestion = "level_2_morphology:nominalization"
                    elif token[0].isupper():
                        suggestion = "level_1_graphology:proper_noun"
                    else:
                        suggestion = "level_3_lexical:content_word"
                    print(f"    • '{token}' -> suggested: {suggestion}")
            else:
                print("    (none - all tokens mapped)")

            # Coverage summary
            all_tokens = set(input_text.lower().split())
            semantic_tokens = all_tokens - noise_words
            covered = len(semantic_tokens) - len(semantic_gaps)
            coverage_pct = (covered / len(semantic_tokens) * 100) if semantic_tokens else 0

            print(f"\n  COVERAGE SUMMARY:")
            print(f"    Semantic tokens: {len(semantic_tokens)}")
            print(f"    Covered:         {covered} ({coverage_pct:.1f}%)")
            print(f"    Gaps:            {len(semantic_gaps)}")
            print("=" * 60)

        # --thoughts: Show current thought process
        if args.thoughts:
            print("\n" + "=" * 20 + " CURRENT THOUGHTS " + "=" * 22)
            thoughts = []

            # Confidence-based thoughts
            if gap_analysis.confidence_score < 0.3:
                thoughts.append(f"CRITICAL GAPS ({gap_analysis.confidence_score:.0%}): Major pattern coverage issues")
            elif gap_analysis.confidence_score < 0.6:
                thoughts.append(f"MODERATE COVERAGE ({gap_analysis.confidence_score:.0%}): Several patterns missing")
            else:
                thoughts.append(f"GOOD COVERAGE ({gap_analysis.confidence_score:.0%}): Most tokens recognized")

            # Pattern coverage thoughts
            low_coverage = [(cat, cov) for cat, cov in gap_analysis.pattern_coverage.items() if cov < 0.3]
            if low_coverage:
                for cat, cov in low_coverage[:3]:
                    thoughts.append(f"LOW COVERAGE: {cat} at {cov:.0%} - needs expansion")

            # Gap-based thoughts
            gap_count = len(gap_analysis.unrecognized_tokens)
            if gap_count > 5:
                thoughts.append(f"HIGH GAP DENSITY: {gap_count} tokens unrecognized")
                thoughts.append("RECOMMENDATION: Consider /teach session or domain-specific ingestion")
            elif gap_count > 0:
                thoughts.append(f"MINOR GAPS: {gap_count} tokens need pattern additions")

            # Recommendation thoughts
            if gap_analysis.recommendations:
                thoughts.append(f"TOP PRIORITY: {gap_analysis.recommendations[0]}")

            for i, thought in enumerate(thoughts, 1):
                print(f"  [{i}] {thought}")
            print("=" * 60)

        # --gap-summary: Concise gap summary
        if args.gap_summary:
            print("\n" + "=" * 20 + " GAP SUMMARY " + "=" * 27)
            print(f"  Input: \"{input_text[:50]}{'...' if len(input_text) > 50 else ''}\"")
            print(f"  Confidence: {gap_analysis.confidence_score:.0%}")

            # Categorize by suggested pattern
            high_priority = []
            medium_priority = []
            low_priority = []

            for suggestion in gap_analysis.suggested_patterns[:10]:
                token = suggestion.get("token", "")
                category = suggestion.get("category", "")
                confidence = suggestion.get("confidence", 0)

                if "domain" in category.lower() or confidence > 0.8:
                    high_priority.append((token, category))
                elif "lexical" in category.lower():
                    medium_priority.append((token, category))
                else:
                    low_priority.append((token, category))

            if high_priority:
                print("\n  HIGH PRIORITY (Domain/High-Confidence):")
                for token, cat in high_priority[:3]:
                    print(f"    ! '{token}' -> {cat}")

            if medium_priority:
                print("  MEDIUM PRIORITY (Lexical):")
                for token, cat in medium_priority[:3]:
                    print(f"    ~ '{token}' -> {cat}")

            if low_priority:
                print("  LOW PRIORITY (Structural):")
                for token, cat in low_priority[:2]:
                    print(f"    . '{token}' -> {cat}")

            if not (high_priority or medium_priority or low_priority):
                if gap_analysis.unrecognized_tokens:
                    print("\n  UNCLASSIFIED GAPS:")
                    for token in gap_analysis.unrecognized_tokens[:5]:
                        print(f"    ? '{token}'")
                else:
                    print("\n  No significant gaps detected.")

            # Learning recommendation
            gap_ratio = len(gap_analysis.unrecognized_tokens) / max(len(input_text.split()), 1)
            if gap_ratio > 0.4:
                print(f"\n  LEARNING ACTION: High gap density ({gap_ratio:.0%})")
                print("    -> Run: gap_analyzer.py --workflow deep --pinpoint")
            elif gap_ratio > 0.2:
                print(f"\n  LEARNING ACTION: Moderate gaps ({gap_ratio:.0%})")
                print("    -> Run: /teach command for vocabulary expansion")

            print("=" * 60)

        # Log to file
        if not args.no_log:
            timestamp = datetime.now().isoformat().replace(':', '-')
            log_file = os.path.join(config["logs"], f"regex_diff_{timestamp}.json")
            with open(log_file, 'w') as f:
                json.dump({
                    "timestamp": timestamp,
                    "input_text": input_text,
                    "gap_analysis": asdict(gap_analysis)
                }, f, indent=2)
            print(f"\n📁 Log saved to: {log_file}")
    
    elif args.orchestrator:
        print("[MODE] Running orchestrator analysis...")
        
        # Run code analysis
        code_analyzer = CodeAnalyzer(config["orchestrator"])
        code_issues = code_analyzer.analyze()
        pattern_matches = code_analyzer.pattern_matches
        
        # Run orchestrator state analysis
        orchestrator_runner = OrchestratorRunner(config["orchestrator"])
        orchestrator_state = orchestrator_runner.run_analysis()
        
        # Display results
        print("\n" + "="*60)
        print("ORCHESTRATOR ANALYSIS")
        print("="*60)
        
        # Count issues by severity
        issue_counts = {"high": 0, "medium": 0, "low": 0}
        for issue in code_issues:
            issue_counts[issue.severity] += 1
        
        print(f"Total Issues: {len(code_issues)} "
              f"(High: {issue_counts['high']}, "
              f"Medium: {issue_counts['medium']}, "
              f"Low: {issue_counts['low']})")
        
        print(f"\n⚙️  ORCHESTRATOR STATE:")
        print(f"  Initialized: {'✓' if orchestrator_state.class_initialized else '✗'}")
        print(f"  Components Loaded: {len(orchestrator_state.components_loaded)}")
        print(f"  Runtime Errors: {len(orchestrator_state.runtime_errors)}")
        
        if orchestrator_state.runtime_errors:
            print(f"\n❌ RUNTIME ERRORS:")
            for error in orchestrator_state.runtime_errors[:5]:
                print(f"  - {error}")
        
        if args.verbose and code_issues:
            print(f"\n🔍 DETAILED ISSUES:")
            for issue in code_issues:
                print(f"\n  [{issue.severity.upper()}] {issue.category}")
                print(f"     Location: {issue.location}")
                print(f"     Description: {issue.description}")
                print(f"     Suggestion: {issue.suggestion}")
                print(f"     Confidence: {issue.confidence:.0%}")
        
        print("="*60)
        
        # Generate diffs if requested
        if args.generate_diff:
            print("\n🛠️  DIFF SUGGESTIONS:")
            diff_gen = DiffGenerator()
            for issue in code_issues[:5]:  # Limit to top 5
                if issue.confidence >= args.fix_confidence:
                    fix = diff_gen.generate_fix_suggestion(issue)
                    if fix:
                        print(f"\n  For: {issue.description}")
                        print(f"  Location: {issue.location}")
                        print(f"  Suggestion:\n{textwrap.indent(fix, '    ')}")
        
        # Log to file
        if not args.no_log:
            timestamp = datetime.now().isoformat().replace(':', '-')
            log_file = os.path.join(config["logs"], f"orchestrator_audit_{timestamp}.json")
            with open(log_file, 'w') as f:
                json.dump({
                    "timestamp": timestamp,
                    "code_issues": [
                        {
                            "severity": issue.severity,
                            "category": issue.category,
                            "location": issue.location,
                            "description": issue.description,
                            "suggestion": issue.suggestion,
                            "confidence": issue.confidence,
                            "code_excerpt": issue.code_excerpt
                        }
                        for issue in code_issues
                    ],
                    "orchestrator_state": asdict(orchestrator_state),
                    "pattern_matches": [
                        {
                            "line_num": match.line_num,
                            "pattern_name": match.pattern_name,
                            "matched": match.matched,
                            "confidence": match.confidence
                        }
                        for match in pattern_matches
                    ]
                }, f, indent=2)
            print(f"\n📁 Log saved to: {log_file}")
    
    elif args.full or args.test_all:
        print("[MODE] Running full comprehensive audit...")
        
        # Determine input text for pattern analysis
        input_text = args.text
        if args.file:
            with open(args.file, 'r') as f:
                input_text = f.read().strip()
        if not input_text and args.test_all:
            input_text = "Test input for quantum server development with professional costs $500"
        
        # Run full audit
        result = audit_engine.run_full_audit(
            text=input_text,
            depth=args.depth,
            verbose=args.verbose,
            generate_diff=args.generate_diff
        )
        
        if args.summary:
            print("\n📋 EXECUTIVE SUMMARY:")
            summary = result.summary
            print(f"  Health Score: {summary['orchestrator_health']}/100")
            print(f"  Issues: {summary['total_issues']} "
                  f"(H:{summary['issue_counts']['high']} "
                  f"M:{summary['issue_counts']['medium']} "
                  f"L:{summary['issue_counts']['low']})")
            print(f"  Pattern Coverage: {summary['pattern_coverage_avg']:.0%}")
            print(f"  Unrecognized: {summary['unrecognized_tokens']} tokens")
            print(f"  Components: {summary['components_loaded']} loaded")
        
        # Compare if requested
        if args.compare:
            print(f"\n🔍 COMPARISON MODE ({args.compare}):")
            compare_results = audit_engine._compare_audits(args.compare)
            if compare_results:
                print(f"  Found {len(compare_results)} previous audits")
                # Simple comparison logic
                # (Full comparison implementation would go here)
    
    else:
        parser.print_help()
        print("\n❌ No analysis mode specified. Use --regex-diff, --orchestrator, or --full")
        return 1
    
    return 0

# ============================================================================
# Test Functions
# ============================================================================

def run_test_suite():
    """Run comprehensive test suite"""
    test_cases = [
        "what is quantum tunneling?",
        "professional development costs $500",
        "why is CPU temperature high?",
        "The system efficiency is dropping in kernel layer",
        "Hello there! How are you today?"
    ]
    
    print("🧪 RUNNING COMPREHENSIVE TEST SUITE")
    print("="*60)
    
    config = DEFAULT_PATHS.copy()
    audit_engine = OrchestratorAuditEngine(config)
    
    all_results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}/{len(test_cases)}: '{test_case}'")
        try:
            result = audit_engine.run_full_audit(
                text=test_case,
                depth=1,
                verbose=False,
                generate_diff=True
            )
            all_results.append(result)
            print(f"  ✓ Analysis complete")
            print(f"    Confidence: {result.gap_analysis.confidence_score:.0%}")
            print(f"    Issues: {result.summary['total_issues']}")
        except Exception as e:
            print(f"  ✗ Test failed: {e}")
    
    # Generate summary report
    if all_results:
        print("\n" + "="*60)
        print("TEST SUITE SUMMARY")
        print("="*60)
        
        avg_confidence = sum(r.gap_analysis.confidence_score for r in all_results) / len(all_results)
        total_issues = sum(r.summary['total_issues'] for r in all_results)
        
        print(f"Tests Run: {len(all_results)}")
        print(f"Average Confidence: {avg_confidence:.0%}")
        print(f"Total Issues Found: {total_issues}")
        print(f"Average Health Score: {sum(r.summary['orchestrator_health'] for r in all_results) / len(all_results):.0f}/100")
        
        # Identify common gaps
        all_gaps = []
        for result in all_results:
            all_gaps.extend(result.gap_analysis.unrecognized_tokens)
        
        from collections import Counter
        gap_counts = Counter(all_gaps)
        if gap_counts:
            print(f"\n📊 MOST COMMON GAPS:")
            for gap, count in gap_counts.most_common(5):
                print(f"  '{gap}': {count} occurrences")
    
    print("\n✅ Test suite complete")

# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    # Example usage:
    # python orchestrator_audit.py --regex-diff "what is quantum tunneling?"
    # python orchestrator_audit.py --orchestrator --verbose
    # python orchestrator_audit.py --full --text "test" --generate-diff
    
    # Check if running test suite directly
    if len(sys.argv) == 1:
        # No arguments, show help
        subprocess.run([sys.executable, __file__, "--help"])
    elif "--test-all" in sys.argv:
        run_test_suite()
    else:
        sys.exit(main())