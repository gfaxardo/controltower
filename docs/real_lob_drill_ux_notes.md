# Real LOB Drill — Notas de UX (microfase cierre)

- **Totales:** La barra de KPIs por país lleva la etiqueta "Totales (periodos listados)" y tooltip aclarando que las métricas son la suma de todos los periodos de la tabla, no solo del periodo expandido.
- **Estado del periodo:** "Abierto" incluye tooltip "Mes/semana en curso (datos parciales)"; "Cerrado" y "Vacío" también tienen tooltip breve.
- **Desglose expandido:** Al abrir una fila de periodo, el bloque de subfilas tiene borde izquierdo y el título "Desglose de [Ene 2025] por LOB" (o Park / Tipo de servicio) para que quede claro que aplica solo a ese periodo.
- **LOW_VOLUME:** No se muestra en la UI (excluido en backend para desglose LOB y filtro defensivo en frontend). Se mantiene en backend para control interno si aplica.
