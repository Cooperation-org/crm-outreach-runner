# CRM Outreach Runner

An Odoo 17 module that gives you a fast, prioritized outreach queue over your
CRM campaigns.

Pick a campaign and work the list top-to-bottom by priority. For each contact,
without opening the card, you see the key labels and click straight through to
**email**, **LinkedIn**, **Discord**, or **website**. One click on **Contacted**
stamps the time and logs a chatter note, so the queue reorders itself.

Available as a dense **tree** view and a **kanban** view, under **CRM →
Outreach Runner**.

Built entirely on the Odoo addon system; no core files are modified. It adds two
structured fields to contacts (LinkedIn, Discord) plus read-only related/display
fields and a `last_outreach_date` field on `crm.lead`, and one action button.

## Install

The module already lives in the addons path (`/opt/odoo/custom-addons`). To
install it:

1. In Odoo, enable developer mode (Settings → Developer Tools) if not already on.
2. Go to **Apps → Update Apps List** and confirm.
3. Search for **CRM Outreach Runner** and click **Install**.

Then open **CRM → Outreach Runner**.

## Dashboard queue API

`GET /outreach/api/queue?limit=5` — `auth='user'` (Odoo session cookie),
JSON. Feeds the cohort dashboard's reach-out card (see
`PLAN-cohort-dash.md`). Response:

```json
{"leads": [{"id": 7, "name": "Pilot kitchens intro",
            "partner_name": "R. Okafor", "email": "…",
            "linkedin": "…", "last_outreach_date": null,
            "outreach_score": 85,
            "outreach_score_reason": "tier+45 known+25 reachable+10",
            "url": "https://…/web#id=7&model=crm.lead&view_type=form"}],
 "count_to_reach": 3}
```

- Only opportunities (`type = 'opportunity'`), in **two tiers within the
  limit**:
  1. the session user's **own** leads (`user_id` = the caller), ordered
     like the Outreach Runner tree view: `outreach_pinned desc,
     outreach_seq asc, outreach_score desc`;
  2. if fewer than `limit`, a fill from the rest of the team —
     **unassigned** leads first, then leads **assigned to others** —
     each group in that same tree order (so a pinned team lead still
     outranks unpinned ones within its group, and an unassigned lead
     beats an assigned-to-someone-else lead even at equal score).
- `count_to_reach` = opportunities with no `last_outreach_date`, counted
  across the **whole queue universe** (own + unassigned +
  assigned-to-others — everything the caller's record rules let them
  read), independent of `limit`.
- `limit` defaults to 5, max 100; invalid values fall back to the default.
- `last_outreach_date` is ISO 8601 UTC (`…Z`) or `null`.
- `url` is built from the request host — one addon serves every per-team
  Odoo host.
- CORS: the handler echoes the `Origin` header only when it is exactly
  `https://workers.vc` or `https://www.workers.vc`, with
  `Access-Control-Allow-Credentials: true`, and answers `OPTIONS`
  preflight on the same route (`auth='none'` — preflights carry no
  credentials). All other origins get no CORS grant.

## Session-warming hop: `GET /outreach/connect?next=<url>`

For the dash's SSO-once chain (sign in once on the dash, every card's
app session gets warmed by chained redirects). `auth='user'`:

- **Anonymous** hit → Odoo bounces through
  `/web/login?redirect=/outreach/connect?next=…` (the query string is
  preserved — `redirect` carries the full path). Stock `auth_oauth`
  passes that same `redirect` through the OAuth round-trip (`get_state`),
  so after "Log in with LinkedTrust" the browser lands back on
  `/outreach/connect?next=…` with a fresh Odoo session.
- **Authenticated** → 302 to `next`, but only when `next` parses
  (urllib) to scheme+host exactly `https://workers.vc` or
  `https://www.workers.vc` — any path is fine; other origins,
  protocol-relative (`//…`), userinfo/port variants, and non-http
  schemes all fall through. Missing/invalid `next` → 302 to the
  Outreach Runner tree view (`/web#action=…`). No open redirect.

**Residual friction:** the stock Odoo 17 login page still requires one
click on the "Log in with LinkedTrust" OAuth button — `auth_oauth` has
no stock URL that jumps straight to the provider (each provider's
`auth_link` is built per-request in `OAuthLogin.list_providers`, with
the `state` carrying the redirect). The clean, supported path to remove
that click — if wanted later — is a small controller in this addon
inheriting `OAuthLogin` that calls `list_providers()` and 302s to the
sole enabled provider's `auth_link`; no core patching. Not built yet.

### Access requirements (who can call it)

The endpoint reads `crm.lead` as the session user, so normal Odoo access
control applies:

- **Required group: `sales_team.group_sale_salesman_all_leads`** ("Sales /
  User: All Documents"). The fill tier shows teammates' and unassigned
  leads, so the all-documents record rule is needed. It implies
  `sales_team.group_sale_salesman` (which carries the crm.lead read ACL)
  and `base.group_user`, so the caller must be an **internal** user;
  portal users have no `crm.lead` access. Cohort users provisioned via
  OIDC must be created as internal users with this group.
- With only `sales_team.group_sale_salesman` ("User: Own Documents
  Only") the endpoint still responds, but its record rule
  (`user_id in (uid, False)`) silently hides teammates' leads — the
  fill tier degrades to unassigned leads only, and `count_to_reach`
  shrinks the same way. Not the intended team queue.

## `<crm-reachout>` web component

`static/src/embed/crm-reachout.js` — vanilla JS custom element, no
dependencies, served unauthenticated at
`{origin}/crm_outreach_runner/static/src/embed/crm-reachout.js`
(standard Odoo module static serving).

```html
<script src="https://crm-<team>.workers.vc/crm_outreach_runner/static/src/embed/crm-reachout.js"></script>
<crm-reachout data-up="https://crm-<team>.workers.vc" data-limit="5"></crm-reachout>
```

- `data-up` (required): the team CRM origin. The component fetches
  `{data-up}/outreach/api/queue` with `credentials: 'include'`.
- `data-limit` (optional): rows to show, default 5.
- Rows: contact name, a one-line why (`outreach_score_reason`, or
  "no reply in N days" once contacted), and an "open" link to the lead
  form.
- Non-200, network error, or empty queue → renders nothing and sets
  `hidden`. Never placeholder data.
- On success it sets `data-count="<count_to_reach>"` and dispatches a
  bubbling `crm-reachout-loaded` CustomEvent
  (`detail: {count_to_reach, shown}`) for the host page's
  "CRM · N to reach" pill.
- All DOM writes are `textContent`/attribute based; lead links are checked
  to be http(s) URLs.

## Tests

`tests/test_queue_endpoint.py` (`HttpCase`, tagged `post_install`) covers
auth, ordering, `count_to_reach`, the `limit` param, CORS echo for
allowed origins only, and preflight. Run against a scratch database only
— never a live one:

```bash
odoo-bin -c <conf> -d <fresh_test_db> --http-port=<free_port> \
    --workers=0 --max-cron-threads=0 --stop-after-init \
    --test-enable --test-tags /crm_outreach_runner -i crm_outreach_runner
```

## License

This module is licensed under the **MIT License** (see [LICENSE](LICENSE)).

The team's **NoHarmV0** do-no-harm license
(https://github.com/CivicWorks/noharm-license) is used for our larger shared
repositories; this smaller standalone module uses plain MIT.
