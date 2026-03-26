#!/usr/bin/env python3
#[Version:#<#v1.1.0-unification_taxonomy_integration#>#]
"""
FileSync - Intelligent File Organization & Timeline Reconstruction
Single-script tool for analyzing, cataloging, and organizing files by timestamp,
relationships, and content patterns with taxonomic classification.
"""

import os
import sys
import json
import re
import argparse
import shutil
import hashlib
import time
import math
from datetime import datetime, timedelta
from pathlib import Path, PurePath
from typing import Dict, List, Optional, Tuple, Set, Any, Union, DefaultDict
from collections import defaultdict, Counter, OrderedDict
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
import mimetypes
import textwrap
import itertools
import concurrent.futures
import functools
import warnings

# ============================================================================
# SHARED LOGGING - BABEL UNIFICATION
# ============================================================================

def log_event(event_name, message, level="INFO", context=None):
    """Log an event to the unified Babel traceback system"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        module_name = "filesync"
        
        # Construct event tag
        event_tag = f"#[Event:{event_name}]"
        
        # Construct full log message
        full_message = f"[{timestamp}] [{module_name}] [{level}] {event_tag} {message}"
        if context:
            full_message += f" | Context: {context}"
        
        # Write to console
        print(f"BABEL_LOG: {full_message}")
        
        # Write to shared log
        babel_root = Path(__file__).resolve().parent
        log_dir = babel_root / "babel_data" / "logs"
        if log_dir.exists():
            shared_log = log_dir / "unified_traceback.log"
            with open(shared_log, 'a') as f:
                f.write(full_message + "\n")
    except Exception:
        pass

warnings.filterwarnings('ignore')

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

VERSION = "1.0.0"
TOOL_NAME = "FileSync"

# Default paths
DEFAULT_OUTPUT_DIR = Path.cwd() / "filesync_output"
CATALOG_DIR = DEFAULT_OUTPUT_DIR / "catalogs"
ORGANIZED_DIR = DEFAULT_OUTPUT_DIR / "organized"
MANIFEST_DIR = DEFAULT_OUTPUT_DIR / "manifests"
REPORTS_DIR = DEFAULT_OUTPUT_DIR / "reports"

# File type categories
FILE_CATEGORIES = {
    "software": [
        '.py', '.js', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go',
        '.rs', '.swift', '.kt', '.scala', '.pl', '.lua', '.r', '.m', '.f', '.for',
        '.asm', '.s', '.v', '.vhdl', '.vhd', '.tcl', '.sh', '.bash', '.zsh', '.fish',
        '.ps1', '.bat', '.cmd', '.vbs', '.ahk', '.lisp', '.clj', '.erl', '.ex',
        '.hs', '.ml', '.fs', '.dart', '.elm', '.coffee', '.ts', '.jsx', '.tsx'
    ],
    "interpreters": [
        '.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib', '.exe', '.bin', '.app',
        '.jar', '.war', '.ear', '.class', '.o', '.obj', '.ko', '.elf', '.com'
    ],
    "apps": [
        '.exe', '.app', '.apk', '.ipa', '.deb', '.rpm', '.msi', '.pkg', '.dmg',
        '.appimage', '.flatpak', '.snap', '.appx', '.xap', '.cab'
    ],
    "documents": [
        '.txt', '.md', '.markdown', '.rst', '.tex', '.doc', '.docx', '.odt',
        '.pdf', '.rtf', '.pages', '.epub', '.mobi', '.azw', '.djvu', '.xps',
        '.ppt', '.pptx', '.odp', '.key', '.xls', '.xlsx', '.ods', '.csv',
        '.xml', '.json', '.yaml', '.yml', '.ini', '.cfg', '.conf', '.toml',
        '.html', '.htm', '.xhtml', '.css', '.scss', '.sass', '.less'
    ],
    "media": [
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp',
        '.svg', '.ico', '.psd', '.ai', '.eps', '.indd', '.sketch', '.xd',
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.opus',
        '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.m4v',
        '.3gp', '.mpeg', '.mpg', '.vob', '.ogv'
    ],
    "archives": [
        '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.z', '.lz',
        '.lzma', '.lzo', '.sz', '.zst', '.lz4', '.arc', '.arj', '.cab',
        '.cpio', '.dump', '.iso', '.lha', '.lzh', '.rpm', '.shar', '.tar.Z',
        '.tgz', '.tbz2', '.txz', '.tzst', '.war', '.xar', '.zoo'
    ],
    "data": [
        '.db', '.sqlite', '.sqlite3', '.db3', '.mdb', '.accdb', '.frm', '.myd',
        '.myi', '.ibd', '.dbf', '.mdf', '.ndf', '.ldf', '.sdf', '.sql', '.dump',
        '.backup', '.bak', '.wal', '.journal'
    ],
    "config": [
        '.cfg', '.conf', '.config', '.ini', '.inf', '.properties', '.props',
        '.toml', '.yaml', '.yml', '.json', '.xml', '.plist', '.reg', '.desktop',
        '.service', '.target', '.timer', '.socket', '.mount', '.automount',
        '.swap', '.path', '.slice', '.scope', '.link', '.network', '.netdev'
    ]
}

# Time grouping thresholds (in seconds)
TIME_THRESHOLDS = {
    'same_moment': 60,           # Files created within 60 seconds
    'same_session': 3600,        # Files created within 1 hour
    'same_day': 86400,           # Files created within 24 hours
    'same_week': 604800,         # Files created within 7 days
}

# ============================================================================
# DATA STRUCTURES
# ============================================================================

class FileCategory(Enum):
    SOFTWARE = "software"
    INTERPRETERS = "interpreters"
    APPS = "apps"
    DOCUMENTS = "documents"
    MEDIA = "media"
    ARCHIVES = "archives"
    DATA = "data"
    CONFIG = "config"
    UNKNOWN = "unknown"

class TimeGroup(Enum):
    SAME_MOMENT = "same_moment"
    SAME_SESSION = "same_session"
    SAME_DAY = "same_day"
    SAME_WEEK = "same_week"
    DIFFERENT = "different"

@dataclass
class FileRecord:
    """Complete file metadata record"""
    file_id: str
    original_path: str
    original_name: str
    
    # Basic metadata
    size_bytes: int
    created_time: str
    modified_time: str
    accessed_time: str
    
    # Classification
    category: FileCategory
    mime_type: str
    extension: str
    
    # Hashes for identification
    hash_md5: str
    hash_sha1: str
    hash_sha256: str
    
    # Relationships
    parent_dir: str
    depth_from_root: int
    
    # Content analysis (optional)
    content_preview: Optional[str] = None
    line_count: Optional[int] = None
    encoding: Optional[str] = None
    
    # String matches (populated if --string-match used)
    string_matches: List[str] = field(default_factory=list)
    
    # Related files (populated during analysis)
    related_files: List[str] = field(default_factory=list)
    mentioned_in_files: List[str] = field(default_factory=list)
    
    # Taxonomic classification
    taxonomic_path: str = ""
    project_association: str = ""
    
    def to_dict(self):
        return asdict(self)
    
    def get_time_group_key(self, time_format: str = "day") -> str:
        """Get time-based grouping key"""
        dt = datetime.fromisoformat(self.created_time.replace('Z', '+00:00'))
        
        if time_format == "year":
            return dt.strftime("%Y")
        elif time_format == "month":
            return dt.strftime("%Y-%m")
        elif time_format == "day":
            return dt.strftime("%Y-%m-%d")
        elif time_format == "hour":
            return dt.strftime("%Y-%m-%d %H")
        else:
            return dt.strftime("%Y-%m-%d")

@dataclass
class Relationship:
    """Relationship between files"""
    source_id: str
    target_id: str
    relation_type: str
    strength: float  # 0.0 to 1.0
    evidence: List[str] = field(default_factory=list)

@dataclass
class ProjectCluster:
    """Cluster of files that belong to the same project"""
    cluster_id: str
    name: str
    file_ids: List[str]
    
    # Time boundaries
    first_file_time: str
    last_file_time: str
    
    # Characteristics
    primary_category: FileCategory
    file_extensions: List[str]
    total_size_bytes: int
    
    # Inferred properties
    inference: Dict[str, Any] = field(default_factory=dict)
    
    # Relationships
    relationships: List[Relationship] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)

# ============================================================================
# MAIN ORGANIZER CLASS
# ============================================================================

class FileSyncOrganizer:
    """Main file organization engine"""
    
    def __init__(self, source_dir: Path, output_dir: Path, depth: Optional[int] = None):
        self.source_dir = source_dir.resolve()
        self.output_dir = output_dir.resolve()
        self.max_depth = depth
        
        # Data stores
        self.files: Dict[str, FileRecord] = {}  # file_id -> FileRecord
        self.relationships: List[Relationship] = []
        self.projects: Dict[str, ProjectCluster] = {}
        
        # Indexes for fast lookup
        self.path_index: Dict[str, str] = {}  # path -> file_id
        self.hash_index: Dict[str, str] = {}  # hash -> file_id
        self.time_index: DefaultDict[str, List[str]] = defaultdict(list)  # time_key -> [file_ids]
        self.category_index: DefaultDict[FileCategory, List[str]] = defaultdict(list)
        
        # Statistics
        self.stats = {
            'total_files': 0,
            'total_size_bytes': 0,
            'files_by_category': Counter(),
            'files_by_extension': Counter(),
            'start_time': datetime.now(),
            'end_time': None
        }

        # Load Universal Taxonomy
        self.taxonomy = {}
        self.regex_library = {}
        self._load_universal_taxonomy()
        
        # Ensure output directories exist
        self._init_output_dirs()
    
    def _load_universal_taxonomy(self):
        """Load universal taxonomy and regex library from schemas"""
        # Look in standard babel location
        schema_dir = self.output_dir.parent / "profile" / "schemas"
        tax_path = schema_dir / "universal_taxonomy.json"
        reg_path = schema_dir / "master_regex.json"
        
        if tax_path.exists():
            try:
                with open(tax_path, 'r', encoding='utf-8') as f:
                    self.taxonomy = json.load(f)
            except: pass
                
        if reg_path.exists():
            try:
                with open(reg_path, 'r', encoding='utf-8') as f:
                    self.regex_library = json.load(f)
            except: pass

    def _classify_with_taxonomy(self, name: str, extension: str) -> Optional[str]:
        """Use taxonomy regex to improve classification"""
        if not self.regex_library:
            return None
            
        for level, patterns in self.regex_library.items():
            for p_name, p_regex in patterns.items():
                try:
                    if re.search(p_regex, name, re.IGNORECASE):
                        # Map regex level/pattern to FileCategory
                        if "software" in p_name.lower() or "hardware" in p_name.lower() or "source_code" in p_name.lower():
                            return FileCategory.SOFTWARE.value
                        if "document" in p_name.lower() or "text" in p_name.lower():
                            return FileCategory.DOCUMENTS.value
                        if "data" in p_name.lower() or "json" in p_name.lower() or "data_storage" in p_name.lower():
                            return FileCategory.DATA.value
                        if "log" in p_name.lower() or "config" in p_name.lower() or "system" in p_name.lower():
                            return FileCategory.CONFIG.value
                except:
                    continue
        return None

    def _init_output_dirs(self):
        """Initialize output directory structure"""
        self.catalog_dir = self.output_dir / "catalogs"
        self.organized_dir = self.output_dir / "organized"
        self.manifest_dir = self.output_dir / "manifests"
        self.reports_dir = self.output_dir / "reports"
        
        directories = [
            self.catalog_dir, self.organized_dir, self.manifest_dir, self.reports_dir,
            self.catalog_dir / "software",
            self.catalog_dir / "interpreters",
            self.catalog_dir / "apps",
            self.catalog_dir / "users",
            self.catalog_dir / "documents",
            self.catalog_dir / "scripts",
            self.organized_dir / "by_date",
            self.organized_dir / "by_project",
            self.organized_dir / "by_category"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def scan_files(self, enable_string_match: bool = False, 
                  string_match_full: bool = False,
                  workers: int = 4):
        """Scan source directory and collect file metadata"""
        print(f"[*] Scanning directory: {self.source_dir}")
        print(f"    Depth: {'unlimited' if self.max_depth is None else self.max_depth}")
        print(f"    String matching: {'enabled' if enable_string_match else 'disabled'}")
        
        file_paths = []
        
        # Collect all file paths
        ignore_dirs = {
            '.git', '.svn', '.hg', '.idea', '.vscode', '__pycache__', 
            'node_modules', 'venv', 'env', '.gemini',
            self.output_dir.name, 'babel_data', 'filesync_output'
        }
        
        for root, dirs, files in os.walk(self.source_dir):
            # Modify dirs in-place to prune ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
            
            # Calculate depth
            rel_root = Path(root).relative_to(self.source_dir)
            current_depth = len(rel_root.parts)
            
            # Skip if beyond max depth
            if self.max_depth is not None and current_depth > self.max_depth:
                continue
            
            for file in files:
                if file.startswith('.'): continue
                file_path = Path(root) / file
                file_paths.append(file_path)
        
        total_files = len(file_paths)
        print(f"[*] Found {total_files:,} files to process")
        
        # Process files in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all file processing tasks
            # Default to 100,000 for this project
            future_to_path = {
                executor.submit(self._process_file, path, enable_string_match, string_match_full): path
                for path in file_paths[:100000]
            }
            
            # Process completed tasks
            completed = 0
            for future in concurrent.futures.as_completed(future_to_path):
                try:
                    file_record = future.result()
                    if file_record:
                        self._add_file_record(file_record)
                        completed += 1
                        
                        # Progress indicator
                        if completed % 100 == 0:
                            print(f"    Processed {completed:,}/{min(total_files, 10000):,} files")
                except Exception as e:
                    print(f"    [!] Error processing file: {e}")
        
        print(f"[+] Scan complete. Processed {len(self.files):,} files")
        
        # Update statistics
        self.stats['end_time'] = datetime.now()
        self.stats['total_files'] = len(self.files)
        self.stats['total_size_bytes'] = sum(f.size_bytes for f in self.files.values())
    
    def _process_file(self, file_path: Path, enable_string_match: bool, 
                     string_match_full: bool) -> Optional[FileRecord]:
        """Process a single file and extract metadata"""
        try:
            # Skip if it's not a file or we can't access it
            if not file_path.is_file():
                return None
            
            # Get file stats
            stat_info = file_path.stat()
            
            # Skip if file is too large for string matching
            file_size = stat_info.st_size
            if enable_string_match and file_size > 10 * 1024 * 1024:  # 10MB limit
                enable_string_match = False
            
            # Calculate hashes
            hashes = self._calculate_file_hashes(file_path)
            
            # Generate file ID
            file_id = f"file_{hashes['sha256'][:16]}"
            
            # Determine file category
            category, mime_type = self._categorize_file(file_path)
            
            # Get times
            created_time = datetime.fromtimestamp(stat_info.st_ctime).isoformat()
            modified_time = datetime.fromtimestamp(stat_info.st_mtime).isoformat()
            accessed_time = datetime.fromtimestamp(stat_info.st_atime).isoformat()
            
            # Calculate depth from source
            try:
                rel_path = file_path.relative_to(self.source_dir)
                depth = len(rel_path.parts)
                parent_dir = str(rel_path.parent)
            except:
                depth = 0
                parent_dir = str(file_path.parent)
            
            # Optional: extract content for string matching
            content_preview = None
            line_count = None
            encoding = None
            string_matches = []
            
            if enable_string_match:
                content_analysis = self._analyze_file_content(file_path, string_match_full)
                content_preview = content_analysis.get('preview')
                line_count = content_analysis.get('line_count')
                encoding = content_analysis.get('encoding')
                string_matches = content_analysis.get('string_matches', [])
            
            # Create file record
            record = FileRecord(
                file_id=file_id,
                original_path=str(file_path),
                original_name=file_path.name,
                size_bytes=file_size,
                created_time=created_time,
                modified_time=modified_time,
                accessed_time=accessed_time,
                category=category,
                mime_type=mime_type,
                extension=file_path.suffix.lower(),
                hash_md5=hashes['md5'],
                hash_sha1=hashes['sha1'],
                hash_sha256=hashes['sha256'],
                parent_dir=parent_dir,
                depth_from_root=depth,
                content_preview=content_preview,
                line_count=line_count,
                encoding=encoding,
                string_matches=string_matches
            )
            
            return record
            
        except Exception as e:
            # Silent fail for inaccessible files
            return None
    
    def _calculate_file_hashes(self, file_path: Path) -> Dict[str, str]:
        """Calculate file hashes"""
        hashers = {
            'md5': hashlib.md5(),
            'sha1': hashlib.sha1(),
            'sha256': hashlib.sha256()
        }
        
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    for hasher in hashers.values():
                        hasher.update(chunk)
            
            return {k: v.hexdigest() for k, v in hashers.items()}
        except:
            # Return empty hashes for inaccessible files
            return {k: '' for k in hashers.keys()}
    
    def _categorize_file(self, file_path: Path) -> Tuple[FileCategory, str]:
        """Categorize file by extension and content"""
        extension = file_path.suffix.lower()
        name = file_path.name
        
        # 1. Try Universal Taxonomy first
        tax_cat = self._classify_with_taxonomy(name, extension)
        if tax_cat:
            return FileCategory(tax_cat), mimetypes.guess_type(str(file_path))[0] or 'unknown'

        # 2. Fallback to extension check against categories
        for category, extensions in FILE_CATEGORIES.items():
            if extension in extensions:
                return FileCategory(category), mimetypes.guess_type(str(file_path))[0] or 'unknown'
        
        # 3. Try to determine by MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            if 'text' in mime_type:
                return FileCategory.DOCUMENTS, mime_type
            elif 'image' in mime_type:
                return FileCategory.MEDIA, mime_type
            elif 'audio' in mime_type or 'video' in mime_type:
                return FileCategory.MEDIA, mime_type
            elif 'application' in mime_type:
                # Check if it's executable
                if os.access(file_path, os.X_OK):
                    return FileCategory.INTERPRETERS, mime_type
                else:
                    return FileCategory.SOFTWARE, mime_type
        
        return FileCategory.UNKNOWN, 'unknown'
    
    def _analyze_file_content(self, file_path: Path, full_match: bool) -> Dict[str, Any]:
        """Analyze file content for string matching"""
        analysis = {
            'preview': None,
            'line_count': 0,
            'encoding': 'unknown',
            'string_matches': []
        }
        
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252', 'ascii']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read(50000)  # Read first 50KB for preview
                        
                        # Get line count
                        f.seek(0)
                        analysis['line_count'] = sum(1 for _ in f)
                        
                        # Get preview
                        analysis['preview'] = content[:1000]  # First 1000 chars
                        analysis['encoding'] = encoding
                        
                        # Extract potential file references
                        if full_match:
                            # Look for file paths and names
                            patterns = [
                                r'[\w\-_\.]+\.(py|js|java|cpp|c|h|cs|php|rb|go|rs|swift|kt|scala|pl|lua|r|m|f|for|asm|s|v|vhdl|vhd|tcl|sh|bash|zsh|fish|ps1|bat|cmd|vbs|ahk|lisp|clj|erl|ex|hs|ml|fs|dart|elm|coffee|ts|jsx|tsx)\b',
                                r'[\w\-_\.]+\.(txt|md|markdown|rst|tex|doc|docx|odt|pdf|rtf|pages|epub|mobi|azw|djvu|xps|ppt|pptx|odp|key|xls|xlsx|ods|csv|xml|json|yaml|yml|ini|cfg|conf|toml|html|htm|xhtml|css|scss|sass|less)\b',
                                r'[\w\-_\.]+\.(jpg|jpeg|png|gif|bmp|tiff|tif|webp|svg|ico|psd|ai|eps|indd|sketch|xd|mp3|wav|flac|aac|ogg|m4a|wma|opus|mp4|avi|mov|wmv|flv|mkv|webm|m4v|3gp|mpeg|mpg|vob|ogv)\b',
                                r'[\w\-_\.]+\.(zip|tar|gz|bz2|xz|7z|rar|z|lz|lzma|lzo|sz|zst|lz4|arc|arj|cab|cpio|dump|iso|lha|lzh|rpm|shar|tar\.Z|tgz|tbz2|txz|tzst|war|xar|zoo)\b',
                                r'[\w\-_\.]+\.(db|sqlite|sqlite3|db3|mdb|accdb|frm|myd|myi|ibd|dbf|mdf|ndf|ldf|sdf|sql|dump|backup|bak|wal|journal)\b',
                                r'[\w\-_\.]+\.(cfg|conf|config|ini|inf|properties|props|toml|yaml|yml|json|xml|plist|reg|desktop|service|target|timer|socket|mount|automount|swap|path|slice|scope|link|network|netdev)\b'
                            ]
                            
                            all_matches = []
                            for pattern in patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                all_matches.extend(matches)
                            
                            analysis['string_matches'] = list(set(all_matches))[:100]  # Limit to 100 matches
                        
                    break  # Successfully read with this encoding
                    
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
        
        except Exception:
            # File might be binary or inaccessible
            pass
        
        return analysis
    
    def _add_file_record(self, record: FileRecord):
        """Add file record to all indexes"""
        self.files[record.file_id] = record
        
        # Update indexes
        self.path_index[record.original_path] = record.file_id
        self.hash_index[record.hash_sha256] = record.file_id
        
        # Time index by day
        time_key = record.get_time_group_key("day")
        self.time_index[time_key].append(record.file_id)
        
        # Category index
        self.category_index[record.category].append(record.file_id)
        
        # Update statistics
        self.stats['files_by_category'][record.category.value] += 1
        self.stats['files_by_extension'][record.extension] += 1
    
    def analyze_relationships(self):
        """Analyze relationships between files"""
        print("[*] Analyzing file relationships...")
        
        file_list = list(self.files.values())
        total_files = len(file_list)
        
        for i, file_a in enumerate(file_list):
            for file_b in file_list[i+1:]:
                # Calculate relationship strength
                strength, relation_type, evidence = self._calculate_relationship(file_a, file_b)
                
                if strength > 0.1:  # Threshold for meaningful relationship
                    relationship = Relationship(
                        source_id=file_a.file_id,
                        target_id=file_b.file_id,
                        relation_type=relation_type,
                        strength=strength,
                        evidence=evidence
                    )
                    self.relationships.append(relationship)
                    
                    # Update file records
                    file_a.related_files.append(file_b.file_id)
                    file_b.related_files.append(file_a.file_id)
            
            # Progress indicator
            if i % 100 == 0:
                print(f"    Analyzed {i:,}/{total_files:,} files")
        
        print(f"[+] Relationship analysis complete. Found {len(self.relationships):,} relationships")
    
    def _calculate_relationship(self, file_a: FileRecord, file_b: FileRecord) -> Tuple[float, str, List[str]]:
        """Calculate relationship strength between two files"""
        strength = 0.0
        relation_type = "unknown"
        evidence = []
        
        # 1. Time proximity (30% weight)
        time_a = datetime.fromisoformat(file_a.created_time.replace('Z', '+00:00'))
        time_b = datetime.fromisoformat(file_b.created_time.replace('Z', '+00:00'))
        time_diff = abs((time_a - time_b).total_seconds())
        
        if time_diff <= TIME_THRESHOLDS['same_moment']:
            time_score = 1.0
            evidence.append(f"Created within {time_diff:.0f} seconds")
        elif time_diff <= TIME_THRESHOLDS['same_session']:
            time_score = 0.7
            evidence.append(f"Created within {time_diff/3600:.1f} hours")
        elif time_diff <= TIME_THRESHOLDS['same_day']:
            time_score = 0.5
            evidence.append(f"Created within same day")
        elif time_diff <= TIME_THRESHOLDS['same_week']:
            time_score = 0.3
            evidence.append(f"Created within same week")
        else:
            time_score = 0.0
        
        strength += time_score * 0.3
        
        # 2. Directory proximity (25% weight)
        dir_a = file_a.parent_dir
        dir_b = file_b.parent_dir
        
        if dir_a == dir_b:
            dir_score = 1.0
            evidence.append("Same directory")
        elif dir_a in dir_b or dir_b in dir_a:
            dir_score = 0.8
            evidence.append("Nested directories")
        else:
            # Calculate directory similarity
            dir_a_parts = dir_a.split('/')
            dir_b_parts = dir_b.split('/')
            common_depth = 0
            for part_a, part_b in zip(dir_a_parts, dir_b_parts):
                if part_a == part_b:
                    common_depth += 1
                else:
                    break
            
            max_depth = max(len(dir_a_parts), len(dir_b_parts))
            dir_score = common_depth / max_depth if max_depth > 0 else 0
            
            if dir_score > 0.5:
                evidence.append(f"Shared parent path ({common_depth} levels)")
        
        strength += dir_score * 0.25
        
        # 3. Content references (25% weight)
        content_score = 0.0
        
        # Check if file_b is mentioned in file_a's content
        if file_b.original_name in (file_a.string_matches or []):
            content_score += 0.5
            evidence.append(f"{file_b.original_name} mentioned in {file_a.original_name}")
        
        # Check if file_a is mentioned in file_b's content
        if file_a.original_name in (file_b.string_matches or []):
            content_score += 0.5
            evidence.append(f"{file_a.original_name} mentioned in {file_b.original_name}")
        
        # Normalize content score
        content_score = min(content_score, 1.0)
        strength += content_score * 0.25
        
        # 4. File type similarity (20% weight)
        if file_a.category == file_b.category:
            type_score = 1.0
            evidence.append(f"Same category: {file_a.category.value}")
        elif file_a.category.value in ['software', 'scripts'] and file_b.category.value in ['software', 'scripts']:
            type_score = 0.8
            evidence.append("Both are code files")
        elif file_a.category.value == 'documents' and file_b.category.value in ['software', 'scripts']:
            type_score = 0.6
            evidence.append(f"Document related to code file")
        else:
            type_score = 0.0
        
        strength += type_score * 0.2
        
        # Determine relation type based on strongest evidence
        if content_score >= 0.5:
            relation_type = "content_reference"
        elif dir_score >= 0.8:
            relation_type = "same_directory"
        elif time_score >= 0.7:
            relation_type = "same_session"
        elif type_score >= 0.8:
            relation_type = "same_type"
        else:
            relation_type = "related"
        
        return min(strength, 1.0), relation_type, evidence
    
    def cluster_projects(self):
        """
        #[Mark:P2-7-COMPLETE] Fix Project Association
        Cluster files into projects based on relationships
        """
        print("[*] Clustering files into projects...")
        
        # Start with strong relationships to form initial clusters
        strong_relationships = [r for r in self.relationships if r.strength > 0.5]
        
        # Union-Find algorithm for clustering
        parent = {}
        
        def find(x):
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent[x], parent[x])
                x = parent[x]
            return x
        
        def union(x, y):
            root_x = find(x)
            root_y = find(y)
            if root_x != root_y:
                parent[root_y] = root_x
        
        # Union files with strong relationships
        for rel in strong_relationships:
            union(rel.source_id, rel.target_id)
        
        # Group files by their root parent
        clusters = defaultdict(list)
        for file_id in self.files.keys():
            root = find(file_id)
            clusters[root].append(file_id)
        
        # Filter out small clusters
        min_cluster_size = 3
        significant_clusters = {k: v for k, v in clusters.items() if len(v) >= min_cluster_size}
        
        # Create project objects
        for cluster_id, file_ids in significant_clusters.items():
            project = self._create_project_cluster(cluster_id, file_ids)
            if project:
                self.projects[project.cluster_id] = project
                
                # LINK BACK: Populate project_association in individual files
                for file_id in file_ids:
                    if file_id in self.files:
                        self.files[file_id].project_association = project.cluster_id
        
        print(f"[+] Created {len(self.projects)} project clusters and linked {sum(len(p.file_ids) for p in self.projects.values()):,} files")

    def _infer_project_type(self, file_ids: List[str]) -> Dict[str, Any]:
        """
        #[Mark:P2-6-COMPLETE] Project Intelligence Layer - Inference Engine
        Emergent Inference Engine:
        Combines Property Attribution (what) + Temporal Association (when).
        """
        evidence = {
            'has_gui': False,
            'has_cli': False,
            'has_shell_ops': False,
            'has_logging': False,
            'has_testing': False,
            'file_count': len(file_ids),
            'categories': Counter(),
            'extensions': Counter()
        }

        # Look up properties from files
        for fid in file_ids:
            f = self.files.get(fid)
            if not f: continue
            
            # Use string representation of Enum value for JSON compatibility
            cat_val = f.category.value if hasattr(f.category, 'value') else str(f.category)
            evidence['categories'][cat_val] += 1
            evidence['extensions'][str(f.extension)] += 1

            # Simple property attribution from content/extensions
            if f.extension in ['.py', '.sh', '.bash']:
                # Heuristic: Check for GUI/CLI libs in string matches or content
                matches = " ".join(f.string_matches or []).lower()
                if 'tkinter' in matches or 'pyqt' in matches or 'pyside' in matches:
                    evidence['has_gui'] = True
                if 'argparse' in matches or 'click' in matches or 'typer' in matches:
                    evidence['has_cli'] = True
                if 'subprocess' in matches or 'os.system' in matches:
                    evidence['has_shell_ops'] = True
                if 'logging' in matches:
                    evidence['has_logging'] = True
                if 'pytest' in matches or 'unittest' in matches or 'test' in f.original_name.lower():
                    evidence['has_testing'] = True

        # Convert Counter to dict for JSON serialization
        evidence['categories'] = dict(evidence['categories'])
        evidence['extensions'] = dict(evidence['extensions'])

        return self._classify_project_from_evidence(evidence)

    def _classify_project_from_evidence(self, evidence: Dict) -> Dict[str, Any]:
        """Apply emergent rules to determine project type."""
        res = {
            'type': 'Unknown',
            'subtype': 'Generic Cluster',
            'confidence': 0.4,
            'evidence': evidence
        }

        # GUI Application + System Utility
        if evidence['has_gui'] and evidence['has_shell_ops']:
            res.update({'type': 'GUI Application', 'subtype': 'System Utility', 'confidence': 0.85})
        
        # CLI Tool
        elif evidence.get('has_cli'):
            res.update({'type': 'CLI Tool', 'subtype': 'Command Interface', 'confidence': 0.80})
        
        # Testing Suite
        elif evidence.get('has_testing'):
            res.update({'type': 'Testing Suite', 'subtype': 'Automation Tests', 'confidence': 0.75})
            
        # Development Project
        elif evidence['categories'].get('software', 0) > 0:
            res.update({'type': 'Software Project', 'subtype': 'Development', 'confidence': 0.60})

        # Document Collection
        elif evidence['categories'].get('documents', 0) > evidence['file_count'] * 0.5:
            res.update({'type': 'Document Project', 'subtype': 'Documentation', 'confidence': 0.70})

        return res

    def _create_project_cluster(self, cluster_id: str, file_ids: List[str]) -> Optional[ProjectCluster]:
        """Create a project cluster from file IDs with inference"""
        if not file_ids:
            return None
        
        files = [self.files[fid] for fid in file_ids]
        
        # Determine time range
        created_times = [datetime.fromisoformat(f.created_time.replace('Z', '+00:00')) for f in files]
        first_time = min(created_times)
        last_time = max(created_times)
        
        # Determine primary category
        categories = Counter(f.category for f in files)
        primary_category = categories.most_common(1)[0][0]
        
        # Get all extensions
        extensions = list(set(f.extension for f in files if f.extension))
        
        # Calculate total size
        total_size = sum(f.size_bytes for f in files)
        
        # Emergent Inference
        inference = self._infer_project_type(file_ids)
        
        # Generate project name (use inferred name if possible)
        name = f"{inference['type'].replace(' ', '_')}_{cluster_id[:8]}"
        
        return ProjectCluster(
            cluster_id=cluster_id,
            name=name,
            file_ids=file_ids,
            first_file_time=first_time.isoformat(),
            last_file_time=last_time.isoformat(),
            primary_category=primary_category,
            file_extensions=extensions,
            total_size_bytes=total_size,
            inference=inference
        )
    
    def load_latest_manifest(self):
        """Load the latest manifest for correction/listing."""
        if not self.manifest_dir.exists():
            print("[-] No manifest directory found.")
            return

        manifests = sorted(self.manifest_dir.glob("manifest_*.json"))
        if not manifests:
            print("[-] No manifests found.")
            return

        latest_manifest = manifests[-1]
        try:
            with open(latest_manifest, 'r') as f:
                self.manifest_data = json.load(f)
                self.current_manifest_path = latest_manifest
                print(f"[+] Loaded manifest: {latest_manifest.name}")
        except Exception as e:
            print(f"[-] Error loading manifest: {e}")

    def _list_projects(self):
        """List all projects with their inferences."""
        if not hasattr(self, 'manifest_data'):
            print("[-] No manifest loaded.")
            return

        projects = self.manifest_data.get('projects', {})

        if not projects:
            print("No projects found in manifest.")
            return

        print(f"\nFound {len(projects)} projects:\n")

        for project_id, project in projects.items():
            print("="*60)
            print(f"Project ID: {project_id}")
            print(f"Name: {project.get('name', 'N/A')}")
            print(f"Files: {len(project.get('file_ids', []))}")
            print(f"Category: {project.get('primary_category', 'N/A')}")

            inference = project.get('inference', {})
            if inference:
                print(f"\nInferred Type: {inference.get('type', 'Unknown')} - {inference.get('subtype', '')}")
                print(f"Confidence: {int(inference.get('confidence', 0) * 100)}%")

                if inference.get('user_corrected_type'):
                    print(f"✓ Corrected to: {inference['user_corrected_type']}")
            print()

    def _handle_project_correction(self, args):
        """
        #[Mark:P2-correction-COMPLETE] Correction Interface
        Handle user correction of project inference.
        """
        if not hasattr(self, 'manifest_data'):
            print("[-] No manifest loaded.")
            return

        project_id = args.correct_project
        projects = self.manifest_data.get('projects', {})

        if project_id not in projects:
            print(f"Error: Project {project_id} not found")
            return

        project = projects[project_id]

        # Store correction
        if 'corrections' not in project:
            project['corrections'] = []

        correction = {
            'timestamp': datetime.now().isoformat(),
            'original_inference': project.get('inference'),
            'corrected_type': args.set_type,
            'corrected_name': args.set_name,
            'notes': args.set_notes
        }

        project['corrections'].append(correction)

        # Update project with corrected values
        if 'inference' not in project:
            project['inference'] = {}
            
        if args.set_type:
            project['inference']['user_corrected_type'] = args.set_type
            project['inference']['corrected'] = True
            project['inference']['type'] = args.set_type # Override main type for display

        if args.set_name:
            project['name'] = args.set_name

        # Save manifest
        self._save_manifest()

        print(f"✓ Project {project_id} corrected")
        if args.set_type:
            print(f"  Corrected Type: {args.set_type}")
        if args.set_name:
            print(f"  Corrected Name: {args.set_name}")

    def _save_manifest(self):
        """Save the modified manifest back to disk."""
        if not hasattr(self, 'current_manifest_path') or not self.current_manifest_path:
            return
        
        try:
            with open(self.current_manifest_path, 'w') as f:
                json.dump(self.manifest_data, f, indent=2, default=str)
            log_event("MANIFEST_SAVED", f"Manifest updated: {self.current_manifest_path}", context={"path": str(self.current_manifest_path)})
            print(f"[+] Manifest updated: {self.current_manifest_path}")
        except Exception as e:
            print(f"[-] Error saving manifest: {e}")

    def generate_manifest(self, output_path: Optional[Path] = None) -> Path:
        """Generate comprehensive manifest JSON"""
        print("[*] Generating manifest...")
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.manifest_dir / f"manifest_{timestamp}.json"
        
        manifest = {
            'metadata': {
                'tool': TOOL_NAME,
                'version': VERSION,
                'generated': datetime.now().isoformat(),
                'source_directory': str(self.source_dir),
                'file_count': len(self.files),
                'total_size_bytes': self.stats['total_size_bytes']
            },
            'statistics': {
                'files_by_category': dict(self.stats['files_by_category']),
                'top_extensions': dict(self.stats['files_by_extension'].most_common(20)),
                'time_range': {
                    'first_file': min(f.created_time for f in self.files.values()),
                    'last_file': max(f.created_time for f in self.files.values())
                }
            },
            'catalogs': self._generate_catalogs(),
            'timeline': self._generate_timeline(),
            'projects': {pid: proj.to_dict() for pid, proj in self.projects.items()},
            'files': {fid: f.to_dict() for fid, f in self.files.items()}
        }
        
        with open(output_path, 'w') as f:
            json.dump(manifest, f, indent=2, default=str)
        
        print(f"[+] Manifest saved to: {output_path}")
        return output_path
    
    def _generate_catalogs(self) -> Dict[str, List[Dict]]:
        """Generate categorized file catalogs"""
        catalogs = {}
        
        # Software catalog
        software_files = [f for f in self.files.values() if f.category == FileCategory.SOFTWARE or str(f.category.value) == "software"]
        catalogs['software'] = [
            {
                'file_id': f.file_id,
                'name': f.original_name,
                'path': f.original_path,
                'size': f.size_bytes,
                'created': f.created_time,
                'lines': f.line_count
            }
            for f in software_files[:5000]  # Increased limit
        ]
        
        # Documents catalog
        doc_files = [f for f in self.files.values() if f.category == FileCategory.DOCUMENTS or str(f.category.value) == "documents"]
        catalogs['documents'] = [
            {
                'file_id': f.file_id,
                'name': f.original_name,
                'path': f.original_path,
                'size': f.size_bytes,
                'created': f.created_time,
                'preview': f.content_preview[:200] if f.content_preview else None
            }
            for f in doc_files[:5000]
        ]
        
        # Scripts catalog
        script_extensions = {'.py', '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd', '.js', '.ts', '.lua', '.pl', '.rb'}
        script_files = [f for f in self.files.values() if f.extension in script_extensions or f.category.value == "scripts"]
        catalogs['scripts'] = [
            {
                'file_id': f.file_id,
                'name': f.original_name,
                'path': f.original_path,
                'size': f.size_bytes,
                'created': f.created_time,
                'lines': f.line_count
            }
            for f in script_files[:5000]
        ]
        
        # Interpreters catalog (binaries/executables)
        interpreter_files = [f for f in self.files.values() if f.category == FileCategory.INTERPRETERS or str(f.category.value) == "interpreters"]
        catalogs['interpreters'] = [
            {
                'file_id': f.file_id,
                'name': f.original_name,
                'path': f.original_path,
                'size': f.size_bytes,
                'created': f.created_time,
                'type': f.mime_type
            }
            for f in interpreter_files[:5000]
        ]
        
        # Users catalog (approximated by directory structure)
        user_dirs = defaultdict(list)
        for f in self.files.values():
            # Look for common user directory patterns
            if '/home/' in f.original_path or '/Users/' in f.original_path:
                parts = f.original_path.split('/')
                for i, part in enumerate(parts):
                    if part in ['home', 'Users'] and i + 1 < len(parts):
                        user = parts[i + 1]
                        user_dirs[user].append(f.file_id)
                        break
        
        catalogs['users'] = [
            {
                'username': user,
                'file_count': len(file_ids),
                'total_size': sum(self.files[fid].size_bytes for fid in file_ids),
                'sample_files': [self.files[fid].original_name for fid in file_ids[:5]]
            }
            for user, file_ids in list(user_dirs.items())[:20]  # Top 20 users
        ]

        return catalogs

    def _write_catalog_files(self):
        """Write catalog data to separate txt files for easy browsing."""
        catalogs = self._generate_catalogs()

        for category, items in catalogs.items():
            catalog_file = self.catalog_dir / category / "catalog.txt"
            catalog_file.parent.mkdir(parents=True, exist_ok=True)

            with open(catalog_file, 'w') as f:
                f.write(f"# {category.upper()} CATALOG\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Total items: {len(items)}\n")
                f.write("#" + "="*70 + "\n\n")

                for item in items:
                    # Handle different catalog formats
                    if 'path' in item:
                        f.write(f"{item['path']}\n")
                    elif 'username' in item:  # Users catalog
                        f.write(f"{item['username']} ({item['file_count']} files)\n")
                
            log_event("CATALOG_SAVED", f"{category.upper()} catalog saved to {catalog_file}", context={"category": category, "path": str(catalog_file)})

            print(f"[+] Wrote catalog: {catalog_file}")

    def _generate_timeline(self) -> List[Dict]:
        """Generate chronological timeline of file creation"""
        # Sort files by creation time
        sorted_files = sorted(self.files.values(), 
                            key=lambda f: f.created_time)
        
        timeline = []
        current_day = None
        day_entries = []
        
        for file in sorted_files:
            file_date = file.created_time[:10]  # YYYY-MM-DD
            
            if file_date != current_day:
                if day_entries:
                    timeline.append({
                        'date': current_day,
                        'file_count': len(day_entries),
                        'files': day_entries[:10],  # Limit per day
                        'total_size': sum(f['size_bytes'] for f in day_entries)
                    })
                current_day = file_date
                day_entries = []
            
            day_entries.append({
                'file_id': file.file_id,
                'name': file.original_name,
                'path': file.original_path,
                'size_bytes': file.size_bytes,
                'category': file.category.value,
                'created_time': file.created_time
            })
        
        # Add last day
        if day_entries:
            timeline.append({
                'date': current_day,
                'file_count': len(day_entries),
                'files': day_entries[:10],
                'total_size': sum(f['size_bytes'] for f in day_entries)
            })
        
        return timeline
    
    def organize_files(self, group_by: str = "date", dry_run: bool = False):
        """Organize files into new directory structure"""
        print(f"[*] Organizing files by: {group_by}")
        print(f"    Dry run: {'yes' if dry_run else 'no'}")
        
        if group_by == "date":
            self._organize_by_date(dry_run)
        elif group_by == "project":
            self._organize_by_project(dry_run)
        elif group_by == "category":
            self._organize_by_category(dry_run)
        elif group_by == "extension":
            self._organize_by_extension(dry_run)
        
        if not dry_run:
            print("[+] File organization complete")
    
    def _organize_by_date(self, dry_run: bool):
        """Organize files by creation date"""
        for time_key, file_ids in self.time_index.items():
            # Create directory for this date
            date_dir = self.organized_dir / "by_date" / time_key
            if not dry_run:
                date_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy files (or simulate)
            for file_id in file_ids:
                file_record = self.files[file_id]
                source_path = Path(file_record.original_path)
                
                # Create destination path
                dest_name = f"{file_record.created_time[11:16].replace(':', '')}_{file_record.original_name}"
                dest_path = date_dir / dest_name
                
                if dry_run:
                    print(f"    Would copy: {source_path.name} -> {dest_path}")
                else:
                    try:
                        shutil.copy2(source_path, dest_path)
                    except Exception as e:
                        print(f"    [!] Error copying {source_path}: {e}")
    
    def _organize_by_project(self, dry_run: bool):
        """Organize files by project clusters"""
        for project_id, project in self.projects.items():
            # Create project directory
            project_dir = self.organized_dir / "by_project" / project.name
            if not dry_run:
                project_dir.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories by category
            category_dirs = {}
            
            for file_id in project.file_ids:
                file_record = self.files[file_id]
                source_path = Path(file_record.original_path)
                
                # Get or create category directory
                category = file_record.category.value
                if category not in category_dirs:
                    cat_dir = project_dir / category
                    if not dry_run:
                        cat_dir.mkdir(exist_ok=True)
                    category_dirs[category] = cat_dir
                else:
                    cat_dir = category_dirs[category]
                
                # Destination path
                dest_path = cat_dir / file_record.original_name
                
                if dry_run:
                    print(f"    Would copy: {source_path.name} -> {dest_path.relative_to(self.organized_dir)}")
                else:
                    try:
                        shutil.copy2(source_path, dest_path)
                    except Exception as e:
                        print(f"    [!] Error copying {source_path}: {e}")
    
    def _organize_by_category(self, dry_run: bool):
        """Organize files by category"""
        for category, file_ids in self.category_index.items():
            # Create category directory
            category_dir = self.organized_dir / "by_category" / category.value
            if not dry_run:
                category_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy files
            for file_id in file_ids:
                file_record = self.files[file_id]
                source_path = Path(file_record.original_path)
                dest_path = category_dir / file_record.original_name
                
                if dry_run:
                    print(f"    Would copy: {source_path.name} -> {dest_path.relative_to(self.organized_dir)}")
                else:
                    try:
                        shutil.copy2(source_path, dest_path)
                    except Exception as e:
                        print(f"    [!] Error copying {source_path}: {e}")
    
    def _organize_by_extension(self, dry_run: bool):
        """Organize files by extension"""
        extension_groups = defaultdict(list)
        
        for file_record in self.files.values():
            if file_record.extension:
                extension_groups[file_record.extension].append(file_record.file_id)
        
        for extension, file_ids in extension_groups.items():
            # Clean extension for directory name
            clean_ext = extension[1:] if extension.startswith('.') else extension
            if not clean_ext:
                clean_ext = "no_extension"
            
            # Create extension directory
            ext_dir = self.organized_dir / "by_extension" / clean_ext
            if not dry_run:
                ext_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy files
            for file_id in file_ids:
                file_record = self.files[file_id]
                source_path = Path(file_record.original_path)
                dest_path = ext_dir / file_record.original_name
                
                if dry_run:
                    print(f"    Would copy: {source_path.name} -> {dest_path.relative_to(self.organized_dir)}")
                else:
                    try:
                        shutil.copy2(source_path, dest_path)
                    except Exception as e:
                        print(f"    [!] Error copying {source_path}: {e}")
    
    def generate_report(self, output_path: Optional[Path] = None) -> Path:
        """Generate human-readable report"""
        print("[*] Generating report...")
        
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.reports_dir / f"report_{timestamp}.txt"
        
        with open(output_path, 'w') as f:
            f.write(f"{'='*80}\n")
            f.write(f"FileSync Analysis Report\n")
            f.write(f"{'='*80}\n\n")
            
            # Summary
            f.write("SUMMARY\n")
            f.write(f"Source Directory: {self.source_dir}\n")
            f.write(f"Total Files: {len(self.files):,}\n")
            f.write(f"Total Size: {self.stats['total_size_bytes']:,} bytes ({self.stats['total_size_bytes']/1024/1024:.1f} MB)\n")
            f.write(f"Analysis Time: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            # File Categories
            f.write("\nFILE CATEGORIES\n")
            for category, count in self.stats['files_by_category'].most_common():
                f.write(f"  {category:15} {count:6,} files\n")
            
            # Top Extensions
            f.write("\nTOP EXTENSIONS\n")
            for ext, count in self.stats['files_by_extension'].most_common(10):
                f.write(f"  {ext:10} {count:6,} files\n")
            
            # Timeline Summary
            f.write("\nTIMELINE\n")
            if self.time_index:
                dates = sorted(self.time_index.keys())
                f.write(f"  Date Range: {dates[0]} to {dates[-1]}\n")
                f.write(f"  Total Days: {len(dates)}\n")
                
                # Busiest days
                busy_days = sorted(self.time_index.items(), key=lambda x: len(x[1]), reverse=True)[:5]
                f.write("\n  Busiest Days:\n")
                for date, file_ids in busy_days:
                    f.write(f"    {date}: {len(file_ids):,} files\n")
            
            # Projects
            f.write("\nPROJECT CLUSTERS\n")
            f.write(f"  Total Projects: {len(self.projects)}\n")
            
            for project in list(self.projects.values())[:10]:  # Top 10 projects
                f.write(f"\n  Project: {project.name}\n")
                f.write(f"    Files: {len(project.file_ids):,}\n")
                f.write(f"    Size: {project.total_size_bytes:,} bytes\n")
                f.write(f"    Time Range: {project.first_file_time[:10]} to {project.last_file_time[:10]}\n")
                f.write(f"    Categories: {', '.join(set(ext for ext in project.file_extensions if ext))[:5]}\n")
            
            # Relationships
            f.write("\nFILE RELATIONSHIPS\n")
            f.write(f"  Total Relationships: {len(self.relationships):,}\n")
            
            if self.relationships:
                # Group by type
                rel_by_type = Counter(r.relation_type for r in self.relationships)
                f.write("\n  By Type:\n")
                for rel_type, count in rel_by_type.most_common():
                    f.write(f"    {rel_type:20} {count:6,}\n")
            
            # Recommendations
            f.write("\nRECOMMENDATIONS\n")
            if len(self.projects) > 10:
                f.write("  ✓ Consider organizing by project structure\n")
            if len(self.time_index) > 30:
                f.write("  ✓ Consider organizing by date for historical clarity\n")
            if self.stats['files_by_category'][FileCategory.DOCUMENTS.value] > 100:
                f.write("  ✓ Consider separating documents from code files\n")
            
            f.write(f"\n{'='*80}\n")
            f.write("Report generated by FileSync\n")
            f.write(f"{'='*80}\n")
        
        print(f"[+] Report saved to: {output_path}")
        return output_path

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description=f"FileSync v{VERSION} - Intelligent File Organization & Timeline Reconstruction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic scan and manifest generation
  filesync.py /path/to/source --manifest
  
  # Deep scan with string matching
  filesync.py /path/to/source --depth 5 --string-match --full
  
  # Organize files by date (dry run first)
  filesync.py /path/to/source --organize date --diff
  
  # Generate catalog and report
  filesync.py /path/to/source --catalog --report
  
  # Complex workflow: scan, analyze relationships, organize by project
  filesync.py /path/to/source --analyze-relationships --organize project --batch
  
  # Match specific files against documents
  filesync.py /path/to/source --match-file important.py --documents-only

Workflows:
  1. Discovery: filesync.py <source> --manifest --report
  2. Organization: filesync.py <source> --organize date --batch
  3. Analysis: filesync.py <source> --analyze-relationships --catalog
  4. Cleanup: filesync.py <source> --organize category --diff --batch
        """
    )
    
    # Required arguments
    parser.add_argument('source', type=str, help='Source directory to analyze')
    
    # Scan options
    parser.add_argument('--depth', '-d', type=int, help='Maximum recursion depth (default: unlimited)')
    parser.add_argument('--string-match', '-s', action='store_true', 
                       help='Enable string matching between files')
    parser.add_argument('--full', '-f', action='store_true',
                       help='Enable full string matching (reads file content)')
    
    # Analysis options
    parser.add_argument('--analyze-relationships', '-r', action='store_true',
                       help='Analyze relationships between files')
    parser.add_argument('--cluster-projects', '-c', action='store_true',
                       help='Cluster files into projects')
    
    # Output options
    parser.add_argument('--manifest', '-m', action='store_true',
                       help='Generate JSON manifest')
    parser.add_argument('--catalog', action='store_true',
                       help='Generate file catalogs')
    parser.add_argument('--report', action='store_true',
                       help='Generate human-readable report')
    parser.add_argument('--output-dir', '-o', type=str, default=DEFAULT_OUTPUT_DIR,
                       help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})')
    
    # Project Correction options
    parser.add_argument('--list-projects', action='store_true',
                       help='List all projects with inferences')
    parser.add_argument('--correct-project', type=str,
                       help='Project ID to correct')
    parser.add_argument('--set-type', type=str,
                       help='Corrected project type')
    parser.add_argument('--set-name', type=str,
                       help='Corrected project name')
    parser.add_argument('--set-notes', type=str,
                       help='Notes about correction')
    
    # Organization options
    parser.add_argument('--organize', type=str, choices=['date', 'project', 'category', 'extension'],
                       help='Organize files into new structure')
    parser.add_argument('--diff', action='store_true',
                       help='Show what would be done without actually doing it')
    parser.add_argument('--batch', '-b', action='store_true',
                       help='Batch mode (no interactive confirmation)')
    
    # Matching options
    parser.add_argument('--match-file', type=str,
                       help='Find documents that mention this file')
    parser.add_argument('--documents-only', action='store_true',
                       help='Only scan document files when matching')
    
    # Performance options
    parser.add_argument('--workers', '-w', type=int, default=4,
                       help='Number of worker threads (default: 4)')
    parser.add_argument('--max-files', type=int, default=10000,
                       help='Maximum files to process (default: 10000)')
    
    # Info options
    parser.add_argument('--version', action='version', version=f'FileSync v{VERSION}')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Log command execution to unified traceback
    log_event("COMMAND_EXEC", f"Running scan on: {args.source}", level="INFO",
              context={"args": sys.argv[1:], "source": args.source})
    
    # Validate source directory
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"[-] Source directory does not exist: {source_path}")
        sys.exit(1)
    
    if not source_path.is_dir():
        print(f"[-] Source is not a directory: {source_path}")
        sys.exit(1)
    
    # Create organizer
    organizer = FileSyncOrganizer(
        source_dir=source_path,
        output_dir=Path(args.output_dir),
        depth=args.depth
    )

    # Handle Correction Commands immediately (bypass scan if possible)
    if args.list_projects:
        organizer.load_latest_manifest()
        organizer._list_projects()
        return

    if args.correct_project:
        organizer.load_latest_manifest()
        organizer._handle_project_correction(args)
        return
    
    try:
        # Step 1: Scan files
        organizer.scan_files(
            enable_string_match=args.string_match,
            string_match_full=args.full,
            workers=args.workers
        )
        
        # Step 2: Analyze relationships if requested
        if args.analyze_relationships:
            organizer.analyze_relationships()
        
        # Step 3: Cluster projects if requested
        if args.cluster_projects:
            organizer.cluster_projects()
        
        # Step 4: Generate manifest if requested
        if args.manifest:
            manifest_path = organizer.generate_manifest()
            print(f"[+] Manifest: {manifest_path}")
        
        # Step 5: Generate catalog if requested
        if args.catalog:
            # Catalogs are generated as part of the manifest
            print("[+] Catalogs generated in manifest")
            # Also write catalog files to disk for easy browsing
            organizer._write_catalog_files()
        
        # Step 6: Generate report if requested
        if args.report:
            report_path = organizer.generate_report()
            print(f"[+] Report: {report_path}")
        
        # Step 7: Organize files if requested
        if args.organize:
            if not args.batch:
                response = input(f"\nOrganize {len(organizer.files):,} files by {args.organize}? [y/N] ")
                if response.lower() != 'y':
                    print("[-] Organization cancelled")
                    sys.exit(0)
            
            log_event("ORGANIZE_START", f"Organizing files by {args.organize}", context={"group_by": args.organize, "dry_run": args.diff})
            organizer.organize_files(
                group_by=args.organize,
                dry_run=args.diff
            )
            log_event("ORGANIZE_COMPLETE", f"File organization complete")
        
        # Step 8: File matching if requested
        if args.match_file:
            print(f"[*] Searching for documents mentioning: {args.match_file}")
            log_event("MATCH_START", f"Searching for mentions of: {args.match_file}")
            matching_files = organizer.find_file_mentions(args.match_file, args.documents_only)
            
            if matching_files:
                print(f"\nFound {len(matching_files)} documents mentioning '{args.match_file}':")
                for file_record in matching_files[:10]:  # Show top 10
                    print(f"  • {file_record.original_path}")
                    if file_record.content_preview:
                        # Find the mention in preview
                        preview = file_record.content_preview.lower()
                        target = args.match_file.lower()
                        if target in preview:
                            start = max(0, preview.find(target) - 50)
                            end = min(len(preview), preview.find(target) + len(target) + 50)
                            context = preview[start:end].replace('\n', ' ')
                            print(f"    Context: ...{context}...")
            else:
                print(f"[-] No documents found mentioning '{args.match_file}'")
        
        # Final statistics
        print(f"\n{'='*60}")
        print("ANALYSIS COMPLETE")
        print(f"{'='*60}")
        log_event("ANALYSIS_COMPLETE", "FileSync analysis finished", context={
            "files": len(organizer.files),
            "projects": len(organizer.projects),
            "output": str(args.output_dir)
        })
        print(f"Files processed: {len(organizer.files):,}")
        print(f"Total size: {organizer.stats['total_size_bytes']/1024/1024:.1f} MB")
        print(f"Projects identified: {len(organizer.projects):,}")
        print(f"Relationships found: {len(organizer.relationships):,}")
        
        if args.output_dir:
            print(f"\nOutput saved to: {args.output_dir}")
            try:
                print(f"  • Manifests: {organizer.manifest_dir.relative_to(Path(args.output_dir))}")
                print(f"  • Reports: {organizer.reports_dir.relative_to(Path(args.output_dir))}")
                print(f"  • Organized: {organizer.organized_dir.relative_to(Path(args.output_dir))}")
            except ValueError:
                # Fallback if paths are not relative (e.g. symlinks or different drives)
                print(f"  • Manifests: {organizer.manifest_dir}")
                print(f"  • Reports: {organizer.reports_dir}")
                print(f"  • Organized: {organizer.organized_dir}")
        
    except KeyboardInterrupt:
        print("\n\n[-] Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[-] Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

# ============================================================================
# ADDITIONAL UTILITY FUNCTIONS
# ============================================================================

def find_file_mentions(self, target_file: str, documents_only: bool = True) -> List[FileRecord]:
    """Find files that mention the target file"""
    target_name = Path(target_file).name.lower()
    matching_files = []
    
    for file_record in self.files.values():
        # Skip if documents_only and not a document
        if documents_only and file_record.category != FileCategory.DOCUMENTS:
            continue
        
        # Check string matches
        if file_record.string_matches:
            for match in file_record.string_matches:
                if target_name in match.lower():
                    matching_files.append(file_record)
                    break
        # Check content preview
        elif file_record.content_preview and target_name in file_record.content_preview.lower():
            matching_files.append(file_record)
    
    # Sort by relevance (more matches = higher relevance)
    matching_files.sort(key=lambda f: len([m for m in (f.string_matches or []) 
                                         if target_name in m.lower()]), 
                       reverse=True)
    
    return matching_files

# Add method to class
FileSyncOrganizer.find_file_mentions = find_file_mentions

# ============================================================================
# QUICK USAGE EXAMPLES
# ============================================================================

QUICK_EXAMPLES = """
Quick Usage Examples:
---------------------
1. Quick scan and manifest:
   python filesync.py ~/Projects --manifest

2. Deep analysis with relationships:
   python filesync.py ~/Documents --depth 10 --analyze-relationships --report

3. Organize photos by date:
   python filesync.py ~/Photos --organize date --batch

4. Find documents mentioning a script:
   python filesync.py ~/Work --match-file analysis.py --documents-only

5. Full analysis and organization:
   python filesync.py ~/Archive --string-match --full --cluster-projects --organize project --batch
"""

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"FileSync v{VERSION} - Intelligent File Organization")
    print(f"{'='*60}")
    main()
