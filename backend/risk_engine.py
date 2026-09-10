"""
risk_engine.py — Multi-source risk calculation engine.

Combines telemetry (rainfall, soil moisture) with historical susceptibility
and optical/SAR changes to produce a deterministic risk score.
"""

from typing import Dict, Any

def calculate_risk_score(observation: Dict[str, Any], toolkit_output: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Calculate a numerical risk score (0 to 100) based on multiple evidence sources.
    
    Args:
        observation: The latest data from data_fetcher.
        toolkit_output: Analysis from rs_toolkit (like pct_changed), if available.
        
    Returns:
        Dict containing the risk score and contributing factors.
    """
    score = 0.0
    evidence = []
    
    # 1. Rainfall factor (e.g. > 50mm adds risk)
    rain = observation.get("rainfall_mm_24h", 0)
    if rain > 100:
        score += 35
        evidence.append(f"Extreme rainfall ({rain:.1f}mm)")
    elif rain > 50:
        score += 15
        evidence.append(f"Heavy rainfall ({rain:.1f}mm)")
        
    # 2. Soil Moisture (saturation increases landslide risk)
    soil = observation.get("soil_moisture_pct", 0)
    if soil > 85:
        score += 25
        evidence.append(f"Critical soil saturation ({soil:.1f}%)")
    elif soil > 70:
        score += 10
        evidence.append(f"High soil moisture ({soil:.1f}%)")
        
    # 3. Slope & Susceptibility
    slope = observation.get("avg_slope_degrees", 0)
    susceptibility = observation.get("historical_susceptibility", 0)
    if slope > 30 and susceptibility > 0.7:
        score += 15
        evidence.append("Historically highly susceptible steep terrain")
        
    # 4. Remote Sensing Evidence (Change Detection)
    if toolkit_output:
        pct_changed = toolkit_output.get("pct_changed", 0)
        if pct_changed > 15:
            score += 25
            evidence.append(f"Significant visual surface change ({pct_changed}%)")
        elif pct_changed > 5:
            score += 10
            evidence.append(f"Moderate visual surface change ({pct_changed}%)")
            
    # Cap score at 100
    score = min(100.0, score)
    
    return {
        "risk_score": score,
        "evidence": evidence
    }
