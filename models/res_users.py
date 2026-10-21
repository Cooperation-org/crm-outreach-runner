from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _auth_oauth_signin(self, provider, validation, params):
        # Stock auth_oauth matches only (provider, oauth_uid). A person whose user
        # was made by invite, or under another capitalization of their email, gets
        # a second user created on first SSO sign-in. Before that happens, bind the
        # provider id to the one existing user whose login is that email.
        oauth_uid = validation.get("user_id")
        email = (validation.get("email") or "").strip()
        if oauth_uid and email and validation.get("email_verified") is not False:
            known = self.sudo().search_count([("oauth_uid", "=", oauth_uid), ("oauth_provider_id", "=", provider)])
            if not known:
                match = self.sudo().with_context(active_test=False).search([("login", "=ilike", email)])
                if len(match) == 1 and match.active:
                    match.write({"oauth_provider_id": provider, "oauth_uid": oauth_uid})
        return super()._auth_oauth_signin(provider, validation, params)
