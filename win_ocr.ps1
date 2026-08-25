# Windows Built-in OCR script for Ranique Store Toolkit
# Uses Windows.Media.Ocr to perform offline local OCR on PNG/JPG files.

param (
    [string]$ImagePath
)

try {
    # Force loading of WinRT metadata namespaces in PowerShell 5.1
    [void][System.Type]::GetType('Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime')
    [void][System.Type]::GetType('Windows.Storage.FileAccessMode, Windows.Storage, ContentType=WindowsRuntime')
    [void][System.Type]::GetType('Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType=WindowsRuntime')
    [void][System.Type]::GetType('Windows.Media.Ocr.OcrEngine, Windows.Media, ContentType=WindowsRuntime')
    [void][System.Type]::GetType('Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime')

    # Load Assembly for SystemExtensions
    Add-Type -AssemblyName System.Runtime.WindowsRuntime -ErrorAction SilentlyContinue

    # Helper function to await WinRT async operations in PowerShell
    function Await-WinRT ($asyncOp, $resultType) {
        $methods = [System.WindowsRuntimeSystemExtensions].GetMethods()
        # Find ONLY the Generic Method Definition of AsTask
        $asTask = $methods | Where-Object { 
            $_.Name -eq 'AsTask' -and 
            $_.IsGenericMethodDefinition -and
            $_.GetParameters().Length -eq 1
        } | Select-Object -First 1

        if (-not $asTask) {
            throw "AsTask generic method not found."
        }

        $generic = $asTask.MakeGenericMethod($resultType)
        $task = $generic.Invoke($null, @($asyncOp))
        $task.Wait()
        return $task.Result
    }

    # Resolve absolute path
    $absPath = [System.IO.Path]::GetFullPath($ImagePath)

    # 1. Get file
    $op1 = [Windows.Storage.StorageFile]::GetFileFromPathAsync($absPath)
    $file = Await-WinRT $op1 ([Windows.Storage.StorageFile])

    # 2. Open stream
    $op2 = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
    $stream = Await-WinRT $op2 ([Windows.Storage.Streams.IRandomAccessStream])

    # 3. Create decoder
    $op3 = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
    $decoder = Await-WinRT $op3 ([Windows.Graphics.Imaging.BitmapDecoder])

    # 4. Get software bitmap
    $op4 = $decoder.GetSoftwareBitmapAsync()
    $softwareBitmap = Await-WinRT $op4 ([Windows.Graphics.Imaging.SoftwareBitmap])

    # Initialize OCR engine (uses user system languages)
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if (-not $engine) {
        # Fallback to English
        $lang = [Windows.Globalization.Language]::new("en-US")
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
    }

    if (-not $engine) {
        Write-Error "Could not initialize Windows OCR engine."
        exit 1
    }

    # 5. Recognize text
    $op5 = $engine.RecognizeAsync($softwareBitmap)
    $ocrResult = Await-WinRT $op5 ([Windows.Media.Ocr.OcrResult])

    # Output text
    Write-Output $ocrResult.Text
}
catch {
    Write-Error "OCR failed: $_"
    exit 1
}
