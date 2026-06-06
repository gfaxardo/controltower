# LG-C1.4-P2 — User Journey Audit

**Date:** 2026-06-05

## Simulated User Flow

### 1. Entra a Lima Growth
- **Puede hacerlo:** SI — Sidebar navegable con 11 tabs
- **Ve:** Tab activo = Resumen
- **Estado:** OK

### 2. Ve universo y pipeline
- **Puede hacerlo:** SI
- **Ve:** Pipeline bar azul: Universo: 18,475 → Elegibles: 17,917 → Priorizados: 5,777 → Accionables: 500
- **También ve:** 8 KPIs (Universo Total, Priorizados, Accionables Hoy, Capacidad Diaria, En Cola, Contactos Exportados, LoopControl, Gap Capacidad)
- **Explicación:** Banner amarillo "Accionables hoy (500) estan limitados por daily_action_capacity = 500"
- **Estado:** OK

### 3. Revisa estado del conductor
- **Puede hacerlo:** SI — Click en "Estado del Conductor"
- **Ve:** Total Drivers: 18,475, Snapshot Date: 2026-06-02
- **También ve:** 3 columnas: Lifecycle State, Performance State, Retention State con barras de porcentaje
- **Estado:** OK

### 4. Revisa programas
- **Puede hacerlo:** SI — Click en "Programas"
- **Ve:** 4 cards con: Elegibles, Priorizados, Accionables, En Cola, Exportados, Status
- **Aviso:** "Programas actualmente definidos en STATIC_REGISTRY. Program Builder pendiente P2."
- **Estado:** OK

### 5. Revisa oportunidades
- **Puede hacerlo:** SI — Click en "Oportunidades"
- **Ve:** 4 contadores por programa + tabla top 20 con Rank, Driver ID, Programa, Lifecycle, Performance, Score, Bucket
- **Estado:** OK (usa endpoint legacy pero funcional)

### 6. Entra a Worklist
- **Puede hacerlo:** SI — Click en "Worklist"
- **Ve:** Filtros (Programa, Canal, Ciudad) + tabla con Nombre, Teléfono, Programa, Prioridad, Canal, Motivo, Último Viaje, Viajes Rec., Ciudad
- **Acciones:** Filtros funcionan (onChange dispara fetch)
- **Estado:** OK

### 7. Revisa Queue
- **Puede hacerlo:** SI — Click en "Queue"
- **Ve:** KPIs (En Cola, READY, HELD) + Filtros (Estado, Programa, Canal) + tabla
- **Estado:** OK (si no hay queue, muestra "Usa Construir cola del dia para generar la cola")

### 8. Construye Queue
- **Puede hacerlo:** SI — Botón "Construir cola del dia"
- **Ve:** Botón naranja, loading state mientras construye
- **Feedback:** Muestra resultado (+X creados, Y dup) después de construir
- **Estado:** OK

### 9. Exporta/Ve exportados
- **Puede hacerlo:** PARCIAL
- **Ve exportados:** SI — Tab "Ejecución Loop" muestra tabla de export history
- **Exporta desde Queue:** NO — No hay botón "Exportar" en tab Queue (endpoint /export existe en backend)
- **Estado:** WARNING — funcionalidad backend existe, falta UI button

### 10. Verifica LoopControl LIVE
- **Puede hacerlo:** SI
- **Ve:** Header muestra "LC: LIVE". Engine Health bar muestra LoopControl verde. Config tab muestra detalles.
- **Estado:** OK

### 11. Ve campañas/export ledger
- **Puede hacerlo:** SI — Click en "Ejecución Loop"
- **Ve:** KPIs (Campañas Exportadas, Contactos Totales, Último Campaign ID, LC Mode) + tabla Export History
- **Estado:** OK

### 12. Intenta ver resultados
- **Puede hacerlo:** NO
- **Ve:** Tab "Impacto" → EmptyState "No certificada — Pendiente LC-2"
- **Estado:** OK — el usuario sabe que no está disponible

### 13. Intenta ver impacto
- **Puede hacerlo:** NO
- **Ve:** Mismo tab "Impacto" → EmptyState claro
- **Estado:** OK

### 14. Intenta ver movimiento
- **Puede hacerlo:** NO
- **Ve:** Tab "Movimiento" → EmptyState "No certificada — Pendiente LC-2"
- **Estado:** OK

### 15. Intenta ver atribución
- **Puede hacerlo:** NO
- **Ve:** Tab "Atribución" → EmptyState "No certificada — Pendiente LC-2"
- **Estado:** OK

### 16. Revisa configuración
- **Puede hacerlo:** SI — Click en "Configuración"
- **Ve:** Policy (daily_action_capacity=500, accionables, priorizados) + LoopControl Integration (LIVE/DRY_RUN, URL, Key) + Capacidad Operativa (tabla editable por canal)
- **Acciones:** Editar agentes/capacidad, Guardar configuración
- **Estado:** OK

## Resumen

- **16 pasos** en el journey
- **11 OK** — funcionalidad completa y visible
- **1 WARNING** — Queue Export sin botón en UI
- **4 OK (P0)** — Tabs no certificadas con mensaje claro, no engañan
