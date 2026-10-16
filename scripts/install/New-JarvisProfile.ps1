# New-JarvisProfile.ps1 - FIX: fresh Hermes profiles always get the gateway provider.
# Usage: .\New-JarvisProfile.ps1 -Name myagent [-CloneFrom coder] [-Description "..."]
param(
  [Parameter(Mandatory)][string]$Name,
  [string]$CloneFrom = 'coder',
  [string]$Description = 'Jarvis fleet profile'
)
$ErrorActionPreference = 'Stop'
$hermes = "$env:LOCALAPPDATA\hermes\bin\hermes.cmd"
$ref    = "$env:LOCALAPPDATA\hermes\profiles\coder\config.yaml"
$dst    = "$env:LOCALAPPDATA\hermes\profiles\$Name\config.yaml"
& $hermes profile create $Name --clone-from $CloneFrom --description $Description
if (-not (Test-Path $dst)) { throw "profile config missing: $dst" }
if ((Get-Content $dst -Raw) -match 'openjarvis') {
  "gateway provider already present (cloned from $CloneFrom)"
} else {
  $py = 'D:\AI-Tools\OpenJarvis\.venv\Scripts\python.exe'
  $inject = @'
import sys, yaml
ref_p, dst_p = sys.argv[1], sys.argv[2]
blk = (yaml.safe_load(open(ref_p, encoding="utf-8")) or {}).get("providers", {}).get("openjarvis")
if not blk:
    sys.exit("reference profile has no openjarvis provider")
cfg = yaml.safe_load(open(dst_p, encoding="utf-8")) or {}
cfg.setdefault("providers", {})["openjarvis"] = blk
yaml.safe_dump(cfg, open(dst_p, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
print("gateway provider injected")
'@
  $tmp = "$env:TEMP\inject_provider.py"
  $inject | Set-Content $tmp -Encoding UTF8
  & $py $tmp $ref $dst
}
"OK: profile '$Name' ready"
