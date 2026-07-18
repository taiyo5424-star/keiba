param(
    [string]$DataSpec = $(if ($env:JV_DATASPEC) { $env:JV_DATASPEC } else { "RACE" }),
    [string]$FromTime = $(if ($env:JV_FROMTIME) { $env:JV_FROMTIME } else { "20260601000000" }),
    [int]$Option = $(if ($env:JV_OPTION) { [int]$env:JV_OPTION } else { 2 }),
    [int]$MaxRecords = $(if ($env:JV_MAX_RECORDS) { [int]$env:JV_MAX_RECORDS } else { 200000 }),
    [string]$OutputName = ""
)

$ErrorActionPreference = "Stop"

$outDir = Join-Path (Get-Location) "data\jra_van_exports"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outFile = if ($OutputName) {
    Join-Path $outDir $OutputName
} else {
    Join-Path $outDir ("raw_" + $DataSpec.ToLower() + "_records.csv")
}

$jv = New-Object -ComObject JVDTLab.JVLink
$init = $jv.JVInit("UNKNOWN")
if ($init -ne 0) {
    throw "JVInit failed: $init"
}

$readCount = 0
$downloadCount = 0
$lastFileTimestamp = ""
$open = $jv.JVOpen($DataSpec, $FromTime, $Option, [ref]$readCount, [ref]$downloadCount, [ref]$lastFileTimestamp)
if ($open -ne 0) {
    $null = $jv.JVClose()
    throw "JVOpen failed: $open"
}

do {
    $status = $jv.JVStatus()
    if ($status -lt 0) {
        $null = $jv.JVClose()
        throw "JVStatus failed: $status"
    }
    if ($status -ge $downloadCount) {
        break
    }
    Start-Sleep -Seconds 2
} while ($true)

$rows = New-Object System.Collections.Generic.List[object]
$count = 0
while ($count -lt $maxRecords) {
    $buff = ""
    $filename = ""
    $ret = $jv.JVRead([ref]$buff, 120000, [ref]$filename)
    if ($ret -eq 0) {
        break
    }
    if ($ret -eq -1) {
        continue
    }
    if ($ret -lt 0) {
        $null = $jv.JVClose()
        throw "JVRead failed: $ret"
    }
    $raw = $buff.TrimEnd([char]0, "`r", "`n")
    $rows.Add([pscustomobject]@{
        data_spec = $DataSpec
        filename = $filename
        record_type = if ($raw.Length -ge 2) { $raw.Substring(0, 2) } else { "" }
        raw = $raw
    }) | Out-Null
    $count += 1
}

$close = $jv.JVClose()
$rows | Export-Csv -Path $outFile -NoTypeInformation -Encoding UTF8

Write-Output ("dataSpec=" + $DataSpec)
Write-Output ("fromTime=" + $FromTime)
Write-Output ("option=" + $Option)
Write-Output ("readCount=" + $readCount)
Write-Output ("downloadCount=" + $downloadCount)
Write-Output ("lastFileTimestamp=" + $lastFileTimestamp)
Write-Output ("records=" + $rows.Count)
Write-Output ("JVClose=" + $close)
Write-Output ("output=" + $outFile)
