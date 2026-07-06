# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    linkedin = fields.Char(
        string="LinkedIn",
        help="LinkedIn profile or company page URL.",
    )
    discord = fields.Char(
        string="Discord",
        help="Discord invite/community URL or handle.",
    )
