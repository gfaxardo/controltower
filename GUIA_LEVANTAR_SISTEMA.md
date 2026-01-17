# 🚀 GUÍA PARA LEVANTAR YEGO CONTROL TOWER

**Paso a paso completo para ejecutar el sistema**

---

## 📋 PRE-REQUISITOS

Antes de comenzar, asegúrate de tener instalado:

- ✅ **Python 3.11+** (verificar: `python --version`)
- ✅ **Node.js 18+** (verificar: `node --version`)
- ✅ **PostgreSQL 12+** ejecutándose
- ✅ **Git** (para clonar el proyecto)

---

## 🔧 PASO 1: CONFIGURAR BASE DE DATOS

### 1.1. Verificar que PostgreSQL esté ejecutándose

```bash
# Windows (PowerShell)
Get-Service -Name postgresql*

# O verificar manualmente en Services
```

### 1.2. Verificar conexión a la base de datos

Debes tener una base de datos llamada `yego_integral` en PostgreSQL. Si no existe, créala:

```sql
-- Conectarse a PostgreSQL como superusuario
psql -U postgres

-- Crear base de datos
CREATE DATABASE yego_integral;

-- Salir
\q
```

### 1.3. Verificar que existen las tablas necesarias

El sistema requiere las siguientes tablas/vistas:
- `dim.dim_park`
- `bi.real_monthly_agg` o `public.trips_all`
- `ops.plan_trips_monthly` (se crea automáticamente)
- `ops.mv_real_trips_monthly` (se crea con migraciones)

---

## ⚙️ PASO 2: CONFIGURAR VARIABLES DE ENTORNO

### 2.1. Crear o verificar archivo `.env` en `backend/`

```powershell
# ⚠️ IMPORTANTE: Usar 'backend' con minúsculas, NO 'BACKEND'
# Si estás en otra carpeta, navega a la carpeta backend:
cd "C:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\backend"

# Verificar si el archivo ya existe y manejarlo apropiadamente
if (Test-Path .env) {
    Write-Host "✓ El archivo .env ya existe." -ForegroundColor Green
    Write-Host "  Puedes verificar su contenido con: Get-Content .env" -ForegroundColor Yellow
    Write-Host "  O editarlo con: notepad .env" -ForegroundColor Yellow
} else {
    Write-Host "Creando archivo .env..." -ForegroundColor Cyan
    New-Item -Path .env -ItemType File | Out-Null
    Write-Host "✓ Archivo .env creado. Ábrelo para configurarlo." -ForegroundColor Green
}

# Mostrar el contenido actual (si existe)
if (Test-Path .env) {
    Write-Host "`nContenido actual del archivo .env:" -ForegroundColor Cyan
    Get-Content .env
}
```

**⚠️ NOTA:** 
- Si el archivo ya existe, **solo ábrelo** para verificar/editar la configuración.
- Asegúrate de estar en la carpeta `backend` (minúsculas), no `BACKEND` (mayúsculas).

### 2.2. Editar el archivo `.env` con tu configuración

Abre `backend/.env` y agrega:

```env
# Base de datos PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=yego_integral
DB_USER=tu_usuario_postgres
DB_PASSWORD=tu_password_postgres

# Entorno
ENVIRONMENT=dev

# CORS (opcional, ya tiene valores por defecto)
# CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

**⚠️ IMPORTANTE:** Reemplaza `tu_usuario_postgres` y `tu_password_postgres` con tus credenciales reales.

---

## 🐍 PASO 3: INSTALAR Y CONFIGURAR BACKEND

### 3.1. Navegar a la carpeta backend

```bash
cd backend
```

### 3.2. Crear entorno virtual (Recomendado)

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Windows CMD:
venv\Scripts\activate.bat

# Linux/Mac:
source venv/bin/activate
```

### 3.3. Instalar dependencias Python

```bash
pip install -r requirements.txt
```

**Dependencias que se instalarán:**
- FastAPI
- Uvicorn
- Pandas
- psycopg2-binary
- Alembic
- Y más...

### 3.4. Ejecutar migraciones Alembic

```bash
# Asegurarse de estar en la carpeta backend
cd backend

# Ejecutar todas las migraciones pendientes
alembic upgrade head
```

**Resultado esperado:**
```
INFO  [alembic.runtime.migration] Running upgrade 006_create_plan_city_map -> 007_create_plan_vs_real_views, create_plan_vs_real_views
```

**Si hay errores:**
- Verifica que PostgreSQL esté ejecutándose
- Verifica las credenciales en `.env`
- Verifica que la base de datos `yego_integral` exista

### 3.5. Verificar migraciones (Opcional)

```bash
# Ver estado de migraciones
alembic current

# Ver historial de migraciones
alembic history
```

---

## 🚀 PASO 4: LEVANTAR EL BACKEND

### 4.1. Desde la carpeta `backend/`

```bash
# Asegurarse de estar en backend/
cd backend

# Ejecutar el servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Resultado esperado:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Pool de conexiones inicializado
INFO:     Esquema plan creado/verificado
INFO:     Application startup complete.
```

### 4.2. Verificar que el backend funciona

Abre tu navegador y ve a:
- **API Root:** http://localhost:8000
- **Documentación Swagger:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

Deberías ver respuestas JSON válidas.

### 4.3. Dejar el backend ejecutándose

**No cierres esta terminal.** El backend debe seguir ejecutándose.

**💡 TIP:** Abre una nueva terminal para los siguientes pasos.

---

## ⚛️ PASO 5: INSTALAR Y LEVANTAR FRONTEND

### 5.1. Abrir nueva terminal y navegar a frontend

```bash
# Desde la raíz del proyecto
cd frontend
```

### 5.2. Instalar dependencias Node.js

```bash
npm install
```

**Dependencias que se instalarán:**
- React
- Vite
- Axios
- Tailwind CSS
- Y más...

### 5.3. Ejecutar el frontend

```bash
npm run dev
```

**Resultado esperado:**
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### 5.4. Verificar que el frontend funciona

Abre tu navegador y ve a:
- **Frontend:** http://localhost:5173

Deberías ver la interfaz de YEGO Control Tower.

---

## ✅ PASO 6: VERIFICACIÓN FINAL

### 6.1. Verificar que ambos servicios están ejecutándose

**Backend:** http://localhost:8000  
**Frontend:** http://localhost:5173

### 6.2. Probar endpoints API

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Obtener universo operativo:**
```bash
curl http://localhost:8000/ops/universe
```

**Obtener Plan vs Real:**
```bash
curl http://localhost:8000/ops/plan-vs-real/monthly
```

### 6.3. Verificar frontend

En el navegador (http://localhost:5173):
- ✅ Debe cargar la interfaz sin errores
- ✅ Debe poder hacer llamadas al backend
- ✅ La consola del navegador no debe mostrar errores de CORS

---

## 🐛 SOLUCIÓN DE PROBLEMAS COMUNES

### Error: "connection to server at localhost failed"

**Solución:**
1. Verificar que PostgreSQL esté ejecutándose
2. Verificar credenciales en `backend/.env`
3. Verificar que el puerto 5432 esté disponible

```bash
# Verificar que PostgreSQL escucha en el puerto 5432
netstat -an | findstr :5432
```

### Error: "ModuleNotFoundError: No module named 'app'"

**Solución:**
1. Asegurarse de estar en la carpeta `backend/` al ejecutar
2. Verificar que el entorno virtual esté activado
3. Reinstalar dependencias: `pip install -r requirements.txt`

### Error: "relation does not exist"

**Solución:**
1. Ejecutar migraciones: `alembic upgrade head`
2. Verificar que la base de datos `yego_integral` exista
3. Verificar que el usuario tenga permisos suficientes

### Error: "CORS policy"

**Solución:**
1. Verificar que `CORS_ORIGINS` en `.env` incluya `http://localhost:5173`
2. Reiniciar el backend después de cambiar `.env`
3. Verificar que el frontend esté en el puerto 5173

### Error: "npm ERR! code ENOENT"

**Solución:**
1. Asegurarse de estar en la carpeta `frontend/`
2. Limpiar e reinstalar: `rm -rf node_modules && npm install`

### El frontend no se conecta al backend

**Solución:**
1. Verificar que el backend esté ejecutándose en el puerto 8000
2. Verificar la URL en `frontend/src/services/api.js`
3. Verificar que no haya firewall bloqueando la conexión

---

## 📝 RESUMEN DE COMANDOS RÁPIDOS

### Backend (Terminal 1)
```bash
cd backend
# Activar venv si existe
.\venv\Scripts\Activate.ps1
# Instalar dependencias (solo primera vez)
pip install -r requirements.txt
# Ejecutar migraciones (solo primera vez o cuando haya cambios)
alembic upgrade head
# Levantar backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Terminal 2)
```bash
cd frontend
# Instalar dependencias (solo primera vez)
npm install
# Levantar frontend
npm run dev
```

---

## 🎯 VERIFICACIÓN RÁPIDA

### ✅ Checklist Pre-Inicio

- [ ] PostgreSQL ejecutándose
- [ ] Base de datos `yego_integral` existe
- [ ] Archivo `backend/.env` configurado
- [ ] Variables de entorno correctas (DB_USER, DB_PASSWORD)
- [ ] Python 3.11+ instalado
- [ ] Node.js 18+ instalado

### ✅ Checklist Durante Ejecución

- [ ] Backend ejecutándose en puerto 8000
- [ ] Frontend ejecutándose en puerto 5173
- [ ] No hay errores en consola del backend
- [ ] No hay errores en consola del frontend
- [ ] http://localhost:8000/health responde OK
- [ ] http://localhost:5173 carga correctamente

---

## 🔄 PRÓXIMAS VECES (Inicio Rápido)

Una vez configurado, para levantar el sistema solo necesitas:

### Terminal 1 - Backend:
```bash
cd backend
.\venv\Scripts\Activate.ps1  # Si usas venv
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

---

## 📞 AYUDA ADICIONAL

Si encuentras problemas:

1. **Revisar logs del backend** en la terminal donde lo ejecutaste
2. **Revisar consola del navegador** (F12 → Console)
3. **Verificar migraciones:** `alembic current`
4. **Verificar conexión a BD:** Probar con `psql -U tu_usuario -d yego_integral`

---

## 🎉 ¡LISTO!

Una vez completados todos los pasos:

✅ **Backend:** http://localhost:8000  
✅ **Frontend:** http://localhost:5173  
✅ **API Docs:** http://localhost:8000/docs

**El sistema YEGO CONTROL TOWER está listo para usar.** 🚀
