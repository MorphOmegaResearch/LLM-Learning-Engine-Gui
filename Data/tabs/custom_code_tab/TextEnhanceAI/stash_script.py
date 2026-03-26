#!/usr/bin/env python3

import os
import sys
import argparse
import shutil
import json
from pathlib import Path
import datetime
import uuid

class ConfigManager:
    DEFAULT_CONFIG = {
        'base_dir': None, # Will be set in __init__
        'snapshot_dir': None, # Will be set in __init__
        'inventory_dir': None, # Will be set in __init__
        'known_inventories': []
    }

    def __init__(self, script_dir=None):
        # Determine the script's current directory
        if script_dir:
            self.script_dir = os.path.abspath(script_dir)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Default configuration file
        self.config_path = os.path.join(self.script_dir, 'config.json')
        self.manifest_path = os.path.join(self.script_dir, 'manifest.json')
        
        # Load or initialize configuration and manifest
        self.config = self.load_config()
        # Ensure base_dir and related paths are set if not present in loaded config
        if self.config['base_dir'] is None:
            self.config['base_dir'] = self.script_dir
            self.config['snapshot_dir'] = os.path.join(self.script_dir, 'snapshots')
            self.config['inventory_dir'] = os.path.join(self.script_dir, 'inventory')
            self.save_config() # Save the updated default config
        
        self.manifest = self.load_manifest()

    def load_config(self):
        """Load existing configuration or create a default one, ensuring all keys are present."""
        loaded_config = {}
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
        
        # Start with a copy of the default config
        merged_config = self.DEFAULT_CONFIG.copy()
        # Update with loaded values
        merged_config.update(loaded_config)
        
        # Ensure base_dir and related paths are correctly initialized if still None
        if merged_config['base_dir'] is None:
            merged_config['base_dir'] = self.script_dir
        if merged_config['snapshot_dir'] is None:
            merged_config['snapshot_dir'] = os.path.join(merged_config['base_dir'], 'snapshots')
        if merged_config['inventory_dir'] is None:
            merged_config['inventory_dir'] = os.path.join(merged_config['base_dir'], 'inventory')

        return merged_config

    def save_config(self):
        """Save current configuration to config file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            print("Configuration saved successfully.")
        except Exception as e:
            print(f"Error saving config: {e}")

    def load_manifest(self):
        """Load existing manifest or return an empty one."""
        try:
            if os.path.exists(self.manifest_path):
                with open(self.manifest_path, 'r') as f:
                    return json.load(f)
            else:
                return []
        except Exception as e:
            print(f"Error loading manifest: {e}")
            return []

    def save_manifest(self):
        """Save current manifest to manifest file."""
        try:
            with open(self.manifest_path, 'w') as f:
                json.dump(self.manifest, f, indent=4)
            print("Manifest saved successfully.")
        except Exception as e:
            print(f"Error saving manifest: {e}")

    def confirm_base_dir(self, gui_mode=False):
        """Confirm and potentially modify base directory."""
        if gui_mode:
            # In GUI mode, do not prompt for input. Assume confirmation.
            # If the base_dir needs to be changed, the GUI should provide controls for it.
            print(f"GUI Mode: Base directory confirmed as {self.config['base_dir']}")
            # Record base_dir update in manifest (even if just confirmed)
            base_dir_id = str(uuid.uuid4())
            manifest_entry = {
                'id': base_dir_id,
                'timestamp': datetime.datetime.now().isoformat(),
                'type': 'base_dir_update',
                'base_dir': self.config['base_dir']
            }
            self.manifest.append(manifest_entry)
            self.save_manifest()
            return
        
        print(f"Current base directory: {self.config['base_dir']}")
        confirm = input("Confirm this as base directory? (y/n): ").lower()
        
        if confirm != 'y':
            new_base_dir = input("Enter new base directory path: ").strip()
            if os.path.isdir(new_base_dir):
                self.config['base_dir'] = os.path.abspath(new_base_dir)
                self.config['snapshot_dir'] = os.path.join(new_base_dir, 'snapshots')
                self.config['inventory_dir'] = os.path.join(new_base_dir, 'inventory')
                self.save_config()
            else:
                print("Invalid directory. Using current base directory.")
        
        # Record base_dir update in manifest
        base_dir_id = str(uuid.uuid4())
        manifest_entry = {
            'id': base_dir_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'type': 'base_dir_update',
            'base_dir': self.config['base_dir']
        }
        self.manifest.append(manifest_entry)
        self.save_manifest()

def perform_quick_stash(config_manager):
    """
    Moves all files from the current directory into a timestamped subdirectory
    within the configured snapshot directory.
    """
    snapshot_base_dir = config_manager.config['snapshot_dir']
    
    # Ensure the base snapshot directory exists
    os.makedirs(snapshot_base_dir, exist_ok=True)

    # Create a timestamped directory for the current stash
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stash_target_dir = os.path.join(snapshot_base_dir, f"stash_{timestamp}")
    os.makedirs(stash_target_dir, exist_ok=True)
    
    print(f"Performing quick stash to: {stash_target_dir}")
    
    stashed_files_count = 0
    stashed_file_names = []
    current_dir_contents = os.listdir('.') # Moved this line up
    for item in current_dir_contents:
        item_path = os.path.abspath(item)
        # Exclude config.json, manifest.json, and the script itself
        is_config = (item == os.path.basename(config_manager.config_path))
        is_manifest = (item == os.path.basename(config_manager.manifest_path))
        is_self_script = (item == os.path.basename(os.path.abspath(__file__)))

        if os.path.isfile(item_path) and not is_config and not is_manifest and not is_self_script:
            try:
                shutil.move(item_path, stash_target_dir)
                print(f"  Stashed: {item}")
                stashed_files_count += 1
                stashed_file_names.append(item)
            except Exception as e:
                print(f"  Error stashing {item}: {e}")
    
    if stashed_files_count > 0:
        print(f"Quick stash complete. {stashed_files_count} file(s) stashed.")
        
        # Record in manifest
        stash_id = str(uuid.uuid4())
        manifest_entry = {
            'id': stash_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'type': 'quick_stash',
            'source_dir': os.getcwd(),
            'target_dir': stash_target_dir,
            'stashed_files': stashed_file_names # Assuming stashed_file_names is collected
        }
        config_manager.manifest.append(manifest_entry)
        config_manager.save_manifest()
    else:
        print("No files found to stash in the current directory.")

def perform_copy_self_stash(config_manager, target_dir):
    """
    Copies the script itself to a new target directory, updates the base_dir
    in the configuration, and then stashes other files from the original
    current directory into the new snapshot directory.
    """
    original_script_path = os.path.abspath(__file__)
    original_cwd = os.getcwd() # Store original current working directory

    # 1. Create target_dir if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)
    
    # 2. Copy the current script to target_dir
    new_script_path = os.path.join(target_dir, os.path.basename(original_script_path))
    try:
        shutil.copy2(original_script_path, new_script_path)
        print(f"Script copied to: {new_script_path}")
    except Exception as e:
        print(f"Error copying script: {e}")
        return # Abort if script cannot be copied

    # 3. Create and save a new config for the copied script
    new_config_path = os.path.join(target_dir, 'config.json')
    new_manifest_path = os.path.join(target_dir, 'manifest.json')

    new_config_data = {
        'base_dir': os.path.abspath(target_dir),
        'snapshot_dir': os.path.join(target_dir, 'snapshots'),
        'inventory_dir': os.path.join(target_dir, 'inventory')
    }
    try:
        with open(new_config_path, 'w') as f:
            json.dump(new_config_data, f, indent=4)
        print(f"New configuration saved for copied script at: {new_config_path}")
    except Exception as e:
        print(f"Error saving new config for copied script: {e}")
        return

    # Also handle manifest for the new script
    original_manifest_path = os.path.join(os.path.dirname(original_script_path), 'manifest.json')
    if os.path.exists(original_manifest_path):
        try:
            shutil.copy2(original_manifest_path, new_manifest_path)
            print(f"Original manifest copied to: {new_manifest_path}")
        except Exception as e:
            print(f"Error copying original manifest: {e}")
            # If copy fails, create an empty one to avoid errors later
            try:
                with open(new_manifest_path, 'w') as f:
                    json.dump([], f, indent=4)
                print(f"Empty manifest created for copied script at: {new_manifest_path} due to copy error.")
            except Exception as e_inner:
                print(f"Error creating empty manifest after copy failure: {e_inner}")
    else:
        try:
            with open(new_manifest_path, 'w') as f:
                json.dump([], f, indent=4)
            print(f"Empty manifest created for copied script at: {new_manifest_path}")
        except Exception as e:
            print(f"Error creating empty manifest for copied script: {e}")
            return

    # 4. Perform the stash operation for other files from the original CWD
    # Use the snapshot_dir from the *new* config for stashing
    snapshot_base_dir_for_stash = new_config_data['snapshot_dir']
    os.makedirs(snapshot_base_dir_for_stash, exist_ok=True) # Ensure new snapshot dir exists

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stash_target_dir = os.path.join(snapshot_base_dir_for_stash, f"stash_{timestamp}")
    os.makedirs(stash_target_dir, exist_ok=True)
    
    print(f"Stashing other files from '{original_cwd}' to: {stash_target_dir}")
    
    stashed_files_count = 0
    stashed_file_names = []
    for item in os.listdir(original_cwd):
        item_path = os.path.join(original_cwd, item)
        if os.path.isfile(item_path) and item_path != original_script_path:
            try:
                shutil.move(item_path, stash_target_dir)
                print(f"  Stashed: {item}")
                stashed_files_count += 1
                stashed_file_names.append(item)
            except Exception as e:
                print(f"  Error stashing {item}: {e}")
    
    if stashed_files_count > 0:
        print(f"Copy self and stash complete. {stashed_files_count} other file(s) stashed.")
        
        # Record in manifest for the *new* script's manifest
        stash_id = str(uuid.uuid4())
        manifest_entry = {
            'id': stash_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'type': 'copy_self_stash',
            'source_dir': original_cwd,
            'target_dir': stash_target_dir,
            'new_script_path': new_script_path,
            'stashed_files': stashed_file_names
        }
        
        # Load the new manifest, append, and save
        new_manifest_data = []
        if os.path.exists(new_manifest_path):
            try:
                with open(new_manifest_path, 'r') as f:
                    new_manifest_data = json.load(f)
            except Exception as e:
                print(f"Error loading new manifest for appending: {e}")
        
        new_manifest_data.append(manifest_entry)
        try:
            with open(new_manifest_path, 'w') as f:
                json.dump(new_manifest_data, f, indent=4)
            print("Manifest updated for copied script.")
        except Exception as e:
            print(f"Error saving new manifest for copied script: {e}")
    else:
        print("No other files found to stash in the original directory.")

def perform_restore(config_manager, stash_id):
    """
    Restores stashed files from a snapshot directory back to their original location.
    """
    found_stash_index = -1
    found_stash = None
    for i, entry in enumerate(config_manager.manifest):
        if entry['id'].startswith(stash_id): # Allow partial ID match
            found_stash_index = i
            found_stash = entry
            break
    
    if not found_stash:
        print(f"Error: Stash with ID '{stash_id}' not found in manifest.")
        return

    print(f"\n--- Restoring Stash ID: {found_stash['id']} ---")
    display_stash_details(found_stash) # Use the existing display function

    confirm = input("Are you sure you want to restore this stash? This will move files back to their original location. (y/n): ").lower()
    if confirm != 'y':
        print("Restore cancelled.")
        return

    source_dir = found_stash['source_dir']
    target_dir = found_stash['target_dir']
    stashed_files = found_stash['stashed_files']

    # Ensure source directory exists
    os.makedirs(source_dir, exist_ok=True)

    restored_files_count = 0
    for filename in stashed_files:
        source_file_path = os.path.join(target_dir, filename)
        destination_file_path = os.path.join(source_dir, filename)
        
        if os.path.exists(source_file_path):
            try:
                shutil.move(source_file_path, destination_file_path)
                print(f"  Restored: {filename} to {source_dir}")
                restored_files_count += 1
            except Exception as e:
                print(f"  Error restoring {filename}: {e}")
        else:
            print(f"  Warning: Stashed file '{filename}' not found in '{target_dir}'.")
    
    if restored_files_count > 0:
        print(f"Restore complete. {restored_files_count} file(s) restored.")
    else:
        print("No files were restored.")

    # Clean up: remove entry from manifest
    config_manager.manifest.pop(found_stash_index)
    config_manager.save_manifest()
    print("Stash entry removed from manifest.")

    # Clean up: remove empty target directory
    try:
        if not os.listdir(target_dir): # Check if directory is empty
            os.rmdir(target_dir)
            print(f"Removed empty stash directory: {target_dir}")
    except OSError as e:
        print(f"Error removing empty stash directory '{target_dir}': {e}")

def perform_lineage_view(config_manager):
    """
    Processes the manifest to display inventory activity over time,
    listing all events chronologically.
    """
    print("\n--- Inventory Lineage View ---")
    if not config_manager.manifest:
        print("No activity recorded in manifest yet.")
        return

    # Sort all manifest entries chronologically
    sorted_manifest = sorted(config_manager.manifest, key=lambda x: x['timestamp'])

    for entry in sorted_manifest:
        display_stash_details(entry)
        print("-" * 20) # Separator
    
    print(f"\nTotal events recorded: {len(sorted_manifest)}")

def get_function_line_numbers():
    """
    Reads the script's source code and returns a dictionary mapping
    function/class names to their starting line numbers.
    """
    line_numbers = {}
    try:
        with open(os.path.abspath(__file__), 'r') as f:
            for i, line in enumerate(f.readlines()):
                stripped_line = line.strip()
                if stripped_line.startswith('def ') or stripped_line.startswith('class '):
                    # Extract name, handling potential (self) or (args)
                    name_part = stripped_line.split(' ')[1]
                    name = name_part.split('(')[0].split(':')[0]
                    line_numbers[name] = i + 1 # Line numbers are 1-based
    except Exception as e:
        print(f"Error getting function line numbers: {e}")
    return line_numbers

def get_relative_imports(file_path):
    """
    Reads a Python file and returns a list of relative import statements found.
    """
    imports = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line.startswith('from .') and 'import' in stripped_line:
                    imports.append(stripped_line)
                elif stripped_line.startswith('import .') and 'from' not in stripped_line: # Handles 'import .module'
                    imports.append(stripped_line)
    except Exception as e:
        print(f"Error getting relative imports from {file_path}: {e}")
    return imports

def add_inventory_entry(config_manager, name, path):
    """Adds a new inventory entry to the config_manager."""
    if not os.path.isdir(path):
        return False, f"Error: Inventory path '{path}' does not exist or is not a directory."
    
    # Check if inventory with this name or path already exists
    for inv in config_manager.config['known_inventories']:
        if inv['name'] == name:
            return False, f"Error: Inventory with name '{name}' already exists."
        if os.path.abspath(inv['path']) == os.path.abspath(path):
            return False, f"Error: Inventory with path '{path}' already exists."
    
    config_manager.config['known_inventories'].append({'name': name, 'path': os.path.abspath(path), 'tags': [name]}) # Add name as default tag
    config_manager.save_config()
    return True, f"Inventory '{name}' added with path '{os.path.abspath(path)}'."

def tag_inventory_entry(config_manager, name, tag):
    """Adds a tag to an existing inventory."""
    found_inventory = None
    for inv in config_manager.config['known_inventories']:
        if inv['name'] == name:
            found_inventory = inv
            break
    
    if found_inventory:
        if tag not in found_inventory['tags']:
            found_inventory['tags'].append(tag)
            config_manager.save_config()
            return True, f"Tag '{tag}' added to inventory '{name}'."
        else:
            return False, f"Inventory '{name}' already has tag '{tag}'."
    else:
        return False, f"Error: Inventory with name '{name}' not found."

def create_parser():
    """Create argument parser with comprehensive options."""
    parser = argparse.ArgumentParser(
        description='Flexible directory and inventory management script',
        epilog='Use -h for detailed help on available commands.'
    )
    
    # Base directory configuration
    parser.add_argument('-b', '--base', 
                        help='Set or view base directory', 
                        nargs='?', 
                        const='view', 
                        metavar='PATH')
    
    # Snapshot management
    parser.add_argument('-s', '--snapshot', 
                        help='Create or manage snapshots', 
                        action='store_true')
    
    # View current configuration or manifest
    parser.add_argument('-v', '--view', 
                        help='View current configuration, manifest, or a specific inventory. Optionally provide a STASH_ID or INVENTORY_NAME.', 
                        nargs='?', 
                        const='list', # Changed back to 'list'
                        metavar='ID_OR_NAME')
    
    # Restore stash functionality
    parser.add_argument('--restore', 
                        help='Restore a specific stash by its ID', 
                        metavar='STASH_ID')
    
    # Inventory management
    inventory_group = parser.add_argument_group('Inventory Management')
    inventory_group.add_argument('--add-inventory',
                                 nargs='+', # Changed from 2 to '+'
                                 metavar=('NAME', 'PATH'),
                                 help='Add a new inventory. Use "--add-inventory <PATH>" to use path as name, or "--add-inventory <NAME> <PATH>".')
    inventory_group.add_argument('--list-inventories',
                                 action='store_true',
                                 help='List all known inventories.')
    inventory_group.add_argument('--tag-inventory',
                                 nargs=2,
                                 metavar=('NAME', 'TAG'),
                                 help='Add a tag to an existing inventory.')
    
    # Lineage view
    parser.add_argument('-l', '--lineage',
                        action='store_true',
                        help='Display inventory activity over time (lineage view).')
    
    return parser

def main():
    # Initialize configuration manager
    config_manager = ConfigManager()
    
    parser = create_parser()
    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 0: # Help message was requested
            parser.print_help()
            print("\n--- Pre-flight Check (Function Line Numbers) ---")
            line_numbers = get_function_line_numbers()
            for name, line_num in line_numbers.items():
                print(f"  {name}: Line {line_num}")
            
            print("\n--- Pre-flight Check (Relative Imports) ---")
            script_path = os.path.abspath(__file__)
            relative_imports = get_relative_imports(script_path)
            if relative_imports:
                for imp in relative_imports:
                    print(f"  {imp}")
            else:
                print("  No relative imports found.")
            sys.exit(0) # Exit cleanly after printing help and PFC
        else:
            sys.exit(e.code) # Re-raise other SystemExit errors

    if hasattr(args, 'copy_self_to') and args.copy_self_to:
        perform_copy_self_stash(config_manager, args.copy_self_to)
        return # Exit after copying and stashing
    
    # Handle inventory management arguments
    if hasattr(args, 'add_inventory') and args.add_inventory:
        if len(args.add_inventory) == 1:
            path = args.add_inventory[0]
            name = os.path.basename(os.path.abspath(path)) # Default name to basename of path
        elif len(args.add_inventory) == 2:
            name, path = args.add_inventory
        else:
            print("Error: --add-inventory expects either 1 (PATH) or 2 (NAME PATH) arguments.")
            return
        
        success, message = add_inventory_entry(config_manager, name, path)
        print(message)
        return

    if hasattr(args, 'list_inventories') and args.list_inventories:
        print("\n--- Known Inventories ---")
        if not config_manager.config['known_inventories']:
            print("No inventories registered yet.")
        else:
            for inv in config_manager.config['known_inventories']:
                tags_str = f" (Tags: {', '.join(inv['tags'])})" if inv['tags'] else ""
                print(f"  Name: {inv['name']}, Path: {inv['path']}{tags_str}")
        return

    if hasattr(args, 'tag_inventory') and args.tag_inventory:
        name, tag = args.tag_inventory
        success, message = tag_inventory_entry(config_manager, name, tag)
        print(message)
        return

    # Confirm base directory only if no primary action arguments are present
    if not ((hasattr(args, 'quick_stash') and args.quick_stash) or \
            (hasattr(args, 'view') and args.view) or \
            (hasattr(args, 'restore') and args.restore) or \
            (hasattr(args, 'base') and args.base) or \
            (hasattr(args, 'lineage') and args.lineage) or \
            (hasattr(args, 'snapshot') and args.snapshot) or \
            (hasattr(args, 'inventory') and args.inventory)):
        config_manager.confirm_base_dir(gui_mode=False)

    # Parse arguments again (or use the already parsed args)
    # args = create_parser().parse_args() # Already parsed above

    if hasattr(args, 'base') and args.base == 'view':
        print(f"Base directory: {config_manager.config['base_dir']}")
    elif hasattr(args, 'base') and args.base:
        if os.path.isdir(args.base):
            config_manager.config['base_dir'] = os.path.abspath(args.base)
            config_manager.config['snapshot_dir'] = os.path.join(args.base, 'snapshots')
            config_manager.config['inventory_dir'] = os.path.join(args.base, 'inventory')
            config_manager.save_config()
            print(f"Base directory set to: {config_manager.config['base_dir']}")
        else:
            print(f"Error: Directory '{args.base}' not found.")
    
    if hasattr(args, 'view') and args.view:
        if args.view == 'list':
            print("\n--- Stash Manifest ---")
            if not config_manager.manifest:
                print("No stashes recorded yet.")
            else:
                for entry in config_manager.manifest:
                    display_stash_details(entry)
                    print("-" * 20) # Separator
        else: # args.view is either a STASH_ID or an INVENTORY_NAME
            # First, try to find as a STASH_ID
            stash_id_to_find = args.view
            found_stash = None
            for entry in config_manager.manifest:
                if entry['id'].startswith(stash_id_to_find): # Allow partial ID match
                    found_stash = entry
                    break
            
            if found_stash:
                print(f"\n--- Details for Stash ID: {found_stash['id']} ---")
                display_stash_details(found_stash)
                # Offer to open directory
                confirm_open = input(f"Open target directory '{found_stash['target_dir']}'? (y/n): ").lower()
                if confirm_open == 'y':
                    try:
                        print(f"Listing contents of: {found_stash['target_dir']}")
                        for item in os.listdir(found_stash['target_dir']):
                            print(f"  - {item}")
                    except Exception as e:
                        print(f"Error opening directory: {e}")
            else:
                # If not a STASH_ID, try to find as an INVENTORY_NAME
                inventory_name_to_find = args.view
                found_inventory = None
                for inv in config_manager.config['known_inventories']:
                    if inv['name'] == inventory_name_to_find:
                        found_inventory = inv
                        break
                
                if found_inventory:
                    print(f"\n--- Details for Inventory: {found_inventory['name']} ---")
                    print(f"  Path: {found_inventory['path']}")
                    if found_inventory['tags']:
                        print(f"  Tags: {', '.join(found_inventory['tags'])}")
                    # Optionally, list stashes associated with this inventory
                    print("\n  --- Stashes in this Inventory ---")
                    inventory_stashes_found = False
                    for entry in config_manager.manifest:
                        # This needs a way to link stashes to inventories.
                        # For now, we'll assume source_dir is within the inventory path.
                        if entry.get('source_dir', '').startswith(found_inventory['path']):
                            display_stash_details(entry)
                            print("-" * 20)
                            inventory_stashes_found = True
                    if not inventory_stashes_found:
                        print("  No stashes directly associated with this inventory found in manifest.")
                else:
                    print(f"Stash with ID or Inventory with Name '{args.view}' not found.")

    if hasattr(args, 'quick_stash') and args.quick_stash:
        perform_quick_stash(config_manager)
    elif hasattr(args, 'restore') and args.restore:
        perform_restore(config_manager, args.restore)
    elif hasattr(args, 'lineage') and args.lineage:
        perform_lineage_view(config_manager)

    if hasattr(args, 'snapshot') and args.snapshot:
        print("Snapshot management functionality (not yet implemented).")

    if hasattr(args, 'inventory') and args.inventory:
        print("Inventory management functionality (not yet implemented).")

def display_stash_details(entry):
    """Helper function to display formatted stash details."""
    print(f"ID: {entry.get('id', 'N/A')}")
    print(f"Timestamp: {entry.get('timestamp', 'N/A')}")
    print(f"Type: {entry.get('type', 'N/A')}")
    
    if entry.get('type') == 'base_dir_update':
        print(f"Base Dir: {entry.get('base_dir', 'N/A')}")
    else:
        print(f"Source Dir: {entry.get('source_dir', 'N/A')}")
        print(f"Target Dir: {entry.get('target_dir', 'N/A')}")
        if 'new_script_path' in entry:
            print(f"New Script Path: {entry['new_script_path']}")
        print(f"Stashed Files: {', '.join(entry.get('stashed_files', []))}")

if __name__ == "__main__":
    main()
