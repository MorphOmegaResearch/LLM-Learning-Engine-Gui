#!/usr/bin/env python3
"""
Plant Care Management System
A CLI tool for plant health monitoring and maintenance guidance
"""

import argparse
import sys
import json
import csv
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import requests
from requests.exceptions import RequestException
import pandas as pd
from pathlib import Path
import pickle
import hashlib
import re

# ==================== DATA STRUCTURES ====================

class PlantStatus(Enum):
    """Operational status categories"""
    OPTIMAL = "optimal"
    STRESSED = "stressed"
    CRITICAL = "critical"
    DYING = "dying"
    DECEASED = "deceased"

class ResourceLevel(Enum):
    """Resource collection levels"""
    ABUNDANT = "abundant"
    SUFFICIENT = "sufficient"
    DEFICIENT = "deficient"
    CRITICAL = "critical"

@dataclass
class EnvironmentalData:
    """Container for environmental metrics"""
    temperature: float
    humidity: float
    season: str
    precipitation: float = 0.0
    sunlight_hours: float = 0.0
    wind_speed: float = 0.0
    soil_moisture: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class PlantMetrics:
    """Health and operational metrics"""
    health_score: float = 100.0  # 0-100%
    survival_likelihood: float = 100.0
    resource_collection: ResourceLevel = ResourceLevel.SUFFICIENT
    utility_score: float = 0.0  # Aesthetic/functional value
    retention_score: float = 100.0  # Resource retention
    loss_rate: float = 0.0  # Resource loss per day
    stress_level: float = 0.0  # 0-1 scale
    vitality: float = 100.0  # Overall vitality
    last_assessment: datetime = field(default_factory=datetime.now)

@dataclass
class RiskFactor:
    """Identified risks"""
    name: str
    severity: float  # 0-1
    impact: str
    mitigation: str
    urgency: str  # low/medium/high/critical

@dataclass
class Plant:
    """Plant entity with all data"""
    id: str
    common_name: str
    scientific_name: str
    taxonomy: Dict[str, str]
    location: str
    planting_date: datetime
    metrics: PlantMetrics
    environmental_needs: Dict[str, Any]
    current_environment: EnvironmentalData
    risks: List[RiskFactor]
    maintenance_history: List[Dict]
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def status(self) -> PlantStatus:
        """Determine plant status from metrics"""
        if self.metrics.health_score >= 80:
            return PlantStatus.OPTIMAL
        elif self.metrics.health_score >= 60:
            return PlantStatus.STRESSED
        elif self.metrics.health_score >= 30:
            return PlantStatus.CRITICAL
        else:
            return PlantStatus.DYING

# ==================== CORE SYSTEM ====================

class PlantCareSystem:
    """Main system orchestrating all operations"""
    
    def __init__(self, data_source: str = "sqlite"):
        self.data_source = data_source
        self.plants: Dict[str, Plant] = {}
        self.environment_cache: Dict[str, EnvironmentalData] = {}
        self.config = self._load_config()
        self.db_conn = None
        
        # Pre-loaded variables
        self.SEASONS = ["spring", "summer", "fall", "winter"]
        self.METRIC_WEIGHTS = {
            "health": 0.3,
            "vitality": 0.25,
            "resource": 0.2,
            "retention": 0.15,
            "utility": 0.1
        }
        
        # API endpoints (can be overridden via config)
        self.APIS = {
            "weather": "https://api.openweathermap.org/data/2.5/weather",
            "taxonomy": "https://api.gbif.org/v1/species",
            "pest_data": "https://api.inaturalist.org/v1/observations"
        }
        
        self._initialize_data_source()
    
    def _load_config(self) -> Dict:
        """Load configuration from file or environment"""
        config_path = Path("plantcare_config.json")
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
        return {
            "api_keys": {},
            "data_refresh_hours": 24,
            "default_location": "auto",
            "risk_threshold": 0.7,
            "enable_net_fetch": True
        }
    
    def _initialize_data_source(self):
        """Initialize the chosen data source"""
        if self.data_source == "sqlite":
            self.db_conn = sqlite3.connect('plantcare.db')
            self._init_sqlite_db()
        elif self.data_source == "csv":
            self._load_csv_data()
        elif self.data_source == "memory":
            # For testing/demo
            self._load_sample_data()
    
    def _init_sqlite_db(self):
        """Initialize SQLite database with required tables"""
        cursor = self.db_conn.cursor()
        
        # Plants table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plants (
                id TEXT PRIMARY KEY,
                common_name TEXT,
                scientific_name TEXT,
                taxonomy_json TEXT,
                location TEXT,
                planting_date TEXT,
                metrics_json TEXT,
                needs_json TEXT,
                environment_json TEXT,
                risks_json TEXT,
                history_json TEXT,
                created_at TEXT
            )
        ''')
        
        # Environmental data cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS environment_cache (
                location_hash TEXT PRIMARY KEY,
                data_json TEXT,
                timestamp TEXT
            )
        ''')
        
        # Maintenance logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS maintenance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id TEXT,
                action TEXT,
                details TEXT,
                timestamp TEXT,
                FOREIGN KEY (plant_id) REFERENCES plants (id)
            )
        ''')
        
        self.db_conn.commit()
    
    def _load_csv_data(self):
        """Load plant data from CSV files"""
        try:
            plants_path = Path("plants.csv")
            if plants_path.exists():
                df = pd.read_csv(plants_path)
                for _, row in df.iterrows():
                    plant = self._create_plant_from_row(row)
                    self.plants[plant.id] = plant
        except Exception as e:
            print(f"Warning: Could not load CSV data: {e}")
    
    def _load_sample_data(self):
        """Load sample data for demonstration"""
        sample_plant = Plant(
            id="P001",
            common_name="Snake Plant",
            scientific_name="Sansevieria trifasciata",
            taxonomy={
                "kingdom": "Plantae",
                "family": "Asparagaceae",
                "genus": "Dracaena"
            },
            location="indoor",
            planting_date=datetime.now() - timedelta(days=180),
            metrics=PlantMetrics(
                health_score=85.0,
                vitality=90.0,
                resource_collection=ResourceLevel.SUFFICIENT
            ),
            environmental_needs={
                "min_temp": 15,
                "max_temp": 29,
                "ideal_temp": 22,
                "min_humidity": 40,
                "max_humidity": 70,
                "water_frequency": 14,  # days
                "light": "indirect",
                "soil_type": "well-draining"
            },
            current_environment=EnvironmentalData(
                temperature=23.5,
                humidity=55.0,
                season="winter"
            ),
            risks=[
                RiskFactor(
                    name="Overwatering risk",
                    severity=0.3,
                    impact="Root rot",
                    mitigation="Check soil moisture before watering",
                    urgency="low"
                )
            ],
            maintenance_history=[]
        )
        self.plants[sample_plant.id] = sample_plant
    
    def _create_plant_from_row(self, row: pd.Series) -> Plant:
        """Helper to create Plant from CSV row"""
        # Implementation would parse row data
        pass

# ==================== DATA FETCHING MODULES ====================

class DataFetcher:
    """Handles all external data fetching"""
    
    def __init__(self, system: PlantCareSystem):
        self.system = system
        self.session = requests.Session()
        self.session.timeout = 10
    
    def fetch_environmental_data(self, location: str) -> Optional[EnvironmentalData]:
        """Fetch current environmental data for location"""
        cache_key = hashlib.md5(location.encode()).hexdigest()
        
        # Check cache first
        if cache_key in self.system.environment_cache:
            cached = self.system.environment_cache[cache_key]
            if (datetime.now() - cached.last_updated).hours < self.system.config.get("data_refresh_hours", 24):
                return cached
        
        if not self.system.config.get("enable_net_fetch", True):
            return self._get_fallback_environment(location)
        
        try:
            # Try to fetch from weather API
            if "openweathermap" in self.system.config.get("api_keys", {}):
                data = self._fetch_from_openweather(location)
            else:
                data = self._fetch_from_fallback_service(location)
            
            if data:
                self.system.environment_cache[cache_key] = data
                return data
        except RequestException as e:
            print(f"Warning: Could not fetch environmental data: {e}")
        
        return self._get_fallback_environment(location)
    
    def _fetch_from_openweather(self, location: str) -> Optional[EnvironmentalData]:
        """Fetch data from OpenWeatherMap API"""
        api_key = self.system.config.get("api_keys", {}).get("openweathermap")
        if not api_key:
            return None
        
        params = {
            "q": location,
            "appid": api_key,
            "units": "metric"
        }
        
        response = self.session.get(self.system.APIS["weather"], params=params)
        response.raise_for_status()
        data = response.json()
        
        return EnvironmentalData(
            temperature=data["main"]["temp"],
            humidity=data["main"]["humidity"],
            season=self._determine_season(data["sys"]["country"]),
            precipitation=data.get("rain", {}).get("1h", 0),
            wind_speed=data["wind"]["speed"]
        )
    
    def fetch_taxonomy_data(self, scientific_name: str) -> Dict:
        """Fetch taxonomic data for a plant"""
        try:
            params = {"name": scientific_name, "limit": 1}
            response = self.session.get(self.system.APIS["taxonomy"], params=params)
            if response.status_code == 200:
                return response.json()
        except RequestException:
            pass
        
        # Fallback to local taxonomy database
        return self._get_local_taxonomy(scientific_name)
    
    def fetch_pest_disease_data(self, plant_species: str, location: str = None) -> List[Dict]:
        """Fetch recent pest/disease observations"""
        try:
            params = {
                "taxon_name": plant_species,
                "quality_grade": "research",
                "order_by": "observed_on",
                "per_page": 10
            }
            if location:
                params["place_id"] = location
            
            response = self.session.get(self.system.APIS["pest_data"], params=params)
            if response.status_code == 200:
                return response.json().get("results", [])
        except RequestException as e:
            print(f"Warning: Could not fetch pest data: {e}")
        
        return []
    
    def _determine_season(self, country_code: str) -> str:
        """Determine current season based on hemisphere and date"""
        month = datetime.now().month
        hemisphere = self._get_hemisphere(country_code)
        
        if hemisphere == "north":
            if month in [12, 1, 2]:
                return "winter"
            elif month in [3, 4, 5]:
                return "spring"
            elif month in [6, 7, 8]:
                return "summer"
            else:
                return "fall"
        else:
            if month in [12, 1, 2]:
                return "summer"
            elif month in [3, 4, 5]:
                return "fall"
            elif month in [6, 7, 8]:
                return "winter"
            else:
                return "spring"
    
    def _get_hemisphere(self, country_code: str) -> str:
        """Determine hemisphere for country"""
        # Simplified - would need complete mapping
        northern = ["US", "CA", "UK", "FR", "DE", "CN", "JP", "KR"]
        return "north" if country_code.upper() in northern else "south"
    
    def _get_fallback_environment(self, location: str) -> EnvironmentalData:
        """Provide fallback environmental data"""
        # Simple seasonal averages
        month = datetime.now().month
        if month in [12, 1, 2]:  # Winter
            temp = 5.0 if "indoor" not in location.lower() else 21.0
            humidity = 60.0
        elif month in [3, 4, 5]:  # Spring
            temp = 15.0 if "indoor" not in location.lower() else 22.0
            humidity = 65.0
        elif month in [6, 7, 8]:  # Summer
            temp = 25.0 if "indoor" not in location.lower() else 24.0
            humidity = 70.0
        else:  # Fall
            temp = 15.0 if "indoor" not in location.lower() else 22.0
            humidity = 65.0
        
        return EnvironmentalData(
            temperature=temp,
            humidity=humidity,
            season=self._determine_season("US")
        )
    
    def _get_local_taxonomy(self, scientific_name: str) -> Dict:
        """Get taxonomy from local database"""
        # This would query a local SQLite/CSV taxonomy database
        return {"scientificName": scientific_name, "family": "Unknown"}

# ==================== ANALYSIS ENGINE ====================

class PlantAnalyzer:
    """Analyzes plant health and calculates metrics"""
    
    def __init__(self, system: PlantCareSystem):
        self.system = system
        self.fetcher = DataFetcher(system)
    
    def analyze_plant(self, plant: Plant, update_env: bool = True) -> Tuple[PlantMetrics, List[RiskFactor]]:
        """Perform comprehensive plant analysis"""
        
        # Update environmental data if needed
        if update_env:
            env_data = self.fetcher.fetch_environmental_data(plant.location)
            if env_data:
                plant.current_environment = env_data
        
        # Calculate metrics
        metrics = self._calculate_metrics(plant)
        
        # Identify risks
        risks = self._identify_risks(plant, metrics)
        
        # Update pest/disease data
        self._update_pest_data(plant)
        
        return metrics, risks
    
    def _calculate_metrics(self, plant: Plant) -> PlantMetrics:
        """Calculate all plant metrics"""
        
        # Temperature suitability (0-1)
        temp_diff = abs(plant.current_environment.temperature - plant.environmental_needs.get("ideal_temp", 22))
        temp_range = plant.environmental_needs.get("max_temp", 30) - plant.environmental_needs.get("min_temp", 10)
        temp_suitability = max(0, 1 - (temp_diff / (temp_range * 0.5)))
        
        # Humidity suitability
        humidity = plant.current_environment.humidity
        min_humidity = plant.environmental_needs.get("min_humidity", 30)
        max_humidity = plant.environmental_needs.get("max_humidity", 80)
        if min_humidity <= humidity <= max_humidity:
            humidity_suitability = 1.0
        else:
            diff = min(abs(humidity - min_humidity), abs(humidity - max_humidity))
            humidity_suitability = max(0, 1 - (diff / 20))
        
        # Seasonal adjustment
        season_factor = self._get_season_factor(plant)
        
        # Calculate health score
        base_health = (temp_suitability * 0.4 + humidity_suitability * 0.3 + season_factor * 0.3) * 100
        
        # Apply time decay (plants degrade over time without care)
        days_since_planting = (datetime.now() - plant.planting_date).days
        time_factor = max(0.5, 1 - (days_since_planting * 0.0001))
        
        # Apply maintenance history factor
        maintenance_factor = self._calculate_maintenance_factor(plant)
        
        final_health = base_health * time_factor * maintenance_factor
        
        # Determine resource collection level
        resource_score = (temp_suitability + humidity_suitability + season_factor) / 3
        if resource_score >= 0.8:
            resource_level = ResourceLevel.ABUNDANT
        elif resource_score >= 0.6:
            resource_level = ResourceLevel.SUFFICIENT
        elif resource_score >= 0.4:
            resource_level = ResourceLevel.DEFICIENT
        else:
            resource_level = ResourceLevel.CRITICAL
        
        return PlantMetrics(
            health_score=round(final_health, 1),
            survival_likelihood=round(final_health * 0.9, 1),  # Slightly pessimistic
            resource_collection=resource_level,
            utility_score=self._calculate_utility(plant),
            retention_score=round(resource_score * 100, 1),
            loss_rate=round((1 - resource_score) * 5, 2),  # Arbitrary units
            stress_level=round(1 - resource_score, 2),
            vitality=round(final_health * 0.95, 1)
        )
    
    def _get_season_factor(self, plant: Plant) -> float:
        """Get seasonal suitability factor"""
        # Some plants prefer specific seasons
        preferred_seasons = plant.environmental_needs.get("preferred_seasons", ["spring", "summer", "fall"])
        current_season = plant.current_environment.season
        
        if current_season in preferred_seasons:
            return 1.0
        elif len(preferred_seasons) == 4:  # All seasons
            return 0.9
        else:
            return 0.6  # Non-preferred season penalty
    
    def _calculate_maintenance_factor(self, plant: Plant) -> float:
        """Factor based on maintenance history"""
        if not plant.maintenance_history:
            return 0.8  # Penalty for no maintenance records
        
        recent_maintenance = [
            m for m in plant.maintenance_history
            if (datetime.now() - datetime.fromisoformat(m["timestamp"])).days < 30
        ]
        
        if len(recent_maintenance) >= 4:
            return 1.0
        elif len(recent_maintenance) >= 2:
            return 0.9
        elif len(recent_maintenance) >= 1:
            return 0.85
        else:
            return 0.7
    
    def _calculate_utility(self, plant: Plant) -> float:
        """Calculate utility score (aesthetic/functional value)"""
        # This could be based on various factors
        utility_map = {
            "edible": 0.8,
            "medicinal": 0.9,
            "ornamental": 0.7,
            "air_purifying": 0.6,
            "shade_providing": 0.5
        }
        
        plant_type = plant.environmental_needs.get("type", "ornamental")
        base_utility = utility_map.get(plant_type, 0.5)
        
        # Adjust based on health
        return base_utility * (plant.metrics.health_score / 100)
    
    def _identify_risks(self, plant: Plant, metrics: PlantMetrics) -> List[RiskFactor]:
        """Identify potential risks to plant health"""
        risks = []
        
        # Temperature risks
        current_temp = plant.current_environment.temperature
        min_temp = plant.environmental_needs.get("min_temp", 10)
        max_temp = plant.environmental_needs.get("max_temp", 30)
        
        if current_temp < min_temp:
            severity = (min_temp - current_temp) / 10
            risks.append(RiskFactor(
                name="Low temperature stress",
                severity=min(severity, 1.0),
                impact="Growth stunting, leaf damage",
                mitigation="Move to warmer location or provide insulation",
                urgency="high" if severity > 0.5 else "medium"
            ))
        
        if current_temp > max_temp:
            severity = (current_temp - max_temp) / 10
            risks.append(RiskFactor(
                name="Heat stress",
                severity=min(severity, 1.0),
                impact="Wilting, leaf scorch",
                mitigation="Increase watering, provide shade",
                urgency="high" if severity > 0.5 else "medium"
            ))
        
        # Humidity risks
        current_humidity = plant.current_environment.humidity
        ideal_min = plant.environmental_needs.get("min_humidity", 40)
        ideal_max = plant.environmental_needs.get("max_humidity", 70)
        
        if current_humidity < ideal_min:
            severity = (ideal_min - current_humidity) / 20
            risks.append(RiskFactor(
                name="Low humidity",
                severity=min(severity, 0.8),
                impact="Leaf browning, poor growth",
                mitigation="Use humidifier or pebble tray",
                urgency="medium" if severity > 0.3 else "low"
            ))
        
        # Health-based risks
        if metrics.health_score < 50:
            risks.append(RiskFactor(
                name="Poor overall health",
                severity=1 - (metrics.health_score / 100),
                impact="Increased susceptibility to diseases",
                mitigation="Review all care parameters, consider repotting",
                urgency="high" if metrics.health_score < 30 else "medium"
            ))
        
        return risks
    
    def _update_pest_data(self, plant: Plant):
        """Update plant with pest/disease observations"""
        if self.system.config.get("enable_net_fetch", True):
            pest_data = self.fetcher.fetch_pest_disease_data(
                plant.scientific_name,
                plant.location
            )
            
            if pest_data:
                # Add pest risks if common in area
                common_pests = self._extract_common_pests(pest_data)
                for pest in common_pests[:3]:  # Top 3 most common
                    existing_risk_names = [r.name for r in plant.risks]
                    if pest["name"] not in existing_risk_names:
                        plant.risks.append(RiskFactor(
                            name=f"Common pest: {pest['name']}",
                            severity=pest.get("frequency", 0.3),
                            impact=pest.get("impact", "Leaf damage"),
                            mitigation="Apply appropriate treatment, improve plant health",
                            urgency="medium"
                        ))
    
    def _extract_common_pests(self, observations: List[Dict]) -> List[Dict]:
        """Extract common pests from observation data"""
        pest_counts = {}
        for obs in observations:
            taxa = obs.get("taxon", {})
            if "pest" in taxa.get("preferred_common_name", "").lower():
                name = taxa.get("preferred_common_name", "Unknown pest")
                pest_counts[name] = pest_counts.get(name, 0) + 1
        
        return [{"name": name, "frequency": min(count/10, 1.0)} 
                for name, count in pest_counts.items()]

# ==================== UX & GUIDANCE ENGINE ====================

class GuidanceEngine:
    """Provides user guidance and maintenance instructions"""
    
    def __init__(self, system: PlantCareSystem):
        self.system = system
        self.analyzer = PlantAnalyzer(system)
    
    def generate_guidance(self, plant: Plant) -> Dict[str, Any]:
        """Generate comprehensive guidance for a plant"""
        
        # Re-analyze if data is stale
        if (datetime.now() - plant.metrics.last_assessment).days > 1:
            metrics, risks = self.analyzer.analyze_plant(plant)
            plant.metrics = metrics
            plant.risks = risks
        
        guidance = {
            "plant_info": {
                "id": plant.id,
                "name": plant.common_name,
                "scientific_name": plant.scientific_name,
                "status": plant.status.value,
                "health_score": plant.metrics.health_score
            },
            "current_conditions": asdict(plant.current_environment),
            "assessment": self._generate_assessment(plant),
            "immediate_actions": self._get_immediate_actions(plant),
            "maintenance_schedule": self._generate_schedule(plant),
            "risk_report": self._generate_risk_report(plant),
            "improvement_plan": self._generate_improvement_plan(plant)
        }
        
        return guidance
    
    def _generate_assessment(self, plant: Plant) -> Dict[str, Any]:
        """Generate human-readable assessment"""
        status = plant.status
        
        assessments = {
            PlantStatus.OPTIMAL: {
                "summary": "Your plant is thriving!",
                "details": f"{plant.common_name} is in excellent health with a score of {plant.metrics.health_score}%.",
                "emotion": "Happy and vigorous"
            },
            PlantStatus.STRESSED: {
                "summary": "Your plant is experiencing some stress.",
                "details": f"Health score: {plant.metrics.health_score}%. Some parameters need adjustment.",
                "emotion": "Slightly stressed but resilient"
            },
            PlantStatus.CRITICAL: {
                "summary": "Your plant needs immediate attention!",
                "details": f"Health score: {plant.metrics.health_score}%. Significant intervention required.",
                "emotion": "Struggling to survive"
            },
            PlantStatus.DYING: {
                "summary": "CRITICAL: Plant is in danger!",
                "details": f"Health score: {plant.metrics.health_score}%. Emergency measures needed.",
                "emotion": "In distress, near collapse"
            }
        }
        
        return assessments.get(status, assessments[PlantStatus.STRESSED])
    
    def _get_immediate_actions(self, plant: Plant) -> List[Dict]:
        """Determine immediate actions needed"""
        actions = []
        
        # Check watering needs
        last_watering = None
        for action in reversed(plant.maintenance_history):
            if "watering" in action.get("action", "").lower():
                last_watering = datetime.fromisoformat(action["timestamp"])
                break
        
        water_freq = plant.environmental_needs.get("water_frequency", 7)
        if last_watering:
            days_since = (datetime.now() - last_watering).days
            if days_since >= water_freq:
                actions.append({
                    "action": "Water plant",
                    "priority": "high",
                    "instructions": f"Water thoroughly until it drains from the bottom. Last watered {days_since} days ago.",
                    "estimated_time": "5 minutes"
                })
        
        # Address high-priority risks
        for risk in plant.risks:
            if risk.urgency in ["high", "critical"]:
                actions.append({
                    "action": f"Address: {risk.name}",
                    "priority": risk.urgency,
                    "instructions": risk.mitigation,
                    "estimated_time": "15-30 minutes"
                })
        
        # General health actions
        if plant.metrics.health_score < 70:
            actions.append({
                "action": "General health inspection",
                "priority": "medium",
                "instructions": "Check for yellow leaves, pests, and soil condition.",
                "estimated_time": "10 minutes"
            })
        
        return actions[:5]  # Limit to 5 most important
    
    def _generate_schedule(self, plant: Plant) -> Dict[str, List[str]]:
        """Generate maintenance schedule"""
        schedule = {
            "daily": ["Check soil moisture", "Observe leaf color"],
            "weekly": self._get_weekly_tasks(plant),
            "monthly": ["Fertilize (during growing season)", "Wipe leaves", "Check for pests"],
            "seasonal": self._get_seasonal_tasks(plant)
        }
        
        return schedule
    
    def _get_weekly_tasks(self, plant: Plant) -> List[str]:
        """Get weekly tasks based on plant needs"""
        tasks = []
        water_freq = plant.environmental_needs.get("water_frequency", 7)
        
        if water_freq <= 7:
            tasks.append("Water plant")
        if plant.current_environment.humidity < 40:
            tasks.append("Mist leaves or use humidifier")
        
        return tasks
    
    def _get_seasonal_tasks(self, plant: Plant) -> List[str]:
        """Get seasonal tasks"""
        season = plant.current_environment.season
        seasonal_tasks = {
            "spring": ["Repot if needed", "Start regular fertilizing", "Prune dead growth"],
            "summer": ["Increase watering frequency", "Provide shade if needed", "Monitor for pests"],
            "fall": ["Reduce fertilizing", "Prepare for winter", "Clean up fallen leaves"],
            "winter": ["Reduce watering", "Protect from cold drafts", "Provide supplemental light if needed"]
        }
        
        return seasonal_tasks.get(season, [])
    
    def _generate_risk_report(self, plant: Plant) -> Dict[str, Any]:
        """Generate detailed risk report"""
        return {
            "total_risks": len(plant.risks),
            "critical_risks": len([r for r in plant.risks if r.urgency == "critical"]),
            "high_risks": len([r for r in plant.risks if r.urgency == "high"]),
            "detailed_risks": [
                {
                    "name": r.name,
                    "severity": r.severity,
                    "urgency": r.urgency,
                    "mitigation": r.mitigation
                } for r in sorted(plant.risks, key=lambda x: x.severity, reverse=True)
            ]
        }
    
    def _generate_improvement_plan(self, plant: Plant) -> List[Dict]:
        """Generate plan to improve plant health"""
        plan = []
        
        if plant.metrics.health_score < 90:
            # Environmental improvements
            env_needs = plant.environmental_needs
            current_env = plant.current_environment
            
            if abs(current_env.temperature - env_needs.get("ideal_temp", 22)) > 3:
                plan.append({
                    "goal": "Optimize temperature",
                    "action": f"Adjust environment to {env_needs.get('ideal_temp')}°C",
                    "expected_impact": "+5-10% health"
                })
            
            if current_env.humidity < env_needs.get("min_humidity", 40):
                plan.append({
                    "goal": "Increase humidity",
                    "action": "Use humidifier or pebble tray",
                    "expected_impact": "+3-7% health"
                })
            
            # General improvements
            plan.append({
                "goal": "Improve soil nutrition",
                "action": "Apply balanced fertilizer next watering",
                "expected_impact": "+2-5% health"
            })
        
        return plan

# ==================== CLI INTERFACE ====================

class PlantCareCLI:
    """Command-line interface for the plant care system"""
    
    def __init__(self):
        self.parser = self._create_parser()
        self.system = None
        self.guidance_engine = None
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser with all commands"""
        parser = argparse.ArgumentParser(
            description="Plant Care Management System - Monitor and care for your plants",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Available Workflows:
  setup          Initialize the system with your plants
  monitor        Check all plant statuses
  analyze        Detailed analysis of specific plant
  guide          Get care guidance
  fetch          Update environmental data
  risks          View and manage risks
  report         Generate reports
  maintain       Log maintenance activities
            
Examples:
  %(prog)s setup --csv plants.csv
  %(prog)s monitor --all
  %(prog)s analyze --plant P001 --detailed
  %(prog)s guide --plant P001 --actions
            """
        )
        
        # Global arguments
        parser.add_argument("--data-source", choices=["sqlite", "csv", "memory"],
                          default="sqlite", help="Data storage method")
        parser.add_argument("--config", type=str, help="Config file path")
        parser.add_argument("--verbose", "-v", action="count", default=0,
                          help="Increase verbosity level")
        
        # Subparsers for commands
        subparsers = parser.add_subparsers(dest="command", help="Command to execute")
        
        # Setup command
        setup_parser = subparsers.add_parser("setup", help="Initialize system")
        setup_parser.add_argument("--csv", type=str, help="Import plants from CSV")
        setup_parser.add_argument("--db", type=str, help="SQLite database path")
        setup_parser.add_argument("--sample", action="store_true", 
                                help="Load sample data for testing")
        
        # Monitor command
        monitor_parser = subparsers.add_parser("monitor", help="Monitor plant health")
        monitor_parser.add_argument("--all", action="store_true", 
                                  help="Monitor all plants")
        monitor_parser.add_argument("--plant", type=str, help="Specific plant ID")
        monitor_parser.add_argument("--quick", action="store_true",
                                  help="Quick status check only")
        
        # Analyze command
        analyze_parser = subparsers.add_parser("analyze", help="Analyze plant health")
        analyze_parser.add_argument("--plant", type=str, required=True,
                                  help="Plant ID to analyze")
        analyze_parser.add_argument("--detailed", action="store_true",
                                  help="Show detailed analysis")
        analyze_parser.add_argument("--no-fetch", action="store_true",
                                  help="Don't fetch new environmental data")
        
        # Guide command
        guide_parser = subparsers.add_parser("guide", help="Get care guidance")
        guide_parser.add_argument("--plant", type=str, required=True,
                                help="Plant ID to get guidance for")
        guide_parser.add_argument("--actions", action="store_true",
                                help="Show only immediate actions")
        guide_parser.add_argument("--schedule", action="store_true",
                                help="Show maintenance schedule")
        
        # Fetch command
        fetch_parser = subparsers.add_parser("fetch", help="Fetch external data")
        fetch_parser.add_argument("--environment", action="store_true",
                                help="Fetch environmental data")
        fetch_parser.add_argument("--pest", action="store_true",
                                help="Fetch pest/disease data")
        fetch_parser.add_argument("--taxonomy", action="store_true",
                                help="Fetch taxonomy data")
        fetch_parser.add_argument("--all", action="store_true",
                                help="Fetch all data types")
        
        # Risks command
        risks_parser = subparsers.add_parser("risks", help="Manage plant risks")
        risks_parser.add_argument("--list", action="store_true",
                                help="List all risks")
        risks_parser.add_argument("--plant", type=str, help="Filter by plant ID")
        risks_parser.add_argument("--critical", action="store_true",
                                help="Show only critical risks")
        
        # Report command
        report_parser = subparsers.add_parser("report", help="Generate reports")
        report_parser.add_argument("--format", choices=["text", "json", "csv"],
                                 default="text", help="Output format")
        report_parser.add_argument("--output", type=str, help="Output file")
        report_parser.add_argument("--summary", action="store_true",
                                 help="Summary report only")
        
        # Maintain command
        maintain_parser = subparsers.add_parser("maintain", help="Log maintenance")
        maintain_parser.add_argument("--plant", type=str, required=True,
                                   help="Plant ID for maintenance")
        maintain_parser.add_argument("--action", type=str, required=True,
                                   help="Maintenance action performed")
        maintain_parser.add_argument("--details", type=str,
                                   help="Additional details")
        
        return parser
    
    def run(self):
        """Run the CLI application"""
        args = self.parser.parse_args()
        
        if not args.command:
            self.parser.print_help()
            return 1
        
        try:
            # Initialize system
            self.system = PlantCareSystem(data_source=args.data_source)
            self.guidance_engine = GuidanceEngine(self.system)
            
            # Execute command
            command_method = getattr(self, f"cmd_{args.command}", None)
            if command_method:
                return command_method(args)
            else:
                print(f"Error: Unknown command '{args.command}'")
                return 1
                
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return 130
        except Exception as e:
            if args.verbose > 0:
                import traceback
                traceback.print_exc()
            else:
                print(f"Error: {str(e)}")
            return 1
    
    def cmd_setup(self, args):
        """Handle setup command"""
        print("Setting up Plant Care System...")
        
        if args.csv:
            print(f"Importing plants from {args.csv}...")
            # Implementation for CSV import
        elif args.sample:
            print("Loading sample data...")
            self.system._load_sample_data()
        
        print("Setup complete!")
        return 0
    
    def cmd_monitor(self, args):
        """Handle monitor command"""
        if not self.system.plants:
            print("No plants found. Use 'setup' command first.")
            return 1
        
        if args.all or not args.plant:
            plants_to_monitor = list(self.system.plants.values())
        else:
            if args.plant not in self.system.plants:
                print(f"Plant '{args.plant}' not found.")
                return 1
            plants_to_monitor = [self.system.plants[args.plant]]
        
        print(f"Monitoring {len(plants_to_monitor)} plant(s)...\n")
        
        for plant in plants_to_monitor:
            if args.quick:
                print(f"{plant.id}: {plant.common_name} - "
                      f"Health: {plant.metrics.health_score}% - "
                      f"Status: {plant.status.value}")
            else:
                self._display_plant_details(plant)
                print("-" * 50)
        
        return 0
    
    def cmd_analyze(self, args):
        """Handle analyze command"""
        if args.plant not in self.system.plants:
            print(f"Plant '{args.plant}' not found.")
            return 1
        
        plant = self.system.plants[args.plant]
        analyzer = PlantAnalyzer(self.system)
        
        print(f"Analyzing {plant.common_name} ({plant.id})...")
        
        metrics, risks = analyzer.analyze_plant(plant, not args.no_fetch)
        plant.metrics = metrics
        plant.risks = risks
        
        if args.detailed:
            self._display_detailed_analysis(plant, metrics, risks)
        else:
            print(f"\nHealth Score: {metrics.health_score}%")
            print(f"Status: {plant.status.value}")
            print(f"Vitality: {metrics.vitality}")
            print(f"Resource Collection: {metrics.resource_collection.value}")
            print(f"Identified Risks: {len(risks)}")
        
        return 0
    
    def cmd_guide(self, args):
        """Handle guide command"""
        if args.plant not in self.system.plants:
            print(f"Plant '{args.plant}' not found.")
            return 1
        
        plant = self.system.plants[args.plant]
        guidance = self.guidance_engine.generate_guidance(plant)
        
        print(f"\n=== Care Guidance for {plant.common_name} ===\n")
        
        if args.actions:
            print("IMMEDIATE ACTIONS:")
            for action in guidance["immediate_actions"]:
                print(f"  • [{action['priority'].upper()}] {action['action']}")
                print(f"    {action['instructions']}\n")
        elif args.schedule:
            print("MAINTENANCE SCHEDULE:")
            for frequency, tasks in guidance["maintenance_schedule"].items():
                if tasks:
                    print(f"\n  {frequency.capitalize()}:")
                    for task in tasks:
                        print(f"    • {task}")
        else:
            print(f"STATUS: {guidance['assessment']['summary']}")
            print(f"Assessment: {guidance['assessment']['details']}")
            print(f"How your plant feels: {guidance['assessment']['emotion']}\n")
            
            print("IMMEDIATE ACTIONS:")
            for action in guidance["immediate_actions"][:3]:
                print(f"  • {action['action']} ({action['priority']})")
            
            print("\nTOP RISKS:")
            for risk in guidance["risk_report"]["detailed_risks"][:3]:
                print(f"  • {risk['name']} (urgency: {risk['urgency']})")
        
        return 0
    
    def cmd_fetch(self, args):
        """Handle fetch command"""
        fetcher = DataFetcher(self.system)
        
        if args.all or args.environment:
            print("Fetching environmental data...")
            # Fetch for all plants
            for plant in self.system.plants.values():
                data = fetcher.fetch_environmental_data(plant.location)
                if data:
                    plant.current_environment = data
                    print(f"  Updated {plant.common_name}")
        
        if args.all or args.pest:
            print("\nFetching pest/disease data...")
            for plant in self.system.plants.values():
                fetcher.fetch_pest_disease_data(plant.scientific_name, plant.location)
        
        print("\nData fetch complete!")
        return 0
    
    def cmd_risks(self, args):
        """Handle risks command"""
        all_risks = []
        
        if args.plant:
            if args.plant not in self.system.plants:
                print(f"Plant '{args.plant}' not found.")
                return 1
            plants = [self.system.plants[args.plant]]
        else:
            plants = self.system.plants.values()
        
        for plant in plants:
            for risk in plant.risks:
                if not args.critical or risk.urgency == "critical":
                    all_risks.append({
                        "plant": plant.common_name,
                        "risk": risk
                    })
        
        if not all_risks:
            print("No risks found!")
            return 0
        
        print(f"Found {len(all_risks)} risk(s):\n")
        
        for item in sorted(all_risks, 
                          key=lambda x: x["risk"].severity, 
                          reverse=True):
            risk = item["risk"]
            print(f"Plant: {item['plant']}")
            print(f"Risk: {risk.name}")
            print(f"Severity: {risk.severity:.2f} - Urgency: {risk.urgency}")
            print(f"Impact: {risk.impact}")
            print(f"Mitigation: {risk.mitigation}\n")
        
        return 0
    
    def cmd_report(self, args):
        """Handle report command"""
        report_data = []
        
        for plant in self.system.plants.values():
            report_data.append({
                "id": plant.id,
                "name": plant.common_name,
                "health_score": plant.metrics.health_score,
                "status": plant.status.value,
                "temperature": plant.current_environment.temperature,
                "humidity": plant.current_environment.humidity,
                "risks_count": len(plant.risks),
                "critical_risks": len([r for r in plant.risks if r.urgency == "critical"])
            })
        
        if args.format == "json":
            output = json.dumps(report_data, indent=2, default=str)
        elif args.format == "csv":
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=report_data[0].keys())
            writer.writeheader()
            writer.writerows(report_data)
            output = output.getvalue()
        else:  # text
            output = "PLANT HEALTH REPORT\n" + "="*50 + "\n"
            for item in report_data:
                output += f"\n{item['name']} ({item['id']}):\n"
                output += f"  Health: {item['health_score']}% - Status: {item['status']}\n"
                output += f"  Environment: {item['temperature']}°C, {item['humidity']}% humidity\n"
                output += f"  Risks: {item['risks_count']} total, {item['critical_risks']} critical\n"
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Report saved to {args.output}")
        else:
            print(output)
        
        return 0
    
    def cmd_maintain(self, args):
        """Handle maintain command"""
        if args.plant not in self.system.plants:
            print(f"Plant '{args.plant}' not found.")
            return 1
        
        plant = self.system.plants[args.plant]
        
        maintenance_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": args.action,
            "details": args.details or "",
            "performed_by": "user"
        }
        
        plant.maintenance_history.append(maintenance_entry)
        
        # Update metrics after maintenance
        analyzer = PlantAnalyzer(self.system)
        metrics, risks = analyzer.analyze_plant(plant)
        plant.metrics = metrics
        plant.risks = risks
        
        print(f"Maintenance logged for {plant.common_name}")
        print(f"Action: {args.action}")
        if args.details:
            print(f"Details: {args.details}")
        print(f"New health score: {metrics.health_score}%")
        
        return 0
    
    def _display_plant_details(self, plant: Plant):
        """Display detailed plant information"""
        print(f"\n{plant.common_name} ({plant.scientific_name})")
        print(f"ID: {plant.id} | Status: {plant.status.value}")
        print(f"Location: {plant.location}")
        print(f"Planted: {plant.planting_date.strftime('%Y-%m-%d')}")
        print(f"Age: {(datetime.now() - plant.planting_date).days} days\n")
        
        print("HEALTH METRICS:")
        print(f"  Overall Health: {plant.metrics.health_score}%")
        print(f"  Survival Likelihood: {plant.metrics.survival_likelihood}%")
        print(f"  Resource Collection: {plant.metrics.resource_collection.value}")
        print(f"  Stress Level: {plant.metrics.stress_level:.2f}")
        print(f"  Vitality: {plant.metrics.vitality}\n")
        
        print("CURRENT ENVIRONMENT:")
        env = plant.current_environment
        print(f"  Temperature: {env.temperature}°C")
        print(f"  Humidity: {env.humidity}%")
        print(f"  Season: {env.season}")
        print(f"  Last Updated: {env.last_updated.strftime('%Y-%m-%d %H:%M')}\n")
        
        if plant.risks:
            print(f"ACTIVE RISKS ({len(plant.risks)}):")
            for risk in sorted(plant.risks, key=lambda x: x.severity, reverse=True)[:3]:
                print(f"  • {risk.name} [{risk.urgency}]")
    
    def _display_detailed_analysis(self, plant: Plant, metrics: PlantMetrics, risks: List[RiskFactor]):
        """Display detailed analysis results"""
        print("\n" + "="*60)
        print(f"DETAILED ANALYSIS: {plant.common_name}")
        print("="*60)
        
        print("\nOPERATIONAL DEPENDENCIES:")
        print(f"  Health Score:           {metrics.health_score:>6.1f}%")
        print(f"  Survival Likelihood:    {metrics.survival_likelihood:>6.1f}%")
        print(f"  Resource Collection:    {metrics.resource_collection.value:>15}")
        print(f"  Utility Score:          {metrics.utility_score:>6.1f}")
        print(f"  Retention Score:        {metrics.retention_score:>6.1f}%")
        print(f"  Loss Rate:              {metrics.loss_rate:>6.2f} units/day")
        print(f"  Stress Level:           {metrics.stress_level:>6.2f}")
        print(f"  Vitality:               {metrics.vitality:>6.1f}")
        
        print("\nENVIRONMENTAL ANALYSIS:")
        needs = plant.environmental_needs
        current = plant.current_environment
        
        temp_status = "✓" if needs.get("min_temp", 0) <= current.temperature <= needs.get("max_temp", 100) else "✗"
        print(f"  Temperature: {current.temperature}°C (ideal: {needs.get('ideal_temp', 'N/A')}°C) {temp_status}")
        
        humidity_status = "✓" if needs.get("min_humidity", 0) <= current.humidity <= needs.get("max_humidity", 100) else "✗"
        print(f"  Humidity:    {current.humidity}% {humidity_status}")
        
        print(f"  Season:      {current.season}")
        
        print("\nRISK ASSESSMENT:")
        if risks:
            for i, risk in enumerate(sorted(risks, key=lambda x: x.severity, reverse=True), 1):
                print(f"\n  {i}. {risk.name}")
                print(f"     Severity: {risk.severity:.2f} | Urgency: {risk.urgency}")
                print(f"     Impact:   {risk.impact}")
                print(f"     Action:   {risk.mitigation}")
        else:
            print("  No significant risks detected.")
        
        print("\nHOW YOUR PLANT FEELS:")
        if metrics.health_score >= 80:
            print("  🌱 Thriving and content")
            print("  Feeling robust and well-nourished")
        elif metrics.health_score >= 60:
            print("  🍃 Managing but showing stress")
            print("  Feeling somewhat strained but coping")
        elif metrics.health_score >= 40:
            print("  🥀 Struggling to maintain function")
            print("  Feeling weakened and distressed")
        else:
            print("  💀 Critical condition")
            print("  Feeling desperate for intervention")
        
        print("\n" + "="*60)

# ==================== MAIN EXECUTION ====================

def main():
    """Main entry point"""
    cli = PlantCareCLI()
    return cli.run()

if __name__ == "__main__":
    sys.exit(main())