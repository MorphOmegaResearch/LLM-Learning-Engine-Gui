
import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

def fetch_taxonomical_data(species_name):
    """Use ai_search to fetch taxonomical data."""
    print(f"Fetching taxonomical data for: {species_name}")
    
    # Construct query
    query = f"Provide full taxonomical hierarchy (Kingdom to Species) and common breeds for {species_name} in JSON format. include 'kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species', 'common_breeds'."
    
    # Path to ai_search.py
    ai_search_path = Path(__file__).parent / "ai_search.py"
    
    # Run ai_search.py
    # We want it to be headless and fast if possible
    try:
        # Note: ai_search.py saves to RESULTS_DIR which is /home/commander/Custom_Applications/Research_Results
        # We might want to capture its output directly or read the latest file.
        subprocess.run([sys.executable, str(ai_search_path), "--headless", "--assume-yes", query], check=True)
        print("AI Search completed.")
        return True
    except Exception as e:
        print(f"Error running AI search: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Ag Forge Data Migration Tool")
    parser.add_argument("--species", help="Species name to migrate", required=True)
    args = parser.parse_args()
    
    success = fetch_taxonomical_data(args.species)
    if success:
        print("Data fetched. Please review in Research Results and use 'Draft Ag Entity' tool to import.")
    else:
        print("Migration failed.")

if __name__ == "__main__":
    main()
