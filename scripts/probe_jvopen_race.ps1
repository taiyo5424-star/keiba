$ErrorActionPreference = "Stop"

$outDir = Join-Path (Get-Location) "outputs"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outFile = Join-Path $outDir "jvlink_race_probe.txt"

$jv = New-Object -ComObject JVDTLab.JVLink
$init = $jv.JVInit("UNKNOWN")
Write-Output ("JVInit=" + $init)
if ($init -ne 0) {
    exit 1
}

$readCount = 0
$downloadCount = 0
$lastFileTimestamp = ""

# RACE = race-related accumulated data. option=1 with an explicit date range keeps the probe bounded.
$fromTime = if ($env:JV_FROMTIME) { $env:JV_FROMTIME } else { "20260601000000" }
$option = if ($env:JV_OPTION) { [int]$env:JV_OPTION } else { 2 }
$open = $jv.JVOpen("RACE", $fromTime, $option, [ref]$readCount, [ref]$downloadCount, [ref]$lastFileTimestamp)
Write-Output ("JVOpen=" + $open)
Write-Output ("fromTime=" + $fromTime)
Write-Output ("option=" + $option)
Write-Output ("readCount=" + $readCount)
Write-Output ("downloadCount=" + $downloadCount)
Write-Output ("lastFileTimestamp=" + $lastFileTimestamp)
if ($open -ne 0) {
    $null = $jv.JVClose()
    exit 2
}

$deadline = (Get-Date).AddMinutes(5)
do {
    $status = $jv.JVStatus()
    Write-Output ("JVStatus=" + $status)
    if ($status -lt 0) {
        $null = $jv.JVClose()
        exit 3
    }
    if ($status -ge $downloadCount) {
        break
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

$records = New-Object System.Collections.Generic.List[string]
for ($i = 0; $i -lt 20; $i++) {
    $buff = ""
    $filename = ""
    $ret = $jv.JVRead([ref]$buff, 120000, [ref]$filename)
    Write-Output ("JVRead=" + $ret + " filename=" + $filename)
    if ($ret -eq 0) {
        break
    }
    if ($ret -eq -1) {
        continue
    }
    if ($ret -lt 0) {
        $null = $jv.JVClose()
        exit 4
    }
    $records.Add(("FILE=" + $filename + "`t" + $buff.TrimEnd([char]0))) | Out-Null
}

$records | Set-Content -Path $outFile -Encoding UTF8
$close = $jv.JVClose()
Write-Output ("JVClose=" + $close)
Write-Output ("output=" + $outFile)
