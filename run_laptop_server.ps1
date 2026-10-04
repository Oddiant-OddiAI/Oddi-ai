$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$oddiDataRoot = Join-Path $env:LOCALAPPDATA "OddiAI"
$oddiChatRoot = Join-Path $oddiDataRoot "ChatHistory"
$oddiSecretPath = Join-Path $oddiDataRoot "session.key"

New-Item -ItemType Directory -Path $oddiChatRoot -Force | Out-Null

if (-not (Test-Path -LiteralPath $oddiSecretPath -PathType Leaf)) {
    $oddiGeneratedSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($oddiGeneratedSecret)) {
        throw "Could not create the local session signing key."
    }
    [System.IO.File]::WriteAllText(
        $oddiSecretPath,
        $oddiGeneratedSecret.Trim(),
        [System.Text.Encoding]::ASCII
    )
}

$env:ODDI_LOCAL_ONLY_STORAGE = "1"
$env:ODDI_SECURE_COOKIES = "1"
$env:ODDI_CHAT_FILES_DIR = $oddiChatRoot
$env:FLASK_SECRET_KEY = [System.IO.File]::ReadAllText($oddiSecretPath).Trim()

python server.py
