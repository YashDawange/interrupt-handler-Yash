# Simple interactive TTS player for demo recording
# This script requires Windows SAPI TTS (built-in). It will speak a long paragraph repeatedly until you press ENTER.

Add-Type -AssemblyName System.speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0

$paragraph = "In the year 1914, a great many events unfolded across the globe. The sun rose and set as always, but beneath the calm surface, strings of decisions and accidents set in motion movements of people and nations that would reshape the world. The details are complex, but the patterns echo through history, teaching us lessons about leadership, chance, and consequence."

Write-Host "Interactive TTS player"
Write-Host "Press Enter to start speaking; press Enter again to stop. Repeat as needed for scenarios."

while ($true) {
    Read-Host "Press ENTER to start speaking (or type 'q' to quit)"
    if ($LASTEXITCODE -ne 0) { break }
    if ($input = Read-Host -Prompt "Type 'q' to quit or press ENTER to start" ) {
        if ($input -eq 'q') { break }
    }
    $async = $synth.SpeakAsync($paragraph)
    Write-Host "Speaking... press ENTER to cancel"
    Read-Host
    $synth.SpeakAsyncCancelAll()
    Write-Host "Stopped."
}

Write-Host "Player exiting."