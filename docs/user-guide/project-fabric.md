# Local Project Fabric

The project fabric is a metadata-first inventory of local development projects.
It is designed for machines that contain many unrelated repositories and sites,
where blindly indexing an entire drive would be slow, noisy, and unsafe.

## Configure a project root

On Windows, set the projects section in config.toml:

    [projects]
    root = "D:\\Projects"
    registry_path = "D:\\AI-Control\\registry\\projects.json"
    max_depth = 5

Then run:

    jarvis projects scan

Or scan an explicit root without writing the registry:

    jarvis projects scan D:\\Projects --max-depth 5 --no-write --json

The scanner recognizes Git repositories and common project markers such as
pyproject.toml, package.json, composer.json, Cargo.toml, go.mod, WordPress
plugin headers, theme headers, and wp-config.php.

It prunes dependency, cache, build, upload, backup, hidden, and temporary
directories before traversal. Discovery is intentionally separate from RAG
ingestion: finding a project does not upload or index its source code.

## NaraRouter

NaraRouter is available as a first-class optional engine. Keep its API key in
the environment:

    $env:NARAROUTER_API_KEY = "..."

Configure the endpoint without embedding the secret:

    [engine.nararouter]
    host = "https://router.bynara.id"

When credentials are present, ordinary engine discovery can retrieve the live
/v1/models roster. Without credentials, the engine remains dormant and does
not perform an unauthenticated remote health probe.

The local project fabric and live model roster are foundations for later
adaptive routing, coding workers, scheduled research, and benchmark-driven
promotion or demotion of local and remote models.
