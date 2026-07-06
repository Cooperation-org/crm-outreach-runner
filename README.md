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

## License

This module is licensed under the **MIT License** (see [LICENSE](LICENSE)).

The team's **NoHarmV0** do-no-harm license
(https://github.com/CivicWorks/noharm-license) is used for our larger shared
repositories; this smaller standalone module uses plain MIT.
