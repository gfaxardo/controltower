/**
 * MatrixExecutiveBanner — Data Trust ejecutivo (compacto, horizontal).
 * Estados: OK | WARNING | BLOCKED (payload API).
 * Modo decisión: SAFE | CAUTION | BLOCKED + score de confianza por pilares.
 */
export default function MatrixExecutiveBanner ({
  executive,
  decisionMode = null,
  confidence = null,
  recommendations = null,
  loading = false,
  actionable = false,
  onActivate,
  contextHints = null,
}) {
  if (loading || !executive) {
    return (
      <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 min-h-[36px] flex items-center gap-2">
        <span className="inline-block w-3 h-3 border-[1.5px] border-slate-300 border-t-slate-500 rounded-full animate-spin flex-shrink-0" />
        <span className="text-[11px] text-slate-400">Data Trust ejecutivo…</span>
      </div>
    )
  }

  const st = executive.status || 'WARNING'
  const isOk = st === 'OK'
  const isBlocked = st === 'BLOCKED'
  const mi = executive.main_issue
  const impact = executive.impact_pct != null ? Number(executive.impact_pct) : 0
  const pri = executive.priority_score != null ? executive.priority_score : null

  const shell =
    isOk
      ? 'border-emerald-300 bg-emerald-50/95 text-emerald-950'
      : isBlocked
        ? 'border-red-300 bg-red-50 text-red-950'
        : 'border-amber-300 bg-amber-50 text-amber-950'

  const badge =
    isOk
      ? 'bg-emerald-600 text-white'
      : isBlocked
        ? 'bg-red-600 text-white'
        : 'bg-amber-600 text-white'

  const dm = decisionMode && String(decisionMode).toUpperCase()
  const decisionBadge =
    dm === 'SAFE'
      ? 'bg-slate-600 text-white'
      : dm === 'BLOCKED'
        ? 'bg-rose-800 text-white'
        : dm === 'CAUTION'
          ? 'bg-amber-800 text-white'
          : null
  const decisionLabel =
    dm === 'SAFE' ? 'Seguro' : dm === 'BLOCKED' ? 'Bloqueado' : dm === 'CAUTION' ? 'Precaución' : null

  const conf = confidence && typeof confidence === 'object' ? confidence : null
  const confScore = conf?.score != null ? Number(conf.score) : null
  const confBaseScore = conf?.score_before_caps != null ? Number(conf.score_before_caps) : null
  const hardCap = conf?.hard_cap && typeof conf.hard_cap === 'object' ? conf.hard_cap : null
  const penaltyCode = hardCap?.code || null
  const pillarBits =
    conf &&
    [conf.coverage, conf.freshness, conf.consistency].every((x) => x != null)
      ? [
          `Coverage ${Number(conf.coverage).toFixed(0)}`,
          `Freshness ${Number(conf.freshness).toFixed(0)}`,
          `Consistency ${Number(conf.consistency).toFixed(0)}`,
          confBaseScore != null && !Number.isNaN(confBaseScore) ? `Base ${confBaseScore}` : null,
          hardCap ? `Penalizado por: ${hardCap.code} (cap ${hardCap.max_score})` : null,
          hardCap?.reason || null,
        ].filter(Boolean).join('\n')
      : null

  const recList = Array.isArray(recommendations) ? recommendations : []
  const recPreview = recList.slice(0, 2).map((r) => r?.message).filter(Boolean)
  const playbook = executive.playbook && typeof executive.playbook === 'object' ? executive.playbook : null

  const mainBits = mi
    ? [
        mi.code && `[${mi.code}]`,
        mi.description,
      ].filter(Boolean).join(' ')
    : null

  const traceBits = mi
    ? [mi.city, mi.lob, mi.period, mi.metric].filter(Boolean).join(' · ')
    : null

  const clickable = actionable && typeof onActivate === 'function' && !isOk && !!mi

  const inner = (
    <>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={`shrink-0 rounded px-1.5 py-px text-[10px] font-bold uppercase tracking-wide ${badge}`}>
          {st}
        </span>
        {decisionBadge && dm && (
          <span
            className={`shrink-0 rounded px-1.5 py-px text-[10px] font-bold uppercase tracking-wide ${decisionBadge}`}
            title={`Modo decisión: ${decisionLabel || dm}`}
          >
            {decisionLabel || dm}
          </span>
        )}
        {confScore != null && !Number.isNaN(confScore) && (
          <span
            className="text-[11px] tabular-nums shrink-0 text-slate-700"
            title={pillarBits || 'Confianza integrada (coverage, freshness, consistency)'}
          >
            Conf. <strong>{confScore}</strong>
          </span>
        )}
        {penaltyCode && (
          <span
            className="text-[10px] shrink-0 text-slate-600 hidden md:inline"
            title={hardCap?.reason || `Cap aplicado por ${penaltyCode}`}
          >
            Penalizado por {penaltyCode}
          </span>
        )}
        <span className="text-[11px] tabular-nums shrink-0">
          Impacto <strong>{impact.toFixed(1)}%</strong>
          {pri != null && pri > 0 && (
            <span className={`font-normal ml-1 ${isOk ? 'text-emerald-800/80' : isBlocked ? 'text-red-800/80' : 'text-amber-900/80'}`}>
              · score {typeof pri === 'number' ? pri.toFixed(1) : pri}
            </span>
          )}
        </span>
        <span className="text-[11px] flex-1 min-w-0 leading-snug">
          {isOk ? (
            <span className="font-medium">{executive.action || 'Sin acción ejecutiva requerida.'}</span>
          ) : (
            <>
              <span className="font-semibold block sm:inline sm:mr-1">Problema:</span>
              <span className="font-medium">{mainBits || executive.action || '—'}</span>
            </>
          )}
        </span>
        {!isOk && executive.action && mainBits && (
          <span className="text-[10px] opacity-90 max-w-[42%] sm:max-w-md truncate hidden sm:inline">
            Acción: {executive.action}
          </span>
        )}
        {clickable && (
          <span className="text-[10px] font-semibold underline shrink-0 ml-auto sm:ml-0">
            Ver en Matrix →
          </span>
        )}
      </div>
      {!isOk && traceBits && (
        <p className={`text-[10px] mt-0.5 leading-tight ${isBlocked ? 'text-red-900/80' : 'text-amber-900/85'}`}>
          Trazas: {traceBits}
        </p>
      )}
      {!isOk && executive.action && (mainBits || !mi) && (
        <p className={`text-[10px] mt-0.5 leading-tight sm:hidden ${isBlocked ? 'text-red-900/85' : 'text-amber-900/85'}`}>
          {executive.action}
        </p>
      )}
      {playbook && (playbook.recommended_action || playbook.operational_meaning) && (
        <p className="text-[10px] mt-0.5 leading-tight text-slate-700 border-t border-slate-200/80 pt-1">
          <span className="font-semibold text-slate-800">Acción estándar: </span>
          {playbook.recommended_action || playbook.operational_meaning}
          {playbook.owner_hint && (
            <span className="text-slate-500"> · owner: {playbook.owner_hint}</span>
          )}
        </p>
      )}
      {recPreview.length > 0 && (
        <p className="text-[10px] mt-0.5 leading-tight text-slate-600 border-t border-slate-200/80 pt-1">
          <span className="font-semibold text-slate-700">Sugerencias: </span>
          {recPreview.join(' · ')}
        </p>
      )}
      {Array.isArray(contextHints) && contextHints.length > 0 && (
        <p className="text-[10px] mt-0.5 leading-tight text-slate-600 border-t border-slate-200/80 pt-1">
          <span className="font-semibold text-slate-700">Contexto operativo: </span>
          {contextHints.join(' · ')}
        </p>
      )}
    </>
  )

  const wrapCls = `w-full rounded-md border ${shell} px-3 py-1.5 text-left transition-shadow ${
    clickable ? 'cursor-pointer hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-400' : 'cursor-default'
  }`

  if (clickable) {
    return (
      <button
        type="button"
        className={wrapCls}
        onClick={() => onActivate()}
        title="Ir al segmento en la Matrix e inspeccionar la celda"
      >
        {inner}
      </button>
    )
  }

  return (
    <div className={wrapCls}>
      {inner}
    </div>
  )
}
