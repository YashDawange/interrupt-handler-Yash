# tools/record_proof.ps1
# Helper script to produce reproducible terminal output for the interruption proof.
# Start a screen recorder (OBS / Game Bar) before running this script.

Write-Host "=== INTERRUPTION HANDLER PROOF RUN ==="
Write-Host "Timestamp: $(Get-Date -Format o)"

Write-Host "\nStep 1: Run demo script (generates proofs/interrupt_proof.log)" -ForegroundColor Cyan
python .\tools\demo_interrupt_proof.py
Write-Host "Demo complete. Showing proof log:\n" -ForegroundColor Cyan
Get-Content .\proofs\interrupt_proof.log

Write-Host "\nStep 2: Run integration tests (fast)" -ForegroundColor Cyan
pytest -q integration_tests

Write-Host "\nStep 3: Run focused runners (optional)" -ForegroundColor Cyan
Write-Host "Running test runner scripts to demonstrate behavior..."
python -u tests\run_interrupt_handler_tests.py
python -u tests\run_interrupt_integration_tests.py

Write-Host "\nFinished. Timestamp: $(Get-Date -Format o)" -ForegroundColor Green
Write-Host "The proof log is at proofs\interrupt_proof.log" -ForegroundColor Green

# Pause so the user can stop recording after a moment
Start-Sleep -Seconds 2
Write-Host "End of scripted run." -ForegroundColor Yellow
