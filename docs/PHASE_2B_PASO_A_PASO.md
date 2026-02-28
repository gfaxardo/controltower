# Fase 2B — Paso a paso (cierre manual)

Sí, el cierre se hace **manual**: tú ejecutas un bloque en PowerShell con tus credenciales de Postgres. Sigue estos pasos al pie de la letra.

---

## Paso 1 — Abrir PowerShell en la raíz del repo

1. Abre **PowerShell** (no CMD).
2. Navega a la raíz del proyecto:
   ```powershell
   cd "c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER"
   ```
3. Comprueba que estás en la raíz (debe existir la carpeta `backend`):
   ```powershell
   dir backend
   ```
   Si ves la lista de archivos/carpetas de `backend`, sigue.

---

## Paso 2 — Tener a mano usuario y contraseña de Postgres

Necesitas:

- **Usuario** de la base (ej. `postgres` o el que uses en `.env`).
- **Contraseña** de ese usuario.
- **Host:** si la BD está en tu PC, usa `localhost`; si es remota, la IP o nombre del servidor.
- **Puerto:** casi siempre `5432`.
- **Nombre de la BD:** en el proyecto suele ser `yego_integral`.

Si tienes un archivo `backend\.env`, puedes mirar ahí `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` (no hace falta copiar el archivo; solo leer los valores para rellenar el bloque).

---

## Paso 3 — Copiar el bloque completo

1. Abre en el editor el archivo:
   ```
   docs/PHASE_2B_RUNBOOK.md
   ```
2. Busca la sección **«Cierre FASE 2B con evidencia»** y el bloque que empieza por:
   ```powershell
   # --- Cierre FASE 2B semanal: desde raíz del repo ---
   ```
3. **Selecciona y copia todo el bloque** (desde esa línea hasta la última que termina en ```, **sin incluir** los tres backticks de cierre).

---

## Paso 4 — Sustituir credenciales en el bloque

Antes de pegar en PowerShell, **edita el bloque** en un editor de texto (Bloc de notas, Cursor, etc.) y cambia solo estas líneas:

| Buscar exactamente        | Reemplazar por tu valor real                          |
|---------------------------|--------------------------------------------------------|
| `'YOUR_DB_USER'`          | Tu usuario Postgres, entre comillas. Ej: `'postgres'` |
| `'YOUR_DB_PASSWORD'`      | Tu contraseña Postgres, entre comillas                |
| `'YOUR_DB_HOST'`         | `'localhost'` si es local, o la IP/host si es remoto  |
| `'YOUR_DB_PORT'`         | `'5432'` (o el puerto que uses)                       |
| `'YOUR_DB_NAME'`         | `'yego_integral'` (o el nombre de tu BD)              |

Ejemplo después de editar (solo como referencia; no copies esto tal cual si tu usuario/contraseña son otros):

```powershell
$env:DB_USER = 'postgres'
$env:DB_PASSWORD = 'mi_password_secreto'
$env:DB_HOST = 'localhost'
$env:DB_PORT = '5432'
$env:DB_NAME = 'yego_integral'
```

Guarda el archivo donde hayas pegado el bloque (o simplemente ten el bloque ya editado en el portapapeles).

---

## Paso 5 — Pegar y ejecutar en PowerShell

1. En la misma ventana de PowerShell donde hiciste `cd` a la raíz del repo (Paso 1), **pega el bloque completo** (clic derecho → Pegar, o Ctrl+V).
2. Pulsa **Enter**.
3. El script se ejecutará solo. Verás salida de:
   - `alembic upgrade head`
   - `alembic current` y `alembic heads`
   - Comprobación de la MV
   - Refresh de la MV (puede tardar varios minutos)
   - Validaciones
4. **No cierres la ventana** hasta que termine. Al final debe aparecer algo como:
   ```
   Log guardado en: c:\...\logs\phase2b_closeout_YYYYMMDD_HHmm.txt
   FASE 2B CERRADA: SI
   ```
   o
   ```
   FASE 2B CERRADA: NO
   ```

---

## Paso 6 — Revisar el resultado

1. **Si sale `FASE 2B CERRADA: SI`**  
   - El cierre se dio bien. Opcional: abre el archivo de log que indica la línea “Log guardado en: …” y copia las ~10 líneas clave que indica el runbook en “Líneas exactas que debes pegar aquí” y pégalas en **docs/PHASE_2B_STATUS.md** en la sección “Evidencia”. Marca en ese mismo archivo los checkboxes y **FASE 2B CERRADA: SÍ** con la fecha.

2. **Si sale `FASE 2B CERRADA: NO`**  
   - Abre el archivo de log (la ruta que salió en “Log guardado en: …”).
   - Busca la sección **`=== RESUMEN ===`** al final. Ahí verás qué falló:
     - `alembic upgrade OK: False` → error en migraciones; revisa el log más arriba donde pone “alembic upgrade head”.
     - `alembic current == head (053): False` → la BD no está en la revisión esperada; vuelve a ejecutar `alembic upgrade head` desde `backend` o revisa errores de migración.
     - `MV semanal existe: False` → la migración 014 no creó la MV; revisa errores de la migración 014 en el log.
     - `Refresh OK: False` → el refresh de la MV falló o hizo timeout; revisa en el log la parte “refresh_mv_real_weekly”.
     - `Validate OK: False` → alguna validación (Unicidad, Reconciliacion, Sanity, PlanSum) falló; en el log busca “RESUMEN DE VALIDACIONES” y “[FAIL]”.

---

## Resumen en 6 pasos

| # | Acción concreta |
|---|------------------|
| 1 | Abrir PowerShell, `cd` a la raíz del repo, comprobar que existe `backend` |
| 2 | Tener usuario, contraseña, host, puerto y nombre de la BD de Postgres |
| 3 | En `docs/PHASE_2B_RUNBOOK.md`, copiar el bloque de “Cierre FASE 2B con evidencia” |
| 4 | En ese bloque, reemplazar `YOUR_DB_USER`, `YOUR_DB_PASSWORD`, `YOUR_DB_HOST`, `YOUR_DB_PORT`, `YOUR_DB_NAME` por tus valores |
| 5 | Pegar el bloque en PowerShell (en la misma sesión donde estás en la raíz) y pulsar Enter; esperar a que termine |
| 6 | Si sale “FASE 2B CERRADA: SI”, opcionalmente rellenar evidencia en `docs/PHASE_2B_STATUS.md`; si sale NO, abrir el log y usar la tabla de “Si algo falla” del runbook |

Sí, es manual: nadie puede ejecutar por ti el script contra tu base de datos porque solo tú tienes las credenciales. Con estos pasos deberías poder hacerlo en una sola ejecución.
