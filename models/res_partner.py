# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    linkedin = fields.Char(
        string="LinkedIn",
        help="LinkedIn profile or company page URL.",
    )
    bluesky = fields.Char(
        string="Bluesky",
        help="Bluesky profile URL or handle (e.g. name.bsky.social).",
    )
    discord = fields.Char(
        string="Discord",
        help="Discord invite/community URL or handle.",
    )
    social_ids = fields.One2many(
        "res.partner.social", "partner_id", string="Other Socials",
        help="Anywhere else this person posts or can be reached: Mastodon, "
             "Substack, Signal, a personal site. LinkedIn and Bluesky have "
             "their own fields because outreach runs on those two; this open "
             "list takes the rest with no code change.",
    )


class ResPartnerSocial(models.Model):
    _name = "res.partner.social"
    _description = "Contact social link"
    _order = "sequence, id"

    partner_id = fields.Many2one(
        "res.partner", string="Contact", required=True,
        ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    platform = fields.Char(
        string="Platform", required=True,
        help="Free text on purpose: Mastodon, Substack, Signal, whatever "
             "they actually use.")
    url = fields.Char(
        string="Link or handle", required=True)
