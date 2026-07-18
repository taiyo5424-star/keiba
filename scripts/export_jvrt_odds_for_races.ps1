param(
    [Parameter(Mandatory = $true)]
    [string]$RaceIdsCsv,
    [string]$DataSpec = "0B31",
    [int]$MaxRecords = 10000,
    [string]$OutputDir = "data\jra_van_exports\today_20260621"
)

$ErrorActionPreference = "Stop"

$raceIds = Import-Csv -Path $RaceIdsCsv
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

foreach ($race in $raceIds) {
    $key = $race.race_id
    if (-not $key) {
        continue
    }

    $env:JV_DATASPEC = $DataSpec
    $env:JV_KEY = $key
    $env:JV_MAX_RECORDS = [string]$MaxRecords

    & "$PSScriptRoot\export_jvrt_raw.ps1"

    $source = Join-Path (Get-Location) ("data\jra_van_exports\raw_rt_" + $DataSpec.ToLower() + "_" + $key + ".csv")
    $target = Join-Path $OutputDir ("raw_rt_" + $DataSpec.ToLower() + "_" + $key + ".csv")
    if (Test-Path $source) {
        Copy-Item -LiteralPath $source -Destination $target -Force
    }
}
