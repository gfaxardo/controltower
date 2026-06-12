# LG-EXP-1A — EXPORT CONTRACT

**Date:** 2026-06-12

---

## REQUEST

```json
POST /yego-lima-growth/export
{
  "source": "driver_explorer",
  "filters": {
    "program": "PROGRAM_ACTIVE_GROWTH",
    "lifecycle": "ACTIVE",
    "segment": null,
    "rna": false,
    "search": null,
    "max_rows": 10000
  },
  "columns": ["driver_id", "lifecycle", "segment", "program", "movement_status"],
  "requested_by": "operator_name",
  "export_reason": "Weekly review"
}
```

## RESPONSE

```json
{
  "export_id": "LG-EXP-A1B2C3D4",
  "status": "COMPLETED",
  "source": "driver_explorer",
  "columns": ["driver_id", "lifecycle", "segment", "program", "movement_status"],
  "rows_count": 5383,
  "generated_at": "2026-06-12T10:00:00Z",
  "warnings": [],
  "file_size_bytes": 245760,
  "csv_preview": "driver_id,lifecycle,segment,program,movement_status\n..."
}
```

## STATUS

```json
GET /yego-lima-growth/export/LG-EXP-A1B2C3D4
{
  "export_id": "LG-EXP-A1B2C3D4",
  "source": "driver_explorer",
  "rows_count": 5383,
  "generated_at": "2026-06-12T10:00:00Z",
  "status": "COMPLETED",
  "warnings": [],
  "file_size_bytes": 245760
}
```

## DOWNLOAD

`GET /yego-lima-growth/export/{export_id}/download`

Returns CSV file or status text.
