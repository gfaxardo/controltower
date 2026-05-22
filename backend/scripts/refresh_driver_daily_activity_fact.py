"""
Fase 2A.1.1 — Driver Daily Activity Fact Refresh

Crea y refresca ops.driver_daily_activity_fact desde trips_2025 + trips_2026.
Grano: driver_id + activity_date.

Modos:
  --days N     : poblar ultimos N dias (default 90, rapido)
  --full       : poblar todo el historico (trips_2025 + trips_2026 completo)
  --backfill-from YYYY-MM-DD : poblar desde fecha especifica

Uso:
  cd backend && python scripts/refresh_driver_daily_activity_fact.py --days 90
  cd backend && python scripts/refresh_driver_daily_activity_fact.py --full
"""
import sys, os, time, logging, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from app.db.connection import init_db_pool, _get_connection_params
init_db_pool()
import psycopg2

FACT_TABLE = "ops.driver_daily_activity_fact"

FACT_DDL = f"""
CREATE TABLE IF NOT EXISTS {FACT_TABLE} (
    driver_id        varchar(100) NOT NULL,
    activity_date    date NOT NULL,
    country          text,
    city             text,
    park_id          varchar(100),
    completed_trips  integer NOT NULL DEFAULT 0,
    source_year      smallint NOT NULL,
    last_refreshed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (driver_id, activity_date)
)
"""

INDEXES = [
    ("ix_dda_activity_date", "activity_date"),
    ("ix_dda_driver_id", "driver_id"),
    ("ix_dda_country_city", "country, city"),
    ("ix_dda_country_city_date", "country, city, activity_date"),
    ("ix_dda_date_driver", "activity_date, driver_id"),
]


def _populate_range(cur, from_date_sql: str, desc: str):
    """Populate fact table from both tables for a date range."""
    t0 = time.time()
    logger.info("Populating: %s...", desc)

    # Delete existing rows in range then insert
    delete_sql = f"DELETE FROM {FACT_TABLE} WHERE activity_date >= {from_date_sql}"
    cur.execute(delete_sql)
    logger.info("  Deleted %s existing rows", cur.rowcount)

    for year, table in [(2025, "public.trips_2025"), (2026, "public.trips_2026")]:
        insert_sql = f"""
        INSERT INTO {FACT_TABLE} (driver_id, activity_date, country, city, park_id, completed_trips, source_year, last_refreshed_at)
        SELECT
            t.conductor_id,
            t.fecha_finalizacion::date,
            COALESCE(MIN(p.country), 'unknown'),
            COALESCE(MIN(p.city), 'unknown'),
            MIN(t.park_id),
            COUNT(*),
            {year},
            now()
        FROM {table} t
        LEFT JOIN dim.dim_park p ON t.park_id = p.park_id
        WHERE t.condicion = 'Completado'
          AND t.fecha_finalizacion IS NOT NULL
          AND t.fecha_finalizacion::date >= {from_date_sql}
        GROUP BY t.conductor_id, t.fecha_finalizacion::date
        ON CONFLICT (driver_id, activity_date) DO UPDATE SET
            completed_trips = {FACT_TABLE}.completed_trips + EXCLUDED.completed_trips,
            last_refreshed_at = now()
        """
        cur.execute(insert_sql)
        logger.info("  %s: %s rows inserted/updated in %.1fs", table, cur.rowcount, time.time() - t0)

    logger.info("  Range done in %.1fs", time.time() - t0)


def main():
    parser = argparse.ArgumentParser(description="Driver Daily Activity Fact Refresh")
    parser.add_argument("--days", type=int, default=None, help="Populate last N days (fast)")
    parser.add_argument("--full", action="store_true", help="Populate full history (2025+)")
    parser.add_argument("--backfill-from", type=str, default=None, help="Populate from date YYYY-MM-DD")
    parser.add_argument("--skip-full", action="store_true", help="Skip full population")
    args = parser.parse_args()

    logger.info("=== DRIVER DAILY ACTIVITY FACT REFRESH ===")
    t_start = time.time()

    conn = psycopg2.connect(**_get_connection_params())
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute("SET statement_timeout = '1800000'")  # 30 min
        cur.execute("SET work_mem = '512MB'")

        # 1. Create table
        logger.info("Step 1: Ensuring table...")
        cur.execute(FACT_DDL)
        logger.info("  Table exists.")

        # 2. Create indexes (IF NOT EXISTS safe)
        logger.info("Step 2: Ensuring indexes...")
        for idx_name, cols in INDEXES:
            sql = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {FACT_TABLE} ({cols})"
            cur.execute(sql)
            logger.info("  %s", idx_name)

        # 3. Populate
        if args.full:
            logger.info("Step 3: FULL population from trips_2025 + trips_2026...")
            cur.execute(f"TRUNCATE TABLE {FACT_TABLE}")
            _populate_range(cur, "'2025-01-01'", "Full history (2025+)")
        elif args.backfill_from:
            from_expr = f"'{args.backfill_from}'"
            _populate_range(cur, from_expr, f"From {args.backfill_from}")
        elif args.days:
            from_expr = f"CURRENT_DATE - {int(args.days)}"
            _populate_range(cur, from_expr, f"Last {args.days} days")
        elif args.skip_full:
            logger.info("Step 3: Skipping population (--skip-full).")
        else:
            # Default: last 90 days
            _populate_range(cur, "CURRENT_DATE - 90", "Last 90 days (default)")

        # 4. Validate
        logger.info("Step 4: Validation...")
        cur.execute(f"""
            SELECT COUNT(*) AS c, COUNT(DISTINCT driver_id) AS d,
                   MIN(activity_date) AS mn, MAX(activity_date) AS mx
            FROM {FACT_TABLE}
        """)
        total, drivers, min_date, max_date = cur.fetchone()
        logger.info("  Total rows: %s", f"{total:,}" if total else "0")
        logger.info("  Distinct drivers: %s", f"{drivers:,}" if drivers else "0")
        logger.info("  Date range: %s to %s", min_date, max_date)

        cur.execute(f"SELECT source_year, COUNT(*) AS c FROM {FACT_TABLE} GROUP BY source_year ORDER BY source_year")
        for r in cur.fetchall():
            logger.info("  Year %s: %s rows", r[0], f"{r[1]:,}" if r[1] else "0")

        # Quality checks
        cur.execute(f"SELECT COUNT(*) AS c FROM {FACT_TABLE} WHERE completed_trips <= 0")
        zero_neg = cur.fetchone()[0]
        if zero_neg:
            logger.warning("  WARNING: %s rows with completed_trips <= 0", zero_neg)

        cur.execute(f"SELECT COUNT(*) AS c FROM {FACT_TABLE} WHERE activity_date > CURRENT_DATE")
        future = cur.fetchone()[0]
        if future:
            logger.warning("  WARNING: %s rows with future date", future)

        cur.execute(f"SELECT COUNT(*) AS c FROM {FACT_TABLE} WHERE driver_id IS NULL")
        null_drivers = cur.fetchone()[0]
        if null_drivers:
            logger.warning("  WARNING: %s rows with NULL driver_id", null_drivers)

        elapsed = time.time() - t_start
        logger.info("=== REFRESH COMPLETE in %.1fs ===", elapsed)

        if total == 0:
            logger.error("FAIL: No data loaded.")
            sys.exit(1)

        print(f"\n  rows_inserted:      {total:,}" if total else "\n  rows_inserted:      0")
        print(f"  distinct_drivers:   {drivers:,}" if drivers else "  distinct_drivers:   0")
        print(f"  min_activity_date:  {min_date}")
        print(f"  max_activity_date:  {max_date}")
        print(f"  duration:           {elapsed:.1f}s")
        print(f"  status:             OK")

    except Exception as e:
        logger.exception("FAIL: %s", e)
        sys.exit(2)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
