$ErrorActionPreference = "Stop"

$jv = New-Object -ComObject JVDTLab.JVLink
$result = $jv.JVInit("UNKNOWN")
Write-Output ("JVInit=" + $result)
