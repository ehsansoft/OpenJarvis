#Requires -RunAsAdministrator
<#
  Fix-VoiceboxLoopback.ps1
  Hardens Voicebox server (127.0.0.1:17493) to loopback-only.
  Run from an elevated PowerShell:  powershell -ExecutionPolicy Bypass -File .\Fix-VoiceboxLoopback.ps1
  Backup: rules are exported to voicebox-firewall-rules.backup.json next to this script before changes.
#>

$ErrorActionPreference = 'Stop'
$rules = Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue |
    ForEach-Object {
        $f = $_
        try { $r = $f | Get-NetFirewallRule -ErrorAction Stop } catch { return }
        if ($r.DisplayName -like '*voicebox*') {
            [pscustomobject]@{
                Name        = $r.Name
                DisplayName = $r.DisplayName
                Direction   = $r.Direction
                Action      = $r.Action
                Enabled     = $r.Enabled
                Program     = $f.Program
                Profile     = $r.Profile
            }
        }
    }

$backupPath = Join-Path $PSScriptRoot 'voicebox-firewall-rules.backup.json'
$rules | ConvertTo-Json -Depth 4 | Set-Content -Path $backupPath -Encoding UTF8
Write-Host "Backed up $($rules.Count) voicebox rule(s) to $backupPath"

# 1) Remove inbound Allow rules that open Voicebox to the LAN
$removed = 0
foreach ($r in $rules) {
    if ($r.Direction -eq 'Inbound' -and $r.Action -eq 'Allow') {
        Remove-NetFirewallRule -Name $r.Name -ErrorAction Stop
        Write-Host "Removed inbound allow: $($r.DisplayName)"
        $removed++
    }
}
Write-Host "Removed $removed inbound allow rule(s)."

# 2) Add a loopback-only inbound allow (explicit, narrow)
New-NetFirewallRule -DisplayName 'voicebox-server-loopback' `
    -Direction Inbound -Action Allow -Enabled True `
    -Protocol TCP -LocalPort 17493 `
    -RemoteAddress 127.0.0.1,::1 `
    -Profile Any | Out-Null
Write-Host "Added loopback-only inbound allow for TCP 17493."

# 3) Verify: the service still binds 0.0.0.0, but LAN hosts can no longer connect.
#    Optional: restart Voicebox so the app can be reconfigured to --host 127.0.0.1 (preferred, app-side).
Write-Host ""
Write-Host "Done. Verify with:  Test-NetConnection 127.0.0.1 -Port 17493  (should succeed)"
Write-Host "Note: Voicebox itself still binds 0.0.0.0; firewall now blocks LAN. Restart the Voicebox app to bind loopback only."
