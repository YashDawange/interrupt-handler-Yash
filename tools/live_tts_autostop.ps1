# tools/live_tts_autostop.ps1
# Plays TTS continuously and listens on the default microphone; if a command word is recognized (stop/wait/no)
# it cancels the speech immediately. Filler words are ignored while speaking.

Add-Type -AssemblyName System.Speech

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0

$paragraph = "In the year 1914, a great many events unfolded across the globe. The sun rose and set as always, but beneath the calm surface, strings of decisions and accidents set in motion movements of people and nations that would reshape the world. The details are complex, but the patterns echo through history, teaching us lessons about leadership, chance, and consequence."

# Split paragraph into sentence chunks for deterministic resume behavior
$chunks = $paragraph -split '(?<=[\.\?\!])\s+'  # keep sentences intact
$currentIndex = 0

# Setup recognizer
$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine ([System.Globalization.CultureInfo]::CurrentCulture)

# Build choices: filler and command words
# Filler/backchannel words
$filler = @('yeah','ok','okay','hmm','uh-huh','right','uhh','mm','uh')

# Command words and short phrases (include variants to improve matching)
$commands = @('stop','wait','no','cancel','hold', 'wait a second', 'wait a minute', 'wait please', 'wait now', 'hold on')

$choices = New-Object System.Speech.Recognition.Choices
$filler + $commands | ForEach-Object { [void]$choices.Add($_) }

$gb = New-Object System.Speech.Recognition.GrammarBuilder($choices)
$grammar = New-Object System.Speech.Recognition.Grammar($gb)
$recognizer.LoadGrammar($grammar)

# Bind event
# Global flag to indicate a command was detected so we can pause before restarting speech
$global:StopRequested = $false
$global:Paused = $false

$action = {
    param($sender, $e)
    $text = $e.Result.Text.ToLower()
    $confidence = $e.Result.Confidence
    Write-Host "[Recognizer] Heard: '$text' (confidence: $confidence)" -ForegroundColor Yellow

    # Match known command words/phrases robustly using substring checks
    # STOP: permanent cancel and stop restarting
    if ($text -match '\bstop\b') {
        Write-Host "[Recognizer] STOP detected -> cancelling speech and stopping" -ForegroundColor Red
        $global:StopRequested = $true
        $synth.SpeakAsyncCancelAll()
    }
    # WAIT: pause current speech, will resume from same point on resume keywords
    elseif ($text -match '\bwait\b|\bhold\b|\bhold on\b') {
        Write-Host "[Recognizer] WAIT detected -> pausing speech" -ForegroundColor Magenta
        try { $synth.Pause() } catch { }
        $global:Paused = $true
    }
    # Resume keywords while paused
    elseif ($global:Paused -and ($text -match '\bresume\b|\bcontinue\b|\bokay\b|\bstart\b')) {
        Write-Host "[Recognizer] Resume detected -> resuming speech" -ForegroundColor Cyan
        try { $synth.Resume() } catch { }
        $global:Paused = $false
    }
    # Other commands (e.g., cancel) handled here
    elseif ($text -match '\bno\b|\bcancel\b') {
        Write-Host "[Recognizer] CANCEL detected -> cancelling speech and stopping" -ForegroundColor Red
        $global:StopRequested = $true
        $synth.SpeakAsyncCancelAll()
    }
    else {
        Write-Host "[Recognizer] Filler detected -> ignoring while speaking" -ForegroundColor Green
    }
}

# Also listen to hypothesized partial results (early best-guess) so we can catch
# commands that may appear in partial recognition before final result.
$hypAction = {
    param($sender, $e)
    $text = $e.Result.Text.ToLower()
    Write-Host "[Recognizer][Hypothesis] $text" -ForegroundColor DarkYellow
    if ($text -match '\bstop\b') {
        Write-Host "[Recognizer][Hypothesis] STOP hypothesized -> cancelling speech" -ForegroundColor Red
        $global:StopRequested = $true
        $synth.SpeakAsyncCancelAll()
    }
    elseif ($text -match '\bwait\b|\bhold\b') {
        Write-Host "[Recognizer][Hypothesis] WAIT hypothesized -> pausing speech" -ForegroundColor Magenta
        try { $synth.Pause() } catch { }
        $global:Paused = $true
    }
    elseif ($global:Paused -and ($text -match '\bresume\b|\bcontinue\b|\bokay\b|\bstart\b')) {
        Write-Host "[Recognizer][Hypothesis] Resume hypothesized -> resuming speech" -ForegroundColor Cyan
        try { $synth.Resume() } catch { }
        $global:Paused = $false
    }
}

# Register event
$null = Register-ObjectEvent -InputObject $recognizer -EventName SpeechRecognized -Action $action -SourceIdentifier LiveTTS_Recognized
$null = Register-ObjectEvent -InputObject $recognizer -EventName SpeechHypothesized -Action $hypAction -SourceIdentifier LiveTTS_Hypothesized

# Set input and start recognizing
$recognizer.SetInputToDefaultAudioDevice()
$recognizer.RecognizeAsync([System.Speech.Recognition.RecognizeMode]::Multiple)

Write-Host "Live TTS + recognizer started. Press Ctrl+C to stop the script." -ForegroundColor Cyan

# Main loop: speak paragraph repeatedly; recognizer runs in background and will cancel on command
try {
    while ($true) {
        if ($global:StopRequested) { break }

        # If current index beyond chunks, wrap to start
        if ($currentIndex -ge $chunks.Length) { $currentIndex = 0 }

        $textToSpeak = $chunks[$currentIndex].Trim()
        if ([string]::IsNullOrWhiteSpace($textToSpeak)) {
            $currentIndex = ($currentIndex + 1)
            continue
        }

    Write-Host ("Speaking chunk {0}: '{1}' (will cancel if 'stop' detected)" -f $currentIndex, $textToSpeak) -ForegroundColor Cyan
        $synth.SpeakAsync($textToSpeak)

        # Wait until speaking finishes or is canceled; poll every 100ms
        while ($synth.State -eq [System.Speech.Synthesis.SynthesizerState]::Speaking) {
            Start-Sleep -Milliseconds 100
            # If StopRequested triggered during speaking, cancel and break
            if ($global:StopRequested) {
                $synth.SpeakAsyncCancelAll()
                break
            }
        }

        # Move to next chunk unless we're paused
        if (-not $global:Paused) {
            $currentIndex = ($currentIndex + 1)
        }
            # If StopRequested was set by a command handler, exit the loop and stop
            if ($global:StopRequested) {
                Write-Host "Stop requested -> exiting main loop." -ForegroundColor Red
                break
            }

            # If we're paused (recognized 'wait' / 'hold'), wait here until Resume or Stop
            while ($global:Paused -and -not $global:StopRequested) {
                Write-Host "Paused: waiting to resume... (current chunk: $currentIndex)" -ForegroundColor Magenta
                Start-Sleep -Milliseconds 200
            }

            # Small backoff before next speech when not paused/stopped
            Start-Sleep -Milliseconds 200
    }
} finally {
    Write-Host "Stopping recognizer and cleaning up..."
    $recognizer.RecognizeAsyncStop()
    Unregister-Event -SourceIdentifier LiveTTS_Recognized -ErrorAction SilentlyContinue
    $recognizer.Dispose()
}
