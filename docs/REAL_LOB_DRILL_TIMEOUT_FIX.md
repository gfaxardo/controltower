# Real LOB Drill — Timeout estable (statement_timeout 15s)

## Problema
El endpoint `GET /ops/real-lob/drill` a veces devuelve **500** o el frontend muestra **timeout** porque el rol de PostgreSQL (`yego_user`) tiene `statement_timeout = 15s`. La consulta sobre `ops.mv_real_drill_dim_agg` y vistas de coverage puede tardar más de 15 segundos y el servidor cancela la sentencia.

## Solución (en el servidor PostgreSQL)
Un usuario con privilegios de superusuario o de rol debe ejecutar:

```sql
ALTER ROLE yego_user SET statement_timeout TO '300s';
```

Para quitar el límite por completo (solo si es aceptable en tu entorno):

```sql
ALTER ROLE yego_user SET statement_timeout TO '0';
```

Tras ejecutarlo, las **nuevas** conexiones de `yego_user` tendrán el nuevo valor. No hace falta reiniciar la API.

## Comprobar el valor actual
Conectar como `yego_user` y ejecutar:

```sql
SHOW statement_timeout;
```

## Probar el drill sin reload (evitar cortes por WatchFiles)
Para que una respuesta 200 llegue bien al frontend sin que el reload corte la conexión:

1. Arrancar el backend **sin** `--reload`:  
   `uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. No modificar código mientras cargas el drill.
3. En el frontend, ir a Real LOB → Drill por país y cargar (o Reintentar).

Si tras aplicar `ALTER ROLE` el drill sigue fallando, revisar en el backend que no aparezca `canceling statement due to statement timeout` en los logs.
