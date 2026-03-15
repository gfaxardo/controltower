# REAL — Política de revenue multi-país / multi-moneda

## Contexto

YEGO opera en **Colombia (COP)** y **Perú (PEN)**. En la capa canónica REAL, el campo de revenue (`comision_empresa_asociada` / `gross_revenue`) está en **moneda local** por transacción, sin código de moneda explícito en la fact. El país se deriva de parque/ciudad (country = 'co' | 'pe').

## Problema

Si se **suma** `gross_revenue` sin filtrar por país, se mezclan COP y PEN. Un total único "Revenue" global es **engañoso** y no debe mostrarse sin conversión documentada.

## Política adoptada

1. **No agregar revenue entre países** en un único KPI monetario global sin tipo de cambio documentado.
2. **Mostrar revenue siempre segmentado por país** cuando haya más de un país en alcance, o cuando el usuario no haya filtrado por país.
3. **En vistas con filtro país**: se puede mostrar un único revenue (en moneda local de ese país).
4. **Si en el futuro existe FX confiable**: se podrá ofrecer un "revenue convertido" (ej. a EUR o USD) con documentación clara del origen del tipo de cambio.

## Implementación

- **Backend**: Los endpoints que devuelven revenue (snapshot, day view, hourly, comparativos) pueden incluir:
  - `gross_revenue`: cuando el filtro es un solo país, es el total en moneda local.
  - `gross_revenue_by_country`: lista `{ country, gross_revenue }` para no mezclar monedas.
- **UI**: 
  - Si hay un solo país seleccionado: mostrar "Revenue (COP)" o "Revenue (PEN)" según país.
  - Si no hay filtro o hay varios países: mostrar "Revenue por país" (desglose) y no un total único, o mostrar totales por país con etiqueta "Revenue CO", "Revenue PE".
- **No dejar revenue en 0** si el dato existe: si el valor es 0, comprobar que no sea por filtro vacío o por bug de agregación.

## Resumen

- Revenue en REAL = moneda local (COP/PEN) por país.
- No sumar entre países en un solo número.
- UI: segmentar por país y etiquetar moneda cuando sea posible.
