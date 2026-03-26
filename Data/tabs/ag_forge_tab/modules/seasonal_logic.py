from datetime import datetime
from typing import List, Dict

class SeasonalManager:
    def __init__(self, region: str = "NZ"):
        self.region = region
        # Standard NZ Seasons
        self.seasons = {
            "Summer": [12, 1, 2],
            "Autumn": [3, 4, 5],
            "Winter": [6, 7, 8],
            "Spring": [9, 10, 11]
        }
        
        # Prototype Task Database (NZ Dairy/Ag Focus)
        self.task_registry = {
            "Spring": [
                {"task": "Calving Management", "desc": "Monitor transition cows and newborn calves.", "source": "DairyNZ", "link": "https://www.dairynz.co.nz/animal/calving/"},
                {"task": "Pasture Rotation", "desc": "Manage spring flush; maintain optimal residual heights.", "source": "PrimaryITO", "link": "https://www.primaryito.ac.nz/"},
                {"task": "Mating Preparation", "desc": "Check heat detection systems and cow condition scores.", "source": "NZDairy", "link": "https://www.nzdaisy.co.nz/"}
            ],
            "Summer": [
                {"task": "Water Infrastructure Check", "desc": "Ensure peak demand flow for heat stress periods.", "source": "DairyNZ", "link": "https://www.dairynz.co.nz/environment/water-use/"},
                {"task": "Summer Crop Monitoring", "desc": "Check brassica or chicory crops for pests.", "source": "PrimaryITO", "link": "https://www.primaryito.ac.nz/"},
                {"task": "Facial Eczema Monitoring", "desc": "Start spore counting in risk areas.", "source": "DairyNZ", "link": "https://www.dairynz.co.nz/animal/health/facial-eczema/"}
            ],
            "Autumn": [
                {"task": "Drying Off Decisions", "desc": "Assess BCS (Body Condition Score) for wintering targets.", "source": "DairyNZ", "link": "https://www.dairynz.co.nz/animal/health/drying-off/"},
                {"task": "Winter Feed Planning", "desc": "Finalize silage and hay stocks; check winter crop growth.", "source": "NZDairy", "link": "https://www.nzdaisy.co.nz/"},
                {"task": "Maintenance & Fencing", "desc": "Repair winter standoff pads and tracks.", "source": "PrimaryITO", "link": "https://www.primaryito.ac.nz/"}
            ],
            "Winter": [
                {"task": "Break Feeding Management", "desc": "Manage muddy conditions; protect soil structure.", "source": "DairyNZ", "link": "https://www.dairynz.co.nz/environment/wintering/"},
                {"task": "Equipment Maintenance", "desc": "Deep service of milking parlor and tractors.", "source": "NZDairy", "link": "https://www.nzdaisy.co.nz/"},
                {"task": "Soil Testing", "desc": "Check nutrient levels before spring planting.", "source": "PrimaryITO", "link": "https://www.primaryito.ac.nz/"}
            ]
        }

    def get_current_season(self) -> str:
        month = datetime.now().month
        for season, months in self.seasons.items():
            if month in months:
                return season
        return "Unknown"

    def get_suggestions(self) -> List[Dict]:
        season = self.get_current_season()
        return self.task_registry.get(season, [])
