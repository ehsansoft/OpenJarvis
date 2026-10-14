# Guided operations and connections

The local desk is `http://127.0.0.1:18080/control`. Open **Setup & connections**.
This branch adds guided setup; it is not a claim that every external account,
editor or site has completed human acceptance.

## What the words mean

A capability is an ability: searching notes, reading inventory, interpreting an
image or sending a notification. A skill is a repeatable procedure using those
abilities. For example, a weekly review turns your notes into priorities and
task proposals. It does not automatically schedule or send them.

| Skill | What you supply | What you get |
| --- | --- | --- |
| Check my workstation | Existing cached inventory | Space/tool summary and a next action |
| Plan my week | Selected notes pasted into chat | Three priorities and proposed next actions |
| Turn notes into tasks | Selected notes | Source-linked commitments, owners/dates and uncertainties |
| Research with evidence | Approved indexed sources | A concise note with sources and missing evidence |
| Investigate a bug | Error and selected code excerpt | Reproduction, likely cause and a focused test proposal |
| Prepare an editor task | One repository and objective | Scope, one implementer, one reviewer and acceptance commands |

The five new procedures are authored instruction-only workspace skills, not
unreviewed Hermes executable bundles. The original workstation brief remains
the sole directly runnable dashboard pipeline. Use the Setup workflow cards to
prepare a prompt; the private runtime retains restricted tool permissions.

## Telegram, without shell token literals

1. Create a bot in Telegram using **@BotFather → /newbot**.
2. In Setup, paste the token into **BotFather token**, then save it securely.
   The input clears; no token is returned in API responses or browser storage.
3. Click **Verify bot**, then send the bot `/start` in Telegram.
4. Click **Find my chat ID** while the owned bot is disabled. Select your own
   ID and save the allowed chats. This lookup refuses when a poller or webhook
   is configured, rather than creating a competing polling loop.
5. Click **Enable bot & restart**. This changes only the configured channel and
   restarts the one Jarvis owner. Token, nonempty allow-list and active private
   permissions are required. No recurring task is created.
6. Verify a reply from your allowed account; an unlisted account must receive
   none. Send `/notify telegram` to opt in. The test notification button sends
   one generic message only after its explicit confirmation.

Telegram is a cloud messaging channel even when inference is local. Ordinary
task notifications are generic and direct you to the local desk for details.
For a reminder, the title you approve is the message sent. Do not put secrets
or private project excerpts into a reminder title.

New credentials are encrypted with Windows CurrentUser DPAPI in
`D:\AI-Control\OpenJarvis\integration-secrets.json`. Existing legacy credential
stores are preserved. Stored integration secrets are injected on startup and
override the corresponding older value. Do not copy this user-bound encrypted
store to another Windows account as a backup strategy; it will not decrypt
there. Reports exclude credential stores, runtime config and private chunks.

Nara and optional Tavily/You.com/Serply keys use the same guided store. Local
Ollama models do not need a key. Saving a credential alone does not activate a
bot, new account connector, public query or recurring workflow.

## Tasks and delivery

Tasks offers **Local model prompt** and **Simple reminder**. A reminder repeats
the approved title without model generation. Both use the existing scheduler
and SQLite task history. Choose a future timestamp; the exact local/UTC time and
optional Telegram destination are reviewed before creating the one-shot task.

Notification retries use a bounded derived receipt file,
`notification-delivery.json`, driven by the existing scheduler's polling tick.
There is no second scheduler or Telegram poller. Task success and notification
delivery are separate records. Persisted run logs can recover queued delivery
after a restart; successful receipts suppress repeated delivery for that run.
Ambiguous Telegram network failures still cannot guarantee exactly-once display.
Retries stop after six failed attempts; inspect the delivery record.

Personal setup replays pending Telegram updates instead of silently dropping
them. This is not an offline delivery SLA or permission for side effects from
old messages. Private channel tools are restricted. Metadata supports
`misfire_policy=skip` and a grace window for overdue tasks; the existing default
remains run once. No recurring personal job is created by setup or verification.

## Knowledge

Setup previews an exact selection of three Jarvis document sources. The
approval includes content hashes; changed sources require another preview.
Indexing replaces only those sources in the existing FTS memory and creates a
rebuildable local vector cache. It does not scan D:, adopt projects or migrate
Project Intelligence schemas. The installed nomic embedder uses task prefixes,
small sequential batches and refuses silent overlength truncation.

Dashboard Research fuses lexical/vector results while the approved source hashes
and model digest match. Offline embeddings fall back to lexical results. Source
excerpts remain visible independently of model citation quality. Broader project
source selection still needs a concrete root, exclusions and review; do not
index a whole drive or choose a different backend by a single config toggle.

**Public research** previews the exact outbound query. It uses external search
and potentially Nara/free inference, without attaching local memory, chat
history or files. Missing search results remain an explicit no-source outcome.
Public model generation and answer quality require separate evaluation.

## Permissions and models

`security.private_operations=true` enables a default-deny private baseline with
named inventory and memory-read grants. It does not inherit the generic
network-fetch/memory-write baseline. Explicit UI actions such as approved
indexing/channel setup are operator actions, separate from model authority.
Editor clients retain their own local tool loop; use `local/code` for private
repositories and assign one writer per task. Keyed `/router/v1` routes now use
the same authentication boundary as the other APIs.

`jarvis model-lab --models local/fast,local/code` provides bounded synthetic
arithmetic, JSON, simple code-expression and source-attribution checks. It never
executes generated code or tools and does not start another scheduler. This
small suite is an initial comparison, not the complete Model Lab qualification
pack. Keep the installed 2B, 7B coder and nomic weights; no pull is required.

Future additions need specific inputs: a calendar account for real calendar
sync, an email account for inbox access, and a selected WAMP/site project for
site operations. Resume drafting and weekly planning can start with pasted
information and local models. Voice remains deferred. Credentials and editor
GUI/channel acceptance cannot be fabricated by fixtures.
