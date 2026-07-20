# Cohort Dash — cross-repo plan (crm-outreach-runner copy)

2026-07-19. One of six coordinated plan files, one per repo:
`workers.vc`, `govkit`, `amebo`, `marten`, `crm-outreach-runner`, `earnkit` —
each named `PLAN-cohort-dash.md` at the repo root. The **Architecture**
section is identical in all six; the **This repo** section is per-repo.
Work in parallel; commit and push regularly; each repo only implements its
own section and consumes the others' contracts as written here.

## Architecture (shared across all six repos)

**Goal.** Land accelerator teams on a real dashboard: the v3 design
(demos.linkedtrust.us/workersvc-design/dashboard.html) grown out of the
existing `/dash/` page, plus a mentor view, so invites can go out now.

**Principle** (amebo docs/DASHBOARD.md): the dash is an orientation
surface, not a workspace. Every fact lives in the tool that owns it; the
dash renders read-only cards and every card expands into the owning app
(Marten, GovKit, CRM, amebo). No fact is copied into the dash's DB.

**Mechanism: web components, one bundle per owning app.** Following the
existing amebo embed pattern (`amebo/embed/amebo.js`): each app ships a
vanilla-JS custom-elements bundle as a static file from its own origin.
The dash page includes the scripts and mounts the tags. No build step, no
framework, no shared library.

**Auth: SSO + same-site cookies + CORS allowlist.** Everything runs under
`*.workers.vc`, and every app logs in via LinkedTrust OIDC
(live.linkedtrust.us). Because all hosts share the registrable domain
`workers.vc`, each app's `SameSite=Lax` session cookie IS sent on a
credentialed fetch from the dash page — the only missing layer is CORS
response headers. So each app: (1) allowlists `https://workers.vc` (and
`https://www.workers.vc`) for CORS **with credentials**, scoped to its
JSON API paths; (2) authenticates component fetches with its normal
session cookie (`credentials: 'include'`). A component whose upstream
returns 401/403 renders nothing (the existing dash behavior) — signed-out
or non-member visitors just see fewer cards. Never render placeholder or
demo data.

**Org scoping.** The dash is per-team: `workers.vc/dash/<org-slug>/`.
The org slug is the shared tenant key across GovKit (`Org.slug`), amebo
(`organizations.slug` / instance orgs), Taiga (project slug), and Odoo
(DB `crm-<slug>_vc`, host `crm-<slug>.workers.vc`) — provisioned together by
`earnkit/playbooks/add-team.yml`. Components take the org via a
`data-org` attribute where the owning app needs it (GovKit), or resolve
it server-side from the authenticated identity (amebo — org is never a
component attribute there).

**Card → owner map** (v3 design → who ships the component):

| Card | Owner | Component | Expand target |
|---|---|---|---|
| The pie | GovKit | `<govkit-pie>` | `dash.workers.vc/o/<org>/pie/` |
| Earned on tasks (hours feed) | GovKit | `<govkit-feed>` | `dash.workers.vc/o/<org>/pie/` |
| Curriculum tracker | GovKit (genesis checklist) | `<govkit-checklist>` | `dash.workers.vc/o/<org>/` |
| Tasks to do | GovKit (tasksources → Taiga) | `<govkit-tasks>` | `marten.workers.vc/p/<org>/board` |
| Money | GovKit (projects app) | `<govkit-money>` | `dash.workers.vc/o/<org>/projects/` |
| Reach out (CRM) | crm-outreach-runner (Odoo) | `<crm-reachout>` | `crm-<org>.workers.vc` Outreach Runner |
| Ask amebo | amebo (exists) | `<amebo-ask>` | `amebo.workers.vc` |
| Campaigns / GTM board | amebo (`/api/organizations/board`) | `<amebo-board>` (phase 2) | org context repo / CRM / Taiga links |
| Whiteboard | amebo (phase 2) | — | amebo whiteboard |
| Tools row, faces, launch card | workers.vc server-side | — | — |

**Mentors.** No new role system. A mentor is a person with GovKit
`Membership` rows in multiple orgs (the accelerator org plus team orgs).
`GET dash.workers.vc/api/v1/accounts/me/` already returns
`memberships[{org_slug, org_name, role}]` — the dash uses it (via the
same CORS/session mechanism) to render an org switcher and a mentor
overview listing every org the viewer belongs to. Mentor booking info
(calendar_url/time_level) already lives in workers.vc's ledger.

**Deploys.** Push to main deploys workers.vc / govkit / amebo / marten
via GitHub Actions → `/opt/earnkit/bin/update-*` (service restart). Odoo
addons and nginx/env changes deploy by ansible run (see earnkit plan).

**Sequencing.** GovKit's CORS + bundle is the critical path (4 of the 8
cards); everything else proceeds in parallel against these contracts, and
each card goes live the moment its owner ships.

---

## This repo: crm_outreach_runner — the reach-out card's JSON + component

The v3 "Reach out — from the CRM" card shows the top few people to
contact with a one-line why and a link. This addon already computes
exactly that ranking (pin/drag > rubric `outreach_score`); what's missing
is a browser-consumable read endpoint and the component.

### Current state (verified 2026-07-19)

- `crm.lead` carries the ranking: `outreach_pinned`, `outreach_seq`,
  stored `outreach_score` 0-100 + `outreach_score_reason`
  (models/crm_lead.py:25-72); `last_outreach_date` stamps "Contacted";
  related partner fields (linkedin/discord/website/notes).
- No controllers/HTTP routes at all in this addon; card-scanner's only
  route is a redirect. All access today is Odoo web-client RPC,
  `auth='user'`.
- Per-team Odoo: one DB per team (`crm-<slug>_vc`, `dbfilter=^%d_vc$`) keyed on host
  `crm-<slug>.workers.vc`; OIDC provider row per DB (add-team.yml).
  Odoo session cookie is host-scoped and SameSite=Lax → rides on
  credentialed same-site fetches from workers.vc.

### Status (2026-07-19)

Items 1-4 below are DONE (see README.md for the full endpoint +
component contract). Implementation notes / deltas from the sketches:

- The example `url` shape `/odoo/crm.lead/7` is Odoo 18 URL style and
  does not exist on Odoo 17 — the endpoint emits the working 17 deep
  link `{host}/web#id=<id>&model=crm.lead&view_type=form`, still built
  from `request.httprequest.host_url`.
- Endpoint scope matches the Outreach Runner action: opportunities only
  (`type = 'opportunity'`); `count_to_reach` counts them regardless of
  `limit`. `limit` clamps to 1..100, invalid → 5.
- **Ordering (user decision 2026-07-20): two tiers within the limit.**
  Own leads first (`user_id = uid`, tree order: pinned desc, seq,
  score desc), then a fill from the rest of the team — unassigned
  before assigned-to-others, each group in the same tree order.
  `count_to_reach` spans the same universe as the queue (own +
  unassigned + others = all opportunities the caller may read).
- OPTIONS preflight is a second route on the same path with
  `auth='none'` (browsers send preflights without credentials, so an
  `auth='user'` OPTIONS route can never succeed); it touches no data.
- Static path verified against `odoo/http.py` (`Application.statics` /
  `_serve_static`): every installable module's `static/` dir is served
  pre-auth at `/<module>/static/<path>`. Note `statics` is a
  `lazy_property` per worker — a service restart (which the ansible
  module-upgrade deploy does anyway) is needed before a *newly added*
  static dir is served.
- **ACL (item 3)**: required group is
  `sales_team.group_sale_salesman_all_leads` ("Sales / User: All
  Documents") — the fill tier reads teammates' and unassigned leads, so
  the all-documents record rule is needed. It implies
  `sales_team.group_sale_salesman` (the group carrying the crm.lead
  read ACL, `crm.access_crm_lead`) and `base.group_user` — cohort users
  provisioned via OIDC must be **internal** users with that group
  (portal users have no crm.lead ACL). With only own-docs salesman the
  endpoint still answers but the record rule silently hides teammates'
  leads (fill degrades to unassigned only).
- **Added (SSO-once scope, 2026-07-19): `GET /outreach/connect?next=<url>`**
  — the dash's session-warming hop. Authenticated: 302 to `next` only
  when scheme+host is exactly one of the two dash origins (urllib-
  parsed; protocol-relative, userinfo, port and scheme variants
  rejected); otherwise 302 to the Outreach Runner tree view.
- **Silent OAuth hop (approved follow-up, built 2026-07-20).** The
  route is `auth='public'` on a controller inheriting auth_oauth's
  `OAuthLogin` (addon now depends on `auth_oauth`; no core patches).
  Anonymous + exactly one enabled `auth.oauth.provider` on the DB →
  302 straight to that provider's `auth_link`; zero or multiple →
  `/web/login?redirect=/outreach/connect?next=…` fallback. State
  round-trip reuses stock code, not a reimplementation: the handler
  sets `request.params['redirect'] = httprequest.full_path` (path
  *including* the `?next=` query) and calls the inherited
  `list_providers()`, whose `get_state` reads exactly that param —
  the same mechanism the login page's provider buttons use — so
  `/auth_oauth/signin` returns the browser to
  `/outreach/connect?next=…` with a session, and the allowlisted
  external redirect fires. Provider discovered from the DB, return URL
  built from the request; nothing hardcoded.
- Tests: `tests/test_queue_endpoint.py` (HttpCase, `post_install`) —
  auth redirect, two-tier ordering (own first; unassigned before
  assigned-to-others in the fill; pin+seq beats score within a group),
  shape, count_to_reach over the full universe, limit truncation across
  tiers, CORS echo allowlist, preflight, and the connect hop (anonymous
  + one enabled provider → 302 to the provider auth URL, asserting
  client_id/redirect_uri and the state's redirect round-trip to
  /outreach/connect?next=…; zero/multiple providers → login fallback
  with redirect preserved; authenticated: valid next 302s,
  invalid/trick next stays local).
  Test user carries the required `group_sale_salesman_all_leads`.
  Not yet executed on the shared
  dev VM: the live `odoo` PG role on VM 100 has no CREATEDB and no
  scratch-DB path exists here, so they run in the earnkit/ansible flow
  (command in README).

### Work items (in order)

1. **Queue endpoint** — new `controllers/dashboard.py`:
   `GET /outreach/api/queue?limit=5`, `type='http'`, `auth='user'`,
   JSON response, CORS for the dash origins. Odoo's `@http.route`
   `cors=` parameter is all-or-nothing (`Access-Control-Allow-Origin`
   single value) and must pair with credentials — set headers explicitly
   in the handler: echo `Origin` when it is in
   `{https://workers.vc, https://www.workers.vc}`,
   `Access-Control-Allow-Credentials: true`, and answer OPTIONS
   preflight on the same route. Response:
   ```json
   {"leads": [{"id": 7, "name": "Pilot kitchens intro",
               "partner_name": "R. Okafor", "email": "…",
               "linkedin": "…", "last_outreach_date": null,
               "outreach_score": 85,
               "outreach_score_reason": "hot; known contact; reachable",
               "url": "https://crm-<team>.workers.vc/odoo/crm.lead/7"}],
    "count_to_reach": 3}
   ```
   Ordering identical to the tree view: pinned desc, seq, score desc.
   `count_to_reach` = leads with `last_outreach_date = False` (drives
   the "CRM · 3 to reach" pill on the dash). Build `url` from
   `request.httprequest.host_url` — never hardcode a domain.
2. **Web component** — `static/src/embed/crm-reachout.js`, vanilla JS,
   amebo-embed conventions, registered as `<crm-reachout>`:
   attributes `data-up` (the team's CRM origin) + optional
   `data-limit`; fetch `{data-up}/outreach/api/queue` with
   `credentials:'include'`; non-200 or empty → render nothing and set
   `hidden`. Rows: name, why (score reason or "no reply in N days" from
   last_outreach_date), action link to the lead `url`. Must be loadable
   from a plain `<script src="{up}/crm_outreach_runner/static/src/embed/crm-reachout.js">`
   (Odoo serves module static files at that path without auth).
3. **ACL check**: the endpoint reads `crm.lead` as the session user —
   confirm a plain portal/internal cohort user provisioned via OIDC has
   read access to leads (internal user of the team DB). Document the
   required group here.
4. **README**: document the endpoint + component contract.

### Deployment note

This addon deploys via ansible playbook re-run (no push-to-main CI):
after pushing, the operator runs the earnkit odoo role / module upgrade
(`-u crm_outreach_runner` on each team DB) — see earnkit plan.

### Definition of done

From `https://workers.vc` with a session on `crm-<team>.workers.vc`:
`<crm-reachout data-up="https://crm-<team>.workers.vc">` renders the top
leads with working links into the Odoo lead form; signed-out visitors
see nothing; the queue order matches the Outreach Runner tree view.
