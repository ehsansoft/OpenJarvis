#Requires -RunAsAdministrator
<#
  Fix-VoiceboxLoopback.ps1
  Hardens the Voicebox server (0.0.0.0:17493) so LAN hosts cannot reach it,
  while same-host (loopback) clients keep working.

  Loopback traffic never crosses Windows Firewall, and loopback addresses are
  not valid -RemoteAddress filter values. So the correct pattern is:
    1) remove any broad Allow rules for the app,
    2) add an explicit inbound BLOCK for TCP 17493 covering LAN subnets
       (Block wins over any future auto-created Allow rule).

  Run from an elevated PowerShell:
    powershell -ExecutionPolicy Bypass -File .\Fix-VoiceboxLoopback.ps1
  Backup: existing rules are exported to voicebox-firewall-rules.backup.json
  next to this script before changes.
#>

$ErrorActionPreference = 'Stop'
$rules = Get-NetFirewallRule -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like '*voicebox*' }
$backupPath = Join-Path $PSScriptRoot 'voicebox-firewall-rules.backup.json'
$rules | Select-Object Name, DisplayName, Direction, Action, Enabled, Profile |
    ConvertTo-Json -Depth 4 | Set-Content -Path $backupPath -Encoding UTF8
Write-Host "Backed up $($rules.Count) voicebox rule(s) to $backupPath"

# 1) Remove inbound Allow rules that open Voicebox to the LAN
$removed = 0
foreach ($r in $rules) {
    if ($r.Direction -eq 'Inbound' -and $r.Action -eq 'Allow') {
        Remove-NetFirewallRule -Name $r.Name -ErrorAction SilentlyContinue
        Write-Host "Removed inbound allow: $($r.DisplayName) [$($r.Name)]"
        $removed++
    }
}
Write-Host "Removed $removed inbound allow rule(s)."

# 2) Add an explicit LAN block for TCP 17493 (idempotent)
$existing = Get-NetFirewallRule -DisplayName 'voicebox-lan-block' -ErrorAction SilentlyContinue
if (-not $existing) {
    New-NetFirewallRule -DisplayName 'voicebox-lan-block' `
        -Direction Inbound -Action Block -Enabled True `
        -Profile Any `
        -Protocol TCP -LocalPort 17493 `
        -RemoteAddress 'LocalSubnet', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', 'fe80::/10' | Out-Null
    Write-Host "Added LAN block rule 'voicebox-lan-block' for TCP 17493."
} else {
    Write-Host "LAN block rule already present - skipping."
}

# 3) Verify: loopback must still succeed (the app binds 0.0.0.0; that is fine
#    because LAN inbound is now blocked by the explicit Block rule, which
#    outranks any Allow rule).
Write-Host ""
Write-Host "Verify locally:  Test-NetConnection 127.0.0.1 -Port 17493  (should succeed)"
Write-Host "Verify from LAN: Test-NetConnection <this-ip> -Port 17493    (should fail)"
Write-Host "Preferred app-side follow-up: configure Voicebox to bind 127.0.0.1 only."
