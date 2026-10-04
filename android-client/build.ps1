$ErrorActionPreference = 'Stop'
$sdkRoot = $env:ANDROID_HOME
if (!$sdkRoot) { $sdkRoot = 'C:\Android\Sdk' }
$jdkRoot = 'C:\Program Files\Microsoft\jdk-17.0.20.8-hotspot'
$buildTools = Join-Path $sdkRoot 'build-tools\35.0.0'
$androidJar = Join-Path $sdkRoot 'platforms\android-35\android.jar'
$outputDir = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\.local-build\airtype-keys'))
New-Item -ItemType Directory -Force $outputDir,"$outputDir\classes","$outputDir\dex","$outputDir\tests" | Out-Null
$expectedBuildRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\.local-build'))
foreach ($subdir in @('classes','dex','tests')) {
    $cleanPath = [IO.Path]::GetFullPath((Join-Path $outputDir $subdir))
    if (!$cleanPath.StartsWith($expectedBuildRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Build cleanup escaped the local build directory' }
    Get-ChildItem -LiteralPath $cleanPath -Force | Remove-Item -Recurse -Force
}
function Run-Native([string]$program, [string[]]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "$program failed: $LASTEXITCODE" }
}
Run-Native "$jdkRoot\bin\javac.exe" @('-encoding','UTF-8','-d',"$outputDir\tests", "$PSScriptRoot\KeySession.java", "$PSScriptRoot\KeySessionTest.java")
Run-Native "$jdkRoot\bin\java.exe" @('-cp',"$outputDir\tests",'local.qaa.airtype.KeySessionTest')
Run-Native "$buildTools\aapt.exe" @('package','-f','-M',"$PSScriptRoot\AndroidManifest.xml",'-S',"$PSScriptRoot\res",'-I',$androidJar,'-F',"$outputDir\unsigned.apk")
$sourceFiles = @(Get-ChildItem $PSScriptRoot -Filter '*.java' | Where-Object Name -NotLike '*Test.java' | ForEach-Object FullName)
Run-Native "$jdkRoot\bin\javac.exe" (@('-encoding','UTF-8','-source','8','-target','8','-Xlint:-options','-classpath',$androidJar,'-d',"$outputDir\classes") + $sourceFiles)
$classFiles = @(Get-ChildItem "$outputDir\classes" -Recurse -Filter '*.class' | ForEach-Object FullName)
# d8/apksigner use JAVA_HOME; set it only in this build process.
$previousJavaHome = $env:JAVA_HOME
$previousPath = $env:PATH
try {
    $env:JAVA_HOME = $jdkRoot
    $env:PATH = "$jdkRoot\bin;$env:PATH"
    Run-Native "$buildTools\d8.bat" (@('--lib',$androidJar,'--output',"$outputDir\dex",'--min-api','29') + $classFiles)
    Push-Location "$outputDir\dex"
    try { Run-Native "$buildTools\aapt.exe" @('add',"$outputDir\unsigned.apk",'classes.dex') } finally { Pop-Location }
    Run-Native "$buildTools\zipalign.exe" @('-f','4',"$outputDir\unsigned.apk", "$outputDir\aligned.apk")
    $keyPath = "$outputDir\local.keystore"
    if (!(Test-Path $keyPath)) {
        Run-Native "$jdkRoot\bin\keytool.exe" @('-genkeypair','-keystore',$keyPath,'-storepass','android','-keypass','android','-alias','local','-keyalg','RSA','-keysize','2048','-validity','10000','-dname','CN=Phone Server Local')
    }
    Run-Native "$buildTools\apksigner.bat" @('sign','--ks',$keyPath,'--ks-pass','pass:android','--key-pass','pass:android','--out',"$outputDir\airtype-keys.apk", "$outputDir\aligned.apk")
    Run-Native "$buildTools\apksigner.bat" @('verify',"$outputDir\airtype-keys.apk")
} finally { $env:JAVA_HOME = $previousJavaHome; $env:PATH = $previousPath }
Write-Output "$outputDir\airtype-keys.apk"
