"""
monitor.py — Autonomous monitoring entry point.

Loops over vulnerable regions, fetches data, runs the toolkit,
computes risk, evaluates alerts, and triggers VLM verification if needed.
"""

import time
import numpy as np
from data_fetcher import fetch_latest_observations
from rs_toolkit import compute_change_mask
from risk_engine import calculate_risk_score
from alert_engine import evaluate_alert_state
from database import db
from prompts import build_prompt
from vlm_client import call_vlm

def run_monitoring_cycle(region_id: str):
    print(f"\n[{time.strftime('%H:%M:%S')}] --- Starting Monitoring Cycle for {region_id} ---")
    
    # 1. Fetch Data
    obs = fetch_latest_observations(region_id)
    
    # 2. Remote Sensing Preprocessing
    state = db.get_region_state(region_id)
    baseline_img = state.get("baseline_optical")
    
    toolkit_output = None
    if baseline_img is not None:
        # Compare new image against baseline
        arr1 = np.array(baseline_img)
        arr2 = np.array(obs["optical_image"])
        toolkit_output = compute_change_mask(arr1, arr2)
    else:
        # Initialize baseline
        db.update_region_state(region_id, {"baseline_optical": obs["optical_image"]})
        print("  -> Baseline image set. Will compute change on next cycle.")
        
    # 3. Risk Engine
    risk_result = calculate_risk_score(obs, toolkit_output)
    print(f"  -> Risk Score: {risk_result['risk_score']} | Evidence: {risk_result['evidence']}")
    
    # 4. Alert Engine (Persistence logic)
    alert_decision = evaluate_alert_state(region_id, risk_result)
    print(f"  -> Alert State: {alert_decision['previous_level']} -> {alert_decision['new_level']} (Persistence: {alert_decision['persistence_count']})")
    
    # 5. VLM Verification (if elevated)
    if alert_decision["needs_vlm_verification"]:
        print("  -> [!] Elevated risk detected. Triggering VLM Verification...")
        # Build prompt
        prompt = (
            "You are GEORE Autonomous Monitor. The numerical risk engine has flagged an "
            f"elevated {alert_decision['new_level']} risk of natural disaster (e.g. landslide or flood). "
            f"Risk Score: {alert_decision['risk_score']}\n"
            f"Evidence: {', '.join(alert_decision['evidence'])}\n\n"
            "Please visually verify the provided satellite images. Do you see evidence "
            "of impending or active disaster? Provide a concise verification."
        )
        
        images = [obs["optical_image"]]
        if baseline_img:
            images.insert(0, baseline_img) # Put baseline first
            
        answer, provider = call_vlm(prompt, images)
        print(f"  -> VLM Verification ({provider}): {answer}")
        
    print("--- Cycle Complete ---\n")

def start_scheduler():
    """Simulate a continuous monitoring loop for a hackathon demo."""
    regions = ["NP-KTM-01"] # Nepal vulnerable region ID
    
    print("Starting GEORE Autonomous Monitoring Prototype...")
    print("(Simulating time-lapse data fetching)")
    
    for i in range(5):
        for region in regions:
            run_monitoring_cycle(region)
        # Sleep short time to simulate delay
        time.sleep(2)

if __name__ == "__main__":
    start_scheduler()
