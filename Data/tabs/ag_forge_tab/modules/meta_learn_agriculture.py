#!/usr/bin/env python3
"""
Meta Learn Agriculture - Tkinter Prototype
------------------------------------------
A comprehensive knowledge management system for agricultural entities with:
1. Categorized directory structure
2. Entity inventory with photos, documents, and health tracking
3. Associative chaining for diseases and taxonomy
4. Interactive confidence-based chat system
5. Tkinter-based GUI with multiple views
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import json
import os
import sys
import random
import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
import shutil
import csv
from PIL import Image, ImageTk
import threading

# Add project root to sys.path to ensure imports work
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from modules.dev_tools.interactive_debug import install_debug_hooks
    print("DEBUG: Interactive Debug module imported successfully.", file=sys.stderr)
except ImportError as e:
    print(f"DEBUG ERROR: Could not import interactive_debug: {e}", file=sys.stderr)
    install_debug_hooks = None

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class EntityType(Enum):
    ANIMAL = "Animal"
    PLANT = "Plant"
    EQUIPMENT = "Equipment"
    LOCATION = "Location"
    DISEASE = "Disease"
    PARASITE = "Parasite"
    NUTRIENT = "Nutrient"
    PRACTICE = "Agricultural Practice"

class HealthStatus(Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    FAIR = "Fair"
    POOR = "Poor"
    CRITICAL = "Critical"
    DECEASED = "Deceased"

class ConfidenceLevel(Enum):
    HIGH = "High (80-100%)"
    MEDIUM = "Medium (50-79%)"
    LOW = "Low (20-49%)"
    UNKNOWN = "Unknown (0-19%)"

@dataclass
class Document:
    id: str
    title: str
    path: str
    type: str  # "research", "health_record", "certificate", "manual"
    upload_date: str
    tags: List[str] = field(default_factory=list)

@dataclass
class HealthRecord:
    date: str
    weight: Optional[float] = None
    temperature: Optional[float] = None
    symptoms: List[str] = field(default_factory=list)
    diagnosis: Optional[str] = None
    treatment: str = ""
    notes: str = ""
    veterinarian: str = ""

@dataclass
class Entity:
    id: str
    name: str
    type: EntityType
    category: str
    birth_date: Optional[str] = None
    acquisition_date: str = ""
    location: str = ""
    description: str = ""
    
    # Media
    photo_path: Optional[str] = None
    documents: List[Document] = field(default_factory=list)
    
    # Health & Status
    health_status: HealthStatus = HealthStatus.GOOD
    health_records: List[HealthRecord] = field(default_factory=list)
    
    # Taxonomy & Associations
    species: str = ""
    breed: str = ""
    parent_id: Optional[str] = None
    offspring_ids: List[str] = field(default_factory=list)
    
    # Associative Chains
    disease_associations: List[str] = field(default_factory=list)
    parasite_associations: List[str] = field(default_factory=list)
    nutrient_associations: List[str] = field(default_factory=list)
    location_associations: List[str] = field(default_factory=list)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    last_updated: str = ""
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['type'] = self.type.value
        data['health_status'] = self.health_status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Entity':
        data = data.copy()
        data['type'] = EntityType(data['type'])
        data['health_status'] = HealthStatus(data['health_status'])
        return cls(**data)

@dataclass
class Disease:
    id: str
    name: str
    scientific_name: str
    category: str  # "bacterial", "viral", "fungal", "parasitic", "nutritional"
    affected_species: List[str]
    symptoms: List[str]
    transmission_methods: List[str]
    treatments: List[str]
    prevention_methods: List[str]
    severity: str  # "low", "medium", "high", "critical"
    zoonotic: bool = False
    confidence_score: float = 0.0

@dataclass
class ChatResponse:
    text: str
    confidence: float
    source_entities: List[str]
    supporting_documents: List[str]
    timestamp: str
    response_id: str

@dataclass
class StagingItem:
    id: str
    source_type: str  # "web", "clipboard", "ai_task"
    source_content: str
    extracted_data: Dict[str, Any]  # The potential Entity or Disease data
    confidence_score: float
    timestamp: str
    status: str = "pending"  # "pending", "approved", "rejected"

# ---------------------------------------------------------------------------
# Core Application
# ---------------------------------------------------------------------------

class KnowledgeForgeApp:
    """Main application controller"""
    
    def __init__(self, base_path: Optional[Path] = None):
        # Default to local directory (Portable Mode)
        self.base_path = base_path or Path(__file__).parent.resolve()
        self.data_path = self.base_path / "data"
        self.media_path = self.base_path / "media"
        self.categories = self._load_categories()
        
        # Data stores
        self.entities: Dict[str, Entity] = {}
        self.diseases: Dict[str, Disease] = {}
        self.staging_items: Dict[str, StagingItem] = {}
        self.chat_history: List[Dict] = []
        
        # Initialize directories
        self._init_directories()
        
        # Load existing data
        self._load_data()
        
        # Chat context
        self.chat_context: List[Dict] = []
        self.response_pool: List[ChatResponse] = []
        
    def _init_directories(self):
        """Create necessary directory structure"""
        directories = [
            self.base_path,
            self.data_path,
            self.media_path,
            self.media_path / "photos",
            self.media_path / "documents",
            self.media_path / "exports"
        ]
        
        # Create category directories
        for category in self.categories:
            cat_path = self.base_path / category
            directories.append(cat_path)
            directories.append(cat_path / "entities")
            directories.append(cat_path / "research")
            directories.append(cat_path / "reports")
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _init_knowledge_structure(self):
        """Create standard Knowledge Base structure"""
        kb_path = self.base_path / "knowledge"
        structure = {
            "100_Sciences": ["Biology", "Chemistry", "Physics", "Botany", "Zoology"],
            "400_Practice": ["Animal_Husbandry", "Crop_Science", "Machinery", "Regulations", "Safety"],
            "900_Local": ["Weather_History", "Soil_Reports", "Market_Data", "Maps"]
        }
        
        created = []
        for domain, subdomains in structure.items():
            domain_path = kb_path / domain
            domain_path.mkdir(parents=True, exist_ok=True)
            created.append(str(domain_path))
            
            for sub in subdomains:
                sub_path = domain_path / sub
                sub_path.mkdir(exist_ok=True)
                created.append(str(sub_path))
        
        return created
    
    def _load_categories(self) -> List[str]:
        """Load or create default categories"""
        categories = [
            "000_Computer_Science_Information_General",
            "100_Philosophy_Psychology",
            "200_Religion",
            "300_Social_Sciences",
            "400_Language",
            "500_Pure_Science",
            "600_Technology_Applied_Sciences",
            "700_Arts_Recreation",
            "800_Literature",
            "900_History_Geography",
            "Agriculture_Horticulture",
            "Animal_Husbandry",
            "Crop_Science",
            "Soil_Science",
            "Veterinary_Medicine"
        ]
        return categories
    
    def _load_data(self):
        """Load entities and diseases from JSON files"""
        # Load entities
        entities_file = self.data_path / "entities.json"
        if entities_file.exists():
            try:
                with open(entities_file, 'r') as f:
                    data = json.load(f)
                    for entity_id, entity_data in data.items():
                        self.entities[entity_id] = Entity.from_dict(entity_data)
            except Exception as e:
                print(f"Error loading entities: {e}")
        
        # Load diseases
        diseases_file = self.data_path / "diseases.json"
        if diseases_file.exists():
            try:
                with open(diseases_file, 'r') as f:
                    data = json.load(f)
                    for disease_id, disease_data in data.items():
                        self.diseases[disease_id] = Disease(**disease_data)
            except Exception as e:
                print(f"Error loading diseases: {e}")

        # Load staging
        staging_file = self.data_path / "staging.json"
        if staging_file.exists():
            try:
                with open(staging_file, 'r') as f:
                    data = json.load(f)
                    for item_id, item_data in data.items():
                        self.staging_items[item_id] = StagingItem(**item_data)
            except Exception as e:
                print(f"Error loading staging: {e}")
    
    def save_data(self):
        """Save all data to JSON files"""
        # Save entities
        entities_data = {eid: entity.to_dict() for eid, entity in self.entities.items()}
        with open(self.data_path / "entities.json", 'w') as f:
            json.dump(entities_data, f, indent=2)
        
        # Save diseases
        diseases_data = {did: asdict(disease) for did, disease in self.diseases.items()}
        with open(self.data_path / "diseases.json", 'w') as f:
            json.dump(diseases_data, f, indent=2)

        # Save staging
        staging_data = {sid: asdict(item) for sid, item in self.staging_items.items()}
        with open(self.data_path / "staging.json", 'w') as f:
            json.dump(staging_data, f, indent=2)
    
    def add_staging_item(self, source_type: str, content: str, extracted_data: Dict, confidence: float) -> str:
        """Add a new item to staging"""
        item_id = f"stage_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}"
        item = StagingItem(
            id=item_id,
            source_type=source_type,
            source_content=content,
            extracted_data=extracted_data,
            confidence_score=confidence,
            timestamp=datetime.datetime.now().isoformat()
        )
        self.staging_items[item_id] = item
        self.save_data()
        return item_id

    def approve_staging_item(self, item_id: str):
        """Approve a staging item and convert to Entity"""
        if item_id in self.staging_items:
            item = self.staging_items[item_id]
            data = item.extracted_data
            
            # Basic validation
            if 'name' not in data or 'type' not in data:
                raise ValueError("Invalid entity data in staging item")
                
            # Convert string type to Enum if needed
            if isinstance(data.get('type'), str):
                 try:
                     # Try to map string to EntityType
                     enum_val = next(e for e in EntityType if e.value == data['type'] or e.name == data['type'])
                     data['type'] = enum_val
                 except StopIteration:
                     # Default to Animal if unknown
                     data['type'] = EntityType.ANIMAL

            if isinstance(data.get('health_status'), str):
                try:
                    enum_val = next(e for e in HealthStatus if e.value == data['health_status'] or e.name == data['health_status'])
                    data['health_status'] = enum_val
                except StopIteration:
                    data['health_status'] = HealthStatus.GOOD

            # Create entity
            self.create_entity(data)
            
            # Remove from staging
            del self.staging_items[item_id]
            self.save_data()

    def reject_staging_item(self, item_id: str):
        """Reject and remove a staging item"""
        if item_id in self.staging_items:
            del self.staging_items[item_id]
            self.save_data()
    
    def create_entity(self, entity_data: Dict) -> str:
        """Create a new entity with auto-generated ID"""
        entity_id = f"{entity_data['type'].value.lower()}_{len(self.entities) + 1:04d}"
        entity = Entity(id=entity_id, **entity_data)
        entity.last_updated = datetime.datetime.now().isoformat()
        self.entities[entity_id] = entity
        self.save_data()
        return entity_id
    
    def update_entity(self, entity_id: str, updates: Dict):
        """Update an existing entity"""
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            for key, value in updates.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            entity.last_updated = datetime.datetime.now().isoformat()
            self.save_data()
    
    def add_health_record(self, entity_id: str, record: HealthRecord):
        """Add health record to entity"""
        if entity_id in self.entities:
            self.entities[entity_id].health_records.append(record)
            
            # Update health status based on diagnosis
            if record.diagnosis:
                self._update_health_status(entity_id, record.diagnosis)
            
            self.save_data()
    
    def _update_health_status(self, entity_id: str, diagnosis: str):
        """Update entity health status based on diagnosis"""
        entity = self.entities[entity_id]
        
        # Check if diagnosis is associated with critical conditions
        critical_diseases = ["mastitis", "pneumonia", "foot and mouth", "anthrax"]
        for disease in critical_diseases:
            if disease.lower() in diagnosis.lower():
                entity.health_status = HealthStatus.CRITICAL
                return
        
        # Simple heuristic for other conditions
        if "mild" in diagnosis.lower():
            entity.health_status = HealthStatus.FAIR
        elif "severe" in diagnosis.lower():
            entity.health_status = HealthStatus.POOR
        elif "recovered" in diagnosis.lower():
            entity.health_status = HealthStatus.GOOD
    
    def search_entities(self, query: str, category: Optional[str] = None) -> List[Entity]:
        """Search entities by name, description, or tags"""
        results = []
        query = query.lower()
        
        for entity in self.entities.values():
            if category and entity.category != category:
                continue
            
            # Search in various fields
            if (query in entity.name.lower() or 
                query in entity.description.lower() or 
                any(query in tag.lower() for tag in entity.tags) or
                query in entity.species.lower() or
                query in entity.breed.lower()):
                results.append(entity)
        
        return results
    
    def get_entity_associations(self, entity_id: str) -> Dict[str, List[str]]:
        """Get all associations for an entity"""
        if entity_id not in self.entities:
            return {}
        
        entity = self.entities[entity_id]
        return {
            "diseases": entity.disease_associations,
            "parasites": entity.parasite_associations,
            "nutrients": entity.nutrient_associations,
            "locations": entity.location_associations,
            "offspring": entity.offspring_ids
        }
    
    def generate_chat_response(self, user_input: str) -> List[ChatResponse]:
        """Generate chat responses with confidence scoring"""
        responses = []
        
        # Extract keywords from user input
        keywords = self._extract_keywords(user_input)
        
        # Generate different response perspectives
        responses.extend(self._generate_entity_responses(keywords))
        responses.extend(self._generate_disease_responses(keywords))
        responses.extend(self._generate_general_responses(keywords))
        
        # Calculate confidence scores
        for response in responses:
            response.confidence = self._calculate_confidence(response, keywords)
        
        # Sort by confidence
        responses.sort(key=lambda x: x.confidence, reverse=True)
        
        # Store for retry mechanism
        self.response_pool = responses
        
        return responses[:5]  # Return top 5 responses
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text"""
        # Simple keyword extraction - in production would use NLP
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by"}
        words = text.lower().split()
        return [w for w in words if w not in stop_words and len(w) > 3]
    
    def _generate_entity_responses(self, keywords: List[str]) -> List[ChatResponse]:
        """Generate responses based on entity data"""
        responses = []
        
        for entity in self.entities.values():
            # Check if entity matches any keyword
            entity_keywords = [entity.name.lower(), entity.species.lower(), 
                              entity.breed.lower()] + [t.lower() for t in entity.tags]
            
            matches = sum(1 for kw in keywords if any(kw in ekw for ekw in entity_keywords))
            
            if matches > 0:
                # Create response about this entity
                if entity.type == EntityType.ANIMAL:
                    response_text = f"{entity.name} ({entity.breed} {entity.species}) is currently {entity.health_status.value.lower()}. "
                    if entity.health_records:
                        latest = entity.health_records[-1]
                        response_text += f"Latest health check: {latest.diagnosis or 'No issues noted'} on {latest.date}."
                
                response_id = f"entity_{entity.id}_{datetime.datetime.now().timestamp()}"
                response = ChatResponse(
                    text=response_text,
                    confidence=0.5,  # Base confidence
                    source_entities=[entity.id],
                    supporting_documents=[doc.id for doc in entity.documents[:2]],
                    timestamp=datetime.datetime.now().isoformat(),
                    response_id=response_id
                )
                responses.append(response)
        
        return responses
    
    def _generate_disease_responses(self, keywords: List[str]) -> List[ChatResponse]:
        """Generate responses based on disease data"""
        responses = []
        
        for disease in self.diseases.values():
            disease_keywords = [disease.name.lower(), disease.scientific_name.lower()] + \
                              [s.lower() for s in disease.symptoms] + \
                              [t.lower() for t in disease.treatments]
            
            matches = sum(1 for kw in keywords if any(kw in dkw for dkw in disease_keywords))
            
            if matches > 0:
                response_text = f"{disease.name} ({disease.scientific_name}) is a {disease.severity} severity disease. "
                response_text += f"Symptoms include: {', '.join(disease.symptoms[:3])}. "
                response_text += f"Treatment options: {', '.join(disease.treatments[:2])}."
                
                response_id = f"disease_{disease.id}_{datetime.datetime.now().timestamp()}"
                response = ChatResponse(
                    text=response_text,
                    confidence=0.6,
                    source_entities=[],
                    supporting_documents=[],
                    timestamp=datetime.datetime.now().isoformat(),
                    response_id=response_id
                )
                responses.append(response)
        
        return responses
    
    def _generate_general_responses(self, keywords: List[str]) -> List[ChatResponse]:
        """Generate general agricultural knowledge responses"""
        responses = []
        
        # Predefined general knowledge
        general_knowledge = {
            "calf": "Calves should receive colostrum within 2 hours of birth for proper immunity development.",
            "milk": "Dairy cows typically produce 6-7 gallons of milk per day during peak lactation.",
            "feed": "A balanced dairy cow ration includes forages, grains, protein supplements, and minerals.",
            "vaccine": "Core vaccines for cattle include IBR, BVD, PI3, and BRSV.",
            "parasite": "Common cattle parasites include worms (nematodes), flies, and ticks.",
            "breed": "Common dairy breeds: Holstein, Jersey, Brown Swiss, Guernsey, Ayrshire."
        }
        
        for keyword in keywords:
            if keyword in general_knowledge:
                response_id = f"general_{keyword}_{datetime.datetime.now().timestamp()}"
                response = ChatResponse(
                    text=general_knowledge[keyword],
                    confidence=0.7,
                    source_entities=[],
                    supporting_documents=[],
                    timestamp=datetime.datetime.now().isoformat(),
                    response_id=response_id
                )
                responses.append(response)
        
        return responses
    
    def _calculate_confidence(self, response: ChatResponse, keywords: List[str]) -> float:
        """Calculate confidence score for a response"""
        base_score = response.confidence
        
        # Boost confidence if we have source entities
        if response.source_entities:
            base_score += 0.1
        
        # Boost confidence if we have supporting documents
        if response.supporting_documents:
            base_score += 0.1
        
        # Adjust based on keyword matching
        keyword_matches = sum(1 for kw in keywords if kw in response.text.lower())
        base_score += (keyword_matches * 0.05)
        
        return min(base_score, 1.0)  # Cap at 100%
    
    def get_retry_responses(self, original_response_id: str) -> List[ChatResponse]:
        """Get alternative responses for retry mechanism"""
        # Remove the original response and reshuffle
        filtered = [r for r in self.response_pool if r.response_id != original_response_id]
        random.shuffle(filtered)
        return filtered[:3]  # Return 3 alternatives

# ---------------------------------------------------------------------------
# Tkinter GUI Components
# ---------------------------------------------------------------------------

class EntityDetailFrame(ttk.Frame):
    """Detailed view of an entity"""
    
    def __init__(self, parent, app: KnowledgeForgeApp, entity_id: str):
        super().__init__(parent)
        self.app = app
        self.entity_id = entity_id
        self.entity = app.entities[entity_id]
        
        self._setup_ui()
        self._load_entity_data()
    
    def _setup_ui(self):
        """Setup the UI layout"""
        # Main container with scrollbar
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(main_container)
        scrollbar = ttk.Scrollbar(main_container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Header
        header_frame = ttk.Frame(scrollable_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.photo_label = ttk.Label(header_frame)
        self.photo_label.pack(side=tk.LEFT, padx=(0, 20))
        
        info_frame = ttk.Frame(header_frame)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.name_label = ttk.Label(info_frame, text="", font=("Arial", 16, "bold"))
        self.name_label.pack(anchor=tk.W)
        
        self.type_label = ttk.Label(info_frame, text="")
        self.type_label.pack(anchor=tk.W)
        
        self.health_label = ttk.Label(info_frame, text="", font=("Arial", 12))
        self.health_label.pack(anchor=tk.W, pady=(5, 0))
        
        # Notebook for tabs
        notebook = ttk.Notebook(scrollable_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Basic Info Tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Basic Info")
        self._setup_basic_tab(basic_frame)
        
        # Health Records Tab
        health_frame = ttk.Frame(notebook)
        notebook.add(health_frame, text="Health Records")
        self._setup_health_tab(health_frame)
        
        # Documents Tab
        docs_frame = ttk.Frame(notebook)
        notebook.add(docs_frame, text="Documents")
        self._setup_documents_tab(docs_frame)
        
        # Associations Tab
        assoc_frame = ttk.Frame(notebook)
        notebook.add(assoc_frame, text="Associations")
        self._setup_associations_tab(assoc_frame)
    
    def _setup_basic_tab(self, parent):
        """Setup basic information tab"""
        fields = [
            ("Species:", self.entity.species),
            ("Breed:", self.entity.breed),
            ("Birth Date:", self.entity.birth_date or "Unknown"),
            ("Location:", self.entity.location),
            ("Description:", self.entity.description)
        ]
        
        for label, value in fields:
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(frame, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)
            ttk.Label(frame, text=value, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def _setup_health_tab(self, parent):
        """Setup health records tab"""
        # Add new record button
        ttk.Button(parent, text="Add Health Record", 
                  command=self._add_health_record).pack(anchor=tk.W, pady=(0, 10))
        
        # Health records list
        if self.entity.health_records:
            for record in reversed(self.entity.health_records[-10:]):  # Show last 10
                self._create_health_record_display(parent, record)
        else:
            ttk.Label(parent, text="No health records available").pack()
    
    def _setup_documents_tab(self, parent):
        """Setup documents tab"""
        # Upload button
        ttk.Button(parent, text="Upload Document",
                  command=self._upload_document).pack(anchor=tk.W, pady=(0, 10))
        
        # Documents list
        if self.entity.documents:
            for doc in self.entity.documents:
                self._create_document_display(parent, doc)
        else:
            ttk.Label(parent, text="No documents available").pack()
    
    def _setup_associations_tab(self, parent):
        """Setup associations tab"""
        associations = self.app.get_entity_associations(self.entity_id)
        
        for assoc_type, items in associations.items():
            if items:
                frame = ttk.LabelFrame(parent, text=assoc_type.title())
                frame.pack(fill=tk.X, pady=5)
                
                for item in items:
                    ttk.Label(frame, text=f"• {item}").pack(anchor=tk.W)
    
    def _load_entity_data(self):
        """Load entity data into UI"""
        self.name_label.config(text=self.entity.name)
        self.type_label.config(text=f"{self.entity.type.value} • {self.entity.category}")
        
        # Health status with color coding
        health_colors = {
            HealthStatus.EXCELLENT: "green",
            HealthStatus.GOOD: "lightgreen",
            HealthStatus.FAIR: "yellow",
            HealthStatus.POOR: "orange",
            HealthStatus.CRITICAL: "red",
            HealthStatus.DECEASED: "gray"
        }
        
        health_color = health_colors.get(self.entity.health_status, "black")
        self.health_label.config(
            text=f"Health: {self.entity.health_status.value}",
            foreground=health_color
        )
        
        # Load photo if available
        if self.entity.photo_path and os.path.exists(self.entity.photo_path):
            try:
                image = Image.open(self.entity.photo_path)
                image.thumbnail((200, 200))
                photo = ImageTk.PhotoImage(image)
                self.photo_label.config(image=photo)
                self.photo_label.image = photo  # Keep reference
            except Exception as e:
                print(f"Error loading image: {e}")
    
    def _add_health_record(self):
        """Open dialog to add health record"""
        dialog = HealthRecordDialog(self, self.app, self.entity_id)
        self.wait_window(dialog)
        self._load_entity_data()
    
    def _upload_document(self):
        """Open file dialog to upload document"""
        file_path = filedialog.askopenfilename(
            title="Select Document",
            filetypes=[
                ("PDF files", "*.pdf"),
                ("Text files", "*.txt"),
                ("Word documents", "*.doc *.docx"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            # Copy file to media directory
            dest_dir = self.app.media_path / "documents" / self.entity_id
            dest_dir.mkdir(exist_ok=True)
            
            dest_path = dest_dir / os.path.basename(file_path)
            shutil.copy2(file_path, dest_path)
            
            # Create document record
            doc_id = f"doc_{len(self.entity.documents) + 1:04d}"
            document = Document(
                id=doc_id,
                title=os.path.basename(file_path),
                path=str(dest_path),
                type="research",
                upload_date=datetime.datetime.now().isoformat(),
                tags=["uploaded"]
            )
            
            self.entity.documents.append(document)
            self.app.save_data()
            
            # Refresh UI
            self._setup_documents_tab(self._get_current_tab("Documents"))
    
    def _get_current_tab(self, tab_name: str) -> ttk.Frame:
        """Helper to get current tab frame"""
        notebook = self.winfo_children()[0].winfo_children()[3]  # Get notebook
        for tab_id in notebook.tabs():
            if notebook.tab(tab_id, "text") == tab_name:
                return notebook.nametowidget(tab_id)
        return None
    
    def _create_health_record_display(self, parent, record: HealthRecord):
        """Create display for a health record"""
        frame = ttk.LabelFrame(parent, text=f"Record: {record.date}")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        if record.diagnosis:
            ttk.Label(frame, text=f"Diagnosis: {record.diagnosis}", 
                     font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        if record.symptoms:
            ttk.Label(frame, text=f"Symptoms: {', '.join(record.symptoms)}").pack(anchor=tk.W)
        
        if record.treatment:
            ttk.Label(frame, text=f"Treatment: {record.treatment}").pack(anchor=tk.W)
        
        if record.notes:
            ttk.Label(frame, text=f"Notes: {record.notes}").pack(anchor=tk.W)
    
    def _create_document_display(self, parent, doc: Document):
        """Create display for a document"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(frame, text=doc.title, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(frame, text="View", width=8,
                  command=lambda: self._view_document(doc.path)).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(frame, text="Open", width=8,
                  command=lambda: os.startfile(doc.path)).pack(side=tk.RIGHT)
    
    def _view_document(self, path: str):
        """View document (placeholder - would open in viewer)"""
        messagebox.showinfo("Document", f"Would open: {path}")

class HealthRecordDialog(tk.Toplevel):
    """Dialog for adding health records"""
    
    def __init__(self, parent, app: KnowledgeForgeApp, entity_id: str):
        super().__init__(parent)
        self.app = app
        self.entity_id = entity_id
        
        self.title("Add Health Record")
        self.geometry("500x600")
        self.resizable(False, False)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup dialog UI"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Date
        ttk.Label(main_frame, text="Date:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.date_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(main_frame, textvariable=self.date_var, width=20).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Weight
        ttk.Label(main_frame, text="Weight (kg):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.weight_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.weight_var, width=20).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Temperature
        ttk.Label(main_frame, text="Temperature (°C):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.temp_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.temp_var, width=20).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Symptoms
        ttk.Label(main_frame, text="Symptoms:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.symptoms_text = scrolledtext.ScrolledText(main_frame, width=40, height=3)
        self.symptoms_text.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Diagnosis
        ttk.Label(main_frame, text="Diagnosis:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.diagnosis_text = scrolledtext.ScrolledText(main_frame, width=40, height=3)
        self.diagnosis_text.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Treatment
        ttk.Label(main_frame, text="Treatment:").grid(row=5, column=0, sticky=tk.NW, pady=5)
        self.treatment_text = scrolledtext.ScrolledText(main_frame, width=40, height=3)
        self.treatment_text.grid(row=5, column=1, sticky=tk.W, pady=5)
        
        # Veterinarian
        ttk.Label(main_frame, text="Veterinarian:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.vet_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.vet_var, width=20).grid(row=6, column=1, sticky=tk.W, pady=5)
        
        # Notes
        ttk.Label(main_frame, text="Notes:").grid(row=7, column=0, sticky=tk.NW, pady=5)
        self.notes_text = scrolledtext.ScrolledText(main_frame, width=40, height=4)
        self.notes_text.grid(row=7, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self._save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
    
    def _save(self):
        """Save health record"""
        try:
            record = HealthRecord(
                date=self.date_var.get(),
                weight=float(self.weight_var.get()) if self.weight_var.get() else None,
                temperature=float(self.temp_var.get()) if self.temp_var.get() else None,
                symptoms=self.symptoms_text.get("1.0", tk.END).strip().split("\n"),
                diagnosis=self.diagnosis_text.get("1.0", tk.END).strip(),
                treatment=self.treatment_text.get("1.0", tk.END).strip(),
                veterinarian=self.vet_var.get(),
                notes=self.notes_text.get("1.0", tk.END).strip()
            )
            
            self.app.add_health_record(self.entity_id, record)
            self.destroy()
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")

class ChatFrame(ttk.Frame):
    """Interactive chat interface"""
    
    def __init__(self, parent, app: KnowledgeForgeApp):
        super().__init__(parent)
        self.app = app
        
        # Chat state
        self.current_responses: List[ChatResponse] = []
        self.selected_response_id: Optional[str] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup chat UI"""
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Chat history display
        history_frame = ttk.LabelFrame(main_frame, text="Chat History")
        history_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.history_text = scrolledtext.ScrolledText(
            history_frame, 
            wrap=tk.WORD,
            height=20,
            font=("Arial", 10)
        )
        self.history_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.history_text.config(state=tk.DISABLED)
        
        # Response selection frame
        response_frame = ttk.LabelFrame(main_frame, text="Responses")
        response_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.response_var = tk.StringVar()
        self.response_combo = ttk.Combobox(
            response_frame,
            textvariable=self.response_var,
            state="readonly",
            height=10
        )
        self.response_combo.pack(fill=tk.X, padx=5, pady=5)
        self.response_combo.bind("<<ComboboxSelected>>", self._on_response_selected)
        
        # Confidence display
        confidence_frame = ttk.Frame(response_frame)
        confidence_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        ttk.Label(confidence_frame, text="Confidence:").pack(side=tk.LEFT)
        self.confidence_label = ttk.Label(confidence_frame, text="0%")
        self.confidence_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # User input frame
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X)
        
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(
            input_frame,
            textvariable=self.input_var,
            font=("Arial", 10)
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind("<Return>", lambda e: self._send_message())
        
        # Buttons
        button_frame = ttk.Frame(input_frame)
        button_frame.pack(side=tk.RIGHT)
        
        ttk.Button(button_frame, text="Send", 
                  command=self._send_message).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Retry",
                  command=self._retry_responses).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Clear",
                  command=self._clear_chat).pack(side=tk.LEFT, padx=2)
    
    def _send_message(self):
        """Send user message and get responses"""
        message = self.input_var.get().strip()
        if not message:
            return
        
        # Add user message to history
        self._add_to_history(f"You: {message}", "user")
        
        # Clear input
        self.input_var.set("")
        
        # Get responses
        responses = self.app.generate_chat_response(message)
        self.current_responses = responses
        
        # Update response dropdown
        response_texts = []
        for i, response in enumerate(responses):
            confidence_pct = int(response.confidence * 100)
            response_texts.append(
                f"[{confidence_pct}%] {response.text[:80]}..."
            )
        
        self.response_combo['values'] = response_texts
        
        if response_texts:
            self.response_combo.set(response_texts[0])
            self._on_response_selected()
    
    def _on_response_selected(self, event=None):
        """Handle response selection"""
        selection = self.response_combo.current()
        if 0 <= selection < len(self.current_responses):
            response = self.current_responses[selection]
            self.selected_response_id = response.response_id
            
            # Update confidence display
            confidence_pct = int(response.confidence * 100)
            self.confidence_label.config(text=f"{confidence_pct}%")
            
            # Color code confidence
            if confidence_pct >= 80:
                self.confidence_label.config(foreground="green")
            elif confidence_pct >= 50:
                self.confidence_label.config(foreground="orange")
            else:
                self.confidence_label.config(foreground="red")
    
    def _retry_responses(self):
        """Get alternative responses"""
        if self.selected_response_id:
            alternatives = self.app.get_retry_responses(self.selected_response_id)
            if alternatives:
                # Update response dropdown with alternatives
                alt_texts = []
                for i, response in enumerate(alternatives):
                    confidence_pct = int(response.confidence * 100)
                    alt_texts.append(
                        f"[Retry {i+1} - {confidence_pct}%] {response.text[:80]}..."
                    )
                
                self.response_combo['values'] = alt_texts
                self.response_combo.set(alt_texts[0])
                
                # Update current responses
                self.current_responses = alternatives
                self._on_response_selected()
                
                self._add_to_history("System: Showing alternative responses...", "system")
    
    def _add_to_history(self, text: str, sender: str = "system"):
        """Add message to chat history"""
        self.history_text.config(state=tk.NORMAL)
        
        # Add timestamp
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.history_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        
        # Color code sender
        if sender == "user":
            self.history_text.insert(tk.END, text + "\n\n", "user")
        elif sender == "system":
            self.history_text.insert(tk.END, text + "\n\n", "system")
        else:
            self.history_text.insert(tk.END, text + "\n\n")
        
        self.history_text.see(tk.END)
        self.history_text.config(state=tk.DISABLED)
    
    def _clear_chat(self):
        """Clear chat history"""
        self.history_text.config(state=tk.NORMAL)
        self.history_text.delete("1.0", tk.END)
        self.history_text.config(state=tk.DISABLED)
        self.current_responses = []
        self.response_combo.set('')
        self.confidence_label.config(text="0%")

class StagingReviewFrame(ttk.Frame):
    """Interface for reviewing staging data"""
    
    def __init__(self, parent, app: KnowledgeForgeApp):
        super().__init__(parent)
        self.app = app
        self._setup_ui()
        self._refresh_list()
        
    def _setup_ui(self):
        # List of items
        list_frame = ttk.LabelFrame(self, text="Pending Items")
        list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        self.item_list = tk.Listbox(list_frame, width=30)
        self.item_list.pack(fill=tk.BOTH, expand=True)
        self.item_list.bind('<<ListboxSelect>>', self._on_select)
        
        # Details view
        detail_frame = ttk.LabelFrame(self, text="Item Details")
        detail_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.content_text = scrolledtext.ScrolledText(detail_frame, height=10, width=50)
        self.content_text.pack(fill=tk.X, padx=5, pady=5)
        
        self.json_text = scrolledtext.ScrolledText(detail_frame, height=10, width=50)
        self.json_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Action buttons
        btn_frame = ttk.Frame(detail_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="✅ Approve", command=self._approve).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Reject", command=self._reject).pack(side=tk.LEFT, padx=5)
        
    def _refresh_list(self):
        self.item_list.delete(0, tk.END)
        self.current_ids = []
        for pid, item in self.app.staging_items.items():
            self.item_list.insert(tk.END, f"{item.source_type}: {item.id}")
            self.current_ids.append(pid)
            
    def _on_select(self, event):
        idx = self.item_list.curselection()
        if idx:
            pid = self.current_ids[idx[0]]
            item = self.app.staging_items[pid]
            
            self.content_text.delete('1.0', tk.END)
            self.content_text.insert('1.0', f"Source: {item.source_content}")
            
            self.json_text.delete('1.0', tk.END)
            self.json_text.insert('1.0', json.dumps(item.extracted_data, indent=2))
            
    def _approve(self):
        idx = self.item_list.curselection()
        if idx:
            pid = self.current_ids[idx[0]]
            try:
                # Update data from text box in case user edited it
                edited_json = self.json_text.get('1.0', tk.END).strip()
                self.app.staging_items[pid].extracted_data = json.loads(edited_json)
                
                self.app.approve_staging_item(pid)
                messagebox.showinfo("Success", "Item approved and entity created.")
                self._refresh_list()
                
                # Clear text boxes
                self.content_text.delete('1.0', tk.END)
                self.json_text.delete('1.0', tk.END)
            except Exception as e:
                messagebox.showerror("Error", f"Approval failed: {e}")

    def _reject(self):
        idx = self.item_list.curselection()
        if idx:
            pid = self.current_ids[idx[0]]
            self.app.reject_staging_item(pid)
            self._refresh_list()
            
            # Clear text boxes
            self.content_text.delete('1.0', tk.END)
            self.json_text.delete('1.0', tk.END)

class InventoryFrame(ttk.Frame):
    """Browser for the static Knowledge Directory"""
    
    def __init__(self, parent, app: KnowledgeForgeApp):
        super().__init__(parent)
        self.app = app
        self.kb_path = self.app.base_path / "knowledge"
        self._setup_ui()
        self._populate_tree()
        
    def _setup_ui(self):
        # Treeview
        self.tree = ttk.Treeview(self)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Bind double click to open folder/file
        self.tree.bind("<Double-1>", self._on_double_click)
        
    def _populate_tree(self):
        if not self.kb_path.exists():
            self.tree.insert("", tk.END, text="Knowledge directory not found")
            return
            
        root_node = self.tree.insert("", tk.END, text="Knowledge Base", open=True)
        self._process_directory(root_node, self.kb_path)
        
    def _process_directory(self, parent_node, path: Path):
        try:
            for item in sorted(path.iterdir()):
                if item.name.startswith('.'): continue
                
                # Determine icon/type (simplified text for now)
                item_type = "📁 " if item.is_dir() else "📄 "
                text = f"{item_type}{item.name}"
                
                node = self.tree.insert(parent_node, tk.END, text=text, values=[str(item)])
                
                if item.is_dir():
                    self._process_directory(node, item)
        except PermissionError:
            pass

    def _on_double_click(self, event):
        item_id = self.tree.selection()[0]
        item_values = self.tree.item(item_id, "values")
        
        if item_values:
            path = Path(item_values[0])
            if path.is_file():
                try:
                    if sys.platform == "win32":
                        os.startfile(path)
                    else:
                        subprocess.run(["xdg-open", str(path)])
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open file: {e}")

class MainApplication(tk.Tk):
    """Main Tkinter application window"""
    
    def __init__(self, app: KnowledgeForgeApp):
        super().__init__()
        
        # Enable Debug Hooks
        if install_debug_hooks:
            install_debug_hooks(self)
            
        self.app = app
        self.title("Meta Learn Agriculture")
        self.geometry("1200x800")
        
        # Configure styles
        self._configure_styles()
        
        # Setup UI
        self._setup_ui()
        
        # Load initial data
        self._load_initial_view()
    
    def _configure_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('Title.TLabel', font=('Arial', 18, 'bold'))
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Status.TLabel', font=('Arial', 10, 'italic'))
        
        # Configure button colors
        style.configure('Primary.TButton', font=('Arial', 10, 'bold'))
        style.map('Primary.TButton',
                 foreground=[('active', 'white'), ('!active', 'white')],
                 background=[('active', '#45a049'), ('!active', '#4CAF50')])
    
    def _setup_ui(self):
        """Setup main application UI"""
        # Menu bar
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Entity", command=self._new_entity)
        file_menu.add_command(label="Import Data", command=self._import_data)
        file_menu.add_command(label="Export Data", command=self._export_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Entity Browser", command=self._show_entity_browser)
        view_menu.add_command(label="Knowledge Inventory", command=self._show_inventory)
        view_menu.add_command(label="Data Staging", command=self._show_staging)
        view_menu.add_command(label="Chat Assistant", command=self._show_chat)
        view_menu.add_command(label="Health Dashboard", command=self._show_health_dashboard)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Data Analysis", command=self._show_analysis)
        tools_menu.add_command(label="Report Generator", command=self._generate_report)
        
        # Main container
        self.main_container = ttk.Frame(self)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Status bar
        self.status_bar = ttk.Label(self, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _show_inventory(self):
        """Show knowledge inventory"""
        self._clear_main_container()
        
        # Header
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(header_frame, text="Knowledge Inventory", 
                 style='Title.TLabel').pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="← Back", 
                  command=self._show_entity_browser).pack(side=tk.RIGHT)
                  
        # Inventory frame
        inventory_frame = InventoryFrame(self.main_container, self.app)
        inventory_frame.pack(fill=tk.BOTH, expand=True)

    def _show_staging(self):
        """Show staging review"""
        self._clear_main_container()
        
        # Header
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(header_frame, text="Data Staging (Pending Validation)", 
                 style='Title.TLabel').pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="← Back", 
                  command=self._show_entity_browser).pack(side=tk.RIGHT)
                  
        # Staging frame
        staging_frame = StagingReviewFrame(self.main_container, self.app)
        staging_frame.pack(fill=tk.BOTH, expand=True)
    
    def _load_initial_view(self):
        """Load initial view (Entity Browser)"""
        self._show_entity_browser()
    
    def _show_entity_browser(self):
        """Show entity browser view"""
        self._clear_main_container()
        
        # Header
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(header_frame, text="Entity Browser", 
                 style='Title.TLabel').pack(side=tk.LEFT)
        
        # Search frame
        search_frame = ttk.Frame(self.main_container)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(search_frame, text="Search", 
                  command=self._search_entities).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(search_frame, text="Clear", 
                  command=self._clear_search).pack(side=tk.LEFT)
        
        # Category filter
        filter_frame = ttk.Frame(self.main_container)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Category:").pack(side=tk.LEFT, padx=(0, 5))
        self.category_var = tk.StringVar(value="All")
        category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, 
                                     values=["All"] + self.app.categories, state="readonly")
        category_combo.pack(side=tk.LEFT, padx=(0, 10))
        category_combo.bind("<<ComboboxSelected>>", lambda e: self._filter_entities())
        
        # Entity list with scrollbar
        list_frame = ttk.Frame(self.main_container)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview
        columns = ("ID", "Name", "Type", "Category", "Health", "Last Updated")
        self.entity_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)
        
        # Define headings
        for col in columns:
            self.entity_tree.heading(col, text=col)
            self.entity_tree.column(col, width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.entity_tree.yview)
        self.entity_tree.configure(yscrollcommand=scrollbar.set)
        
        self.entity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click event
        self.entity_tree.bind("<Double-1>", self._on_entity_double_click)
        
        # Load entities
        self._load_entity_tree()
        
        # Button frame
        button_frame = ttk.Frame(self.main_container)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="New Entity", 
                  command=self._new_entity, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Refresh", 
                  command=self._load_entity_tree).pack(side=tk.LEFT)
    
    def _load_entity_tree(self, entities: Optional[List[Entity]] = None):
        """Load entities into treeview"""
        # Clear existing items
        for item in self.entity_tree.get_children():
            self.entity_tree.delete(item)
        
        # Get entities to display
        if entities is None:
            entities = list(self.app.entities.values())
        
        # Populate treeview
        for entity in entities:
            values = (
                entity.id,
                entity.name,
                entity.type.value,
                entity.category,
                entity.health_status.value,
                entity.last_updated[:10] if entity.last_updated else ""
            )
            self.entity_tree.insert("", tk.END, values=values, tags=(entity.id,))
        
        # Update status
        self.status_bar.config(text=f"Showing {len(entities)} entities")
    
    def _search_entities(self):
        """Search entities based on search term"""
        query = self.search_var.get().strip()
        category = self.category_var.get() if self.category_var.get() != "All" else None
        
        results = self.app.search_entities(query, category)
        self._load_entity_tree(results)
    
    def _filter_entities(self):
        """Filter entities by category"""
        category = self.category_var.get()
        if category == "All":
            self._load_entity_tree()
        else:
            results = [e for e in self.app.entities.values() if e.category == category]
            self._load_entity_tree(results)
    
    def _clear_search(self):
        """Clear search and show all entities"""
        self.search_var.set("")
        self.category_var.set("All")
        self._load_entity_tree()
    
    def _on_entity_double_click(self, event):
        """Handle double-click on entity"""
        selection = self.entity_tree.selection()
        if selection:
            item = self.entity_tree.item(selection[0])
            entity_id = item['values'][0]
            self._show_entity_detail(entity_id)
    
    def _show_entity_detail(self, entity_id: str):
        """Show entity detail view"""
        self._clear_main_container()
        
        # Back button
        back_frame = ttk.Frame(self.main_container)
        back_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(back_frame, text="← Back to Browser", 
                  command=self._show_entity_browser).pack(side=tk.LEFT)
        
        # Entity detail frame
        detail_frame = EntityDetailFrame(self.main_container, self.app, entity_id)
        detail_frame.pack(fill=tk.BOTH, expand=True)
    
    def _show_chat(self):
        """Show chat interface"""
        self._clear_main_container()
        
        # Header
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(header_frame, text="Agricultural Chat Assistant", 
                 style='Title.TLabel').pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="← Back", 
                  command=self._show_entity_browser).pack(side=tk.RIGHT)
        
        # Chat frame
        chat_frame = ChatFrame(self.main_container, self.app)
        chat_frame.pack(fill=tk.BOTH, expand=True)
    
    def _show_health_dashboard(self):
        """Show health dashboard"""
        self._clear_main_container()
        
        # Header
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(header_frame, text="Health Dashboard", 
                 style='Title.TLabel').pack(side=tk.LEFT)
        
        # Statistics frame
        stats_frame = ttk.LabelFrame(self.main_container, text="Health Statistics")
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Calculate statistics
        total_animals = len([e for e in self.app.entities.values() 
                           if e.type == EntityType.ANIMAL])
        
        health_counts = {}
        for entity in self.app.entities.values():
            if entity.type == EntityType.ANIMAL:
                status = entity.health_status.value
                health_counts[status] = health_counts.get(status, 0) + 1
        
        # Display statistics
        stats_text = f"Total Animals: {total_animals}\n"
        for status, count in health_counts.items():
            stats_text += f"{status}: {count}\n"
        
        ttk.Label(stats_frame, text=stats_text).pack(padx=10, pady=10)
        
        # Recent health issues
        issues_frame = ttk.LabelFrame(self.main_container, text="Recent Health Issues")
        issues_frame.pack(fill=tk.BOTH, expand=True)
        
        # Get recent health records with issues
        recent_issues = []
        for entity in self.app.entities.values():
            if entity.health_records:
                latest = entity.health_records[-1]
                if latest.diagnosis and latest.diagnosis.strip():
                    recent_issues.append((entity.name, latest.date, latest.diagnosis))
        
        # Create treeview for issues
        if recent_issues:
            columns = ("Animal", "Date", "Diagnosis")
            issues_tree = ttk.Treeview(issues_frame, columns=columns, show="headings", height=10)
            
            for col in columns:
                issues_tree.heading(col, text=col)
                issues_tree.column(col, width=200)
            
            for animal, date, diagnosis in recent_issues[:10]:  # Show last 10
                issues_tree.insert("", tk.END, values=(animal, date, diagnosis))
            
            scrollbar = ttk.Scrollbar(issues_frame, orient=tk.VERTICAL, command=issues_tree.yview)
            issues_tree.configure(yscrollcommand=scrollbar.set)
            
            issues_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            ttk.Label(issues_frame, text="No recent health issues").pack(padx=10, pady=10)
    
    def _new_entity(self):
        """Open dialog to create new entity"""
        dialog = NewEntityDialog(self, self.app)
        self.wait_window(dialog)
        self._load_entity_tree()
    
    def _import_data(self):
        """Import data from CSV or JSON"""
        file_path = filedialog.askopenfilename(
            title="Import Data",
            filetypes=[
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                if file_path.endswith('.csv'):
                    self._import_csv(file_path)
                elif file_path.endswith('.json'):
                    self._import_json(file_path)
                
                messagebox.showinfo("Success", "Data imported successfully")
                self._load_entity_tree()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import: {e}")
    
    def _export_data(self):
        """Export data to CSV"""
        file_path = filedialog.asksaveasfilename(
            title="Export Data",
            defaultextension=".csv",
            filetypes=[
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    
                    # Write header
                    writer.writerow([
                        'ID', 'Name', 'Type', 'Category', 'Species', 'Breed',
                        'Health Status', 'Birth Date', 'Location', 'Description'
                    ])
                    
                    # Write data
                    for entity in self.app.entities.values():
                        writer.writerow([
                            entity.id, entity.name, entity.type.value,
                            entity.category, entity.species, entity.breed,
                            entity.health_status.value, entity.birth_date or '',
                            entity.location, entity.description
                        ])
                
                messagebox.showinfo("Success", f"Data exported to {file_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")
    
    def _import_csv(self, file_path: str):
        """Import entities from CSV file"""
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    entity_data = {
                        'name': row['Name'],
                        'type': EntityType(row['Type']),
                        'category': row['Category'],
                        'species': row['Species'],
                        'breed': row['Breed'],
                        'health_status': HealthStatus(row['Health Status']),
                        'birth_date': row['Birth Date'] if row['Birth Date'] else None,
                        'location': row['Location'],
                        'description': row['Description']
                    }
                    
                    self.app.create_entity(entity_data)
                    
                except Exception as e:
                    print(f"Error importing row {row}: {e}")
    
    def _import_json(self, file_path: str):
        """Import entities from JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
            
            for entity_data in data:
                try:
                    entity_data['type'] = EntityType(entity_data['type'])
                    entity_data['health_status'] = HealthStatus(entity_data['health_status'])
                    self.app.create_entity(entity_data)
                    
                except Exception as e:
                    print(f"Error importing entity {entity_data}: {e}")
    
    def _show_analysis(self):
        """Show data analysis view"""
        messagebox.showinfo("Analysis", "Data analysis features coming soon!")
    
    def _generate_report(self):
        """Generate health report"""
        messagebox.showinfo("Report", "Report generation features coming soon!")
    
    def _clear_main_container(self):
        """Clear the main container"""
        for widget in self.main_container.winfo_children():
            widget.destroy()

class NewEntityDialog(tk.Toplevel):
    """Dialog for creating new entities"""
    
    def __init__(self, parent, app: KnowledgeForgeApp):
        super().__init__(parent)
        self.app = app
        
        self.title("Create New Entity")
        self.geometry("600x700")
        self.resizable(False, False)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup dialog UI"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Entity type
        ttk.Label(main_frame, text="Entity Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(value=EntityType.ANIMAL.value)
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var,
                                 values=[t.value for t in EntityType], state="readonly")
        type_combo.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Name
        ttk.Label(main_frame, text="Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Category
        ttk.Label(main_frame, text="Category:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.category_var = tk.StringVar(value=self.app.categories[0])
        category_combo = ttk.Combobox(main_frame, textvariable=self.category_var,
                                      values=self.app.categories, state="readonly")
        category_combo.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Species
        ttk.Label(main_frame, text="Species:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.species_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.species_var, width=30).grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Breed
        ttk.Label(main_frame, text="Breed:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.breed_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.breed_var, width=30).grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Birth date
        ttk.Label(main_frame, text="Birth Date:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.birth_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(main_frame, textvariable=self.birth_var, width=20).grid(row=5, column=1, sticky=tk.W, pady=5)
        
        # Location
        ttk.Label(main_frame, text="Location:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.location_var, width=30).grid(row=6, column=1, sticky=tk.W, pady=5)
        
        # Health status
        ttk.Label(main_frame, text="Health Status:").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.health_var = tk.StringVar(value=HealthStatus.GOOD.value)
        health_combo = ttk.Combobox(main_frame, textvariable=self.health_var,
                                   values=[h.value for h in HealthStatus], state="readonly")
        health_combo.grid(row=7, column=1, sticky=tk.W, pady=5)
        
        # Photo upload
        ttk.Label(main_frame, text="Photo:").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.photo_path_var = tk.StringVar()
        photo_frame = ttk.Frame(main_frame)
        photo_frame.grid(row=8, column=1, sticky=tk.W, pady=5)
        
        ttk.Entry(photo_frame, textvariable=self.photo_path_var, width=25).pack(side=tk.LEFT)
        ttk.Button(photo_frame, text="Browse", 
                  command=self._browse_photo).pack(side=tk.LEFT, padx=(5, 0))
        
        # Description
        ttk.Label(main_frame, text="Description:").grid(row=9, column=0, sticky=tk.NW, pady=5)
        self.desc_text = scrolledtext.ScrolledText(main_frame, width=40, height=5)
        self.desc_text.grid(row=9, column=1, sticky=tk.W, pady=5)
        
        # Tags
        ttk.Label(main_frame, text="Tags (comma-separated):").grid(row=10, column=0, sticky=tk.W, pady=5)
        self.tags_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.tags_var, width=30).grid(row=10, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=11, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Create", 
                  command=self._create_entity, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=self.destroy).pack(side=tk.LEFT, padx=5)
    
    def _browse_photo(self):
        """Browse for photo file"""
        file_path = filedialog.askopenfilename(
            title="Select Photo",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.gif"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            self.photo_path_var.set(file_path)
    
    def _create_entity(self):
        """Create new entity from form data"""
        try:
            # Prepare entity data
            entity_data = {
                'name': self.name_var.get().strip(),
                'type': EntityType(self.type_var.get()),
                'category': self.category_var.get(),
                'species': self.species_var.get().strip(),
                'breed': self.breed_var.get().strip(),
                'birth_date': self.birth_var.get().strip() or None,
                'location': self.location_var.get().strip(),
                'health_status': HealthStatus(self.health_var.get()),
                'photo_path': self.photo_path_var.get().strip() or None,
                'description': self.desc_text.get("1.0", tk.END).strip(),
                'tags': [t.strip() for t in self.tags_var.get().split(',') if t.strip()]
            }
            
            # Validate required fields
            if not entity_data['name']:
                raise ValueError("Name is required")
            
            # Create entity
            entity_id = self.app.create_entity(entity_data)
            
            # If photo was provided, copy it to media directory
            if entity_data['photo_path'] and os.path.exists(entity_data['photo_path']):
                entity = self.app.entities[entity_id]
                dest_dir = self.app.media_path / "photos" / entity_id
                dest_dir.mkdir(exist_ok=True)
                
                dest_path = dest_dir / os.path.basename(entity_data['photo_path'])
                shutil.copy2(entity_data['photo_path'], dest_path)
                
                # Update entity with new photo path
                entity.photo_path = str(dest_path)
                self.app.save_data()
            
            messagebox.showinfo("Success", f"Entity created: {entity_data['name']}")
            self.destroy()
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create entity: {e}")

# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Meta Learn Agriculture")
    parser.add_argument("--staging", action="store_true", help="Launch directly into Staging Review mode")
    parser.add_argument("--geometry", type=str, help="Window geometry (WxH+X+Y)")
    parser.add_argument("--init-knowledge", action="store_true", help="Initialize Knowledge Base directory structure")
    parser.add_argument("--base-dir", type=str, help="Base directory for data storage")
    parser.add_argument("--session-token", type=str, help="Authentication token from launcher")
    args = parser.parse_args()

    try:
        # Initialize application with custom base path if provided
        base_path = Path(args.base_dir).resolve() if args.base_dir else None
        app = KnowledgeForgeApp(base_path=base_path)
        app.session_token = args.session_token # Store for later use
        
        if args.init_knowledge:
            print("Initializing Knowledge Base structure...")
            created = app._init_knowledge_structure()
            for path in created:
                print(f"Created: {path}")
            if not args.staging: # If not launching GUI, exit
                 sys.exit(0)
        
        # Create sample data if none exists
        if not app.entities:
            _create_sample_data(app)
        
        # Launch GUI
        root = MainApplication(app)
        
        if args.staging:
            root._show_staging()
        
        # Apply geometry if provided, otherwise center
        if args.geometry:
            root.geometry(args.geometry)
        else:
            # Center window on screen
            root.update_idletasks()
            width = root.winfo_width()
            height = root.winfo_height()
            x = (root.winfo_screenwidth() // 2) - (width // 2)
            y = (root.winfo_screenheight() // 2) - (height // 2)
            root.geometry(f'{width}x{height}+{x}+{y}')
        
        root.mainloop()
        
    except Exception as e:
        messagebox.showerror("Fatal Error", f"Application failed to start: {e}")
        raise

def _create_sample_data(app: KnowledgeForgeApp):
    """Create sample agricultural data"""
    
    # Sample diseases
    diseases = [
        Disease(
            id="dis_001",
            name="Mastitis",
            scientific_name="Bovine Mastitis",
            category="bacterial",
            affected_species=["cattle", "goats", "sheep"],
            symptoms=["swollen udder", "abnormal milk", "fever", "loss of appetite"],
            transmission_methods=["bacterial contamination", "poor milking hygiene"],
            treatments=["antibiotics", "anti-inflammatory drugs", "frequent milking"],
            prevention_methods=["proper hygiene", "teat dipping", "dry cow therapy"],
            severity="medium",
            zoonotic=False,
            confidence_score=0.9
        ),
        Disease(
            id="dis_002",
            name="Foot and Mouth Disease",
            scientific_name="Aphthae epizooticae",
            category="viral",
            affected_species=["cattle", "pigs", "sheep", "goats"],
            symptoms=["fever", "blisters in mouth and feet", "excessive salivation", "lameness"],
            transmission_methods=["direct contact", "airborne", "contaminated equipment"],
            treatments=["supportive care", "isolation"],
            prevention_methods=["vaccination", "biosecurity measures"],
            severity="high",
            zoonotic=False,
            confidence_score=0.85
        )
    ]
    
    for disease in diseases:
        app.diseases[disease.id] = disease
    
    # Sample animals
    animals = [
        Entity(
            id="animal_001",
            name="Bella",
            type=EntityType.ANIMAL,
            category="Animal_Husbandry",
            species="Bos taurus",
            breed="Holstein",
            birth_date="2020-03-15",
            location="North Pasture",
            description="Primary milk producer, calm temperament",
            health_status=HealthStatus.GOOD,
            tags=["dairy", "productive", "vaccinated"]
        ),
        Entity(
            id="animal_002",
            name="Daisy",
            type=EntityType.ANIMAL,
            category="Animal_Husbandry",
            species="Bos taurus",
            breed="Jersey",
            birth_date="2021-06-22",
            location="South Barn",
            description="High butterfat content, recently calved",
            health_status=HealthStatus.FAIR,
            tags=["dairy", "high-fat", "new-mother"],
            disease_associations=["dis_001"]  # Had mastitis
        )
    ]
    
    for animal in animals:
        animal.last_updated = datetime.datetime.now().isoformat()
        app.entities[animal.id] = animal
    
    # Add sample health records
    record = HealthRecord(
        date="2023-10-15",
        weight=650.5,
        temperature=38.5,
        symptoms=["swollen udder", "slightly elevated temperature"],
        diagnosis="Mild mastitis",
        treatment="Intramammary antibiotics, twice daily milking",
        veterinarian="Dr. Smith",
        notes="Responding well to treatment"
    )
    
    app.add_health_record("animal_002", record)
    
    # Save all data
    app.save_data()

if __name__ == "__main__":
    main()