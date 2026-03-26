#!/usr/bin/env python3
"""
Agricultural Data Importer
--------------------------
Handles the parsing and processing of "Trusted Merit" taxonomic data from various sources,
including the Catalogue of Life (COL) archives.

Designed to:
1. Process large TSV and other data files efficiently (line-by-line).
2. Extract relevant taxonomic, distribution, and vernacular name data.
3. Filter data based on user-defined agricultural focus.
4. Prepare data for ingestion into the Ag_Forge knowledge base.
"""

import csv
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Generator, Any
import sys
import datetime

# Ensure the project root is in the system path to allow imports from other modules
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import Ag_Forge data models and app controller
try:
    from modules.meta_learn_agriculture import KnowledgeForgeApp, Entity, EntityType, HealthStatus, Disease
except ImportError as e:
    print(f"Error importing Ag_Forge components in ag_importer: {e}", file=sys.stderr)
    # Provide dummy classes to allow the rest of the file to be parsed for basic checks
    class KnowledgeForgeApp: pass
    class Entity: pass
    class EntityType: ANIMAL="Animal"; PLANT="Plant"; DISEASE="Disease"
    class HealthStatus: GOOD="Good"
    class Disease: pass

def parse_metadata(metadata_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parses the metadata.yaml file to get information about the dataset.

    Args:
        metadata_path: Path to the metadata.yaml file.

    Returns:
        A dictionary containing the parsed metadata, or None on error.
    """
    if not metadata_path.exists():
        print(f"Error: Metadata file not found at {metadata_path}", file=sys.stderr)
        return None
    try:
        with open(metadata_path, 'r') as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, IOError) as e:
        print(f"Error parsing metadata file {metadata_path}: {e}", file=sys.stderr)
        return None

def stream_tsv_file(file_path: Path) -> Generator[Dict[str, str], None, None]:
    """
    Reads a large TSV file line-by-line to avoid high memory usage.

    Args:
        file_path: Path to the TSV file.

    Yields:
        A dictionary representing a single row from the TSV file.
    """
    if not file_path.exists():
        print(f"Error: Data file not found at {file_path}", file=sys.stderr)
        return
        
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                yield row
    except (IOError, csv.Error) as e:
        print(f"Error reading or parsing TSV file {file_path}: {e}", file=sys.stderr)

def filter_by_focus(data_stream: Generator, focus_keywords: List[str]) -> Generator:
    """
    Filters a stream of data based on a list of focus keywords.
    (Placeholder for more complex filtering logic).

    Args:
        data_stream: A generator yielding data dictionaries.
        focus_keywords: A list of keywords defining the user's business focus.

    Yields:
        Data dictionaries that match the filter criteria.
    """
    # This is a placeholder. The actual implementation will need to know which
    # fields to check for matches (e.g., 'scientificName', 'vernacularName', 'phylum').
    print(f"DEBUG: Filtering stream with keywords: {focus_keywords}")
    for item in data_stream:
        # Example simplistic filtering logic:
        # Check a 'col:name' field if it exists.
        name = item.get('col:name', '').lower()
        if any(keyword.lower() in name for keyword in focus_keywords):
            yield item

def populate_ag_forge_data(
    app: KnowledgeForgeApp,
    data_stream: Generator[Dict[str, str], None, None],
    business_focus: Dict
):
    """
    Populates the Ag_Forge application with data from the filtered taxonomic stream.
    This function will create new Entity objects in Ag_Forge.

    Args:
        app: An instance of the KnowledgeForgeApp.
        data_stream: A generator yielding dictionaries of filtered taxonomic data.
        business_focus: The user\'s defined agricultural business focus, including keywords.
    """
    print("DEBUG: Starting Ag_Forge data population...")
    processed_count = 0
    for item in data_stream:
        # Extract relevant fields from the taxonomic data
        taxon_id = item.get('taxonID', f"taxon_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
        vernacular_name = item.get('vernacularName', 'Unknown')
        scientific_name = item.get('scientificName', vernacular_name) # Fallback
        category = business_focus.get('domain', 'General Agriculture') # Use business domain as category
        tags = list(set([t.strip() for t in vernacular_name.split() + business_focus.get('keywords', []) if t.strip()]))

        # Determine EntityType based on domain, or default to ANIMAL
        entity_type = EntityType.ANIMAL
        if "Crop Science" in category or "Horticulture" in category:
            entity_type = EntityType.PLANT
        elif "Equipment" in category:
            entity_type = EntityType.EQUIPMENT # Placeholder if we get equipment data

        # Create a new Entity object
        new_entity_data = {
            'name': vernacular_name,
            'type': entity_type,
            'category': category,
            'species': scientific_name, # Storing scientific name in species for now
            'description': f"Taxonomic data for {scientific_name} (COL source).",
            'tags': tags,
            'last_updated': datetime.datetime.now().isoformat()
        }

        try:
            # Check if an entity with this scientific name already exists to avoid duplicates
            # This is a simplistic check; a more robust solution would use taxonID or other unique identifiers
            existing_entity = None
            for e_id, entity in app.entities.items():
                if entity.species == scientific_name and entity.type == entity_type:
                    existing_entity = entity
                    break
            
            if existing_entity:
                print(f"DEBUG: Updating existing entity: {existing_entity.name} (ID: {existing_entity.id})")
                # For simplicity, we just update tags and last_updated for existing entities
                app.update_entity(existing_entity.id, {
                    'tags': list(set(existing_entity.tags + tags)),
                    'last_updated': datetime.datetime.now().isoformat()
                })
            else:
                app.create_entity(new_entity_data)
                print(f"DEBUG: Created new entity: {vernacular_name} ({scientific_name})")
            processed_count += 1
        except Exception as e:
            print(f"Error creating/updating entity for {vernacular_name} ({scientific_name}): {e}", file=sys.stderr)

    print(f"DEBUG: Finished Ag_Forge data population. Processed {processed_count} items.")
    app.save_data() # Save all changes after processing the stream

if __name__ == '__main__':
    # Example usage for testing the module directly
    print("Testing ag_importer...")
    
    # Define a mock import directory for the test
    mock_import_path = Path(__file__).parent / "Imports" / "seed_pack"
    
    # 1. Test Metadata Parsing
    print("\n--- Testing Metadata Parsing ---")
    metadata = parse_metadata(mock_import_path / "metadata.yaml")
    if metadata:
        print(f"Successfully parsed metadata for: {metadata.get('title')}")
        print(f"Version: {metadata.get('version')}")
    else:
        print("Metadata parsing failed.")

    # 2. Test TSV Streaming (using VernacularName.tsv as it's smaller)
    print("\n--- Testing TSV Streaming ---")
    vernacular_path = mock_import_path / "VernacularName.tsv"
    if vernacular_path.exists():
        count = 0
        for i, row in enumerate(stream_tsv_file(vernacular_path)):
            if i < 5: # Print first 5 records
                print(f"Row {i+1}: {row.get('taxonID')}, Name: {row.get('vernacularName')}")
            count += 1
        print(f"Successfully streamed {count} records from {vernacular_path.name}")
    else:
        print(f"Could not find {vernacular_path.name} for testing.")

    # 3. Test Filtering
    print("\n--- Testing Filtering ---")
    if vernacular_path.exists():
        stream = stream_tsv_file(vernacular_path)
        filtered_stream = filter_by_focus(stream, ["Cattle", "Cow"])
        
        print("Found matching 'Cattle' or 'Cow' records:")
        found_count = 0
        for record in filtered_stream:
            print(f" - {record.get('vernacularName')} (Taxon ID: {record.get('taxonID')})")
            found_count += 1
        print(f"Found a total of {found_count} matching records.")
    else:
        print(f"Could not find {vernacular_path.name} for testing.")
