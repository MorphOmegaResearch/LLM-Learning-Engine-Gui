#!/usr/bin/env python3
"""
Template Storage and Hash Conversion System
Manages Python script templates using SHA256 hashing
"""

import os
import sys
import json
import hashlib
import argparse
import threading
import datetime
import logging
import ast
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('template_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HashMethod(Enum):
    """Supported hash methods"""
    SHA256 = "sha256"
    SHA512 = "sha512"
    MD5 = "md5"

@dataclass
class TemplateMetadata:
    """Metadata for stored templates"""
    name: str
    description: str
    tags: List[str]
    category: int  # 1-10 default categories
    original_path: str
    template_hash: str
    hash_method: str
    created_at: str
    last_accessed: str
    custom_tags: List[str] = None
    ast_info: Dict = None
    
    def __post_init__(self):
        if self.custom_tags is None:
            self.custom_tags = []
        if self.ast_info is None:
            self.ast_info = {}

class TemplateManager:
    """Manages template storage, hashing, and retrieval"""
    
    def __init__(self, base_dir: str = None):
        """Initialize template manager with base directory"""
        self.base_dir = base_dir or os.path.join(os.path.expanduser("~"), ".template_store")
        self.manifest_path = os.path.join(self.base_dir, "manifest", "root.json")
        self.templates_dir = os.path.join(self.base_dir, "templates")
        self.lock = threading.RLock()
        
        # Ensure directories exist
        os.makedirs(os.path.join(self.base_dir, "manifest"), exist_ok=True)
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Load or create manifest
        self.manifest = self._load_manifest()
        
        # Default categories 1-10
        self.default_categories = [str(i) for i in range(1, 11)]
        
    def _load_manifest(self) -> Dict:
        """Load or create the manifest file"""
        try:
            if os.path.exists(self.manifest_path):
                with open(self.manifest_path, 'r') as f:
                    manifest = json.load(f)
                # Ensure structure exists
                if 'templates' not in manifest:
                    manifest['templates'] = {}
                if 'tags_index' not in manifest:
                    manifest['tags_index'] = {}
                if 'categories_index' not in manifest:
                    manifest['categories_index'] = {str(i): [] for i in range(1, 11)}
                return manifest
        except Exception as e:
            logger.warning(f"Could not load manifest: {e}")
        
        # Create new manifest
        manifest = {
            'version': '1.0',
            'created_at': datetime.datetime.now().isoformat(),
            'base_dir': self.base_dir,
            'templates': {},
            'tags_index': {},
            'categories_index': {str(i): [] for i in range(1, 11)},
            'custom_tags': []
        }
        return manifest
    
    def _save_manifest(self):
        """Save manifest to file"""
        with self.lock:
            try:
                with open(self.manifest_path, 'w') as f:
                    json.dump(self.manifest, f, indent=2, default=str)
                logger.debug("Manifest saved successfully")
            except Exception as e:
                logger.error(f"Failed to save manifest: {e}")
    
    def _compute_hash(self, content: str, method: HashMethod = HashMethod.SHA256) -> str:
        """Compute hash of content using specified method"""
        content_bytes = content.encode('utf-8')
        
        if method == HashMethod.SHA256:
            return hashlib.sha256(content_bytes).hexdigest()
        elif method == HashMethod.SHA512:
            return hashlib.sha512(content_bytes).hexdigest()
        elif method == HashMethod.MD5:
            return hashlib.md5(content_bytes).hexdigest()
        else:
            raise ValueError(f"Unsupported hash method: {method}")
    
    def _extract_template_sections(self, script_path: str) -> Dict[str, Any]:
        """Extract template sections and AST information from script"""
        try:
            with open(script_path, 'r') as f:
                content = f.read()
            
            # Parse AST for structure analysis
            tree = ast.parse(content)
            
            ast_info = {
                'functions': [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)],
                'classes': [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)],
                'imports': [ast.unparse(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))],
                'docstrings': []
            }
            
            # Extract docstrings
            for node in ast.walk(tree):
                if hasattr(node, 'body') and node.body and isinstance(node.body[0], ast.Expr):
                    if hasattr(node.body[0], 'value') and isinstance(node.body[0].value, ast.Constant):
                        ast_info['docstrings'].append(str(node.body[0].value.value))
            
            # Look for template markers
            template_start = "# TEMPLATE_START"
            template_end = "# TEMPLATE_END"
            
            lines = content.split('\n')
            template_lines = []
            in_template = False
            
            for line in lines:
                if template_start in line:
                    in_template = True
                    continue
                if template_end in line:
                    in_template = False
                    continue
                if in_template:
                    template_lines.append(line)
            
            template_content = '\n'.join(template_lines) if template_lines else content
            
            return {
                'full_content': content,
                'template_content': template_content,
                'ast_info': ast_info,
                'is_full_script': len(template_lines) == 0
            }
            
        except Exception as e:
            logger.error(f"Failed to extract template sections: {e}")
            return None
    
    def convert_script(self, script_path: str, tags: List[str], category: int, 
                      name: str, description: str, custom_tags: List[str] = None) -> bool:
        """
        Convert a script to template and store with hash
        
        Args:
            script_path: Path to Python script
            tags: List of tags for categorization
            category: Category number (1-10)
            name: Template name
            description: Template description
            custom_tags: Optional custom tags
        
        Returns:
            bool: Success status
        """
        try:
            if not os.path.exists(script_path):
                logger.error(f"Script not found: {script_path}")
                return False
            
            # Validate category
            if category < 1 or category > 10:
                logger.warning(f"Category {category} outside 1-10 range, using default 1")
                category = 1
            
            # Extract template sections
            extraction_result = self._extract_template_sections(script_path)
            if not extraction_result:
                return False
            
            # Compute hash of template content
            template_content = extraction_result['template_content']
            template_hash = self._compute_hash(template_content)
            
            # Create template file with hash as name
            template_filename = f"{template_hash}.template"
            template_filepath = os.path.join(self.templates_dir, template_filename)
            
            # Store template content
            with open(template_filepath, 'w') as f:
                f.write(template_content)
            
            # Create metadata
            metadata = TemplateMetadata(
                name=name,
                description=description,
                tags=tags,
                category=category,
                original_path=os.path.abspath(script_path),
                template_hash=template_hash,
                hash_method=HashMethod.SHA256.value,
                created_at=datetime.datetime.now().isoformat(),
                last_accessed=datetime.datetime.now().isoformat(),
                custom_tags=custom_tags or [],
                ast_info=extraction_result['ast_info']
            )
            
            # Update manifest
            with self.lock:
                self.manifest['templates'][template_hash] = asdict(metadata)
                
                # Update indexes
                for tag in tags:
                    if tag not in self.manifest['tags_index']:
                        self.manifest['tags_index'][tag] = []
                    if template_hash not in self.manifest['tags_index'][tag]:
                        self.manifest['tags_index'][tag].append(template_hash)
                
                # Update category index
                cat_key = str(category)
                if template_hash not in self.manifest['categories_index'][cat_key]:
                    self.manifest['categories_index'][cat_key].append(template_hash)
                
                # Update custom tags
                if custom_tags:
                    for ctag in custom_tags:
                        if ctag not in self.manifest['custom_tags']:
                            self.manifest['custom_tags'].append(ctag)
                
                self._save_manifest()
            
            logger.info(f"Template '{name}' converted and stored with hash: {template_hash}")
            logger.info(f"Category: {category}, Tags: {tags}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to convert script: {e}")
            return False
    
    def inventory_view(self, view_tag: str = None, category: int = None, 
                      show_sub_listings: bool = False) -> None:
        """
        Display inventory of stored templates
        
        Args:
            view_tag: Filter by specific tag
            category: Filter by category (1-10)
            show_sub_listings: Show detailed listings
        """
        with self.lock:
            if view_tag:
                self._view_by_tag(view_tag, show_sub_listings)
            elif category:
                self._view_by_category(category, show_sub_listings)
            else:
                self._view_all(show_sub_listings)
    
    def _view_all(self, show_sub_listings: bool):
        """View all templates"""
        print("\n" + "="*80)
        print("TEMPLATE INVENTORY - ALL TEMPLATES")
        print("="*80)
        
        total_templates = len(self.manifest['templates'])
        print(f"Total Templates: {total_templates}")
        print(f"Total Tags: {len(self.manifest['tags_index'])}")
        print(f"Total Custom Tags: {len(self.manifest['custom_tags'])}")
        
        if show_sub_listings:
            print("\n" + "-"*40)
            print("BY CATEGORY:")
            for cat in range(1, 11):
                templates = self.manifest['categories_index'].get(str(cat), [])
                print(f"  Category {cat}: {len(templates)} templates")
            
            print("\n" + "-"*40)
            print("BY TAG (Top 20):")
            sorted_tags = sorted(self.manifest['tags_index'].items(), 
                               key=lambda x: len(x[1]), reverse=True)[:20]
            for tag, hashes in sorted_tags:
                print(f"  {tag}: {len(hashes)} templates")
        
        # List all templates
        if total_templates > 0:
            print("\n" + "-"*40)
            print("ALL TEMPLATES:")
            for idx, (template_hash, metadata) in enumerate(self.manifest['templates'].items(), 1):
                print(f"\n{idx}. {metadata['name']}")
                print(f"   Hash: {template_hash[:16]}...")
                print(f"   Category: {metadata['category']}")
                print(f"   Tags: {', '.join(metadata['tags'])}")
                print(f"   Description: {metadata['description'][:100]}...")
    
    def _view_by_tag(self, tag: str, show_sub_listings: bool):
        """View templates by tag"""
        print(f"\n" + "="*80)
        print(f"INVENTORY FOR TAG: {tag}")
        print("="*80)
        
        template_hashes = self.manifest['tags_index'].get(tag, [])
        print(f"Found {len(template_hashes)} templates with tag '{tag}'")
        
        if show_sub_listings:
            print("\nDetailed Information:")
            print("-"*40)
        
        for template_hash in template_hashes:
            metadata = self.manifest['templates'].get(template_hash)
            if metadata:
                print(f"\n• {metadata['name']}")
                print(f"  Hash: {template_hash[:16]}...")
                print(f"  Category: {metadata['category']}")
                print(f"  Created: {metadata['created_at'][:10]}")
                if show_sub_listings:
                    print(f"  Description: {metadata['description']}")
                    print(f"  AST Functions: {len(metadata['ast_info'].get('functions', []))}")
                    print(f"  AST Classes: {len(metadata['ast_info'].get('classes', []))}")
    
    def _view_by_category(self, category: int, show_sub_listings: bool):
        """View templates by category"""
        print(f"\n" + "="*80)
        print(f"INVENTORY FOR CATEGORY: {category}")
        print("="*80)
        
        cat_key = str(category)
        template_hashes = self.manifest['categories_index'].get(cat_key, [])
        print(f"Found {len(template_hashes)} templates in category {category}")
        
        if show_sub_listings:
            print("\nTemplates:")
            print("-"*40)
        
        for template_hash in template_hashes:
            metadata = self.manifest['templates'].get(template_hash)
            if metadata:
                print(f"\n• {metadata['name']}")
                print(f"  Tags: {', '.join(metadata['tags'])}")
                if show_sub_listings:
                    print(f"  Description: {metadata['description']}")
                    print(f"  Original: {metadata['original_path']}")
    
    def spawn_template(self, tags: List[str] = None, template_hash: str = None, 
                      output_path: str = None, custom_name: str = None) -> bool:
        """
        Spawn a template from stored hash
        
        Args:
            tags: List of tags to filter by
            template_hash: Specific template hash
            output_path: Output file path
            custom_name: Custom name for spawned template
        
        Returns:
            bool: Success status
        """
        try:
            template_to_spawn = None
            
            # Find template by hash or tags
            if template_hash:
                template_to_spawn = self.manifest['templates'].get(template_hash)
            elif tags:
                # Find intersection of templates with all tags
                template_sets = []
                for tag in tags:
                    if tag in self.manifest['tags_index']:
                        template_sets.append(set(self.manifest['tags_index'][tag]))
                
                if template_sets:
                    # Find common templates across all tags
                    common_templates = set.intersection(*template_sets)
                    if common_templates:
                        # Get first matching template
                        template_hash = list(common_templates)[0]
                        template_to_spawn = self.manifest['templates'].get(template_hash)
            
            if not template_to_spawn:
                logger.error("No matching template found")
                return False
            
            # Load template content
            template_file = os.path.join(self.templates_dir, f"{template_to_spawn['template_hash']}.template")
            if not os.path.exists(template_file):
                logger.error(f"Template file not found: {template_file}")
                return False
            
            with open(template_file, 'r') as f:
                template_content = f.read()
            
            # Determine output path
            if not output_path:
                if custom_name:
                    output_path = f"{custom_name}.py"
                else:
                    output_path = f"spawned_{template_to_spawn['name']}.py"
            
            # Write spawned template
            with open(output_path, 'w') as f:
                # Add header with template info
                header = f'''# Spawned Template: {template_to_spawn['name']}
# Original Hash: {template_to_spawn['template_hash']}
# Category: {template_to_spawn['category']}
# Tags: {', '.join(template_to_spawn['tags'])}
# Description: {template_to_spawn['description']}
# Spawned: {datetime.datetime.now().isoformat()}
# Custom Tags: {', '.join(template_to_spawn.get('custom_tags', []))}

'''
                f.write(header + template_content)
            
            # Update last accessed time
            template_to_spawn['last_accessed'] = datetime.datetime.now().isoformat()
            self._save_manifest()
            
            logger.info(f"Template spawned to: {output_path}")
            logger.info(f"Hash: {template_to_spawn['template_hash']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to spawn template: {e}")
            return False
    
    def list_categories(self) -> None:
        """List all categories with template counts"""
        print("\n" + "="*80)
        print("CATEGORIES INVENTORY")
        print("="*80)
        
        for cat in range(1, 11):
            templates = self.manifest['categories_index'].get(str(cat), [])
            print(f"Category {cat}: {len(templates)} templates")
            
            # Show top 3 templates in each category
            if templates:
                print("  Top templates:")
                for i, template_hash in enumerate(templates[:3], 1):
                    metadata = self.manifest['templates'].get(template_hash)
                    if metadata:
                        print(f"    {i}. {metadata['name']} - {metadata['description'][:50]}...")
                print()
    
    def search_templates(self, search_term: str) -> None:
        """Search templates by name, description, or tags"""
        print(f"\n" + "="*80)
        print(f"SEARCH RESULTS FOR: '{search_term}'")
        print("="*80)
        
        results = []
        search_term_lower = search_term.lower()
        
        for template_hash, metadata in self.manifest['templates'].items():
            # Search in name
            if search_term_lower in metadata['name'].lower():
                results.append((template_hash, metadata))
                continue
            
            # Search in description
            if search_term_lower in metadata['description'].lower():
                results.append((template_hash, metadata))
                continue
            
            # Search in tags
            for tag in metadata['tags']:
                if search_term_lower in tag.lower():
                    results.append((template_hash, metadata))
                    break
            
            # Search in custom tags
            for ctag in metadata.get('custom_tags', []):
                if search_term_lower in ctag.lower():
                    results.append((template_hash, metadata))
                    break
        
        print(f"Found {len(results)} matching templates\n")
        
        for template_hash, metadata in results:
            print(f"• {metadata['name']}")
            print(f"  Hash: {template_hash[:16]}...")
            print(f"  Category: {metadata['category']}")
            print(f"  Tags: {', '.join(metadata['tags'])}")
            print(f"  Description: {metadata['description'][:100]}...")
            print()

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Template Storage and Hash Conversion System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert a script to template
  template_manager.py --convert myscript.py --tag web --tag api --category 5 --name "Web API" --description "REST API template"
  
  # View inventory by tag
  template_manager.py --inventory --view-tag web --sub-listings
  
  # View all inventory
  template_manager.py --inventory --sub-listings
  
  # Spawn template by tag
  template_manager.py --spawn --tag web --tag api --output new_api.py
  
  # Spawn template by hash
  template_manager.py --spawn --template-hash abc123... --output clone.py
  
  # List categories
  template_manager.py --list-categories
  
  # Search templates
  template_manager.py --search "API"
        """
    )
    
    # Main commands
    parser.add_argument('--convert', type=str, help='Convert script to template')
    parser.add_argument('--tag', action='append', help='Tag for template (can be used multiple times)')
    parser.add_argument('--category', type=int, choices=range(1, 11), default=1, 
                       help='Category number 1-10 (default: 1)')
    parser.add_argument('--name', type=str, help='Template name')
    parser.add_argument('--description', type=str, help='Template description')
    parser.add_argument('--custom-tag', action='append', help='Custom tag (can be used multiple times)')
    
    # Inventory/view commands
    parser.add_argument('--inventory', action='store_true', help='View inventory')
    parser.add_argument('--view-tag', type=str, help='View inventory by tag')
    parser.add_argument('--view-category', type=int, choices=range(1, 11), 
                       help='View inventory by category')
    parser.add_argument('--sub-listings', action='store_true', 
                       help='Show detailed sub-listings in inventory')
    
    # Spawn commands
    parser.add_argument('--spawn', action='store_true', help='Spawn template')
    parser.add_argument('--template-hash', type=str, help='Template hash to spawn')
    parser.add_argument('--output', type=str, help='Output file path for spawned template')
    parser.add_argument('--custom-name', type=str, help='Custom name for spawned template')
    
    # Additional commands
    parser.add_argument('--list-categories', action='store_true', 
                       help='List all categories with template counts')
    parser.add_argument('--search', type=str, help='Search templates')
    
    # System options
    parser.add_argument('--base-dir', type=str, help='Base directory for template storage')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Initialize template manager
    manager = TemplateManager(args.base_dir)
    
    # Execute commands based on arguments
    if args.convert:
        if not args.name:
            print("Error: --name is required for conversion")
            sys.exit(1)
        
        tags = args.tag or []
        custom_tags = args.custom_tag or []
        
        success = manager.convert_script(
            script_path=args.convert,
            tags=tags,
            category=args.category,
            name=args.name,
            description=args.description or "",
            custom_tags=custom_tags
        )
        
        if success:
            print(f"✓ Successfully converted '{args.convert}' to template")
        else:
            print(f"✗ Failed to convert '{args.convert}'")
            sys.exit(1)
    
    elif args.inventory or args.view_tag or args.view_category:
        if args.view_tag:
            manager.inventory_view(view_tag=args.view_tag, show_sub_listings=args.sub_listings)
        elif args.view_category:
            manager.inventory_view(category=args.view_category, show_sub_listings=args.sub_listings)
        else:
            manager.inventory_view(show_sub_listings=args.sub_listings)
    
    elif args.spawn:
        tags = args.tag or []
        
        success = manager.spawn_template(
            tags=tags,
            template_hash=args.template_hash,
            output_path=args.output,
            custom_name=args.custom_name
        )
        
        if success:
            print("✓ Template spawned successfully")
        else:
            print("✗ Failed to spawn template")
            sys.exit(1)
    
    elif args.list_categories:
        manager.list_categories()
    
    elif args.search:
        manager.search_templates(args.search)
    
    else:
        print("No command specified. Use --help for usage information.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)