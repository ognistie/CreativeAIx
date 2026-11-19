param(
    [Parameter(Mandatory = $true)][string]$ImagePath,
    [string]$Language
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStreamWithContentType, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType=WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods().Where({
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
    $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Wait-WinRt($Operation, [Type]$Result) {
    $task = $asTask.MakeGenericMethod($Result).Invoke($null, @($Operation))
    $task.GetAwaiter().GetResult()
}

$engine = if ($Language) {
    [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new($Language))
} else {
    [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if ($null -eq $engine) {
    [Console]::WriteLine('[]')
    exit 0
}

$file = Wait-WinRt ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = Wait-WinRt ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
try {
    $decoder = Wait-WinRt ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $transform = [Windows.Graphics.Imaging.BitmapTransform, Windows.Graphics.Imaging, ContentType=WindowsRuntime]::new()
    $limit = [Windows.Media.Ocr.OcrEngine]::MaxImageDimension
    $ratio = [Math]::Min(1, $limit / [double][Math]::Max($decoder.PixelWidth, $decoder.PixelHeight))
    $transform.ScaledWidth = [Math]::Max(1, [Math]::Floor($decoder.PixelWidth * $ratio))
    $transform.ScaledHeight = [Math]::Max(1, [Math]::Floor($decoder.PixelHeight * $ratio))
    $scaleX = $decoder.PixelWidth / $transform.ScaledWidth
    $scaleY = $decoder.PixelHeight / $transform.ScaledHeight
    $bitmap = Wait-WinRt ($decoder.GetSoftwareBitmapAsync(
        [Windows.Graphics.Imaging.BitmapPixelFormat, Windows.Graphics.Imaging, ContentType=WindowsRuntime]::Bgra8,
        [Windows.Graphics.Imaging.BitmapAlphaMode, Windows.Graphics.Imaging, ContentType=WindowsRuntime]::Ignore,
        $transform,
        [Windows.Graphics.Imaging.ExifOrientationMode, Windows.Graphics.Imaging, ContentType=WindowsRuntime]::IgnoreExifOrientation,
        [Windows.Graphics.Imaging.ColorManagementMode, Windows.Graphics.Imaging, ContentType=WindowsRuntime]::DoNotColorManage
    )) ([Windows.Graphics.Imaging.SoftwareBitmap])
    try {
        $result = Wait-WinRt ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $lines = @(
            foreach ($line in $result.Lines) {
                $words = @(
                    foreach ($word in $line.Words) {
                        $box = $word.BoundingRect
                        @{
                            text = $word.Text
                            bbox = @(($box.X * $scaleX), ($box.Y * $scaleY),
                                     (($box.X + $box.Width) * $scaleX), (($box.Y + $box.Height) * $scaleY))
                        }
                    }
                )
                @{text = $line.Text; words = $words}
            }
        )
        [Console]::WriteLine((ConvertTo-Json -InputObject $lines -Depth 5 -Compress))
    } finally {
        $bitmap.Dispose()
    }
} finally {
    $stream.Dispose()
}
