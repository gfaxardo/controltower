# Drivers — Guía de Handoff al Operador

## 1. Qué es Drivers

Drivers es el módulo de Control Tower que identifica, prioriza y mide acciones sobre conductores. Define **qué hacer, con quién y por qué**, pero NO ejecuta el contacto directo.

## 2. Qué NO es Drivers

- NO es un CRM
- NO envía mensajes ni WhatsApp
- NO automatiza comunicación
- NO predice ni usa IA
- NO reemplaza al equipo de contacto

## 3. Qué hace el CRM

El CRM externo (call center, WhatsApp, etc.) es quien:
- Recibe la lista de conductores desde Drivers
- Ejecuta el contacto (llamada, mensaje)
- Registra el resultado (contestó, no contestó, teléfono malo, etc.)
- Devuelve los outcomes a Control Tower

## 4. Qué hace Control Tower

Control Tower (Drivers):
- Detecta conductores en riesgo, inactivos o con oportunidad
- Los prioriza por urgencia y potencial de recuperación
- Crea campañas con universos congelados
- Exporta listas al CRM
- Recibe outcomes y los clasifica
- Mide si hubo cambio observado en viajes
- Cierra o repite según resultados

## 5. Cómo elegir una lista

1. Ir a **Campaign Intelligence → Campaign Builder**
2. Seleccionar queues fuente (At Risk, Churned Recent, etc.)
3. Filtrar por país, ciudad, prioridad
4. Click **Preview** para ver cuántos conductores hay
5. Revisar que el GO/NO-GO sea positivo
6. Si la cobertura de teléfono es baja, considerar fuentes de datos adicionales

## 6. Cómo crear campaña

1. En Campaign Builder, después del Preview exitoso
2. Asignar un **nombre claro** (ej: "Reactivación Lima AT_RISK Semana 22")
3. Click **Create Campaign**
4. La campaña se crea en estado DRAFT con los miembros congelados

## 7. Cómo exportar al CRM

1. Ir a **Campaign Detail** de la campaña creada
2. Verificar el **Estado del Loop Operativo** (debe decir "Lista para enviar al CRM")
3. Click **Export CRM Payload** o usar el endpoint:
   ```
   GET /drivers/campaigns/{campaign_id}/crm-export
   ```
4. El CRM recibirá: driver_id, nombre, teléfono, razón de contacto, prioridad

## 8. Cómo registrar outcomes

Después de que el CRM ejecute el contacto:

1. Importar outcomes vía endpoint:
   ```
   POST /drivers/campaigns/{campaign_id}/crm-sync/outcomes
   ```
2. Cada outcome debe incluir: driver_id, crm_status, outcome_note
3. Statuses válidos: CONTACTED, NO_RESPONSE, BAD_PHONE, PROMISED_RETURN, RETURNED, IRRECOVERABLE

## 9. Cómo leer efectividad

1. Ir a **Campaign Detail → Effectiveness (D+7)**
2. Revisar:
   - **Cambio observado en viajes**: ¿subió, bajó o igual?
   - **Tasa de reactivación**: % de conductores que volvieron a viajar
   - **Viajes después**: total de viajes en la ventana post-contacto
3. **IMPORTANTE**: Esto es "cambio observado", NO causalidad comprobada

## 10. Qué hacer si hay bad phones

- Revisar el QA Checklist de la campaña
- Si > 20% tiene teléfono malo:
  1. Reportar a Data Quality
  2. No repetir campaña con mismos conductores sin actualizar datos
  3. Marcar como DATA_QUALITY_REVIEW

## 11. Qué hacer con no response

- Si intentos < 3: marcar para segundo intento
- Si intentos >= 3 sin respuesta: evaluar cerrar como no contactable
- Revisar si el horario de contacto es adecuado
- Considerar canal alternativo si está disponible

## 12. Cuándo cerrar campaña

Cerrar cuando:
- Todos los outcomes están registrados
- Los follow-ups se completaron o decidieron no repetir
- La ventana de medición D+7 (o D+14) se cumplió
- Se revisó la efectividad
- Se tomó decisión de repetir o no

NO cerrar si:
- Hay conductores pendientes de contacto
- No se importaron todos los outcomes
- No se cumplió la ventana de medición
