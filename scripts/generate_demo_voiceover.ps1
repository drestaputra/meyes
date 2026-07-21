param(
    [string]$OutputPath = "docs/media/demo/meyes-demo-voiceover.wav"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Speech

$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPath))
$outputDirectory = Split-Path -Parent $resolvedOutput
[System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null

$narration = @"
Hi, I'm Dresta, and I built MEYES: a local-first Windows application that explores hands-free computer control using only an ordinary webcam, eye gaze, and simple face gestures.

I was inspired by eye trackers used by professional gamers and streamers, but dedicated hardware can be expensive. I wanted to explore a more accessible alternative that could also support people who find a traditional mouse or keyboard difficult to use. MEYES is an assistive productivity prototype, not a medical device.

MediaPipe face and hand landmarks run locally. MEYES converts those observations into deliberate events: winks can trigger clicks, temple gestures can scroll, and cheek touches can be configured as additional actions. Camera frames are not intentionally stored or uploaded.

For gaze control, I replaced a confusing manual calibration with Smooth Pursuit. I follow one moving target while MEYES captures eye features continuously across nine screen regions. It checks spatial coverage and target-following correlation, fits a robust calibration mapper, and shows the result before any real pointer output is allowed.

Live Input is always an explicit choice. After confirmation, the accepted mapper can move the Windows pointer, while the configured gestures handle clicks and scrolling. The emergency shortcut immediately releases every owned input and returns MEYES to Safe Mode.

The architecture keeps camera observations, gesture intent, cursor candidates, user consent, and Windows Send Input execution in separate layers. That separation helped me test failures safely and prevent camera startup from silently enabling operating-system input.

I used Codex as my engineering collaborator throughout the project. With GPT-5.6, I planned the architecture, implemented and reviewed state machines, traced lifecycle bugs, generated regression tests, audited the native Windows safety boundary, and iterated on the interface and documentation. I made the final product, accessibility, safety, and evidence decisions.

Next, I want to validate MEYES with more users, webcams, lighting conditions, and accessibility needs. My goal is to make hands-free interaction more affordable using hardware people already own.
"@

$synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synthesizer.SelectVoice("Microsoft Hazel Desktop")
    # Hazel's default pace leaves little room below Devpost's three-minute cap.
    # Rate 1 stays clear and conversational while preserving a safe export margin.
    $synthesizer.Rate = 1
    $synthesizer.Volume = 100
    $synthesizer.SetOutputToWaveFile($resolvedOutput)
    $synthesizer.Speak($narration)
}
finally {
    $synthesizer.Dispose()
}

Write-Output $resolvedOutput
