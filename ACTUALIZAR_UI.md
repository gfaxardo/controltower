# Pasos para Actualizar la UI - Corrección Revenue Plan

## ✅ Estado Actual
- ✅ Código corregido (planDataSplit se usa después de definirse)
- ✅ Tooltips agregados
- ✅ Sin errores de linter

## 🔄 Pasos para Aplicar Cambios en UI

### 1. Limpiar Caché de Vite (PowerShell)
```powershell
cd c:\cursor\controltower\controltower\frontend
if (Test-Path "node_modules\.vite") { Remove-Item -Recurse -Force "node_modules\.vite" }
```

### 2. Reiniciar Servidor de Desarrollo

**Opción A: Si ya está corriendo**
- Presionar `Ctrl+C` para detenerlo
- Ejecutar: `npm run dev`

**Opción B: Iniciar nuevo**
```powershell
cd c:\cursor\controltower\controltower\frontend
npm run dev
```

### 3. Limpiar Caché del Navegador
- Abrir DevTools (F12)
- Clic derecho en botón de recargar → "Vaciar caché y recargar de manera forzada"
- O usar: `Ctrl+Shift+R` (Windows) / `Cmd+Shift+R` (Mac)

### 4. Verificar en Consola del Navegador (F12)
Buscar errores en rojo. Si no hay errores, los cambios deberían estar aplicados.

### 5. Verificar Datos desde API
En la consola del navegador (F12 → Console), ejecutar:
```javascript
fetch('http://localhost:8000/ops/plan/monthly?country=PE&year=2026')
  .then(r => r.json())
  .then(data => {
    console.log('Plan data sample:', data.data?.slice(0, 2));
    console.log('Revenue values:', data.data?.map(r => ({month: r.month, revenue: r.projected_revenue})));
  });
```

## 🐛 Si la UI Sigue Sin Actualizarse

### Verificar Backend
```powershell
# Verificar que la migración 009 esté ejecutada
cd c:\cursor\controltower\controltower\backend

# Verificar estado de migración (requiere venv activado)
python -m alembic current
```

### Verificar Estructura de BD
```sql
-- Ejecutar en psql o herramienta de BD
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_schema = 'ops' 
AND table_name = 'plan_trips_monthly' 
AND column_name = 'projected_revenue';

-- Debería mostrar: projected_revenue | numeric | YES | NULL
-- (NO debe mostrar GENERATED)
```

## 📝 Notas Importantes

1. **La migración 009 debe ejecutarse primero** para cambiar `projected_revenue` de GENERATED a campo normal.

2. **El Excel debe tener columna `revenue_plan`** para que se guarde en `projected_revenue`.

3. **Los tooltips ya están en el código** - aparecerán cuando la UI se recargue correctamente.

## ✅ Checklist

- [ ] Caché de Vite limpiado
- [ ] Servidor de desarrollo reiniciado
- [ ] Caché del navegador limpiado (Ctrl+Shift+R)
- [ ] No hay errores en consola del navegador
- [ ] Migración 009 ejecutada (si aplica)
- [ ] Plan reingestado con revenue_plan (si aplica)

---

**Si después de estos pasos la UI no se actualiza, comparte:**
- Errores de consola del navegador (F12 → Console)
- Respuesta de la API (F12 → Network → ver llamada a `/ops/plan/monthly`)
