# -*- coding: utf-8 -*-
"""Tell the web client where the cohort's cross-app bar lives.

A team CRM in the cohort is one tool among several (dash, board, org, chat),
and Odoo's own chrome offers no way back to any of them. workers.vc owns and
serves that bar; this addon only carries the address, as a system parameter so
each database says it for itself:

    cohort_nav.src = https://workers.vc/static/embed/cohort-nav.js

Unset (the default) mounts nothing, which is what a standalone Odoo wants.
"""

from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        info = super().session_info()
        info["cohort_nav_src"] = (
            self.env["ir.config_parameter"].sudo().get_param("cohort_nav.src", "")
        )
        return info
