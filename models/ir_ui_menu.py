# -*- coding: utf-8 -*-
from odoo import api, models

# The two doors this CRM has. Everything else is turned off, not deleted.
KEEP = (
    "crm_outreach_runner.menu_outreach_runner",
    "crm_outreach_runner.menu_campaigns_root",
)

# Admin-only roots, left alone. Both are restricted to base.group_system, so
# nobody outside an admin sees them anyway — and Settings is the one menu that,
# once off, cannot be turned back on from the UI.
KEEP_ADMIN = (
    "base.menu_administration",
    "base.menu_management",
)


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _outreach_keep_two_sections(self):
        """Leave two top-level menus active: Outreach and Campaigns.

        Called from data on every install and upgrade, so a deploy re-asserts
        it and a newly installed addon cannot quietly add a ninth door.

        Deactivating a root takes its whole subtree with it, which is the point:
        crm_card_scanner, quick_outreach and crm_relationship_dashboard all hang
        their menus under the CRM root, so they go with it and this module does
        not have to know their names or depend on them.
        """
        keep_ids = set()
        for xmlid in KEEP + KEEP_ADMIN:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                keep_ids.add(menu.id)

        # Guard: if our own two menus are missing, the data file has not loaded
        # yet and switching everything off would leave no way in. Do nothing.
        if not all(self.env.ref(x, raise_if_not_found=False) for x in KEEP):
            return

        # ir.ui.menu.search_fetch quietly drops menus the current user cannot
        # see (_filter_visible_menus), so a plain search misses exactly the
        # ones nobody asked for: Link Tracker has no visible action, Tests is
        # base.group_no_one. 'ir.ui.menu.full_list' is Odoo's own opt-out and
        # is the only way to get the real list.
        others = self.with_context(
            active_test=False, **{"ir.ui.menu.full_list": True}
        ).search([
            ("parent_id", "=", False),
            ("id", "not in", list(keep_ids)),
            ("active", "=", True),
        ])
        others.write({"active": False})
        return True
