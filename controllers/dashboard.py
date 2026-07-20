# -*- coding: utf-8 -*-
"""Read-only JSON queue endpoint for the cohort dashboard's <crm-reachout> card.

See PLAN-cohort-dash.md. The dash page on https://workers.vc does a
credentialed fetch against the team's Odoo host; the Odoo session cookie
(SameSite=Lax, same registrable domain) rides along, and CORS response
headers are added explicitly here.

CORS is handled in the handlers rather than via ``@http.route(cors=...)``
because Odoo's ``cors=`` parameter sets a single fixed
``Access-Control-Allow-Origin`` value for all requests (all-or-nothing) —
it cannot echo one of several allowed origins, which is required when the
response also carries ``Access-Control-Allow-Credentials: true``.
"""
from urllib.parse import urlparse

from odoo import http
from odoo.http import request
from odoo.addons.auth_oauth.controllers.main import OAuthLogin

# Exact origins allowed to read the queue cross-origin, with credentials.
ALLOWED_ORIGINS = (
    "https://workers.vc",
    "https://www.workers.vc",
)

# Identical to views/outreach_runner_views.xml tree default_order.
QUEUE_ORDER = "outreach_pinned desc, outreach_seq asc, outreach_score desc"

# Identical to the Outreach Runner action domain.
QUEUE_DOMAIN = [("type", "=", "opportunity")]

DEFAULT_LIMIT = 5
MAX_LIMIT = 100


def _cors_headers():
    """CORS headers for the current request: echo the Origin only when it
    is exactly one of ALLOWED_ORIGINS. Always Vary on Origin so caches
    never serve one origin's headers to another."""
    headers = [("Vary", "Origin")]
    origin = request.httprequest.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        headers += [
            ("Access-Control-Allow-Origin", origin),
            ("Access-Control-Allow-Credentials", "true"),
        ]
    return headers


def _iso_utc(dt):
    """Odoo datetimes are naive UTC; emit unambiguous ISO 8601 with Z."""
    if not dt:
        return None
    return dt.replace(microsecond=0).isoformat() + "Z"


class OutreachDashboard(http.Controller):

    @http.route("/outreach/api/queue", type="http", auth="user",
                methods=["GET"])
    def queue(self, limit=None, **kwargs):
        """Top-of-queue leads for the reach-out card, plus count_to_reach
        (opportunities never yet contacted).

        Two tiers within the limit:
          1. the session user's own leads (user_id = uid), ordered like
             the Outreach Runner tree view (pinned desc, seq, score desc);
          2. fill from the rest of the team — unassigned leads first,
             then leads assigned to others — each group in the same tree
             order, so a pinned team lead still outranks unpinned ones
             within its group.

        count_to_reach spans the same universe as the queue (own +
        unassigned + assigned-to-others = every opportunity the caller
        may read). crm.lead ACLs and record rules apply unchanged — see
        README for the required group.
        """
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = DEFAULT_LIMIT
        limit = max(1, min(limit, MAX_LIMIT))

        Lead = request.env["crm.lead"]
        uid = request.env.uid
        # Tier 1: own leads.
        leads = Lead.search(QUEUE_DOMAIN + [("user_id", "=", uid)],
                            order=QUEUE_ORDER, limit=limit)
        # Tier 2 fill: unassigned first, then assigned to teammates.
        remaining = limit - len(leads)
        if remaining > 0:
            leads += Lead.search(
                QUEUE_DOMAIN + [("user_id", "=", False)],
                order=QUEUE_ORDER, limit=remaining)
            remaining = limit - len(leads)
        if remaining > 0:
            leads += Lead.search(
                QUEUE_DOMAIN + [("user_id", "!=", False),
                                ("user_id", "!=", uid)],
                order=QUEUE_ORDER, limit=remaining)

        count_to_reach = Lead.search_count(
            QUEUE_DOMAIN + [("last_outreach_date", "=", False)])

        # Never hardcode a domain: one addon serves many per-team hosts.
        host_url = request.httprequest.host_url  # ends with '/'
        payload = {
            "leads": [{
                "id": lead.id,
                "name": lead.name or "",
                "partner_name": lead.partner_id.name or lead.contact_name
                                or lead.partner_name or "",
                "email": lead.email_from or lead.partner_id.email or None,
                "linkedin": lead.partner_linkedin or None,
                "last_outreach_date": _iso_utc(lead.last_outreach_date),
                "outreach_score": lead.outreach_score,
                "outreach_score_reason": lead.outreach_score_reason or "",
                # Odoo 17 form deep link (the /odoo/<model>/<id> shape is
                # Odoo 18; it does not exist on 17).
                "url": "%sweb#id=%d&model=crm.lead&view_type=form"
                       % (host_url, lead.id),
            } for lead in leads],
            "count_to_reach": count_to_reach,
        }
        return request.make_json_response(payload, headers=_cors_headers())

    @http.route("/outreach/api/queue", type="http", auth="none",
                methods=["OPTIONS"])
    def queue_preflight(self, **kwargs):
        """CORS preflight. auth='none' because browsers send preflights
        without credentials; the handler touches no data."""
        headers = _cors_headers() + [
            ("Access-Control-Allow-Methods", "GET, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type, Accept"),
            ("Access-Control-Max-Age", "86400"),
        ]
        return request.make_response("", headers=headers, status=204)


class OutreachConnect(OAuthLogin):
    """Session-warming hop for the dash's SSO-once chain.

    Inherits auth_oauth's ``OAuthLogin`` (standard controller extension,
    no core patching) so the anonymous branch can reuse the stock
    ``list_providers``/``get_state`` auth-link building — same signing,
    same state shape as the login page's own OAuth buttons.
    """

    @http.route("/outreach/connect", type="http", auth="public",
                methods=["GET"])
    def outreach_connect(self, next=None, **kwargs):
        """GET /outreach/connect?next=<url>.

        Signed in: 302 to ``next`` — but only to the exact dash origins,
        any path (no open redirect); missing/invalid next lands on the
        Outreach Runner view.

        Anonymous: skip the login page when exactly one enabled OAuth
        provider exists on this DB — 302 straight into its auth flow,
        with the OAuth ``state`` carrying this same URL (path + query) as
        the post-auth redirect, so the browser comes back here with a
        session and the allowlisted external redirect then fires. Zero
        or multiple providers: normal login page, redirect preserved.
        """
        if request.session.uid:
            return self._connect_signed_in(next)
        return self._connect_anonymous()

    def _connect_signed_in(self, next_url):
        target = None
        if next_url:
            # urlparse strips ASCII tab/newline; redirect to the parsed
            # rebuild (geturl), never the raw parameter.
            parsed = urlparse(next_url.strip())
            # Exact scheme+host allowlist. Protocol-relative ("//host/…")
            # parses with an empty scheme, userinfo/port variants change
            # netloc — all rejected here. Host compare case-insensitive.
            origin = "%s://%s" % (parsed.scheme, parsed.netloc.lower())
            if origin in ALLOWED_ORIGINS:
                target = parsed.geturl()
        if target:
            return request.redirect(target, code=302, local=False)
        # Missing/invalid next: land in the addon's own tree view.
        action = request.env.ref(
            "crm_outreach_runner.action_outreach_runner",
            raise_if_not_found=False)
        return request.redirect(
            "/web#action=%d" % action.id if action else "/web", code=302)

    def _connect_anonymous(self):
        # This URL, path + query ('?next=...'), is what the browser must
        # come back to after auth. full_path always carries a trailing
        # '?' when there is no query — strip it.
        full_path = request.httprequest.full_path.rstrip("?")
        # get_state() (used by list_providers to sign each auth_link)
        # reads the post-auth redirect from request.params['redirect'] —
        # exactly how the login page builds its provider buttons. Set it
        # rather than reimplementing state building here.
        request.params["redirect"] = full_path
        providers = self.list_providers()
        if len(providers) == 1:
            # Silent hop: straight into the sole provider's auth flow.
            return request.redirect(
                providers[0]["auth_link"], code=302, local=False)
        # Zero or multiple providers: the user must see/choose — normal
        # login page with the same redirect preserved.
        return request.redirect_query(
            "/web/login", {"redirect": full_path}, code=302)
