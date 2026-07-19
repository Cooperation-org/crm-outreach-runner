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
        # Minimum documented ACL: sales_team.group_sale_salesman is what
        # grants read on crm.lead (see README). The record rule then shows
        # own + unassigned leads, which is why fixtures set user_id=False.
        cls.user = cls.env["res.users"].create({
            "name": "Cohort Tester",
            "login": "cohort_tester",
            "password": cls.password,
            "groups_id": [(6, 0, [
                cls.env.ref("sales_team.group_sale_salesman").id,
            ])],
        })

        Lead = cls.env["crm.lead"]
        common = {"type": "opportunity", "user_id": False}
        # Rubric (models/crm_lead.py): priority*15, +25 known (no Cold
        # tag), no activities, no email -> scores are fully determined by
        # priority here: '0'->25, '1'->40, '3'->70.
        cls.pinned_first = Lead.create(dict(
            common, name="Pinned first", priority="0",
            outreach_pinned=True, outreach_seq=1))     # score 25, pinned
        cls.pinned_second = Lead.create(dict(
            common, name="Pinned second", priority="3",
            outreach_pinned=True, outreach_seq=2))     # score 70, pinned
        cls.high = Lead.create(dict(
            common, name="High rubric", priority="3"))  # score 70
        cls.low = Lead.create(dict(
            common, name="Low rubric", priority="1",
            last_outreach_date="2026-07-01 12:00:00"))  # score 40, contacted
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
        """Order identical to the tree view: pinned desc, seq, score desc.
        Manual pin+seq beats a higher rubric score; type='lead' excluded."""
        self.authenticate("cohort_tester", self.password)
        _res, data = self._queue()
        names = [lead["name"] for lead in data["leads"]]
        self.assertEqual(
            names,
            ["Pinned first", "Pinned second", "High rubric", "Low rubric"])

        first = data["leads"][0]
        for key in ("id", "name", "partner_name", "email", "linkedin",
                    "last_outreach_date", "outreach_score",
                    "outreach_score_reason", "url"):
            self.assertIn(key, first)
        self.assertEqual(first["id"], self.pinned_first.id)
        self.assertIsNone(first["last_outreach_date"])
        # url built from the request host, Odoo 17 form deep link.
        self.assertTrue(first["url"].endswith(
            "/web#id=%d&model=crm.lead&view_type=form" % self.pinned_first.id))
        self.assertTrue(first["url"].startswith(self.base_url()))

        low = data["leads"][3]
        self.assertEqual(low["last_outreach_date"], "2026-07-01T12:00:00Z")
        self.assertEqual(low["outreach_score"], 40)

    def test_count_to_reach(self):
        """count_to_reach = opportunities never contacted, regardless of
        the row limit."""
        self.authenticate("cohort_tester", self.password)
        _res, data = self._queue()
        self.assertEqual(data["count_to_reach"], 3)
        _res, data = self._queue("?limit=1")
        self.assertEqual(data["count_to_reach"], 3)

    def test_limit_param(self):
        self.authenticate("cohort_tester", self.password)
        _res, data = self._queue("?limit=2")
        self.assertEqual(len(data["leads"]), 2)
        self.assertEqual([lead["name"] for lead in data["leads"]],
                         ["Pinned first", "Pinned second"])
        # Garbage limit falls back to the default (5 > fixture count of 4).
        _res, data = self._queue("?limit=nope")
        self.assertEqual(len(data["leads"]), 4)

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
