$ErrorActionPreference = "Stop"

$jv = New-Object -ComObject JVDTLab.JVLink
$init = $jv.JVInit("UNKNOWN")
Write-Output ("JVInit=" + $init)

$type = $jv.GetType()
Write-Output ("ComType=" + $type.FullName)

try {
    $version = $jv.JVLinkVersion()
    Write-Output ("JVLinkVersion=" + $version)
} catch {
    Write-Output ("JVLinkVersion=unavailable: " + $_.Exception.Message)
}
