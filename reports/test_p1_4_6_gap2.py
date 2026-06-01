import sys, json, os
sys.path.insert(0, 'backend')
os.environ['ENVIRONMENT'] = 'dev'
os.environ['DB_USER'] = 'yego_user'
os.environ['DB_HOST'] = '168.119.226.236'
os.environ['DB_NAME'] = 'yego_integral'
os.environ['DB_PASSWORD'] = '37>MNA&-35+'
os.environ['DB_PORT'] = '5432'

from app.services.yego_pro_profitability_service import run_simulator

bt = {
    "general_branded": [{"min_trips": 190, "pct": 27, "amount": 720},
        {"min_trips": 150, "pct": 25, "amount": 550}, {"min_trips": 125, "pct": 23, "amount": 470},
        {"min_trips": 100, "pct": 21, "amount": 390}, {"min_trips": 75, "pct": 20, "amount": 320},
        {"min_trips": 50, "pct": 19, "amount": 260}, {"min_trips": 30, "pct": 18, "amount": 175}],
    "general_unbranded": [{"min_trips": 150, "pct": 20, "amount": 450},
        {"min_trips": 125, "pct": 18, "amount": 390}, {"min_trips": 100, "pct": 16, "amount": 315},
        {"min_trips": 75, "pct": 14, "amount": 230}, {"min_trips": 50, "pct": 13, "amount": 170},
        {"min_trips": 30, "pct": 12, "amount": 125}, {"min_trips": 10, "pct": 11, "amount": 60}],
    "premier": [{"min_trips": 20, "pct": 40, "amount": 600}, {"min_trips": 15, "pct": 36, "amount": 410},
        {"min_trips": 10, "pct": 33, "amount": 250}, {"min_trips": 8, "pct": 31, "amount": 190},
        {"min_trips": 6, "pct": 29, "amount": 130}, {"min_trips": 4, "pct": 27, "amount": 85},
        {"min_trips": 2, "pct": 25, "amount": 40}],
}

# LOSS scenario
p = {'shifts_per_vehicle': 1, 'selected_shift': 'day', 'trips_day_week': 30, 'trips_night_week': 0,
     'trips_premier_day_week': 2, 'trips_premier_night_week': 0,
     'ticket_avg_general': 12, 'ticket_avg_premier': 18,
     'general_bonus_trips_week': 30, 'premier_bonus_trips_week': 2,
     'eligible_for_general_bonus': True, 'eligible_for_premier_bonus': True,
     'vehicle_branded': True, 'driver_payout_pct': 55,
     'fuel_per_km': 0.4, 'maintenance_per_trip': 1.5, 'insurance_gps_weekly': 50,
     'vehicle_weekly_cost': 400,
     'bonus_tables': bt}
r = run_simulator(p)

ga = r.get('gap_analysis', {})
assert ga, "gap_analysis missing"
print(f"GAP ANALYSIS: status={ga['break_even_status']} profit=S/{ga['current_profit_week']}/wk gap=S/{ga['gap_week']}/wk")
assert len(ga['levers']) >= 6, f"expected 6+ levers, got {len(ga['levers'])}"
for l in ga['levers']:
    assert 'key' in l and 'explanation' in l and 'feasibility_hint' in l
    print(f"  [OK] {l['key']}: delta={l['delta_abs']} feasible={l['feasibility_hint']}")

lr = r.get('lever_ranking', [])
assert len(lr) >= 8, f"expected 8+ ranking entries, got {len(lr)}"
print(f"LEVER RANKING: {len(lr)} entries")
for rk in lr[:3]:
    print(f"  [OK] {rk['lever']}: S/{rk['impact_week']}/wk")

combos = r.get('break_even_combinations', [])
assert len(combos) == 6, f"expected 6 combos, got {len(combos)}"
print(f"COMBINATIONS: {len(combos)} combos")
for c in combos:
    print(f"  [OK] {c['name']}: proj=S/{c['projected_profit_week']}/wk closes={c['closes_gap']}")

# PROFITABLE scenario  
p2 = {'shifts_per_vehicle': 1, 'trips_day_week': 150, 'premier_bonus_trips_week': 20,
      'ticket_avg_general': 18, 'ticket_avg_premier': 28, 'driver_payout_pct': 40,
      'eligible_for_general_bonus': True, 'eligible_for_premier_bonus': True,
      'general_bonus_trips_week': 150, 'vehicle_branded': True,
      'bonus_tables': bt}
r2 = run_simulator(p2)
ga2 = r2.get('gap_analysis', {})
assert ga2['break_even_status'] == 'Rentable', f"expected Rentable, got {ga2['break_even_status']}"
print(f"PROFITABLE: status={ga2['break_even_status']} gap={ga2['gap_week']}")

# Verify no NaN
for obj in [r, r2]:
    j = json.dumps(obj)
    assert 'NaN' not in j, "NaN found!"
    assert 'undefined' not in j.lower(), "undefined found!"

print("\nALL GAP ANALYSIS CHECKS PASSED")
