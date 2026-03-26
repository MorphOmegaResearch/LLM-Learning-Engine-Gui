#!/usr/bin/env python3
"""
Ag Forge Bridge: Staging
------------------------
CLI utility to inject data into the Meta Learn Agriculture staging area.
Called by Quick Clip to push researched entities for validation.
"""

import argparse
import json
import sys
import datetime
import random
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
STAGING_FILE = DATA_DIR / "staging.json"

def load_staging():
    if not STAGING_FILE.exists():
        return {}
    try:
        with open(STAGING_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_staging(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STAGING_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def add_to_staging(content, extracted_json, source_type="quick_clip"):
    staging_data = load_staging()
    
    # Generate ID
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    item_id = f"stage_{timestamp}_{random.randint(100,999)}"
    
    # Create item
    item = {
        "id": item_id,
        "source_type": source_type,
        "source_content": content,
        "extracted_data": extracted_json,
        "confidence_score": 0.0, # Needs human review
        "timestamp": datetime.datetime.now().isoformat(),
        "status": "pending"
    }
    
    staging_data[item_id] = item
    save_staging(staging_data)
    print(f"Success: Added item {item_id} to staging.")

def main():
    parser = argparse.ArgumentParser(description="Bridge to Ag Staging")
    parser.add_argument("--content", help="Raw content text", required=True)
    parser.add_argument("--json", help="JSON string of extracted entity", required=True)
    args = parser.parse_args()
    
    try:
        extracted_data = json.loads(args.json)
        add_to_staging(args.content, extracted_data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON provided. {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
