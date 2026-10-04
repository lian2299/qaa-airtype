# Shared by app updates and the temporary device-test APK. The confirmation
# watcher exists only while this install process is pending.
function Start-AirTypeAdbProcess([string]$Adb, [string[]]$Arguments) {
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $Adb
    $info.Arguments = ($Arguments | ForEach-Object {
        if ($_.Contains('"') -or $_.EndsWith('\')) { throw 'Unsupported ADB argument' }
        '"' + $_ + '"'
    }) -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = [Text.Encoding]::UTF8
    $info.StandardErrorEncoding = [Text.Encoding]::UTF8
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $info
    [void]$process.Start()
    return @{ Process = $process; Output = $process.StandardOutput.ReadToEndAsync(); Error = $process.StandardError.ReadToEndAsync() }
}

function Invoke-AirTypeAdb([string]$Adb, [string]$Serial, [string[]]$Arguments, [int]$TimeoutMs = 4000) {
    $pending = Start-AirTypeAdbProcess $Adb (@('-s', $Serial) + $Arguments)
    try {
        if (!$pending.Process.WaitForExit($TimeoutMs)) {
            $pending.Process.Kill()
            throw "ADB timed out: $($Arguments[0])"
        }
        $output = $pending.Output.GetAwaiter().GetResult()
        $errorText = $pending.Error.GetAwaiter().GetResult()
        if ($pending.Process.ExitCode -ne 0) { throw "ADB failed: $output $errorText" }
        return $output
    } finally { $pending.Process.Dispose() }
}

function Test-AirTypeInstallPrompt([string]$Adb, [string]$Serial) {
    $activity = Invoke-AirTypeAdb $Adb $Serial @('shell', 'dumpsys', 'activity', 'activities')
    return $activity -match '(?m)^\s*(?:topResumedActivity|mResumedActivity)[^\r\n]*com\.miui\.securitycenter/(?:com\.miui\.permcenter\.install\.|\.permcenter\.install\.)AdbInstallActivity\b'
}

function Install-AirTypeApk {
    param(
        [Parameter(Mandatory = $true)][string]$Adb,
        [Parameter(Mandatory = $true)][string]$Serial,
        [Parameter(Mandatory = $true)][string]$ApkPath,
        [Parameter(Mandatory = $true)][ValidateSet('local.qaa.airtype', 'local.qaa.airtype.tests')][string]$PackageName,
        [int]$TimeoutSeconds = 60
    )
    $ApkPath = (Resolve-Path -LiteralPath $ApkPath).Path
    $label = if ($PackageName -eq 'local.qaa.airtype.tests') { 'AirType 设备检查' } else { 'F9 远程语音' }
    $sdkRoot = Split-Path (Split-Path $Adb -Parent) -Parent
    $aapt = Join-Path $sdkRoot 'build-tools\35.0.0\aapt.exe'
    $badging = & $aapt dump badging $ApkPath
    if ($LASTEXITCODE -ne 0 -or !($badging -match "^package: name='$([regex]::Escape($PackageName))'")) {
        throw "APK does not match the requested AirType package: $PackageName"
    }
    $manufacturer = (Invoke-AirTypeAdb $Adb $Serial @('shell', 'getprop', 'ro.product.manufacturer')).Trim()
    $isXiaomi = $manufacturer -eq 'Xiaomi'
    if ($isXiaomi -and (Test-AirTypeInstallPrompt $Adb $Serial)) {
        throw 'Another USB installation confirmation is already open'
    }
    $pending = Start-AirTypeAdbProcess $Adb @('-s', $Serial, 'install', '--no-incremental', '-r', $ApkPath)
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $clicked = $false
    $dumpPath = '/data/local/tmp/airtype-install-confirm.xml'
    try {
        while (!$pending.Process.HasExited) {
            if ($timer.Elapsed.TotalSeconds -ge $TimeoutSeconds) { throw 'APK installation timed out' }
            if ($isXiaomi -and !$clicked -and (Test-AirTypeInstallPrompt $Adb $Serial)) {
                [void](Invoke-AirTypeAdb $Adb $Serial @('shell', 'rm', '-f', $dumpPath))
                [void](Invoke-AirTypeAdb $Adb $Serial @('shell', 'uiautomator', 'dump', '--compressed', $dumpPath))
                [xml]$ui = Invoke-AirTypeAdb $Adb $Serial @('shell', 'cat', $dumpPath)
                $nodes = @($ui.SelectNodes('//node[@package="com.miui.securitycenter"]'))
                $titles = @($nodes | Where-Object { $_.GetAttribute('text') -eq 'USB安装提示' })
                $labels = @($nodes | Where-Object { $_.GetAttribute('text') -eq $label })
                $buttons = @($nodes | Where-Object {
                    $_.GetAttribute('text') -eq '继续安装' -and $_.GetAttribute('enabled') -eq 'true' -and $_.GetAttribute('clickable') -eq 'true'
                })
                if ($titles.Count -ne 1 -or $labels.Count -ne 1 -or $buttons.Count -ne 1) {
                    throw "USB installation prompt does not match $label"
                }
                $bounds = $buttons[0].GetAttribute('bounds')
                if ($bounds -notmatch '^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$') { throw 'Install button bounds unavailable' }
                $x = [int](([int]$Matches[1] + [int]$Matches[3]) / 2)
                $y = [int](([int]$Matches[2] + [int]$Matches[4]) / 2)
                if (!$pending.Process.HasExited -and (Test-AirTypeInstallPrompt $Adb $Serial)) {
                    [void](Invoke-AirTypeAdb $Adb $Serial @('shell', 'input', 'tap', "$x", "$y"))
                    $clicked = $true
                    Write-Output "USB installation confirmed automatically: $label"
                }
            }
            Start-Sleep -Milliseconds 200
        }
        $output = $pending.Output.GetAwaiter().GetResult()
        $errorText = $pending.Error.GetAwaiter().GetResult()
        if ($pending.Process.ExitCode -ne 0 -or $output -notmatch '(?m)^Success\s*$') {
            throw "APK installation failed: $output $errorText"
        }
        Write-Output $output.Trim()
        $installed = (Invoke-AirTypeAdb $Adb $Serial @('shell', 'pm', 'path', $PackageName)).Trim()
        $paths = @($installed -split '\r?\n' | Where-Object { $_ -like 'package:*' })
        if ($paths.Count -ne 1) { throw 'Expected one installed AirType APK' }
        $devicePath = $paths[0].Substring('package:'.Length)
        $deviceHash = Invoke-AirTypeAdb $Adb $Serial @('shell', 'sha256sum', $devicePath)
        $localHash = (Get-FileHash -LiteralPath $ApkPath -Algorithm SHA256).Hash
        if ($deviceHash -notmatch "^$localHash\s") { throw 'Installed APK hash does not match the local build' }
        Write-Output "Installed APK SHA-256 verified: $PackageName"
    } finally {
        if (!$pending.Process.HasExited) { $pending.Process.Kill(); $pending.Process.WaitForExit() }
        $pending.Process.Dispose()
    }
}
