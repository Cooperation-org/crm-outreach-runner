# -*- coding: utf-8 -*-
{
    "name": "CRM Outreach Runner",
    "version": "17.0.1.1.0",
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
    "depends": ["crm", "contacts", "utm", "mail"],
    "data": [
        "views/outreach_runner_views.xml",
    ],
    "installable": True,
    "application": False,
}
