# -*- coding: utf-8 -*-
{
    "name": "CRM Outreach Runner",
    "version": "17.0.1.6.0",
    "summary": "Fast, prioritized outreach queue over your CRM campaigns — "
               "clickable email / LinkedIn / Discord, one-click \"contacted\".",
    "description": """
CRM Outreach Runner
===================

A single dense view for *doing* outreach fast. Pick a campaign, work the list
top-to-bottom by priority, and for each contact — without opening the card —
see the key labels and click straight through to email, LinkedIn, Discord, or
website. One click logs "contacted" (timestamp + chatter note) so the queue
reorders itself.

Built entirely on the Odoo addon system; no core files are modified. Adds two
structured fields to contacts (LinkedIn, Discord) and a set of read-only
related/display fields plus one action button to ``crm.lead``.
""",
    "author": "Cooperation.org / LinkedTrust",
    "website": "https://github.com/Cooperation-org/crm-outreach-runner",
    "license": "Other OSI approved licence",
    "category": "Sales/CRM",
    # auth_oauth: /outreach/connect inherits OAuthLogin to reuse the
    # stock auth_link/state building for the silent SSO hop.
    "depends": ["crm", "contacts", "utm", "mail", "auth_oauth"],
    "data": [
        "security/ir.model.access.csv",
        "views/outreach_runner_views.xml",
        "views/social_links_views.xml",
    ],
    "assets": {
        # Backend only, so the bar never appears on the login page — and never
        # for anyone who is not signed in.
        "web.assets_backend": [
            "crm_outreach_runner/static/src/embed/cohort-nav-mount.js",
        ],
    },
    "installable": True,
    "application": False,
}
