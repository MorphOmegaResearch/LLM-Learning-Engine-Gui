
import json
import os
import re
from pathlib import Path

class AgKnowledgeLinker:
    def __init__(self, data_root=None):
        if data_root is None:
            # Try to find data root relative to this file
            # Assuming modules/quick_clip/ag_utils.py
            self.base_path = Path(__file__).parent.parent.parent / "knowledge_forge_data"
        else:
            self.base_path = Path(data_root)
            
        self.entities_path = self.base_path / "data" / "entities.json"
        self.diseases_path = self.base_path / "data" / "diseases.json"
        self.entities = {}
        self.diseases = {}
        self.load_data()

    def load_data(self):
        if self.entities_path.exists():
            try:
                with open(self.entities_path, 'r') as f:
                    self.entities = json.load(f)
            except:
                self.entities = {}
        
        if self.diseases_path.exists():
            try:
                with open(self.diseases_path, 'r') as f:
                    self.diseases = json.load(f)
            except:
                self.diseases = {}

    def scan_text(self, text):
        """Scan text for entity names, breeds, and diseases."""
        found = {
            "entities": [],
            "diseases": [],
            "terms": []
        }
        
        if not text:
            return found

        # Scan for entities (by name)
        for eid, entity in self.entities.items():
            name = entity.get('name', '')
            if name and re.search(rf'\b{re.escape(name)}\b', text, re.IGNORECASE):
                found["entities"].append(entity)
            
            breed = entity.get('breed', '')
            if breed and re.search(rf'\b{re.escape(breed)}\b', text, re.IGNORECASE):
                if breed not in found["terms"]:
                    found["terms"].append(f"Breed: {breed}")

        # Scan for diseases
        for did, disease in self.diseases.items():
            name = disease.get('name', '')
            if name and re.search(rf'\b{re.escape(name)}\b', text, re.IGNORECASE):
                found["diseases"].append(disease)

        return found

    def get_hierarchy(self, entity):
        """Build a simple hierarchy string for an entity."""
        h = []
        if entity.get('species'):
            h.append(entity['species'])
        if entity.get('breed'):
            h.append(entity['breed'])
        if entity.get('name'):
            h.append(entity['name'])
        return " > ".join(h)

    def get_full_associations(self, entity):
        """Resolve linked IDs for parents and offspring."""
        assoc = {
            "parent": None,
            "offspring": [],
            "diseases": []
        }
        
        pid = entity.get('parent_id')
        if pid and pid in self.entities:
            assoc["parent"] = self.entities[pid]
            
        for oid in entity.get('offspring_ids', []):
            if oid in self.entities:
                assoc["offspring"].append(self.entities[oid])
                
        for did in entity.get('disease_associations', []):
            if did in self.diseases:
                assoc["diseases"].append(self.diseases[did])
                
        return assoc
