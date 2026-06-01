import sys, json, os
sys.path.insert(0, 'backend')
os.environ['ENVIRONMENT'] = 'dev'
os.environ['DB_USER'] = 'yego_user'
os.environ['DB_HOST'] = '168.119.226.236'
os.environ['DB_NAME'] = 'yego_integral'
os.environ['DB_PASSWORD'] = '37>MNA&-35+'
os.environ['DB_PORT'] = '5432'

from app.services.yego_pro_profitability_service import run_simulator

# Test with a loss scenario
p = {'shifts_per_vehicle': 1, 'selected_shift': 'day', 'trips_day_week': 30, 'trips_night_week': 0,
     'trips_premier_day_week': 2, 'trips_premier_night_week': 0,
     'ticket_avg_general': 12, 'ticket_avg_premier': 18,
     'general_bonus_trips_week': 30, 'premier_bonus_trips_week': 2,
     'eligible_for_general_bonus': True, 'eligible_for_premier_bonus': True,
     'vehicle_branded': True, 'driver_payout_pct': 55,
     'fuel_per_km': 0.4, 'maintenance_per_trip': 1.5, 'insurance_gps_weekly': 50,
     'vehicle_weekly_cost': 400}
r = run_simulator(p)

ga = r.get('gap_analysis', {})
print("=== GAP ANALYSIS ===")
print(f"Status: {ga.get('break_even_status')}")
print(f"Current profit: S/{ga.get('current_profit_week')}/wk")
print(f"Gap to break-even: S/{ga.get('gap_week')}/wk")
print(f"Levers: {len(ga.get('levers',[]))}")
for l in ga.get('levers', []):
    print(f"  {l['key']}: current={l['current_value']} needed={l['required_value']} delta={l['delta_abs']} feasible={l['feasibility_hint']}")

print()
print("=== LEVER RANKING ===")
for rk in r.get('lever_ranking', []):
    print(f"  {rk['lever']}: S/{rk['impact_week']}/wk [{rk['confidence']}]")

print()
print("=== COMBINATIONS ===")
for c in r.get('break_even_combinations', []):
    print(f"  {c['name']}: projected=S/{c['projected_profit_week']}/wk closes={c['closes_gap']}")

# Test profitable scenario too
print()
p2 = {'shifts_per_vehicle': 1, 'selected_shift': 'day', 'trips_day_week': 150, 'trips_night_week': 0,
      'trips_premier_day_week': 20, 'trips_premier_night_week': 0,
      'ticket_avg_general': 18, 'ticket_avg_premier': 28,
      'general_bonus_trips_week': 150, 'premier_bonus_trips_week': 20,
      'eligible_for_general_bonus': True, 'eligible_for_premier_bonus': True,
      'vehicle_branded': True, 'driver_payout_pct': 40}
r2 = run_simulator(p2)
ga2 = r2.get('gap_analysis', {})
print(f"=== PROFITABLE SCENARIO ===")
print(f"Status: {ga2.get('break_even_status')}")
print(f"Gap: S/{ga2.get('gap_week')}/wk")
print(f"Trips needed: {ga2['levers'][0]['delta_abs']}")
print()
print("ALL OK")
