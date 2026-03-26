import json
import os
from datetime import datetime

os.makedirs('journals', exist_ok=True)
date_str = datetime.now().strftime('%Y-%m-%d')
path = f'journals/{date_str}.json'

entry = {
    'timestamp': datetime.now().isoformat(),
    'activity': 'discussed quantum server architecture',
    'tasks_planned': []
}

with open(path, 'w') as f:
    json.dump([entry], f, indent=2)

print(f"Simulated journal entry created at {path}")
