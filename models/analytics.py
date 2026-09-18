# -*- coding: utf-8 -*-

import json
import logging
import os
from urllib import request

_logger = logging.getLogger(__name__)


def track_event(event_name, properties=None, distinct_id=None):
    """Send an analytics event to PostHog when analytics is configured."""
    endpoint = os.getenv("ANALYTICS_ENDPOINT")
    api_key = os.getenv("ANALYTICS_API_KEY")

    if not endpoint or not api_key or not distinct_id:
        return

    try:
        payload = json.dumps({
            "api_key": api_key,
            "event": event_name,
            "distinct_id": str(distinct_id),
            "properties": properties or {},
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
        }

        req = request.Request(
            endpoint,
            data=payload,
            headers=headers,
            method="POST",
        )

        with request.urlopen(req, timeout=3):
            pass

    except Exception:
        _logger.exception(
            "Failed to send analytics event: %s",
            event_name,
        )