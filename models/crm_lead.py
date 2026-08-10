# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # --- contact links shown/edited straight from the outreach row ---
    partner_linkedin = fields.Char(
        related="partner_id.linkedin", string="LinkedIn", readonly=False)
    partner_discord = fields.Char(
        related="partner_id.discord", string="Discord", readonly=False)
    partner_bluesky = fields.Char(
        related="partner_id.bluesky", string="Bluesky", readonly=False)
    partner_social_ids = fields.One2many(
        related="partner_id.social_ids", string="Other Socials", readonly=False)
    partner_website = fields.Char(
        related="partner_id.website", string="Website", readonly=False)
    # crm.lead has its OWN `function`, only filled when a lead is typed in by
    # hand; leads made from an existing contact leave it empty, so the Role
    # column read blank on every row. The role lives on the contact — read it
    # from there.
    partner_function = fields.Char(
        related="partner_id.function", string="Role", readonly=False)
    partner_category_ids = fields.Many2many(
        related="partner_id.category_id", string="Contact Tags")
    partner_notes = fields.Html(
        related="partner_id.comment", string="Notes")

    last_outreach_date = fields.Datetime(
        string="Last Outreach", index=True,
        help="When outreach was last logged from the Outreach Runner.")

    # Per-campaign columns. This field is NOT new — stock CRM ships it as
    # crm.lead.lead_properties with definition='team_id.lead_properties_definition',
    # so the column set belongs to the sales team. That is the wrong axis
    # here: everyone is on one team and what varies is the campaign. Repointing
    # the definition rather than adding a second field keeps the stock widget,
    # search, group-by and _get_lead_properties working untouched, and leaves
    # one home for the fact instead of two.
    #
    # Safe to repoint: lead_properties holds no values and no crm_team has a
    # definition set, on linkedtrust_crm or on any of the eight team CRM
    # databases (checked 2026-08-10). Nothing is keyed to the old axis.
    lead_properties = fields.Properties(
        string="Outreach Columns",
        definition="campaign_id.lead_properties_definition",
        copy=True,
        help="Columns defined by this lead's campaign. Add or rename one from "
             "any row and it applies to the whole campaign.")

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

    # --- what "won" means here: they agreed to take part, in some role ---
    committed_as = fields.Selection(
        [("founder", "Founder"),
         ("mentor", "Mentor"),
         ("supporter", "Supporter"),
         ("funder", "Funder")],
        string="Committed As",
        help="The role they agreed to take. Set this when the record reaches "
             "the Committed stage; it keeps the board one column instead of "
             "splitting the end of the funnel four ways.")

    @api.depends("priority", "activity_ids", "email_from",
                 "partner_id.category_id", "partner_id.email",
                 "partner_id.linkedin", "partner_id.discord",
                 "partner_id.bluesky", "partner_id.social_ids")
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
               lead.partner_id.linkedin or lead.partner_id.discord or \
               lead.partner_id.bluesky or lead.partner_id.social_ids:
                score += 10
                reasons.append("reachable+10")
            lead.outreach_score = min(score, 100)
            lead.outreach_score_reason = " ".join(reasons)

    @api.depends("partner_id", "campaign_id")
    def _compute_name(self):
        """Name a row typed straight into the outreach list.

        crm.lead.name is required and is not a column here, because picking a
        contact is the whole gesture. Stock already fills it, as
        "<Partner>'s opportunity" — which is a sales-pipeline name, and does
        not say which campaign the row belongs to when the same organisation
        is on four of them. The data already settled this: 1242 of 1299
        existing leads are named "<Org> — <Campaign>". Match it, so new rows
        do not start a second naming style.

        Only fills a blank name or replaces the stock placeholder verbatim.
        Anything a person typed is left exactly as it is.
        """
        for lead in self:
            if not lead.partner_id or not lead.partner_id.name:
                continue
            placeholder = _("%s's opportunity") % lead.partner_id.name
            if lead.name and lead.name != placeholder:
                continue
            parts = [lead.partner_id.name]
            if lead.campaign_id:
                parts.append(lead.campaign_id.name)
            lead.name = " — ".join(parts)

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
