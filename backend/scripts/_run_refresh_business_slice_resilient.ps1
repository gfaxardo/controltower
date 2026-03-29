# Reintentos solo ante fallos transitorios. Código 3 = disco lleno en Postgres → no reintentar.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot\..
$env:BUSINESS_SLICE_LOAD_WORK_MEM = "1GB"
$env:BUSINESS_SLICE_MONTH_CHUNK_GRAIN = "city"
$py = Join-Path (Get-Location) "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "ERROR: No existe $py"
    exit 99
}
$month = if ($args[0]) { $args[0] } else { "2026-03-01" }
$maxWaitHours = 3.5
$retrySleepSec = 60
$start = Get-Date
$attempt = 0
while (((Get-Date) - $start).TotalHours -lt $maxWaitHours) {
    $attempt++
    Write-Host ""
    Write-Host "========== Intento $attempt $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') mes=$month =========="
    & $py -m scripts.refresh_business_slice_mvs --month $month
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Host "========== OK (codigo 0) =========="
        exit 0
    }
    if ($code -eq 3) {
        Write-Host "========== ABORT: codigo 3 = PostgreSQL sin espacio (pgsql_tmp). Liberar disco en el servidor; reintentar no ayuda. =========="
        exit 3
    }
    Write-Host "========== Fallo codigo $code; espera ${retrySleepSec}s =========="
    Start-Sleep -Seconds $retrySleepSec
}
Write-Host "ERROR: Tiempo maximo ($maxWaitHours h) sin exito."
exit 1
