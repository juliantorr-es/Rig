# PublicOps Architecture

Status: FUTURE

`PublicOps` is Rig's future public-facing project operations layer. It exists to manage collaboration surfaces without surrendering canonical authority to GitHub, Google Forms, Google Sheets, or any other external SaaS.

## Doctrine

External systems are interfaces, projections, intake surfaces, and publication targets.

Rig remains the governed local control plane and owns the state machine.

## Scope

PublicOps will cover:

- public intake
- public tracker projection
- public publication
- debug bundle generation and export
- sync observation and receipt capture
- redaction and consent enforcement

PublicOps is future-facing documentation and contract design only. It does not define live integrations yet.

## Provider Families

These names describe future interfaces and contracts. They are not runtime implementations by themselves.

### PublicIntakeProvider

- `GoogleFormsProvider`
- `GitHubIssueIntakeProvider`
- `GitHubDiscussionIntakeProvider`

### PublicTrackerProvider

- `GoogleSheetsTrackerProvider`
- `GitHubProjectsTrackerProvider` only if GitHub Projects support becomes explicitly desirable and documented

### PublicPublisherProvider

- `GitHubIssuePublisher`
- `GitHubDiscussionPublisher`
- `GoogleSheetsPublisher`
- `ReleaseNotesPublisher` if release-note publication becomes a supported projection target

### DebugBundleProvider

- `LocalDebugBundleGenerator`
- `RedactionPolicy`
- `ConsentGate`
- `AttachmentManifest`

## Canonical Normalized Objects

These normalized objects are Rig-owned. External provider payloads are adapted into these shapes before they are allowed to affect canonical state.

### PublicIntakePacket

- `id`
- `source_provider`
- `source_external_id`
- `submitted_at`
- `submitter_contact_optional`
- `kind`: `bug_report | feature_request | debug_bundle | compatibility_report | benchmark_submission | question_response | other`
- `title`
- `description`
- `environment`
- `command`
- `expected_behavior`
- `actual_behavior`
- `attachments`
- `redaction_status`
- `consent_status`
- `classification`
- `dedupe_fingerprint`
- `canonical_workspace_id_optional`
- `canonical_issue_id_optional`
- `receipt_ids`
- `status`

### PublicTrackerRow

- `canonical_id`
- `public_id`
- `title`
- `kind`
- `area`
- `severity`
- `status`
- `source`
- `github_issue_url_optional`
- `rig_workspace_id_optional`
- `last_updated`
- `public_notes`

### DebugBundleManifest

- `bundle_id`
- `rig_version`
- `platform`
- `generated_at`
- `included_files`
- `redacted_files`
- `excluded_files`
- `redaction_warnings`
- `consent_required`
- `consent_recorded`
- `checksum`

### PublicSyncReceipt

- `sync_id`
- `provider`
- `operation`
- `canonical_input_id`
- `external_target_id`
- `diff_summary`
- `result`
- `timestamp`
- `actor`
- `warnings`

## Lifecycle

PublicOps lifecycle is Rig-owned.

- `submitted`
- `needs_review`
- `accepted`
- `duplicate`
- `needs_more_info`
- `ready_for_agent`
- `in_progress`
- `fixed_pending_validation`
- `released`
- `closed`
- `rejected`

External lifecycle states in GitHub or Google are projections or mappings, not canonical state.

## Intake Flow

The intended flow is:

Public user or contributor
→ Google Form / GitHub Issue / GitHub Discussion
→ Rig Intake Adapter
→ Normalized `PublicIntakePacket`
→ Validation / redaction / dedupe / classification
→ Rig Workspace / Issue / Proposal / Receipt
→ GitHub Issue / Google Sheet / public status update

The source system is only the ingress surface. Rig decides whether the intake becomes canonical work.

## Debug Bundle Flow

The intended future CLI flow is:

- `rig debug bundle`
- `rig debug bundle --redact`
- `rig debug bundle --redact --preview`
- `rig debug bundle --redact --open-form`

No debug bundle may be submitted or exported through an external provider without:

- deterministic redaction pass
- manifest generation
- user-visible preview or summary
- explicit consent record
- checksum
- receipt

Logs, paths, environment variables, git remotes, command history, and config files may contain secrets or personal information and must be treated as sensitive inputs.

## Authority Rules

- Rig canonical state MUST NOT be overwritten directly by GitHub or Google state.
- External updates enter Rig as intake events or sync observations.
- All external writes produce receipts.
- All destructive external updates require explicit policy support.
- External IDs are references, not primary keys.
- Provider tokens are capabilities, not identities.
- OAuth grants must be scoped, revocable, encrypted at rest, and optional for local operation.
- Google Sheets may be edited by humans, but Rig must reconcile those edits through validation before they affect canonical state.
- GitHub Issues may be edited by maintainers, but Rig treats those edits as observations unless accepted into canonical state.
- Google Forms responses are intake packets, not tasks by themselves.

## OAuth and Provider Scope Guidance

Future auth strategy should follow least-privilege and connector-scoped access.

- GitHub should prefer GitHub App semantics over broad OAuth App semantics where possible.
- Google integration should request OAuth scopes only for the specific surfaces it needs:
  - Forms response access
  - Drive file access if needed
  - Sheets read/write
  - Docs read/write only when explicitly required
- Auth must be connector-scoped and not required for core Rig operation.
- No provider token should be stored in project files.
- Secrets must not be included in receipts or debug bundles.

## Future CLI Surface

These command shapes are proposed only.

- `rig public init`
- `rig public sync`
- `rig public intake list`
- `rig public intake import`
- `rig public intake triage`
- `rig public tracker publish`
- `rig public tracker diff`
- `rig public github sync`
- `rig public google sync`
- `rig debug bundle`
- `rig debug bundle --redact --preview`
- `rig debug bundle --open-form`

The command family should be added only if Rig has an approved future-facing registration seam for it. No live provider integration is implied by this document.

## Placement Guidance

PublicOps should live alongside the existing future architecture docs rather than inside the current runtime path:

- architecture and doctrine: `docs/architecture/`
- public command expectations: `docs/dev/rig/`
- release and proof artifacts: `docs/proofs/`

If code is added later, it should enter through inert, typed seams and remain subordinate to Rig's existing workspace, receipt, proposal, and validation systems.
