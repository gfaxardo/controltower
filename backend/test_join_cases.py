import requests
import json

url = 'http://localhost:8002/diagnostics/join-keys'

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
        resultados.append({
            "caso": nombre,
            "status": data.get("status"),
            "plan_keys": data.get("plan_keys"),
            "real_keys": data.get("real_keys"),
            "intersection": data.get("intersection"),
            "plan_only": data.get("plan_only"),
            "real_only": data.get("real_only"),
            "intersection_rate_pct": data.get("intersection_rate_pct"),
            "go_threshold_85": data.get("go_threshold_85"),
            "go_threshold_92": data.get("go_threshold_92"),
            "by_cause": data.get("by_cause"),
        })
    except Exception as e:
        resultados.append({"caso": nombre, "error": str(e)})

print("=" * 80)
print("RESULTADOS JOIN DIAGNOSTICS - CASOS FASE E2E")
print("=" * 80)
for r in resultados:
    print(f"\n{r['caso']}")
    print(f"  status: {r.get('status')}")
    print(f"  plan_keys: {r.get('plan_keys')}, real_keys: {r.get('real_keys')}, intersection: {r.get('intersection')}")
    print(f"  plan_only: {r.get('plan_only')}, real_only: {r.get('real_only')}")
    print(f"  intersection_rate_pct: {r.get('intersection_rate_pct')}%")
    print(f"  go_threshold_85: {r.get('go_threshold_85')}, go_threshold_92: {r.get('go_threshold_92')}")
    print(f"  by_cause: {r.get('by_cause')}")

# Guardar JSON
with open("C:/Users/Pc/Documents/Cursor Proyectos/YEGO CONTROL TOWER/backend/join_diagnostics.json", "w") as f:
    json.dump(resultados, f, indent=2)
print("\n\nJSON guardado en join_diagnostics.json")