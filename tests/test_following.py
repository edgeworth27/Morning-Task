import unittest
from briefing import BriefingError
from following import lookup
from test_briefing import QueueHTTP


class FollowingTests(unittest.TestCase):
    def test_paginated_lookup_deduplicates_accounts(self):
        account = {"id": "22", "username": "synthetic", "name": "Synthetic fixture"}
        http = QueueHTTP([{"data": {"id": "11", "username": "test"}},
                          {"data": [account], "meta": {"next_token": "page2"}},
                          {"data": [account]}])
        result = lookup(http, "synthetic", "@test")
        self.assertEqual(result["count"], 1)
        self.assertTrue(result["complete"])
        self.assertIn("pagination_token=page2", http.calls[-1][1])
        self.assertTrue(all(c[0] == "GET" for c in http.calls))

    def test_access_denial_is_not_an_empty_following_list(self):
        http = QueueHTTP([{"data": {"id": "11", "username": "test"}}, BriefingError("HTTP 403")])
        with self.assertRaises(BriefingError):
            lookup(http, "synthetic", "test")

    def test_partial_response_does_not_claim_complete(self):
        http = QueueHTTP([{"data": {"id": "11", "username": "test"}}, {"errors": [{"title": "fixture"}]}])
        with self.assertRaisesRegex(BriefingError, "partial"):
            lookup(http, "synthetic", "test")
