param([Parameter(Mandatory = $true)][string]$Serial)
$ErrorActionPreference = 'Stop'
$sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { 'C:\Android\Sdk' }
$adb = Join-Path $sdkRoot 'platform-tools\adb.exe'
if (!(Test-Path -LiteralPath $adb)) { $adb = 'C:\Android\Sdk\platform-tools\adb.exe' }
. "$PSScriptRoot\adb-install.ps1"
function Run-Adb([string[]]$Arguments) {
    $result = & $adb -s $Serial @Arguments
    if ($LASTEXITCODE -ne 0) { throw "ADB operation failed: $($Arguments[0])" }
    return $result
}
$actualSerial = (Run-Adb @('shell','getprop','ro.serialno')).Trim()
if (!$actualSerial) { throw 'Device identity was not available' }
$manufacturer = (Run-Adb @('shell','getprop','ro.product.manufacturer')).Trim()
Write-Output "Installing on $manufacturer / $actualSerial through $Serial"
& "$PSScriptRoot\build.ps1"
$buildRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\.local-build'))
Install-AirTypeApk -Adb $adb -Serial $Serial -ApkPath "$buildRoot\airtype-keys\airtype-keys.apk" -PackageName 'local.qaa.airtype'
Run-Adb @('shell','pm','grant','local.qaa.airtype','android.permission.POST_NOTIFICATIONS')
$current = (Run-Adb @('shell','settings','get','secure','enabled_accessibility_services')).Trim()
$backup = Join-Path $buildRoot "accessibility-before-$actualSerial.txt"
if (!(Test-Path -LiteralPath $backup)) { [IO.File]::WriteAllText($backup, $current) }
$services = @($current -split ':' | Where-Object { $_ -and $_ -ne 'null' })
if ($services -notcontains 'local.qaa.airtype/.KeyService' -and $services -notcontains 'local.qaa.airtype/local.qaa.airtype.KeyService') { $services += 'local.qaa.airtype/.KeyService' }
Run-Adb @('shell','settings','put','secure','enabled_accessibility_services',($services -join ':'))
if ($manufacturer -eq 'Xiaomi') {
    # This permission was rejected in the Xiaomi 14 live log. MIUI resets it
    # during USB replacement installs, so restore it after updating our APK.
    $before = Run-Adb @('shell','cmd','appops','get','local.qaa.airtype','10021')
    $permissionBackup = Join-Path $buildRoot "background-start-before-$actualSerial.txt"
    if (!(Test-Path -LiteralPath $permissionBackup)) { $before | Set-Content -LiteralPath $permissionBackup }
    Run-Adb @('shell','cmd','appops','set','local.qaa.airtype','10021','allow')
}
Run-Adb @('shell','am','start','-n','local.qaa.airtype/.MainActivity')
if ($manufacturer -eq 'Xiaomi') {
    # Package replacement observers can reset the permission asynchronously.
    # Allow two seconds for them, then confirm three consecutive readbacks.
    Start-Sleep -Seconds 2
    $stable = 0
    for ($attempt = 0; $attempt -lt 10 -and $stable -lt 3; $attempt++) {
        $mode = (Run-Adb @('shell','cmd','appops','get','local.qaa.airtype','10021')) -join "`n"
        if ($mode -match 'MIUIOP\(10021\): allow') { $stable++ }
        else {
            $stable = 0
            Run-Adb @('shell','cmd','appops','set','local.qaa.airtype','10021','allow')
        }
        Start-Sleep -Milliseconds 500
    }
    if ($stable -lt 3) { throw 'Xiaomi background activity permission did not stay allowed' }
    Write-Output 'Xiaomi background activity permission verified: allow'
}
Write-Output 'Tasker F9 Key Down / Key Up must be disabled to prevent duplicate actions.'
