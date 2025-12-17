# Check if twine is installed
if (-not (Get-Command twine -ErrorAction SilentlyContinue)) {
    Write-Host "Installing twine..."
    pip install twine
}

# Upload to PyPI
Write-Host "--- Uploading to PyPI ---"
Write-Host "NOTE: When prompted for username, enter: __token__"
Write-Host "NOTE: When prompted for password, paste your PyPI token (pypi-...)"
Write-Host ""

twine upload dist/*

Write-Host "--- Done ---"
Pause
