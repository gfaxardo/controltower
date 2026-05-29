# Drivers — Supervisor Runbook

## Rutina Diaria

| Hora | Acción | Dónde |
|------|--------|-------|
| 09:00 | Revisar Operating Board | Campaign Intelligence → Operating Board |
| 09:15 | Verificar campañas en "Seguimiento pendiente" | Operating Board → Follow-up Needed |
| 09:30 | Importar outcomes si el CRM los envió | Campaign Detail → CRM Bridge |
| 10:00 | Revisar campañas "Esperando resultados" | Operating Board → Waiting Outcomes |
| 16:00 | Verificar si alguna campaña puede medirse | Operating Board → Waiting Measurement |

## Rutina Semanal

| Día | Acción |
|-----|--------|
| Lunes | Crear nuevas campañas si hay queues con prioridad alta |
| Miércoles | Revisar efectividad de campañas con ventana cumplida |
| Viernes | Cerrar campañas completadas, decidir repeticiones |

## Métricas a revisar

### Diarias
- Campañas activas sin movimiento > 3 días
- Bad phone rate por campaña (alerta si > 20%)
- Outcomes pendientes de importar

### Semanales
- Recovery rate observado (% de reactivados vs contactados)
- Tasa de contacto efectivo (contactados / total con teléfono)
- Follow-ups pendientes acumulados
- Campañas trabadas (sin avance > 5 días)

## Campañas Activas

Revisar en **Operating Board**:
- **Listas para CRM**: ¿alguna lleva más de 2 días sin exportar?
- **En ejecución**: ¿el CRM está avanzando?
- **Esperando resultados**: ¿faltan outcomes por importar?
- **Seguimiento pendiente**: ¿hay segundos intentos por hacer?

## Campañas Trabadas

Una campaña está trabada si:
- Lleva > 5 días en el mismo estado
- Tiene > 50% de bad phones sin resolución
- No se importaron outcomes después de 7 días de envío al CRM
- Follow-up pendiente > 10 días

**Acción**: Revisar QA Checklist, hablar con operador responsable, escalar si es necesario.

## Owners con Atraso

Verificar:
- ¿Quién tiene campañas asignadas sin avance?
- ¿El CRM confirmó recepción de la lista?
- ¿Hay bloqueos técnicos (endpoint caído, datos incorrectos)?

## Bad Phone Rate

| Tasa | Acción |
|------|--------|
| < 10% | Normal, no requiere acción |
| 10-20% | Monitorear, reportar a data quality si persiste |
| > 20% | Pausar campaña, escalar a Data Quality, no repetir sin limpiar datos |

## Recovery Rate Observado

| Tasa | Interpretación |
|------|----------------|
| > 15% | Buen resultado, repetir tipo de campaña |
| 5-15% | Resultado moderado, evaluar ajustes |
| < 5% | Resultado bajo, revisar targeting y timing |

**Nota**: Esto es cambio observado, no causal.

## Follow-up Pendiente

- Revisar conductores con NO_RESPONSE e intentos < 3
- Decidir si vale la pena segundo intento
- Si PROMISED_RETURN sin viajes D+7: reintentar contacto
- Si > 3 intentos sin respuesta: cerrar como no contactable

## Decisión de Repetir/Pausar Campaña

### Repetir si:
- Recovery rate > 10% y hay conductores nuevos en queue
- Se identificó que el timing afectó resultados
- Se corrigieron datos de contacto (bad phones)

### Pausar si:
- Recovery rate < 5% después de 2 intentos
- Bad phone rate > 30%
- No hay capacidad operativa en el CRM
- Los conductores del segmento ya están en otra campaña activa

### Cerrar si:
- Todos los outcomes están registrados
- Medición completada
- No hay follow-ups pendientes
- Decisión tomada de no repetir
