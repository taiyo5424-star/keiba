$ErrorActionPreference = "Stop"

$dataSpec = if ($env:JV_DATASPEC) { $env:JV_DATASPEC } else { "0B31" }
$key = if ($env:JV_KEY) { $env:JV_KEY } else { "2026061409030411" }
$maxRecords = if ($env:JV_MAX_RECORDS) { [int]$env:JV_MAX_RECORDS } else { 10000 }

$outDir = Join-Path (Get-Location) "data\jra_van_exports"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$safeKey = $key -replace '[^0-9A-Za-z_-]', '_'
$outFile = Join-Path $outDir ("raw_rt_" + $dataSpec.ToLower() + "_" + $safeKey + ".csv")

$jv = New-Object -ComObject JVDTLab.JVLink
$init = $jv.JVInit("UNKNOWN")
if ($init -ne 0) {
    throw "JVInit failed: $init"
}

$open = $jv.JVRTOpen($dataSpec, $key)
if ($open -ne 0) {
    $null = $jv.JVClose()
    throw "JVRTOpen failed: $open"
}

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
        data_spec = $dataSpec
        key = $key
        filename = $filename
        record_type = if ($raw.Length -ge 2) { $raw.Substring(0, 2) } else { "" }
        raw = $raw
    }) | Out-Null
    $count += 1
}

$close = $jv.JVClose()
$rows | Export-Csv -Path $outFile -NoTypeInformation -Encoding UTF8

Write-Output ("dataSpec=" + $dataSpec)
Write-Output ("key=" + $key)
Write-Output ("records=" + $rows.Count)
Write-Output ("JVClose=" + $close)
Write-Output ("output=" + $outFile)
