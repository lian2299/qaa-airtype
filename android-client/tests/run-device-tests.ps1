param([Parameter(Mandatory = $true)][string]$Serial, [switch]$ShizukuOnly)
$ErrorActionPreference = 'Stop'
$sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { 'C:\Android\Sdk' }
$jdkRoot = 'C:\Program Files\Microsoft\jdk-17.0.20.8-hotspot'
$buildTools = Join-Path $sdkRoot 'build-tools\35.0.0'
$androidJar = Join-Path $sdkRoot 'platforms\android-35\android.jar'
$adb = Join-Path $sdkRoot 'platform-tools\adb.exe'
$enabledBefore = (& $adb -s $Serial shell settings get secure enabled_accessibility_services).Trim()
[xml]$settingsBefore = (& $adb -s $Serial shell run-as local.qaa.airtype cat shared_prefs/settings.xml) -join "`n"
. "$PSScriptRoot\..\adb-install.ps1"
$buildRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\.local-build\airtype-keys'))
$outputDir = Join-Path $buildRoot 'instrumentation'
New-Item -ItemType Directory -Force $outputDir,"$outputDir\classes","$outputDir\dex" | Out-Null
function Run-Native([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "$program failed: $LASTEXITCODE" }
}
Run-Native "$buildTools\aapt.exe" @('package','-f','-M',"$PSScriptRoot\AndroidManifest.xml",'-I',$androidJar,'-F',"$outputDir\unsigned.apk")
$shizukuJars = @(Get-ChildItem -LiteralPath "$buildRoot\shizuku-deps" -Filter '*.jar' | ForEach-Object FullName)
Run-Native "$jdkRoot\bin\javac.exe" @('-encoding','UTF-8','-source','8','-target','8','-Xlint:-options','-classpath',("$androidJar;$buildRoot\classes;" + ($shizukuJars -join ';')),'-d',"$outputDir\classes","$PSScriptRoot\TransferTest.java","$PSScriptRoot\ShizukuTest.java")
$classFiles = @(Get-ChildItem "$outputDir\classes" -Recurse -Filter '*.class' | ForEach-Object FullName)
$previousJavaHome = $env:JAVA_HOME
$previousPath = $env:PATH
try {
    $env:JAVA_HOME = $jdkRoot; $env:PATH = "$jdkRoot\bin;$env:PATH"
    Run-Native "$buildTools\d8.bat" (@('--lib',$androidJar,'--classpath',"$buildRoot\classes",'--output',"$outputDir\dex",'--min-api','29') + $classFiles)
    Push-Location "$outputDir\dex"
    try { Run-Native "$buildTools\aapt.exe" @('add',"$outputDir\unsigned.apk",'classes.dex') } finally { Pop-Location }
    Run-Native "$buildTools\zipalign.exe" @('-f','4',"$outputDir\unsigned.apk","$outputDir\aligned.apk")
    Run-Native "$buildTools\apksigner.bat" @('sign','--ks',"$buildRoot\local.keystore",'--ks-pass','pass:android','--key-pass','pass:android','--out',"$outputDir\tests.apk","$outputDir\aligned.apk")
    Install-AirTypeApk -Adb $adb -Serial $Serial -ApkPath "$outputDir\tests.apk" -PackageName 'local.qaa.airtype.tests'
    if ((& $adb -s $Serial shell getprop ro.product.manufacturer).Trim() -eq 'Xiaomi') {
        Run-Native $adb @('-s',$Serial,'shell','cmd','appops','set','local.qaa.airtype','10021','allow')
    }
    Run-Native $adb @('-s',$Serial,'reverse','tcp:15001','tcp:15001')
    $testClass = 'TransferTest'
    if ($ShizukuOnly) {
        $other = @($enabledBefore -split ':' | Where-Object { $_ -and $_ -notlike 'local.qaa.airtype/*' }) -join ':'
        $disabledValue = if ($other) { $other } else { 'null' }
        Run-Native $adb @('-s',$Serial,'shell','settings','put','secure','enabled_accessibility_services',$disabledValue)
        Start-Sleep -Milliseconds 500
        $testClass = 'ShizukuTest'
    }
    $result = & $adb -s $Serial shell am instrument -w "local.qaa.airtype.tests/local.qaa.airtype.$testClass" | Tee-Object -FilePath "$outputDir\result.txt"
    $result | Tee-Object -FilePath "$outputDir\result.txt"
    $expectedResult = if ($ShizukuOnly) { 'ShizukuTest: 7 checks passed' } else { 'TransferTest: 26 checks passed' }
    if ($LASTEXITCODE -ne 0 -or !($result -match $expectedResult)) { throw 'Device transfer checks failed' }
} finally {
    $env:JAVA_HOME = $previousJavaHome; $env:PATH = $previousPath
    & $adb -s $Serial reverse --remove tcp:15001 | Out-Null
    & $adb -s $Serial uninstall local.qaa.airtype.tests | Out-Null
    # Instrumentation stops the app process. Rebind only our service, preserving
    # all other enabled accessibility services.
    $other = @($enabledBefore -split ':' | Where-Object { $_ -and $_ -notlike 'local.qaa.airtype/*' }) -join ':'
    if ($enabledBefore -ne $other) {
        $disabledValue = if ($other) { $other } else { 'null' }
        & $adb -s $Serial shell settings put secure enabled_accessibility_services $disabledValue | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Unable to disable F9 service before rebinding' }
        # Settings changes are asynchronous. Let Android unbind and clear its
        # crashed-service entry before enabling our service again.
        Start-Sleep -Milliseconds 1000
    }
    $restoreValue = if ($enabledBefore) { $enabledBefore } else { 'null' }
    & $adb -s $Serial shell settings put secure enabled_accessibility_services $restoreValue | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Unable to restore accessibility services after device tests' }
    if ($enabledBefore -ne $other) {
        $restored = $false
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            $accessibility = (& $adb -s $Serial shell dumpsys accessibility) -join "`n"
            $bound = [regex]::Match($accessibility, '(?s)Bound services:\{(.*?)\}\s*Enabled services:').Groups[1].Value
            $crashed = [regex]::Match($accessibility, 'Crashed services:\{([^\r\n]*)').Groups[1].Value
            if ($bound -match 'label=F9 远程语音,' -and $crashed -notmatch 'local\.qaa\.airtype/') {
                $restored = $true
                break
            }
            Start-Sleep -Milliseconds 250
        }
        if (!$restored) { throw 'F9 accessibility service did not reconnect after device tests' }
        Write-Output 'F9 accessibility service verified: bound, no crashed entry'
    }
    [xml]$settingsAfter = (& $adb -s $Serial shell run-as local.qaa.airtype cat shared_prefs/settings.xml) -join "`n"
    foreach ($name in @('url','draft')) {
        $beforeValue = $settingsBefore.SelectSingleNode("/map/string[@name='$name']").InnerText
        $afterValue = $settingsAfter.SelectSingleNode("/map/string[@name='$name']").InnerText
        if ($beforeValue -ne $afterValue) { throw "Device checks did not restore $name" }
    }
    Write-Output 'Device settings verified: URL and draft restored'
}
