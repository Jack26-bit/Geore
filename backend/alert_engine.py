"""
alert_engine.py — Evaluates risk scores and transitions alert states.

Implements persistence logic to prevent single noisy observations 
from triggering false alarms.
"""

from typing import Dict, Any
from database import db

# Thresholds for risk scores
YELLOW_THRESH = 40.0
ORANGE_THRESH = 60.0
RED_THRESH = 80.0

# Persistence required (number of consecutive elevated observations)
PERSISTENCE_REQUIRED = 2

def evaluate_alert_state(region_id: str, risk_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates the region's alert state based on the new risk score and persistence.
    
    Returns:
        A dict describing the alert decision.
    """
    state = db.get_region_state(region_id)
    current_level = state["alert_level"]
    score = risk_result["risk_score"]
    
    new_level = current_level
    needs_vlm_verification = False
    
    # ── Determine instantaneous condition ──
    if score >= RED_THRESH:
        condition = "RED"
    elif score >= ORANGE_THRESH:
        condition = "ORANGE"
    elif score >= YELLOW_THRESH:
        condition = "YELLOW"
    else:
        condition = "GREEN"
        
    # ── Persistence Logic ──
    if condition == "GREEN":
        # Immediately downgrade on safe signals
        new_level = "GREEN"
        state["elevated_count"] = 0
    else:
        # If the condition is higher or equal to current level, build persistence
        if condition in ["YELLOW", "ORANGE", "RED"]:
            state["elevated_count"] += 1
            
            # If persistence met, upgrade state
            if state["elevated_count"] >= PERSISTENCE_REQUIRED:
                new_level = condition
                # Once elevated, reset counter to avoid immediate double-upgrade
                # wait, for a prototype, we can just keep it at the level
                if new_level in ["ORANGE", "RED"]:
                    needs_vlm_verification = True
        else:
            # Score dropped but not to green, slowly decay
            state["elevated_count"] = max(0, state["elevated_count"] - 1)
            
    # Save updates
    db.update_region_state(region_id, {
        "alert_level": new_level,
        "last_risk_score": score,
        "elevated_count": state["elevated_count"]
    })
    
    return {
        "region_id": region_id,
        "previous_level": current_level,
        "new_level": new_level,
        "risk_score": score,
        "evidence": risk_result["evidence"],
        "needs_vlm_verification": needs_vlm_verification,
        "persistence_count": state["elevated_count"]
    }
