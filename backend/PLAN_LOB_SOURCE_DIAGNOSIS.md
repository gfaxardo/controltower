# Diagnóstico: Fuentes de LOB del Plan
Fecha: 2026-01-23 15:13:59

## 1. Tablas Candidatas

### Schema: `plan`

### Schema: `canon`

### Schema: `ops`

⚠️ **No se encontraron tablas candidatas con columnas de LOB.**

## 2. Estructura de trips_all

**Total de columnas**: 25

### Columnas relevantes para LOB:

- `id` (character varying, nullable: YES)
- `codigo_pedido` (character varying, nullable: YES)
- `conductor_id` (character varying, nullable: YES)
- `fecha_inicio_viaje` (timestamp without time zone, nullable: YES)
- `fecha_finalizacion` (timestamp without time zone, nullable: YES)
- `tipo_servicio` (character varying, nullable: YES)
- `pago_corporativo` (numeric, nullable: YES)
- `park_id` (character varying, nullable: YES)

## 3. Recomendaciones

⚠️ **No se encontraron tablas con LOB del plan.**
   El sistema funcionará en modo REAL-only hasta que se cargue el plan.

