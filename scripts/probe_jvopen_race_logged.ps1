$ErrorActionPreference = "Stop"

$outDir = Join-Path (Get-Location) "outputs"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$logFile = Join-Path $outDir "jvlink_probe.log"

function Log($message) {
    $line = (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " " + $message
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Output $line
}

Remove-Item -Path $logFile -ErrorAction SilentlyContinue
Log "start"

$jv = New-Object -ComObject JVDTLab.JVLink
Log "created_com"

$init = $jv.JVInit("UNKNOWN")
Log ("JVInit=" + $init)
if ($init -ne 0) {
    exit 1
}

Log ("serviceKeyLength=" + $jv.m_servicekey.Length)
Log ("savePath=" + $jv.m_savepath)
Log ("version=" + $jv.m_JVLinkVersion)

$readCount = 0
$downloadCount = 0
$lastFileTimestamp = ""
$fromTime = if ($env:JV_FROMTIME) { $env:JV_FROMTIME } else { "20260601000000" }
$option = if ($env:JV_OPTION) { [int]$env:JV_OPTION } else { 2 }
Log ("before_JVOpen fromTime=" + $fromTime + " option=" + $option)

$open = $jv.JVOpen("RACE", $fromTime, $option, [ref]$readCount, [ref]$downloadCount, [ref]$lastFileTimestamp)
Log ("after_JVOpen result=" + $open + " readCount=" + $readCount + " downloadCount=" + $downloadCount + " lastFileTimestamp=" + $lastFileTimestamp)

$null = $jv.JVClose()
Log "closed"
