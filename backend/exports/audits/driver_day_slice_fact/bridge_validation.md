# Driver Day Slice Bridge Validation
**2026-06-08T03:34:50.972910+00:00**

| Check | Status | Details |
|-------|--------|---------|
| duplicates | PASS | {'value': 0} |
| trips vs day_fact | PASS | {'bridge_trips': 1001200, 'day_trips': Decimal('996863'), 'delta_pct': Decimal('0.44')} |
| drivers vs day_fact | PASS | {'diffs': []} |
| empty_supply | INFO | {'empty_drivers': 7874, 'empty_rows': 37842} |