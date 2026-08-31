# -*- coding: utf-8 -*-
"""Force the Odoo login page straight to LinkedTrust SSO.

Goal: a team CRM host (``crm-<slug>.workers.vc``) should never show the
email+password form. When someone lands on ``/web/login`` unauthenticated
and the database has exactly one enabled OAuth provider (LinkedTrust), we
302 straight into that provider's auth flow. If the LinkedTrust IdP session
cookie is already set (they signed in at the dashboard), the provider returns
silently and the browser lands back in Odoo signed in — no pause, no click.
Elm, which shares the host and reuses the Odoo ``session_id`` cookie, then
renders elm-over-Odoo for the org.

No core files are patched: this extends auth_oauth's ``OAuthLogin`` (which
itself extends web's ``Home``) and reuses ``list_providers`` so the auth_link
and OAuth ``state`` are built exactly as the stock login buttons build them.

Escape hatches (so the box is never locked out of local login):
  * ``/web/login?no_autologin=1`` — always renders the normal form.
  * an ``oauth_error`` on the URL (a failed/again SSO round-trip) renders the
    form instead of bouncing again, so a broken provider can't loop forever.
"""
from odoo import http
from odoo.http import request
from odoo.addons.auth_oauth.controllers.main import OAuthLogin


class OAuthLoginForceSSO(OAuthLogin):

    @http.route()
    def web_login(self, redirect=None, **kw):
        if (request.httprequest.method == "GET"
                and not request.session.uid
                and "no_autologin" not in kw
                and not kw.get("oauth_error")):
            # list_providers() signs each auth_link's OAuth state from
            # request.params['redirect'] — set our post-auth target there so
            # the browser comes back to it (default /web) with a session.
            request.params["redirect"] = redirect or "/web"
            providers = self.list_providers()
            if len(providers) == 1:
                return request.redirect(
                    providers[0]["auth_link"], code=302, local=False)
        return super().web_login(redirect=redirect, **kw)
