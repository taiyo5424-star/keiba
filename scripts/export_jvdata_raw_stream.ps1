param(
    [string]$DataSpec = "RACE",
    [string]$FromTime = "20260601000000",
    [int]$Option = 1,
    [int]$MaxRecords = 2000000,
    [string]$OutputName = ""
)

$ErrorActionPreference = "Stop"

function Escape-CsvValue([string]$Value) {
    if ($null -eq $Value) {
        return '""'
    }
    return '"' + $Value.Replace('"', '""') + '"'
}

$outDir = Join-Path (Get-Location) "data\jra_van_exports"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outFile = if ($OutputName) {
    Join-Path $outDir $OutputName
} else {
    Join-Path $outDir ("raw_" + $DataSpec.ToLower() + "_records.csv")
}

$encoding = New-Object System.Text.UTF8Encoding($false)
$writer = New-Object System.IO.StreamWriter($outFile, $false, $encoding)

$jv = New-Object -ComObject JVDTLab.JVLink
$init = $jv.JVInit("UNKNOWN")
if ($init -ne 0) {
    $writer.Close()
    throw "JVInit failed: $init"
}

$readCount = 0
$downloadCount = 0
$lastFileTimestamp = ""
$open = $jv.JVOpen($DataSpec, $FromTime, $Option, [ref]$readCount, [ref]$downloadCount, [ref]$lastFileTimestamp)
if ($open -ne 0) {
    $null = $jv.JVClose()
    $writer.Close()
    throw "JVOpen failed: $open"
}

try {
    do {
        $status = $jv.JVStatus()
        if ($status -lt 0) {
            throw "JVStatus failed: $status"
        }
        if ($status -ge $downloadCount) {
            break
        }
        Start-Sleep -Seconds 2
    } while ($true)

    $writer.WriteLine('"data_spec","filename","record_type","raw"')
    $count = 0
    while ($count -lt $MaxRecords) {
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
            throw "JVRead failed: $ret"
        }
        $raw = $buff.TrimEnd([char]0, "`r", "`n")
        $recordType = if ($raw.Length -ge 2) { $raw.Substring(0, 2) } else { "" }
        $writer.WriteLine(
            (Escape-CsvValue $DataSpec) + "," +
            (Escape-CsvValue $filename) + "," +
            (Escape-CsvValue $recordType) + "," +
            (Escape-CsvValue $raw)
        )
        $count += 1
    }
}
finally {
    $writer.Close()
    $close = $jv.JVClose()
}

Write-Output ("dataSpec=" + $DataSpec)
Write-Output ("fromTime=" + $FromTime)
Write-Output ("option=" + $Option)
Write-Output ("readCount=" + $readCount)
Write-Output ("downloadCount=" + $downloadCount)
Write-Output ("lastFileTimestamp=" + $lastFileTimestamp)
Write-Output ("records=" + $count)
Write-Output ("JVClose=" + $close)
Write-Output ("output=" + $outFile)
