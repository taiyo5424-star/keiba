$ErrorActionPreference = "Stop"

$jv = New-Object -ComObject JVDTLab.JVLink
$init = $jv.JVInit("UNKNOWN")
Write-Output ("JVInit=" + $init)

try {
    $key = $jv.m_servicekey
    if ($null -eq $key) {
        Write-Output "serviceKeyLength=0"
    } else {
        Write-Output ("serviceKeyLength=" + $key.Length)
    }
} catch {
    Write-Output ("serviceKeyLength=unavailable: " + $_.Exception.Message)
}

foreach ($prop in @("m_savepath", "m_saveflag", "m_payflag", "m_JVLinkVersion")) {
    try {
        $value = $jv.$prop
        Write-Output ($prop + "=" + $value)
    } catch {
        Write-Output ($prop + "=unavailable: " + $_.Exception.Message)
    }
}
