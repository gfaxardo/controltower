from app.db.connection import get_db

with get_db() as conn:
    cur = conn.cursor()
    
    # Contar filas
    cur.execute("SELECT COUNT(*) FROM ops.v_plan_projection_control_loop")
    count = cur.fetchone()[0]
    print(f'Total plan rows: {count}')
    
    # Muestra algunas filas
    if count > 0:
        cur.execute("""
            SELECT plan_version, period_date, country, city, projected_trips
            FROM ops.v_plan_projection_control_loop
            LIMIT 5
        """)
        print('\n=== SAMPLE ROWS ===')
        for row in cur.fetchall():
            print(row)
    else:
        # Try alternative table
        cur.execute("SELECT COUNT(*) FROM ops.plan_trips_monthly")
        count2 = cur.fetchone()[0]
        print(f'plan_trips_monthly rows: {count2}')
        
        if count2 > 0:
            cur.execute("""
                SELECT plan_version, month, country, city, projected_trips
                FROM ops.plan_trips_monthly
                LIMIT 5
            """)
            print('\n=== SAMPLE FROM plan_trips_monthly ===')
            for row in cur.fetchall():
                print(row)
    cur.close()