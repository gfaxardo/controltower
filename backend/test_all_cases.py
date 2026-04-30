import requests
import json

url = 'http://localhost:8002/diagnostics/join-keys'

# Todos los casos obligatorios
casos = [
    ("1. Peru/Lima/Delivery/monthly/2026", {"grain": "monthly", "plan_version": "ruta27_v2026_01_17", "country": "peru", "city": "lima", "business_slice": "delivery", "year": 2026, "month": 1}),
    ("2. Peru/Trujillo/Delivery/monthly/2026", {"grain": "monthly", "plan_version": "ruta27_v2026_01_17", "country": "peru", "city": "trujillo", "business_slice": "delivery", "year": 2026, "month": 1}),
    ("3. Peru/Lima/Delivery/weekly/2026", {"grain": "weekly", "plan_version": "ruta27_v2026_01_17", "country": "peru", "city": "lima", "business_slice": "delivery", "year": 2026, "month": 1}),
    ("4. Peru/Lima/Delivery/daily/2026", {"grain": "daily", "plan_version": "ruta27_v2026_01_17", "country": "peru", "city": "lima", "business_slice": "delivery", "year": 2026, "month": 1}),
    ("5. Colombia/Delivery/monthly/2026", {"grain": "monthly", "plan_version": "ruta27_v2026_01_17", "country": "colombia", "business_slice": "delivery", "year": 2026, "month": 1}),
    ("6. Colombia/Delivery/weekly/2026", {"grain": "weekly", "plan_version": "ruta27_v2026_01_17", "country": "colombia", "business_slice": "delivery", "year": 2026, "month": 1}),
]

resultados = []
for nombre, params in casos:
    try:
        r = requests.get(url, params=params, timeout=90)
        data = r.json()

        # Validar filtro business_slice
        plan_samples = data.get('plan_only_sample', [])
        real_samples = data.get('real_only_sample', [])

        plan_bsns = {k[3] for k in plan_samples if len(k) >= 4}
        real_bsns = {k[3] for k in real_samples if len(k) >= 4}

        filter_ok = (plan_bsns == {'delivery'} or len(plan_bsns) == 0) and (real_bsns == {'delivery'} or len(real_bsns) == 0)

        resultados.append({
            "caso": nombre,
            "plan_keys": data.get('plan_keys'),
            "real_keys": data.get('real_keys'),
            "intersection": data.get('intersection'),
            "plan_only": data.get('plan_only'),
            "real_only": data.get('real_only'),
            "rate": data.get('intersection_rate_pct'),
            "plan_bsns": plan_bsns,
            "real_bsns": real_bsns,
            "filter_ok": filter_ok,
        })
    except Exception as e:
        resultados.append({"caso": nombre, "error": str(e)})

# TABLA FINAL
print("=" * 100)
print("TABLA FINAL - JOIN TEMPORAL PLAN VS REAL")
print("=" * 100)
print("\n| Caso | Plan | Real | Intersection | Plan Only | Real Only | Rate | Status |")
print("|---|---:|---:|---:|---:|---:|---:|:---|")

for r in resultados:
    if 'error' in r:
        print(f"| {r['caso']} | ERROR | - | - | - | - | - | FAIL |")
    else:
        rate = r['rate']
        status = "GO" if rate >= 92 else ("GO PARCIAL" if rate >= 85 else "NO-GO")
        print(f"| {r['caso']} | {r['plan_keys']} | {r['real_keys']} | {r['intersection']} | {r['plan_only']} | {r['real_only']} | {rate}% | {status} |")

# TOP 5 PLAN_ONLY y REAL_ONLY
print("\n" + "=" * 100)
print("TOP 5 PLAN_ONLY:")
print("=" * 100)
for r in resultados:
    if 'error' not in r and r['plan_only'] > 0:
        print(f"\n{r['caso']}: {r['plan_bsns']}")

print("\n" + "=" * 100)
print("TOP 5 REAL_ONLY:")
print("=" * 100)
for r in resultados:
    if 'error' not in r and r['real_only'] > 0:
        print(f"\n{r['caso']}: {r['real_bsns']}")

# GO/NO-GO FINAL
print("\n" + "=" * 100)
print("GO / NO-GO:")
print("=" * 100)
go_count = sum(1 for r in resultados if 'error' not in r and r['rate'] >= 92)
go_partial = sum(1 for r in resultados if 'error' not in r and 85 <= r['rate'] < 92)
no_go = sum(1 for r in resultados if 'error' not in r and r['rate'] < 85)
errors = sum(1 for r in resultados if 'error' in r)

print(f"\nGO COMPLETO (>=92%): {go_count} casos")
print(f"GO PARCIAL (85-92%): {go_partial} casos")
print(f"NO-GO (<85%): {no_go} casos")
print(f"ERRORES: {errors} casos")

if go_count >= 4 and no_go <= 1:
    print("\n=> DECISION: GO (Mayoria de casos cumplen threshold)")
elif no_go >= 3:
    print("\n=> DECISION: NO-GO (Mayoria de casos por debajo del threshold)")
else:
    print("\n=> DECISION: REVISION PARCIAL (Resultados mixtos)")
