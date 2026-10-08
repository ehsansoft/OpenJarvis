# Read-only project review (Phase 1A)

These commands inspect the existing scanner registry. They do not confirm
projects, allocate permanent ids, migrate SQLite, index source code or change
project folders. The scanner's `active` classification remains a proposal.
Canonical adoption and manifest writes require later reviewed plans.

Run from the OpenJarvis checkout in PowerShell:

```powershell
$env:OPENJARVIS_HOME = 'D:\AI-Control\OpenJarvis'
uv run --no-sync jarvis projects audit
uv run --no-sync jarvis projects review --role active --limit 10
```

The audit reports the scanner snapshot SHA-256, role counts and duplicate ids
or paths. Windows paths compare without case sensitivity, including mixed
slashes. Review records retain the scanner id and a pending status; canonical
ids are null. Git remotes and other arbitrary scanner fields are excluded from
the review output. The JSON output contains local project names and paths.

For the next batch, copy `snapshot_sha256` from the first result and use its
`next_offset`. A refreshed scanner snapshot is rejected when the expected hash
does not match, so a review cannot silently refer to a different inventory.

```powershell
uv run --no-sync jarvis projects review --role active --limit 10 --offset 10 --expected-sha256 '<snapshot_sha256>'
```

Unknown scanner versions, invalid roles and invalid/relative project paths fail
validation. Collisions are reported without merging records. No apply or batch
confirmation command exists in this slice.

Validate an optional manifest at the fixed `.openjarvis/project.toml` location:

```powershell
uv run --no-sync jarvis projects manifest-preview 'D:\Projects\YourProject'
```

An absent manifest produces a private default preview without creating a
directory. Existing manifests must be UTF-8 TOML, at most 64 KiB, schema version
1 and migration version 0. Unknown fields/versions fail closed. Manifest paths
through links or Windows junctions are refused. URLs containing credentials,
queries or fragments are refused. Knowledge patterns stay relative to the
project root. Declared commands are argv lists and are never executed.

Only explicitly present fields override inference, including empty lists.
The service accepts an inference dictionary for that merge; the current CLI
validates the manifest alone, without scanning files or loading reviewed facts.
Mandatory exclusions are shown separately and cannot be removed by manifest
includes or an empty exclusion list. The preview creates no knowledge index;
resolved-path and content checks belong to the future approved indexer.

Contracts and the review example are in
`configs/openjarvis/schemas/project-manifest-v1.schema.json`,
`configs/openjarvis/schemas/canonical-project-v1.schema.json` and
`configs/openjarvis/examples/project-manifest-v1.toml`. The canonical contract
is proposed and has no live database implementation yet. Do not copy the
example into a project without reviewing its exact contents first.

The architecture, approval boundaries and next slices are documented in
[`EHSAN_PERSONAL_KNOWLEDGE_PHASE1.md`](../EHSAN_PERSONAL_KNOWLEDGE_PHASE1.md).
