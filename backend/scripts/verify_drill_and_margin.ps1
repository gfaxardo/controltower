# Verificación runtime: drill y margin-quality (ejecutar con backend levantado en 127.0.0.1:8000)
# Uso: .\scripts\verify_drill_and_margin.ps1

$base = "http://127.0.0.1:8000"
$timeout = 120

function Test-Endpoint {
  param($name, $url)
  try {
    $r = Invoke-WebRequest -Uri $url -Method GET -UseBasicParsing -TimeoutSec $timeout
    Write-Host "[OK] $name -> $($r.StatusCode)"
    return $r.StatusCode -eq 200
  } catch {
    $code = $_.Exception.Response.StatusCode.value__
    Write-Host "[FAIL] $name -> $code o timeout/error: $($_.Exception.Message)"
    return $false
  }
}

Write-Host "Verificando endpoints (timeout ${timeout}s)..."
Test-Endpoint "drill week LOB" "$base/ops/real-lob/drill?period=week&desglose=LOB&segmento=all"
Test-Endpoint "drill/children week LOB PE" "$base/ops/real-lob/drill/children?country=pe&period=week&period_start=2026-03-09&desglose=LOB&segmento=all"
Test-Endpoint "drill/children month LOB PE" "$base/ops/real-lob/drill/children?country=pe&period=month&period_start=2026-02-01&desglose=LOB&segmento=all"
Test-Endpoint "drill/children month PARK PE" "$base/ops/real-lob/drill/children?country=pe&period=month&period_start=2026-02-01&desglose=PARK&segmento=all"
Test-Endpoint "drill/children month SERVICE_TYPE PE" "$base/ops/real-lob/drill/children?country=pe&period=month&period_start=2026-03-01&desglose=SERVICE_TYPE&segmento=all"
Test-Endpoint "real-margin-quality" "$base/ops/real-margin-quality?days_recent=90&findings_limit=20"
Write-Host "Listo."
