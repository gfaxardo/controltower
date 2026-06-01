import sys, json, os
sys.path.insert(0, 'backend')
os.environ['ENVIRONMENT'] = 'dev'
os.environ['DB_USER'] = 'yego_user'
os.environ['DB_HOST'] = '168.119.226.236'
os.environ['DB_NAME'] = 'yego_integral'
os.environ['DB_PASSWORD'] = '37>MNA&-35+'
os.environ['DB_PORT'] = '5432'

from app.services.yego_pro_profitability_service import run_simulator

p = {'shifts_per_vehicle': 1, 'selected_shift': 'day', 'trips_day_week': 85, 'trips_night_week': 0,
     'trips_premier_day_week': 6, 'trips_premier_night_week': 0, 'ticket_avg_general': 15,
     'ticket_avg_premier': 25, 'general_bonus_trips_week': 85, 'premier_bonus_trips_week': 6,
     'eligible_for_general_bonus': True, 'eligible_for_premier_bonus': True,
     'vehicle_branded': True, 'driver_payout_pct': 50}
r = run_simulator(p)

print("=== Tree ===")
def show(n, d=0):
    prefix = "  " * d
    v = n.get("value", 0)
    src = n.get("source", "?")
    sig = n.get("sign", "?")
    impact = n.get("impact_on_profit", 0)
    print(f"{prefix}{n.get('label')} = S/{v:,.2f} [{sig}] {src} impact={impact:,.2f}")
    for c in n.get("children", []):
        show(c, d + 1)
show(r.get("profitability_tree", {}))

print()
print("=== Math Summary ===")
for s in r.get("math_summary", []):
    print(f"{s['step']}. {s['title']} = S/{s['result']:,.2f}")

print()
print("=== Baseline Delta ===")
bd = r.get("baseline_delta")
print("exists:", bd is not None)
if bd:
    for k in ["profit_delta", "margin_delta", "cost_delta"]:
        d = bd.get(k, {})
        if d:
            print(f"  {d.get('label')}: base={d.get('baseline_value')} scenario={d.get('scenario_value')} delta={d.get('absolute')} ({d.get('direction')})")
print()
print("ALL OK")
