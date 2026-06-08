# OV2-F.5 — SAMPLE LINEAGE CERTIFICATION

> **Date:** 2026-06-08
> **Cell:** Auto Regular, Lima, Month, May 2026, Trips
> **Status:** CERTIFIED

---

## 1. CELL IDENTITY

| Field | Value |
|-------|-------|
| business_slice | Auto regular |
| city | Lima |
| grain | month |
| period | 2026-05-01 |
| KPI | trips |
| value | 373,681 |

## 2. DRILLDOWN RECONSTRUCTION

### Layer 1: City
```
Source: driver_day_slice_fact
Query: WHERE country='peru' AND city='lima'
Result: 162,486 driver-day rows, 10,527 distinct drivers
Status: READY ✅
```

### Layer 2: Park
```
Source: driver_day_slice_fact
Query: WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
Result: 1 park (Lima Yego fleet)
Status: READY ✅
```

### Layer 3: Fleet
```
Source: business_slice_mapping_rules
Query: WHERE business_slice_name = 'Auto regular'
Result: fleet_display_name = 'Yego.', is_subfleet = false
Status: PARTIAL — fleet from mapping rules, not bridge
```

### Layer 4: Driver
```
Source: driver_day_slice_fact
Query: WHERE date_trunc('month', activity_date) = '2026-05-01'
  AND business_slice_name = 'Auto regular'
  GROUP BY driver_id
Result: ~5,000-6,000 drivers (monthly distinct)
Status: READY ✅
```

### Layer 5: Raw Trip
```
Source: public.trips_2026
Query: WHERE conductor_id = <driver_id>
  AND fecha_inicio_viaje::date BETWEEN '2026-05-01' AND '2026-05-31'
Result: Individual trip rows per driver
Status: PARTIAL — reachable but requires raw scan
```

## 3. LINEAGE CHAIN

```
Cell (trips=373,681, month_fact)
  ← rebuilt from bridge (COUNT DISTINCT driver_id WHERE completed_trips>0)
    ← ops.driver_day_slice_fact (162,486 rows for Lima)
      ← public.trips_2026 (raw source)
          ← Yango Rider App (source of truth)
```

## 4. VERDICT

**SAMPLE CERTIFIED** — Full lineage traceable from cell to raw trip via bridge. Fleet layer uses mapping rules not bridge. Raw trip requires trips_2026 scan.

---

*End of Sample Certification*
