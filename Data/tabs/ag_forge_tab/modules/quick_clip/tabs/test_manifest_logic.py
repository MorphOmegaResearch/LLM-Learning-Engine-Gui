
import sys
import json
from pathlib import Path

# Mock setup
base_path = Path("/home/commander/Trainer/Data")
manifest_path = base_path / "pymanifest" / "py_manifest_augmented.json"

def test_manifest_load():
    print(f"Testing manifest load from: {manifest_path}")
    if not manifest_path.exists():
        print("Manifest file not found!")
        return

    try:
        with open(manifest_path, 'r') as f:
            data = json.load(f)
        
        files = data.get("files", {})
        print(f"Loaded manifest with {len(files)} files.")
        
        # Test finding a file by basename
        test_file = "py_manifest_augmented.py"
        found = None
        for fpath, info in files.items():
            if fpath.endswith(f"/{test_file}") or fpath == test_file:
                found = info
                break
        
        if found:
            print(f"Found info for {test_file}:")
            print(f"  Path: {found.get('file_path')}")
            print(f"  Classes: {[c['name'] for c in found.get('classes', [])]}")
            print(f"  Functions: {[f['name'] for f in found.get('functions', [])]}")
            print(f"  Complexity: {sum(f.get('complexity', 1) for f in found.get('functions', []))}")
        else:
            print(f"Could not find entry for {test_file}")

    except Exception as e:
        print(f"Error loading manifest: {e}")

if __name__ == "__main__":
    test_manifest_load()
