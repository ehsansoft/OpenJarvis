"""Plain-language workflows and honest prerequisites for the local desk."""

WORKFLOWS = [
    {
        "id": "workstation-brief",
        "title": "Check my workstation",
        "description": "Find available space, installed tools and service readiness.",
        "requirements": "Cached inventory; check observation dates.",
        "prompt": (
            "Use the workstation-brief skill. Summarize my cached worksta"
            "tion evidence and list one useful next action. Do not change"
            " files."
        ),
    },
    {
        "id": "weekly-review",
        "title": "Plan my week",
        "description": (
            "Turn notes you paste into priorities and a realistic next-action list."
        ),
        "requirements": (
            "Paste selected notes. No calendar account or automatic scheduling."
        ),
        "prompt": (
            "Use the weekly-review skill. Help organize the notes I will "
            "paste into three priorities and next actions. Propose remind"
            "ers without creating them."
        ),
    },
    {
        "id": "document-to-actions",
        "title": "Turn notes into tasks",
        "description": "Extract commitments, owners and dates from selected notes.",
        "requirements": (
            "Paste the notes; task creation stays a separate reviewed action."
        ),
        "prompt": (
            "Use document-to-actions. Extract task proposals from my next"
            " message. Quote their source sentences, mark uncertain dates"
            " and do not create schedules."
        ),
    },
    {
        "id": "grounded-note",
        "title": "Research with evidence",
        "description": (
            "Answer from local sources and say when an answer is unsupported."
        ),
        "requirements": "Indexed sources. Use Research to see the retrieved excerpts.",
        "prompt": (
            "Use grounded-note. Search the indexed runbook for the comple"
            "ted drive cleanup and cite the evidence. Separate facts from"
            " suggestions."
        ),
    },
    {
        "id": "bounded-debugging",
        "title": "Investigate a bug",
        "description": (
            "Use an error and a small code excerpt to propose a reproducible fix."
        ),
        "requirements": (
            "Paste selected code and error. Let one editor own the actual change."
        ),
        "prompt": (
            "Use bounded-debugging. I will paste an error and selected co"
            "de. Explain reproduction, likely cause and a focused regress"
            "ion test. Do not edit or execute anything."
        ),
    },
    {
        "id": "editor-handoff",
        "title": "Prepare an editor task",
        "description": (
            "Give OpenCode, Kilo or Codex a clear task, scope and test checklist."
        ),
        "requirements": (
            "Select one repository and one implementer. Private editor mo"
            "del: local/code."
        ),
        "prompt": (
            "Use editor-handoff. Help write one task contract for my chos"
            "en editor: objective, repository, allowed files, acceptance "
            "tests and review evidence. Ask for missing scope; do not cha"
            "nge project records."
        ),
    },
]

EXPLANATIONS = {
    "local/fast": (
        "Short private conversations and summaries using your installed small model."
    ),
    "local/code": (
        "Explain code and propose bounded changes. The editor control"
        "s file edits and tests."
    ),
    "local/research": (
        "Summarize selected local evidence; source quality still needs review."
    ),
    "local/vision": (
        "Understand a selected image with your installed local vision model."
    ),
    "embeddings": (
        "Turn text into vectors so related notes can be found even wi"
        "th different wording."
    ),
    "memory": (
        "Search the documents you explicitly indexed; this is not automatic learning."
    ),
    "scheduler": "Run a reviewed task at a chosen time and keep its execution history.",
    "telegram": (
        "Chat or receive generic notifications through Telegram after setup and opt-in."
    ),
    "hermes": (
        "A source of reusable procedures; tools and resources must be"
        " audited before import."
    ),
    "nara-free-pool": (
        "Additional provider models for public material; availability"
        " and limits change."
    ),
    "scoped-project-memory": (
        "Find relevant project documents after reviewing exactly what will be indexed."
    ),
    "opencode": (
        "A coding client for one assigned task. It uses Jarvis's editor model endpoint."
    ),
    "kilo": "A coding client in VS Code, with its own permissions and test workflow.",
    "mcp": (
        "A way to expose selected tools to an editor. A connection is"
        " separate from tool permission."
    ),
}
