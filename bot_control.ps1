param(
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action = "status"
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectName = Split-Path $ProjectRoot -Leaf
$BotScript = Join-Path $ProjectRoot "bot.py"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$CmdExe = Join-Path $env:SystemRoot "System32\cmd.exe"
$ManagedTag = "--codex-managed-bot=$($ProjectName -replace '[^A-Za-z0-9_-]', '_')"

function Get-BotProcesses {
    $allProcesses = Get-CimInstance Win32_Process
    $rootProcesses = $allProcesses | Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -like "*$ManagedTag*" -or
            $_.CommandLine -like "*$BotScript*"
        )
    }

    if (-not $rootProcesses) {
        return @()
    }

    $knownIds = [System.Collections.Generic.HashSet[int]]::new()
    $queue = [System.Collections.Generic.Queue[object]]::new()

    foreach ($process in $rootProcesses) {
        if ($knownIds.Add([int]$process.ProcessId)) {
            $queue.Enqueue($process)
        }
    }

    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        $children = $allProcesses | Where-Object { $_.ParentProcessId -eq $current.ProcessId }
        foreach ($child in $children) {
            if ($knownIds.Add([int]$child.ProcessId)) {
                $queue.Enqueue($child)
            }
        }
    }

    $allProcesses | Where-Object { $knownIds.Contains([int]$_.ProcessId) } | Sort-Object ProcessId -Unique
}

function Show-BotStatus {
    $processes = Get-BotProcesses
    if (-not $processes) {
        Write-Host "Bot is not running."
        return
    }

    Write-Host "Bot is running with these processes:"
    $processes | Select-Object ProcessId, Name, CommandLine | Format-Table -AutoSize
}

function Stop-Bot {
    $processes = Get-BotProcesses
    if (-not $processes) {
        Write-Host "Bot is already stopped."
        return
    }

    foreach ($process in $processes) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
            Write-Host "Stopped PID $($process.ProcessId)"
        } catch {
            Write-Warning "Could not stop PID $($process.ProcessId): $($_.Exception.Message)"
        }
    }
}

function Start-Bot {
    if (-not (Test-Path $PythonExe)) {
        throw "Python executable not found: $PythonExe"
    }

    if (-not (Test-Path $BotScript)) {
        throw "Bot script not found: $BotScript"
    }

    $runningProcesses = Get-BotProcesses
    if ($runningProcesses) {
        Write-Host "Bot is already running."
        Show-BotStatus
        return
    }

    Start-Process -FilePath $PythonExe -ArgumentList @($BotScript, $ManagedTag) -WorkingDirectory $ProjectRoot | Out-Null
    Start-Sleep -Seconds 2
    Show-BotStatus
}

switch ($Action) {
    "start" {
        Start-Bot
    }
    "stop" {
        Stop-Bot
    }
    "restart" {
        Stop-Bot
        Start-Bot
    }
    "status" {
        Show-BotStatus
    }
}
