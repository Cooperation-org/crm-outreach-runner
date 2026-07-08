# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # --- contact links shown/edited straight from the outreach row ---
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

    # --- ordering: manual layer (always wins) + rubric layer ---
    outreach_pinned = fields.Boolean(
        string="Pinned", default=False, index=True,
        help="You placed this by hand. Pinned rows stay on top, in your order, "
             "and the rubric never reorders them.")
    outreach_seq = fields.Integer(
        string="My Order", default=100, index=True,
        help="Your manual drag order among pinned rows.")
    outreach_score = fields.Integer(
        string="Rubric", compute="_compute_outreach_score", store=True, index=True,
        help="0-100 auto-rank from hard signals: relationship, follow-up due, "
             "warm-vs-researched, tier, reachable. Orders everyone you haven't touched.")
    outreach_score_reason = fields.Char(
        string="Why", compute="_compute_outreach_score", store=True)

    @api.depends("priority", "activity_ids", "email_from",
                 "partner_id.category_id", "partner_id.email",
                 "partner_id.linkedin", "partner_id.discord")
    def _compute_outreach_score(self):
        """Score 1 style (integral-mass two-score): computed in code from
        verifiable signals, with weights. No LLM here — an optional Haiku layer
        can later add a capped 'vote, not a veto' for the fuzzy signals."""
        cold = self.env["res.partner.category"].search([("name", "=", "Cold")], limit=1)
        cold_id = cold.id if cold else 0
        for lead in self:
            reasons, score = [], 0
            # Tier (the A/B/C/D you set -> priority stars): 0/15/30/45
            pr = int(lead.priority or "0")
            if pr:
                score += pr * 15
                reasons.append("tier+%d" % (pr * 15))
            # Real relationship vs researched-only (Cold tag)
            cat_ids = lead.partner_id.category_id.ids
            if cold_id and cold_id in cat_ids:
                reasons.append("cold")
            else:
                score += 25
                reasons.append("known+25")
            # Are they waiting on us / is a follow-up in motion?
            if lead.activity_ids:
                score += 20
                reasons.append("followup+20")
            # Reachable at a glance
            if lead.email_from or lead.partner_id.email or \
               lead.partner_id.linkedin or lead.partner_id.discord:
                score += 10
                reasons.append("reachable+10")
            lead.outreach_score = min(score, 100)
            lead.outreach_score_reason = " ".join(reasons)

    def action_mark_contacted(self):
        """One-click: stamp time, log a note, and pin it (you touched it)."""
        for lead in self:
            lead.last_outreach_date = fields.Datetime.now()
            lead.outreach_pinned = True
            lead.message_post(body="Outreach sent (via Outreach Runner).")
        return True

    def write(self, vals):
        # Dragging a row (Odoo writes outreach_seq via the handle) means you
        # placed it by hand -> pin it so the rubric never moves it again.
        if "outreach_seq" in vals and "outreach_pinned" not in vals:
            vals = dict(vals, outreach_pinned=True)
        return super().write(vals)
