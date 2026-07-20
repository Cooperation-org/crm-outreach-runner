# -*- coding: utf-8 -*-
"""HttpCase tests for GET /outreach/api/queue (PLAN-cohort-dash.md).

Run (test DB, never the live one):

    odoo-bin -c <conf> -d <fresh_test_db> --http-port=<free_port> \
        --workers=0 --max-cron-threads=0 --stop-after-init \
        --test-enable --test-tags /crm_outreach_runner -i crm_outreach_runner
"""
import json
from urllib.parse import quote

from odoo.tests import HttpCase, tagged

QUEUE_URL = "/outreach/api/queue"
CONNECT_URL = "/outreach/connect"


@tagged("post_install", "-at_install")
class TestOutreachQueueEndpoint(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Hide any pre-existing (e.g. demo) leads so the queue is exactly
        # the fixture set below.
        cls.env["crm.lead"].with_context(active_test=False).search([]).write(
            {"active": False})

        cls.password = "Outreach-Test-2026!"
        # Required ACL for the two-tier queue (see README): the fill tier
        # reads unassigned AND teammates' leads, so the caller needs
        # sales_team.group_sale_salesman_all_leads (implies salesman,
        # which carries the crm.lead read ACL, and base.group_user).
        cls.user = cls.env["res.users"].create({
            "name": "Cohort Tester",
            "login": "cohort_tester",
            "password": cls.password,
            "groups_id": [(6, 0, [
                cls.env.ref("sales_team.group_sale_salesman_all_leads").id,
            ])],
        })
        cls.other_user = cls.env.ref("base.user_admin")

        Lead = cls.env["crm.lead"]
        common = {"type": "opportunity", "user_id": False}
        # Rubric (models/crm_lead.py): priority*15, +25 known (no Cold
        # tag), no activities, no email -> scores are fully determined by
        # priority here: '0'->25, '1'->40, '3'->70.
        #
        # Tier 1 — own leads (user_id = session user):
        cls.own_pinned = Lead.create(dict(
            common, name="Own pinned", user_id=cls.user.id, priority="0",
            outreach_pinned=True, outreach_seq=1))      # score 25, pinned
        cls.own_plain = Lead.create(dict(
            common, name="Own plain", user_id=cls.user.id, priority="1",
            last_outreach_date="2026-07-01 12:00:00"))  # score 40, contacted
        # Tier 2 fill, group A — unassigned:
        cls.un_pinned = Lead.create(dict(
            common, name="Unassigned pinned", priority="0",
            outreach_pinned=True, outreach_seq=1))      # score 25, pinned
        cls.un_high = Lead.create(dict(
            common, name="Unassigned high", priority="3"))  # score 70
        # Tier 2 fill, group B — assigned to a teammate:
        cls.other_high = Lead.create(dict(
            common, name="Other high", user_id=cls.other_user.id,
            priority="3"))                               # score 70
        # Must never appear: not an opportunity.
        Lead.create(dict(common, name="Plain lead", type="lead",
                         priority="2"))

    def _queue(self, qs="", headers=None):
        res = self.url_open(QUEUE_URL + qs, headers=headers)
        self.assertEqual(res.status_code, 200)
        return res, json.loads(res.content)

    def test_auth_required(self):
        """Signed-out: auth='user' redirects to login, never serves data."""
        res = self.url_open(QUEUE_URL, allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertIn("/web/login", res.headers.get("Location", ""))

    def test_ordering_and_shape(self):
        """Two tiers: own leads first (tree order — an own lead beats even
        a pinned team lead), then the fill: unassigned before
        assigned-to-others (even at equal score), pin/seq still respected
        within each fill group; type='lead' excluded."""
        self.authenticate("cohort_tester", self.password)
        _res, data = self._queue()
        names = [lead["name"] for lead in data["leads"]]
        self.assertEqual(
            names,
            ["Own pinned", "Own plain", "Unassigned pinned",
             "Unassigned high", "Other high"])

        first = data["leads"][0]
        for key in ("id", "name", "partner_name", "email", "linkedin",
                    "last_outreach_date", "outreach_score",
                    "outreach_score_reason", "url"):
            self.assertIn(key, first)
        self.assertEqual(first["id"], self.own_pinned.id)
        self.assertIsNone(first["last_outreach_date"])
        # url built from the request host, Odoo 17 form deep link.
        self.assertTrue(first["url"].endswith(
            "/web#id=%d&model=crm.lead&view_type=form" % self.own_pinned.id))
        self.assertTrue(first["url"].startswith(self.base_url()))

        own_plain = data["leads"][1]
        self.assertEqual(own_plain["last_outreach_date"],
                         "2026-07-01T12:00:00Z")
        self.assertEqual(own_plain["outreach_score"], 40)

    def test_count_to_reach(self):
        """count_to_reach = never-contacted opportunities across the whole
        queue universe (own + unassigned + assigned-to-others),
        regardless of the row limit."""
        self.authenticate("cohort_tester", self.password)
        _res, data = self._queue()
        self.assertEqual(data["count_to_reach"], 4)  # all but Own plain
        _res, data = self._queue("?limit=1")
        self.assertEqual(data["count_to_reach"], 4)

    def test_limit_param(self):
        """The limit truncates across the tiers in order: own leads fill
        first, then unassigned, then assigned-to-others."""
        self.authenticate("cohort_tester", self.password)
        _res, data = self._queue("?limit=2")
        self.assertEqual([lead["name"] for lead in data["leads"]],
                         ["Own pinned", "Own plain"])
        _res, data = self._queue("?limit=3")
        self.assertEqual([lead["name"] for lead in data["leads"]],
                         ["Own pinned", "Own plain", "Unassigned pinned"])
        # Garbage limit falls back to the default (5 = fixture count).
        _res, data = self._queue("?limit=nope")
        self.assertEqual(len(data["leads"]), 5)

    def test_cors_echo_allowed_origins_only(self):
        self.authenticate("cohort_tester", self.password)
        for origin in ("https://workers.vc", "https://www.workers.vc"):
            res, _data = self._queue(headers={"Origin": origin})
            self.assertEqual(
                res.headers.get("Access-Control-Allow-Origin"), origin)
            self.assertEqual(
                res.headers.get("Access-Control-Allow-Credentials"), "true")
            self.assertIn("Origin", res.headers.get("Vary", ""))
        # Any other origin: no CORS grant at all.
        for origin in ("https://evil.example",
                       "http://workers.vc",
                       "https://workers.vc.evil.example"):
            res, _data = self._queue(headers={"Origin": origin})
            self.assertIsNone(res.headers.get("Access-Control-Allow-Origin"))
            self.assertIsNone(
                res.headers.get("Access-Control-Allow-Credentials"))

    def test_preflight_options(self):
        """OPTIONS answers without auth (browsers preflight without
        credentials) and grants only allowlisted origins."""
        res = self.opener.options(
            self.base_url() + QUEUE_URL,
            headers={"Origin": "https://workers.vc",
                     "Access-Control-Request-Method": "GET"},
            timeout=12)
        self.assertEqual(res.status_code, 204)
        self.assertEqual(
            res.headers.get("Access-Control-Allow-Origin"),
            "https://workers.vc")
        self.assertEqual(
            res.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertIn("GET", res.headers.get("Access-Control-Allow-Methods", ""))

        res = self.opener.options(
            self.base_url() + QUEUE_URL,
            headers={"Origin": "https://evil.example",
                     "Access-Control-Request-Method": "GET"},
            timeout=12)
        self.assertEqual(res.status_code, 204)
        self.assertIsNone(res.headers.get("Access-Control-Allow-Origin"))

    def test_connect_anonymous_bounces_through_login(self):
        """Anonymous /outreach/connect goes to the login page with the
        full path (incl. ?next=...) preserved in the redirect param, so
        the hop resumes after sign-in."""
        res = self.url_open(
            CONNECT_URL + "?next=https%3A%2F%2Fworkers.vc%2Fdash%2Fteam-x%2F",
            allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        location = res.headers.get("Location", "")
        self.assertTrue(location.startswith("/web/login"))
        self.assertIn("outreach%2Fconnect", location)
        self.assertIn("next", location)

    def test_connect_valid_next(self):
        self.authenticate("cohort_tester", self.password)
        for target in ("https://workers.vc/dash/team-x/",
                       "https://www.workers.vc/dash/",
                       "https://workers.vc"):
            res = self.url_open(
                CONNECT_URL + "?next=" + quote(target, safe=""),
                allow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertEqual(res.headers.get("Location"), target)

    def test_connect_invalid_next_stays_local(self):
        """No open redirect: anything but the exact dash origins lands on
        a local Odoo page."""
        self.authenticate("cohort_tester", self.password)
        bad = ("https://evil.example/",
               "http://workers.vc/",                # wrong scheme
               "https://workers.vc.evil.example/",  # suffix trick
               "https://workers.vc@evil.example/",  # userinfo trick
               "//workers.vc/dash/",                # protocol-relative
               "javascript:alert(1)",
               "")
        for target in bad:
            res = self.url_open(
                CONNECT_URL + ("?next=" + quote(target, safe="")
                               if target else ""),
                allow_redirects=False)
            self.assertEqual(res.status_code, 302)
            location = res.headers.get("Location", "")
            self.assertTrue(
                location.startswith("/web"),
                "next=%r must redirect locally, got %r" % (target, location))
