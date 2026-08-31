# Deployment Rule

Deployment, service restarts, database migrations against a live NetBox
instance, and any Git action that publishes or discards work (`git push`,
tags, releases, `git reset --hard`, force-push, history rewrites) are
high-blast-radius actions. **Never perform any of them automatically, in any
language, regardless of phrasing.**

This applies to phrases like "plugin i güncelle", "deploy et", "güncelle",
"sunucuya yükle", or any English equivalent ("deploy", "update the plugin",
"push to the server") — none of these are standing authorization. Treat every
request to deploy or update the live plugin as a request that requires a
fresh, explicit confirmation in the current conversation before any of the
following happen:

1. `git push` (to any remote, any branch) — including ordinary,
   non-destructive pushes, not just force-pushes.
2. Any state-changing connection (deploying, configuring, restarting) to a
   production/staging NetBox host, however it's initiated — there is no
   deploy script in this repo; deployment is a manual, ad hoc operation.
3. Restarting a NetBox service or container.
4. Running database migrations against a non-local NetBox instance.
5. Any destructive Git command (`reset --hard`, `clean -f`, force-push,
   branch deletion) anywhere, local or remote.
6. Creating a Git tag, a GitHub Release, or publishing a package (e.g. to
   PyPI) — no exceptions, regardless of any other standing authorization.

Before doing any of the above, state plainly what you are about to do (host,
branch, commands) and wait for the user to confirm in that same turn. A prior
approval earlier in the conversation, or in a past session, does not carry
forward to a new request.

This rule does not gate read-only inspection: `git status`/`log`/`diff`,
and read-only SSH commands against the deploy target (e.g. checking service
status or reading logs) may run freely — only the actions listed above need
approval.

See [`RELEASE_CHECKLIST.md`](../../RELEASE_CHECKLIST.md) for the release
checklist and the CI gates that enforce parts of it. `publish-pypi.yml`'s
`publish` job cannot run unless its own `verify` job passes, so PyPI
publication is gated even if a human creates the GitHub Release by hand —
but tagging and creating the release itself remain manual steps under this
rule.

Host identity, SSH access, and credentials for any deployment target live
outside this repo entirely (local SSH config, environment variables) and
must stay there — this rule's approval requirement does not depend on any
operational detail being documented in-repo.

This rule is the single authority for approval-sensitive git, deployment,
restart, migration, tag, and release actions. Source-level approval rules
that are not live/operational actions — bumping the plugin version,
changing NetBox/Python compatibility bounds, or editing an
already-released migration file — are coding rules, not deployment actions,
and live in `AGENTS.md` instead.
