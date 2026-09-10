"""
database.py — In-memory state tracker for autonomous monitoring.

Maintains the state of vulnerable regions, persistence counters, 
and historical scores to prevent false alarms.
"""

from typing import Dict, Any

class StateTracker:
    def __init__(self):
        # region_id -> state dict
        self.regions = {}

    def get_region_state(self, region_id: str) -> Dict[str, Any]:
        """Fetch current state of a region. Initialize if it doesn't exist."""
        if region_id not in self.regions:
            self.regions[region_id] = {
                "alert_level": "GREEN",      # GREEN, YELLOW, ORANGE, RED
                "elevated_count": 0,         # Persistence counter
                "baseline_optical": None,    # The last known safe optical image
                "last_risk_score": 0.0,
                "history": []
            }
        return self.regions[region_id]

    def update_region_state(self, region_id: str, updates: Dict[str, Any]):
        """Update specific fields in the region's state."""
        state = self.get_region_state(region_id)
        state.update(updates)
        self.regions[region_id] = state

# Global instance for the prototype
db = StateTracker()
