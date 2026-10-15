"""Synthetic fixtures ONLY. These do not establish live X or notification access."""
import base64
from datetime import date, datetime, timedelta
import json
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse

import briefing as b


def post(i="101", author="AndreasSteno", kinds=None):
    return {"id": i, "author": author, "text": "SYNTHETIC TEST INPUT; not a real X post.",
            "created_at": "2026-10-15T02:00:00Z", "kinds": kinds or [],
            "url": f"https://x.com/{author}/status/{i}", "metrics": {"like_count": 10}, "context": []}


def analysis(p, substantive=True):
    return {"id": p["id"], "summary": "Synthetic test summary.", "implication": "Synthetic conditional implication.",
            "substantive": substantive, "relevant": True, "topic": "macro"}


class ClockTests(unittest.TestCase):
    def test_summer_windows(self):
        w = b.windows(date(2026, 7, 2))
        self.assertEqual(b.iso(w["overnight"][0]), "2026-07-02T01:00:00Z")
        self.assertEqual(b.iso(w["overnight"][1]), "2026-07-02T10:15:00Z")
        self.assertEqual(b.iso(w["previous_day"][0]), "2026-07-01T04:00:00Z")

    def test_winter_windows(self):
        w = b.windows(date(2026, 1, 2))
        self.assertEqual(b.iso(w["overnight"][0]), "2026-01-02T02:00:00Z")
        self.assertEqual(b.iso(w["overnight"][1]), "2026-01-02T11:15:00Z")

    def test_dst_days_are_not_fixed_24_hours(self):
        for day, hours in [(date(2026, 3, 9), 23), (date(2026, 11, 2), 25)]:
            a, z = b.windows(day)["previous_day"]
            self.assertEqual((z.astimezone(b.UTC) - a.astimezone(b.UTC)).total_seconds(), hours * 3600)

    def test_overnight_crosses_spring_and_fall_switch(self):
        for day, hours in [(date(2026, 3, 8), 8.25), (date(2026, 11, 1), 10.25)]:
            a, z = b.windows(day)["overnight"]
            self.assertEqual((z.astimezone(b.UTC) - a.astimezone(b.UTC)).total_seconds(), hours * 3600)

    def test_correct_dst_slot_even_with_delay(self):
        now = b.parsed("2026-07-02T12:30:00Z")
        self.assertEqual(b.scheduled_day(now, 10), date(2026, 7, 2))
        self.assertIsNone(b.scheduled_day(now, 11))
        self.assertIsNone(b.scheduled_day(b.parsed("2026-01-02T10:15:00Z"), 10))
        self.assertEqual(b.scheduled_day(b.parsed("2026-01-02T11:20:00Z"), 11), date(2026, 1, 2))

    def test_before_cutoff_skips(self):
        self.assertIsNone(b.scheduled_day(b.parsed("2026-07-02T10:14:59Z"), 10))


class QueueHTTP:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def xpage(ids, token=None, timestamp="2026-10-15T02:00:00Z", kinds=None):
    tweets = [{"id": i, "author_id": "42", "text": "SYNTHETIC API FIXTURE", "created_at": timestamp,
               "referenced_tweets": [{"id": "999", "type": k} for k in (kinds or [])]} for i in ids]
    return {"data": tweets, "includes": {"users": [{"id": "42", "username": "AndreasSteno"}]},
            "meta": {"next_token": token} if token else {}}


class RetrievalTests(unittest.TestCase):
    def search(self, http, **kwargs):
        return b.XClient(http, "test").search("from:AndreasSteno -is:retweet", *b.windows(date(2026, 10, 15))["overnight"], **kwargs)

    def test_all_pages_and_dedup(self):
        http = QueueHTTP([xpage(["101"], "next"), xpage(["101", "102"])])
        posts, stats = self.search(http)
        self.assertEqual([p["id"] for p in posts], ["101", "102"])
        self.assertTrue(stats["complete"])
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(http.calls[1][1]).query)
        self.assertEqual(query["next_token"], ["next"])
        self.assertNotIn("exclude", query)

    def test_replies_included(self):
        posts, _ = self.search(QueueHTTP([xpage(["101"], kinds=["replied_to"])]))
        self.assertIn("replied_to", posts[0]["kinds"])

    def test_budget_marks_partial(self):
        posts, stats = self.search(QueueHTTP([xpage(["101"], "next")]), max_pages=1)
        self.assertFalse(stats["complete"])

    def test_partial_errors_fail_closed(self):
        with self.assertRaisesRegex(b.BriefingError, "partial errors"):
            self.search(QueueHTTP([{"errors": [{"detail": "test"}]}]))

    def test_unavailable_reference_is_labeled_without_discarding_real_reply(self):
        page = xpage(["101"], kinds=["replied_to"])
        page["errors"] = [{"resource_type": "tweet", "resource_id": "999",
                           "type": "https://api.x.com/2/problems/resource-not-found"}]
        posts, stats = self.search(QueueHTTP([page]))
        self.assertEqual(len(posts), 1)
        self.assertEqual(stats["unavailable_context"], 1)
        self.assertIn("unavailable", posts[0]["context"][0]["text"])

    def test_missing_primary_post_is_not_treated_as_missing_context(self):
        page = xpage(["101"], kinds=["replied_to"])
        page["errors"] = [{"resource_type": "tweet", "resource_id": "101",
                           "type": "https://api.x.com/2/problems/resource-not-found"}]
        with self.assertRaisesRegex(b.BriefingError, "partial errors"):
            self.search(QueueHTTP([page]))

    def test_window_end_exclusive(self):
        with self.assertRaisesRegex(b.BriefingError, "outside"):
            self.search(QueueHTTP([xpage(["101"], timestamp="2026-10-15T10:15:00Z")]))

    def test_repeated_token_fails(self):
        with self.assertRaisesRegex(b.BriefingError, "repeated"):
            self.search(QueueHTTP([xpage(["101"], "same"), xpage(["102"], "same")]))

    def test_note_tweet_preferred(self):
        page = xpage(["101"])
        page["data"][0]["note_tweet"] = {"text": "SYNTHETIC FULL LONG POST"}
        posts, _ = self.search(QueueHTTP([page]))
        self.assertEqual(posts[0]["text"], "SYNTHETIC FULL LONG POST")

    def test_missing_author_fails(self):
        page = xpage(["101"])
        page["includes"] = {}
        with self.assertRaisesRegex(b.BriefingError, "author"):
            self.search(QueueHTTP([page]))


class AnalysisTests(unittest.TestCase):
    def analyze(self, items, mode="overnight", posts=None):
        response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"items": items})}}]}
        return b.AI(QueueHTTP([response]), "test", "test-model").analyze(posts or [post()], mode)

    def test_unknown_id_rejected(self):
        with self.assertRaisesRegex(b.BriefingError, "unknown"):
            self.analyze([analysis(post("999"))])

    def test_omitted_post_rejected(self):
        with self.assertRaisesRegex(b.BriefingError, "omitted"):
            self.analyze([])

    def test_missing_batch_items_recovered_without_omitting_any_posts(self):
        posts = [post("101"), post("102")]
        replies = [{"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"items": [analysis(p)]})}}]} for p in posts]
        http = QueueHTTP(replies)
        result = b.AI(http, "synthetic", "synthetic").analyze(posts, "overnight")
        self.assertEqual([p["id"] for p in result], ["101", "102"])
        second_input = json.loads(http.calls[1][2]["body"]["messages"][1]["content"])
        self.assertEqual([p["id"] for p in second_input], ["102"])

    def test_duplicate_post_rejected(self):
        with self.assertRaisesRegex(b.BriefingError, "duplicated"):
            self.analyze([analysis(post()), analysis(post())])

    def test_invented_url_rejected(self):
        item = analysis(post())
        item["summary"] = "See https://x.com/fake/status/999"
        with self.assertRaisesRegex(b.BriefingError, "URL"):
            self.analyze([item])

    def test_exact_five_required(self):
        posts = [post(str(i)) for i in range(6)]
        with self.assertRaisesRegex(b.BriefingError, "required number"):
            self.analyze([analysis(p) for p in posts[:4]], "rank", posts)

    def test_source_link_comes_from_retrieval(self):
        result = self.analyze([analysis(post())])
        self.assertEqual(result[0]["url"], post()["url"])

    def test_schema_constrains_ids_to_actual_retrieved_posts(self):
        response = {"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"items": [analysis(post())]})}}]}
        http = QueueHTTP([response])
        b.AI(http, "synthetic", "synthetic").analyze([post()], "overnight")
        schema = http.calls[0][2]["body"]["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["properties"]["items"]["items"]["properties"]["id"]["enum"], ["101"])

    def test_diverse_topic_pool_deduplicates(self):
        result = b.candidate_pool({"macro": [post()], "rates": [post()]})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["topics"], ["macro", "rates"])


class EndToEndHTTP:
    """Fake transport runs production collect/analyze/render/deliver code, no live posts."""
    def __init__(self):
        self.messages = []
        self.x_calls = 0

    def request(self, method, url, **kw):
        if url.startswith("https://api.x.com/"):
            self.x_calls += 1
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            overnight = "from:" in query["query"][0]
            stamp = "2026-10-15T02:00:00Z" if overnight else "2026-10-14T15:00:00Z"
            return xpage([str(101 if overnight else 200 + self.x_calls)], timestamp=stamp)
        if url.startswith("https://api.openai.com/"):
            posts = json.loads(kw["body"]["messages"][1]["content"])
            overnight = "EVERY" in kw["body"]["messages"][0]["content"]
            items = [analysis(p) for p in (posts if overnight else posts[:5])]
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"items": items})}}]}
        if url.startswith("https://api.telegram.org/") and url.endswith("/sendMessage"):
            self.messages.append(kw)
            return {"ok": True, "result": {"message_id": len(self.messages)}}
        raise AssertionError("Unexpected API destination")


class MemoryState:
    def __init__(self, fail_final=False):
        self.record = None
        self.saves = 0
        self.fail_final = fail_final

    def load(self, day):
        return self.record

    def save(self, record):
        self.saves += 1
        if record["status"] == "sent" and self.fail_final:
            self.fail_final = False
            raise b.BriefingError("SYNTHETIC STATE WRITE FAILURE")
        self.record = json.loads(json.dumps(record))


class PipelineTests(unittest.TestCase):
    ENV = {"X_BEARER_TOKEN": "synthetic", "AI_API_KEY": "synthetic",
           "TELEGRAM_BOT_TOKEN": "123:synthetic", "TELEGRAM_CHAT_ID": "456"}

    def run_pipeline(self, http, state, dry=False, now=None):
        with tempfile.TemporaryDirectory() as out, patch.dict(os.environ, self.ENV, clear=True):
            result = b.execute(day=date(2026, 10, 15), now=now or b.parsed("2026-10-15T12:00:00Z"),
                               dry_run=dry, output=Path(out), http=http, state=state)
            if dry:
                self.assertTrue((Path(out) / "briefing.json").exists())
            return result

    def test_full_mocked_retrieval_to_delivery_and_rerun(self):
        http, state = EndToEndHTTP(), MemoryState()
        result = self.run_pipeline(http, state)
        self.assertEqual(result["status"], "sent")
        self.assertEqual(http.x_calls, 9)
        self.assertEqual(len(http.messages), 1)
        text = http.messages[0]["body"]["text"]
        self.assertIn("@AndreasSteno", text)
        self.assertIn("https://x.com/AndreasSteno/status/101", text)
        self.assertIn("Oct 14 10:00 PM EDT", text)
        self.run_pipeline(http, state)
        self.assertEqual(len(http.messages), 1)
        self.assertEqual(http.x_calls, 9)

    def test_resume_after_final_state_failure_does_not_resend(self):
        http, state = EndToEndHTTP(), MemoryState(fail_final=True)
        with self.assertRaisesRegex(b.BriefingError, "STATE WRITE"):
            self.run_pipeline(http, state)
        self.assertEqual(state.record["status"], "prepared")
        self.run_pipeline(http, state)
        self.assertEqual(http.x_calls, 9)
        self.assertEqual(len(http.messages), 1)

    def test_ambiguous_telegram_delivery_requires_review(self):
        http, state = EndToEndHTTP(), MemoryState(fail_final=True)
        with self.assertRaises(b.BriefingError):
            self.run_pipeline(http, state)
        state.record["status"] = "sending"
        with self.assertRaisesRegex(b.BriefingError, "uncertain"):
            self.run_pipeline(http, state)
        self.assertEqual(len(http.messages), 1)

    def test_dry_run_has_no_delivery_or_state_writes(self):
        http, state = EndToEndHTTP(), MemoryState()
        result = self.run_pipeline(http, state, dry=True)
        self.assertEqual(len(result["top_five"]), 5)
        self.assertEqual(state.saves, 0)
        self.assertEqual(http.messages, [])

    def test_failed_retrieval_does_not_send(self):
        state = MemoryState()
        with self.assertRaisesRegex(b.BriefingError, "unavailable"):
            self.run_pipeline(QueueHTTP([b.BriefingError("X unavailable")]), state)
        self.assertEqual(state.saves, 0)

    def test_future_window_rejected(self):
        with self.assertRaisesRegex(b.BriefingError, "not closed"):
            self.run_pipeline(EndToEndHTTP(), MemoryState(), now=b.parsed("2026-10-15T10:14:00Z"))

    def test_old_date_rejected(self):
        with self.assertRaisesRegex(b.BriefingError, "retention"):
            self.run_pipeline(EndToEndHTTP(), MemoryState(), now=b.parsed("2026-10-23T12:00:00Z"))

    def test_substantive_quotes_only_but_all_replies_retained(self):
        posts = [post("101"), post("102", kinds=["quoted"]), post("103", kinds=["quoted"]),
                 post("104", kinds=["replied_to", "quoted"])]

        class X:
            def search(self, query, *args, **kwargs):
                return (posts if "from:" in query else []), {"pages": 1, "posts": 4, "complete": True}

        class AI:
            model = "synthetic"

            def analyze(self, batch, mode):
                return [{**p, "analysis": analysis(p, substantive=p["id"] == "103")} for p in batch]

        report = b.collect(X(), AI(), date(2026, 10, 15), 2)
        self.assertEqual([p["id"] for p in report["overnight"]], ["101", "103", "104"])
        self.assertEqual(report["omitted_quotes"], 1)
        self.assertEqual(len(report["overnight_raw"]), 4)

    def test_empty_day_reports_no_posts_without_inventing_five(self):
        class X:
            def search(self, *args, **kwargs):
                return [], {"pages": 1, "posts": 0, "complete": True}

        ai = b.AI(QueueHTTP([]), "synthetic", "synthetic")
        report = b.collect(X(), ai, date(2026, 10, 15), 2)
        rendered = b.render(report)
        self.assertIn("Only 0 eligible candidates", rendered["text"])
        self.assertEqual(report["top_five"], [])

    def test_html_escapes_ai_text_and_links_real_source(self):
        http = EndToEndHTTP()
        with patch.dict(os.environ, self.ENV, clear=True):
            report = b.collect(b.XClient(http, "synthetic"), b.AI(http, "synthetic", "synthetic"), date(2026, 10, 15), 2)
        report["overnight"][0]["analysis"]["summary"] = "<script>alert('test')</script>"
        email = b.render(report)
        self.assertNotIn("<script>", email["html"])
        self.assertIn('<a href="https://x.com/AndreasSteno/status/101">', email["html"])

    def test_changed_recipient_stops_duplicate_or_misdirected_delivery(self):
        http, state = EndToEndHTTP(), MemoryState()
        self.run_pipeline(http, state)
        state.record["recipient_fingerprint"] = "different-recipient"
        with self.assertRaisesRegex(b.BriefingError, "changed"):
            self.run_pipeline(http, state)
        self.assertEqual(len(http.messages), 1)

    def test_elon_filter_excludes_off_topic_posts_and_replies_only_for_elon(self):
        posts = [post("101", "elonmusk"), post("102", "elonmusk", ["replied_to"]),
                 post("103", "elonmusk"), post("104", "AndreasSteno")]

        class X:
            def search(self, query, *args, **kwargs):
                return (posts if "from:" in query else []), {"pages": 1, "posts": 4, "complete": True}

        class AI:
            model = "synthetic"

            def analyze(self, batch, mode):
                result = []
                for p in batch:
                    a = analysis(p)
                    if p["id"] in ("101", "102", "104"):
                        a.update(relevant=False, topic="other")
                    result.append({**p, "analysis": a})
                return result

        report = b.collect(X(), AI(), date(2026, 10, 15), 2)
        self.assertEqual([p["id"] for p in report["overnight"]], ["103", "104"])
        self.assertEqual(report["omitted_elon_off_topic"], 2)
        self.assertEqual(len(report["overnight_raw"]), 4)

    def test_off_topic_elon_rank_selection_is_replaced(self):
        posts = [post("101", "elonmusk"), post("102")]

        class X:
            def search(self, query, *args, **kwargs):
                return ([] if "from:" in query else posts), {"pages": 1, "posts": 2, "complete": True}

        class AI:
            model = "synthetic"

            def analyze(self, batch, mode):
                result = []
                for p in batch:
                    a = analysis(p)
                    if p["author"] == "elonmusk":
                        a.update(relevant=False, topic="other")
                    result.append({**p, "analysis": a})
                return result

        report = b.collect(X(), AI(), date(2026, 10, 15), 2)
        self.assertEqual([p["id"] for p in report["top_five"]], ["102"])

    def test_material_tesla_and_spacex_are_eligible_for_elon_coverage(self):
        for topic in ("Tesla", "SpaceX"):
            with self.subTest(topic=topic):
                p = post("101", "elonmusk")
                p["analysis"] = {**analysis(p), "topic": topic, "relevant": True}
                self.assertTrue(b.relevant_elon(p))
                p["analysis"]["relevant"] = False
                self.assertFalse(b.relevant_elon(p))

    def test_spaced_digest_puts_top_five_first_and_uses_safe_telegram_links(self):
        http = EndToEndHTTP()
        with patch.dict(os.environ, self.ENV, clear=True):
            report = b.collect(b.XClient(http, "synthetic"), b.AI(http, "synthetic", "synthetic"), date(2026, 10, 15), 2)
        email = b.render(report)
        self.assertLess(email["text"].index("⭐ TOP FIVE"), email["text"].index("🌙 OVERNIGHT"))
        self.assertIn("\n\nWhy:", email["text"])
        self.assertNotIn("RETRIEVAL COVERAGE", email["text"])
        rendered = b.telegram_html(email["text"] + "\n<script>bad</script>")
        self.assertIn("<b>⭐ TOP FIVE", rendered)
        self.assertIn('>View post ↗</a>', rendered)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)


class DeliveryTests(unittest.TestCase):
    def test_workflow_diagnostic_escapes_annotation_controls(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch("sys.stdout", new_callable=io.StringIO) as stdout, patch("sys.stderr", new_callable=io.StringIO):
            b.report_error("test%\nsecond line")
        self.assertEqual(stdout.getvalue(), "::error::test%25%0Asecond line\n")

    def test_prepared_state_written_as_versioned_content(self):
        http = QueueHTTP([b.BriefingError("api.github.com: HTTP 404 for GET /missing"),
                          b.BriefingError("api.github.com: HTTP 404 for GET /missing"), {}, {"content": {"sha": "new"}}])
        state = b.GitHubState(http, "test", "owner/repo", "commit-sha")
        self.assertIsNone(state.load(date(2026, 10, 15)))
        state.save({"day": "2026-10-15", "status": "prepared"})
        payload = http.calls[-1][2]["body"]
        self.assertEqual(json.loads(base64.b64decode(payload["content"]))["status"], "prepared")
        self.assertEqual(state.sha, "new")

    def test_unsafe_post_not_automatically_retried(self):
        exc = urllib.error.HTTPError("https://api.github.com/repos/o/r/issues", 503, "test", {}, None)
        with patch("urllib.request.urlopen", side_effect=exc) as request:
            with self.assertRaises(b.BriefingError):
                b.HTTP().request("POST", exc.url, token="synthetic", body={})
            self.assertEqual(request.call_count, 1)

    def test_telegram_missing_id_fails_and_blocks_retry(self):
        state = MemoryState()
        record = {"day": "2026-10-15", "status": "prepared", "parts": ["synthetic"], "message_ids": []}
        with self.assertRaisesRegex(b.BriefingError, "message ID"):
            b.deliver_telegram(QueueHTTP([{"ok": True, "result": {}}]), "123:synthetic", "456", record, state)
        self.assertEqual(state.record["status"], "sending")
        with self.assertRaisesRegex(b.BriefingError, "uncertain"):
            b.deliver_telegram(QueueHTTP([]), "123:synthetic", "456", state.record, state)

    def test_parts_fit_telegram_limit_even_with_emoji(self):
        text = "SYNTHETIC "+ "😀" * 5000
        parts = b.telegram_parts(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p.encode("utf-16-le")) // 2 < 4096 for p in parts))
        self.assertEqual("".join(p.split("\n\n", 1)[1] for p in parts), text)

    def test_chat_discovery_requires_private_start(self):
        http = QueueHTTP([{"ok": True, "result": [{"message": {"text": "/start", "chat": {"id": 456, "type": "private"}}}]}])
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(b.telegram_chat(http, "123:synthetic"), "456")
        with self.assertRaises(b.BriefingError):
            b.telegram_chat(QueueHTTP([{"ok": True, "result": []}]), "123:synthetic")

    def test_message_split_preserves_direct_post_link(self):
        url = "https://x.com/AndreasSteno/status/1234567890123456789"
        parts = b.telegram_parts("x" * 3470 + "\n" + url + "\n" + "y" * 100)
        self.assertTrue(any(url in part for part in parts))

    def test_telegram_http_failure_does_not_log_bot_token(self):
        url = "https://api.telegram.org/bot123:synthetic/sendMessage"
        exc = urllib.error.HTTPError(url, 401, "test", {}, None)
        with patch("urllib.request.urlopen", side_effect=exc):
            with self.assertRaises(b.BriefingError) as caught:
                b.HTTP().request("POST", url, token=None, body={})
            self.assertNotIn("synthetic", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
