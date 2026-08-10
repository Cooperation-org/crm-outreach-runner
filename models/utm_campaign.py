# -*- coding: utf-8 -*-
from odoo import fields, models


class UtmCampaign(models.Model):
    _inherit = "utm.campaign"

    # The columns this campaign tracks and no other one does. A sponsor
    # campaign wants "Ask" and "Path in"; a mentor campaign wants "Skill" and
    # "Hours/mo". One fixed field set forces all of that into a Notes blob,
    # which is the thing a spreadsheet does better and why people leave.
    #
    # Stock CRM already ships the machinery for this, keyed to the sales team
    # (crm.team.lead_properties_definition). Everyone here is on one team and
    # what actually varies is the campaign, so the definition lives here
    # instead. See the field on crm.lead for the repoint.
    lead_properties_definition = fields.PropertiesDefinition("Outreach Columns")
