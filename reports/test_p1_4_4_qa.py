"""P1.4.4 Bonus Config Persistence QA — E2E Test Script"""
import sys, json, os

sys.path.insert(0, 'backend')
os.environ['ENVIRONMENT'] = 'dev'
os.environ['DB_USER'] = 'yego_user'
os.environ['DB_HOST'] = '168.119.226.236'
os.environ['DB_NAME'] = 'yego_integral'
os.environ['DB_PASSWORD'] = '37>MNA&-35+'
os.environ['DB_PORT'] = '5432'

from app.services.yego_pro_profitability_service import (
    get_bonus_config, save_bonus_config, reset_bonus_config_to_defaults,
    run_simulator, PARK_ID
)

results = {'pass': 0, 'fail': 0, 'checks': []}

def check(name, passed, detail=''):
    results['checks'].append({'check': name, 'passed': passed, 'detail': str(detail)[:200]})
    if passed:
        results['pass'] += 1
    else:
        results['fail'] += 1
    mark = 'PASS' if passed else 'FAIL'
    print(f'  [{mark}] {name}')

# ===================== FASE 2: GET before save =====================
print('=== FASE 2: GET bonus-config ===')
cfg = get_bonus_config()
check('status OK', cfg['status'] == 'OK', cfg.get('status'))
check('persisted=true', cfg['persisted'] is True)
check('general_branded 7 rows', len(cfg['tables']['general_branded']) == 7)
check('general_unbranded 7 rows', len(cfg['tables']['general_unbranded']) == 7)
check('premier 7 rows', len(cfg['tables']['premier']) == 7)
check('premier[4] amount=130 (default)', cfg['tables']['premier'][4]['amount'] == 130.0,
      f"got {cfg['tables']['premier'][4]['amount']}")
check('no null tables', all(t is not None for t in cfg['tables'].values()))
check('no NaN in response', 'NaN' not in json.dumps(cfg))

with open('reports/yego_pro_bonus_config_get_before.json', 'w') as f:
    json.dump(cfg, f, indent=2, default=str)

# ===================== FASE 3: POST save (modify premier tier) =====================
print('=== FASE 3: POST save ===')
old_updated = cfg.get('updated_at')
new_tables = {
    'general_branded': [{'trips_min': t['min_trips'], 'bonus_pct': t['pct'], 'bonus_amount': t['amount']} for t in cfg['tables']['general_branded']],
    'general_unbranded': [{'trips_min': t['min_trips'], 'bonus_pct': t['pct'], 'bonus_amount': t['amount']} for t in cfg['tables']['general_unbranded']],
    'premier': [
        {'trips_min': 20, 'bonus_pct': 40, 'bonus_amount': 600},
        {'trips_min': 15, 'bonus_pct': 36, 'bonus_amount': 410},
        {'trips_min': 10, 'bonus_pct': 33, 'bonus_amount': 250},
        {'trips_min': 8, 'bonus_pct': 31, 'bonus_amount': 190},
        {'trips_min': 6, 'bonus_pct': 29, 'bonus_amount': 131},
        {'trips_min': 4, 'bonus_pct': 27, 'bonus_amount': 85},
        {'trips_min': 2, 'bonus_pct': 25, 'bonus_amount': 40},
    ],
}

saved = save_bonus_config(PARK_ID, {'tables': new_tables})
check('save status OK', saved['status'] == 'OK', saved.get('status'))
check('persisted=true after save', saved['persisted'] is True)
check('premier[4] amount=131', saved['tables']['premier'][4]['amount'] == 131.0,
      f"got {saved['tables']['premier'][4]['amount']}")
check('updated_at changed', saved.get('updated_at') != old_updated,
      f"old={old_updated} new={saved.get('updated_at')}")
check('general_branded preserved', len(saved['tables']['general_branded']) == 7)

with open('reports/yego_pro_bonus_config_get_after_save.json', 'w') as f:
    json.dump(saved, f, indent=2, default=str)

# Read back
cfg2 = get_bonus_config()
check('re-read persisted=true', cfg2['persisted'] is True)
check('re-read premier[4]=131', cfg2['tables']['premier'][4]['amount'] == 131.0,
      f"got {cfg2['tables']['premier'][4]['amount']}")

# ===================== FASE 4: DB persistence =====================
print('=== FASE 4: DB persistence ===')
import psycopg2
conn = psycopg2.connect(
    host='168.119.226.236', dbname='yego_integral',
    user='yego_user', password='37>MNA&-35+', port=5432
)
cur = conn.cursor()
cur.execute(
    "SELECT bonus_type, trips_min, bonus_pct, bonus_amount, is_active, effective_from, effective_to, updated_at "
    "FROM ops.yego_pro_bonus_config WHERE park_id=%s "
    "ORDER BY is_active DESC, bonus_type, trips_min DESC",
    (PARK_ID,)
)
rows = cur.fetchall()
active_rows = [r for r in rows if r[4]]
inactive_rows = [r for r in rows if not r[4]]

check('has active rows', len(active_rows) >= 21, f"active={len(active_rows)}")
check('premier 6/131 active in DB',
      any(r[0] == 'premier' and r[1] == 6 and r[3] == 131 and r[4] for r in rows))
check('has inactive rows (old version preserved)', len(inactive_rows) >= 21,
      f"inactive={len(inactive_rows)}")
check('no duplicate active per type',
      all(sum(1 for r in active_rows if r[0] == bt) == 7
          for bt in ['general_branded', 'general_unbranded', 'premier']))

with open('reports/yego_pro_bonus_config_db_after_save.csv', 'w') as f:
    f.write('bonus_type,trips_min,bonus_pct,bonus_amount,is_active,effective_from,effective_to,updated_at\n')
    for r in rows:
        f.write(','.join(str(x) for x in r) + '\n')

cur.close()
conn.close()

# ===================== FASE 5: Simulation uses persisted config =====================
print('=== FASE 5: Simulation ===')
sim_payload = {
    'shifts_per_vehicle': 1,
    'selected_shift': 'day',
    'trips_day_week': 0,
    'trips_night_week': 0,
    'trips_premier_day_week': 6,
    'trips_premier_night_week': 0,
    'ticket_avg_general': 15,
    'ticket_avg_premier': 25,
    'general_bonus_trips_week': 0,
    'premier_bonus_trips_week': 6,
    'eligible_for_general_bonus': False,
    'eligible_for_premier_bonus': True,
    'vehicle_branded': True,
    'driver_payout_pct': 50,
}
sim_result = run_simulator(sim_payload)
check('sim premier bonus=131',
      sim_result['bonus_result']['premier']['bonus_amount'] == 131,
      f"got {sim_result['bonus_result']['premier']['bonus_amount']}")
check('sim total_income includes 131',
      sim_result['subtotals']['production']['premier_bonus'] == 131)
trace_premier = [t for t in sim_result.get('calculation_trace', [])
                 if 'premier' in str(t.get('label', '')).lower()]
check('trace has premier bonus entry', len(trace_premier) > 0)
check('trace premier result=131', any(t.get('result') == 131 for t in trace_premier))

with open('reports/yego_pro_bonus_config_simulation_persisted.json', 'w') as f:
    json.dump(sim_result, f, indent=2, default=str)

# ===================== FASE 7: Reset =====================
print('=== FASE 7: Reset ===')
reset_result = reset_bonus_config_to_defaults(PARK_ID)
check('reset status OK', reset_result['status'] == 'OK', reset_result.get('status'))
check('reset persisted=true', reset_result['persisted'] is True)

cfg3 = get_bonus_config()
check('after reset premier[4]=130', cfg3['tables']['premier'][4]['amount'] == 130.0,
      f"got {cfg3['tables']['premier'][4]['amount']}")
check('after reset persisted=true', cfg3['persisted'] is True)

with open('reports/yego_pro_bonus_config_after_reset.json', 'w') as f:
    json.dump(cfg3, f, indent=2, default=str)

# ===================== FASE 8: Validation =====================
print('=== FASE 8: Validation ===')

# invalid bonus_type
try:
    save_bonus_config(PARK_ID, {'tables': {'invalid_type': [{'trips_min': 10, 'bonus_pct': 5, 'bonus_amount': 100}]}})
    check('reject invalid bonus_type', False, 'No exception raised')
except (ValueError, RuntimeError) as e:
    check('reject invalid bonus_type', 'invalid' in str(e).lower() or 'Invalid' in str(e), str(e)[:100])

# negative bonus_amount
try:
    save_bonus_config(PARK_ID, {'tables': {'premier': [{'trips_min': 10, 'bonus_pct': 5, 'bonus_amount': -50}]}})
    check('reject negative bonus_amount', False, 'No exception raised')
except (ValueError, RuntimeError) as e:
    check('reject negative bonus_amount', True, str(e)[:100])

# negative bonus_pct
try:
    save_bonus_config(PARK_ID, {'tables': {'premier': [{'trips_min': 10, 'bonus_pct': -5, 'bonus_amount': 100}]}})
    check('reject negative bonus_pct', False, 'No exception raised')
except (ValueError, RuntimeError) as e:
    check('reject negative bonus_pct', True, str(e)[:100])

# zero trips_min
try:
    save_bonus_config(PARK_ID, {'tables': {'premier': [{'trips_min': 0, 'bonus_pct': 5, 'bonus_amount': 100}]}})
    check('reject zero trips_min', False, 'No exception raised')
except (ValueError, RuntimeError) as e:
    check('reject zero trips_min', True, str(e)[:100])

# negative trips_min
try:
    save_bonus_config(PARK_ID, {'tables': {'premier': [{'trips_min': -1, 'bonus_pct': 5, 'bonus_amount': 100}]}})
    check('reject negative trips_min', False, 'No exception raised')
except (ValueError, RuntimeError) as e:
    check('reject negative trips_min', True, str(e)[:100])

print()
print(f"TOTAL: {results['pass']} passed, {results['fail']} failed")

with open('reports/yego_pro_bonus_config_qa_results.json', 'w') as f:
    json.dump(results, f, indent=2)
