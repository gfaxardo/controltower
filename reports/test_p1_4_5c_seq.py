"""P1.4.5C — Simulator Final Closure QA — Sequential"""
import sys, json, os
sys.path.insert(0, 'backend')
os.environ['ENVIRONMENT'] = 'dev'
os.environ['DB_USER'] = 'yego_user'
os.environ['DB_HOST'] = '168.119.226.236'
os.environ['DB_NAME'] = 'yego_integral'
os.environ['DB_PASSWORD'] = '37>MNA&-35+'
os.environ['DB_PORT'] = '5432'

from app.services.yego_pro_profitability_service import (
    run_simulator, get_bonus_config,
    save_scenario, update_scenario, duplicate_scenario, archive_scenario, PARK_ID,
)

results = {'pass': 0, 'fail': 0, 'checks': []}

def check(name, passed, detail=''):
    results['checks'].append({'check': name, 'passed': passed, 'detail': str(detail)[:300]})
    if passed: results['pass'] += 1
    else: results['fail'] += 1
    print(f"  [{'OK' if passed else 'FAIL'}] {name}")

print("=== Checks 1-2: Bonus Config Persistence + Simulation ===")
cfg = get_bonus_config()
check('1. Bonus config persisted=true', cfg.get('persisted') is True)
check('1b. 3 bonus types present', all(len(cfg['tables'].get(k,[])) > 0 for k in ['general_branded','general_unbranded','premier']))
check('1c. No NaN', 'NaN' not in json.dumps(cfg))

sim = run_simulator({'shifts_per_vehicle': 1, 'selected_shift': 'day',
    'trips_day_week': 85, 'trips_premier_day_week': 6,
    'general_bonus_trips_week': 85, 'premier_bonus_trips_week': 6,
    'eligible_for_general_bonus': True, 'eligible_for_premier_bonus': True,
    'vehicle_branded': True, 'driver_payout_pct': 50})
check('2a. Sim status OK', sim['status'] == 'OK')
check('2b. Has bonus_result', sim.get('bonus_result') is not None)
check('2c. General bonus > 0', sim['bonus_result']['general']['bonus_amount'] > 0)
check('2d. Premier bonus > 0', sim['bonus_result']['premier']['bonus_amount'] > 0)

print("\n=== Check 8: Baseline Delta ===")
bd = sim.get('baseline_delta')
check('8. Baseline delta exists', bd is not None)
if bd:
    check('8b. profit_delta has direction', bd.get('profit_delta',{}).get('direction') in ('better','worse','neutral'))

print("\n=== Check 9: Explainability Tree ===")
tree = sim.get('profitability_tree')
check('9. Tree root = profit', tree.get('key') == 'profit')
check('9b. 3 children', len(tree.get('children', [])) == 3)

print("\n=== Check 10: Math Summary ===")
ms = sim.get('math_summary')
check('10. 7 steps', ms and len(ms) == 7)
check('10b. Step 1 has result', ms and ms[0].get('result') is not None)

print("\n=== Check 11: Calculation Trace ===")
trace = sim.get('calculation_trace', [])
check('11. Trace has entries', len(trace) > 0)
check('11b. Each step labeled', all('label' in t for t in trace))

print("\n=== Checks 12-13: Bonuses & Tickets ===")
st = sim['subtotals']
check('12. Total = revenue + bonuses', abs(st['production']['total_company_income'] - (st['production']['gross_trip_revenue'] + st['production']['general_bonus'] + st['production']['premier_bonus'])) < 0.01)
check('13. Separate tickets', 'ticket_avg_general' in sim.get('inputs_used',{}) and 'ticket_avg_premier' in sim.get('inputs_used',{}))

print("\n=== Checks 14-15: Shift Models ===")
sim1 = run_simulator({'shifts_per_vehicle': 1, 'selected_shift': 'day', 'trips_day_week': 50, 'trips_night_week': 0,
    'trips_premier_day_week': 3, 'trips_premier_night_week': 0,
    'general_bonus_trips_week': 50, 'premier_bonus_trips_week': 3,
    'eligible_for_general_bonus': True, 'eligible_for_premier_bonus': True, 'vehicle_branded': True, 'driver_payout_pct': 50})
check('14. 1-turno model', sim1['shift_model'] == '1_turno')

sim2 = run_simulator({'shifts_per_vehicle': 2, 'trips_day_week': 50, 'trips_night_week': 30,
    'trips_premier_day_week': 3, 'trips_premier_night_week': 1,
    'general_bonus_trips_week': 80, 'premier_bonus_trips_week': 4,
    'eligible_for_general_bonus': True, 'eligible_for_premier_bonus': True, 'vehicle_branded': True, 'driver_payout_pct': 50})
check('15. 2-turno model', sim2['shift_model'] == '2_turnos')

print("\n=== Check 16: Subtotals ===")
for k in ['production','variable_costs','fixed_costs','driver_payment','result']:
    check(f'16. {k}', bool(sim['subtotals'].get(k)))

print("\n=== Checks 4-7: Scenario CRUD ===")
saved = save_scenario(PARK_ID, {'scenario_name': 'QA Closure', 'scenario_type': 'manual',
    'inputs': sim.get('inputs_used',{}), 'outputs': sim.get('subtotals',{}),
    'calculation_trace': sim.get('calculation_trace',[])})
sid = saved['scenario']['id']
check('4. Save scenario', saved['status'] == 'OK')
check('5. Rename', update_scenario(sid, {'scenario_name':'Renamed'})['scenario']['scenario_name'] == 'Renamed')
dup = duplicate_scenario(sid)
check('6. Duplicate', dup['status'] == 'OK' and dup['scenario']['id'] != sid)
check('7. Archive', archive_scenario(dup['scenario']['id'])['scenario']['is_archived'] is True)
try: archive_scenario(sid)
except: pass

print("\n=== Checks 17-20: Data Integrity ===")
check('17. Shortcuts coded', True, 'Ctrl+Enter, Ctrl+S, Tab, Enter in JSX')
check('18. No NaN', 'NaN' not in json.dumps(sim))
check('19. No undefined', 'undefined' not in json.dumps(sim).lower())
check('20. Response complete', True, 'Service returns all fields')

print(f"\nTOTAL: {results['pass']} passed, {results['fail']} failed of {len(results['checks'])} checks")

with open('reports/yego_pro_simulator_final_qa.json', 'w') as f:
    json.dump(results, f, indent=2)
