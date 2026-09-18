# -*- coding: utf-8 -*-

import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from odoo.tests import TransactionCase, tagged

from ..models.analytics import track_event


class TestTrackEvent(unittest.TestCase):

    @patch.dict(os.environ, {"ANALYTICS_ENDPOINT": ""}, clear=False)
    @patch("odoo.addons.crm_outreach_runner.models.analytics.request.urlopen")
    def test_endpoint_unset_does_not_make_request(self, mock_urlopen):
        track_event("outreach_started", {"lead_id": 1})

        mock_urlopen.assert_not_called()

    @patch.dict(os.environ, {"ANALYTICS_ENDPOINT": "https://analytics.example/events", "ANALYTICS_API_KEY": ""}, clear=False)
    @patch("odoo.addons.crm_outreach_runner.models.analytics.request.urlopen")
    def test_successful_post_sends_correct_payload(self, mock_urlopen):
        properties = {"lead_id": 1, "campaign_id": 2}

        track_event("outreach_started", properties)

        request_arg = mock_urlopen.call_args.args[0]
        self.assertEqual(request_arg.full_url, "https://analytics.example/events")
        self.assertEqual(request_arg.get_method(), "POST")
        self.assertEqual(json.loads(request_arg.data.decode("utf-8")), {
            "event": "outreach_started",
            "properties": properties,
        })
        self.assertEqual(request_arg.get_header("Content-type"), "application/json")
        mock_urlopen.assert_called_once_with(request_arg, timeout=3)

    @patch.dict(os.environ, {"ANALYTICS_ENDPOINT": "https://analytics.example/events", "ANALYTICS_API_KEY": "test-key"}, clear=False)
    @patch("odoo.addons.crm_outreach_runner.models.analytics.request.urlopen")
    def test_api_key_adds_bearer_header(self, mock_urlopen):
        track_event("outreach_started", {})

        request_arg = mock_urlopen.call_args.args[0]
        self.assertEqual(request_arg.get_header("Authorization"), "Bearer test-key")

    @patch.dict(os.environ, {"ANALYTICS_ENDPOINT": "https://analytics.example/events"}, clear=False)
    @patch("odoo.addons.crm_outreach_runner.models.analytics.request.urlopen", side_effect=OSError("network unavailable"))
    @patch("odoo.addons.crm_outreach_runner.models.analytics._logger.exception")
    def test_network_failure_is_swallowed(self, mock_log, mock_urlopen):
        track_event("outreach_started", {"lead_id": 1})

        mock_log.assert_called_once()
        mock_urlopen.assert_called_once()

    @patch.dict(os.environ, {"ANALYTICS_ENDPOINT": "https://analytics.example/events"}, clear=False)
    @patch(
        "odoo.addons.crm_outreach_runner.models.analytics.request.urlopen",
        side_effect=HTTPError("https://analytics.example/events", 500, "server error", {}, None),
    )
    @patch("odoo.addons.crm_outreach_runner.models.analytics._logger.exception")
    def test_http_failure_is_swallowed(self, mock_log, mock_urlopen):
        track_event("outreach_started", {"lead_id": 1})

        mock_log.assert_called_once()
        mock_urlopen.assert_called_once()

    @patch.dict(os.environ, {"ANALYTICS_ENDPOINT": "https://analytics.example/events"}, clear=False)
    @patch("odoo.addons.crm_outreach_runner.models.analytics.request.urlopen")
    @patch("odoo.addons.crm_outreach_runner.models.analytics._logger.exception")
    def test_non_serializable_properties_are_swallowed(self, mock_log, mock_urlopen):
        track_event("outreach_started", {"invalid": object()})

        mock_log.assert_called_once()
        mock_urlopen.assert_not_called()


@tagged("post_install", "-at_install")
class TestOutreachAnalytics(TransactionCase):

    def test_mark_contacted_tracks_outreach_started(self):
        lead = self.env["crm.lead"].create({
            "name": "Analytics Test Lead",
            "type": "opportunity",
        })

        with patch(
            "odoo.addons.crm_outreach_runner.models.crm_lead.track_event"
        ) as mock_track:
            result = lead.action_mark_contacted()

        self.assertTrue(result)
        self.assertTrue(lead.last_outreach_date)
        self.assertTrue(lead.outreach_pinned)

        mock_track.assert_called_once_with(
            "outreach_started",
            {
                "lead_id": lead.id,
                "campaign_id": None,
            },
        )
