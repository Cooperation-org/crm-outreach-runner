# -*- coding: utf-8 -*-
from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # Display/edit the contact's links straight from the outreach row.
    partner_linkedin = fields.Char(
        related="partner_id.linkedin", string="LinkedIn", readonly=False)
    partner_discord = fields.Char(
        related="partner_id.discord", string="Discord", readonly=False)
    partner_website = fields.Char(
        related="partner_id.website", string="Website", readonly=False)
    partner_category_ids = fields.Many2many(
        related="partner_id.category_id", string="Contact Tags")
    partner_notes = fields.Html(
        related="partner_id.comment", string="Notes")

    last_outreach_date = fields.Datetime(
        string="Last Outreach", index=True,
        help="When outreach was last logged from the Outreach Runner.")

    def action_mark_contacted(self):
        """One-click from the runner: stamp the time and log a chatter note."""
        for lead in self:
            lead.last_outreach_date = fields.Datetime.now()
            lead.message_post(body="Outreach sent (via Outreach Runner).")
        return True
