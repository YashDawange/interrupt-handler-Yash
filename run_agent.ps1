# Load environment variables from .env file and run the test agent

# Read .env file and set environment variables
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.+)$') {
        $key = $matches[1]
        $value = $matches[2]
        [Environment]::SetEnvironmentVariable($key, $value, 'Process')
        Write-Host "Set $key"
    }
}

Write-Host "`nStarting agent with backchannel filtering enabled...`n"

# Run the agent
python test_interruption_agent.py dev
