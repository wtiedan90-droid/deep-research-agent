"""Run with: python -m unittest discover -s tests -p test_search_diagnostics.py"""

import json
import os
import unittest
from unittest.mock import patch

import httpx
from ddgs.exceptions import TimeoutException

from deep_research_agent import utils


class SearchDiagnosticsTest(unittest.TestCase):
    def test_yahoo_normal_results_and_breadcrumbs(self):
        html = """
        <section class="algo algo-sr">
          <div class="compTitle"><h3><a href="https://example.com/cpu">
            <span class="title-url">Example example.com</span>CPU <b>工作原理</b>
          </a></h3></div>
          <div class="compText">取指、译码和执行。</div>
          <section class="algo-sr">
            <div class="compTitle"><h3><a href="https://example.com/pipeline">流水线</a></h3></div>
            <div class="compText">多条指令分阶段执行。</div>
          </section>
        </section>
        <div class="relsrch"><div class="Title"><h3>相关搜索</h3></div></div>
        """
        rows = utils._YahooCompatibleResults().extract_results(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].title, "CPU 工作原理")
        self.assertEqual(rows[0].href, "https://example.com/cpu")
        self.assertEqual(rows[0].body, "取指、译码和执行。")
        self.assertEqual(rows[1].title, "流水线")
        self.assertEqual(rows[1].body, "多条指令分阶段执行。")

    def test_yahoo_legacy_layout_still_parses(self):
        html = """
        <div class="relsrch">
          <div class="Title"><h3><a href="https://example.com/python">Python</a></h3></div>
          <div class="Text">Programming language.</div>
        </div>
        """
        rows = utils._YahooCompatibleResults().extract_results(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "Python")
        self.assertEqual(rows[0].body, "Programming language.")

    def test_yahoo_prefers_result_link_over_site_breadcrumb(self):
        for heading in (
            '<h3><a href="https://example.com/cpu">CPU</a></h3>',
            '<a href="https://example.com/cpu"><h3>CPU</h3></a>',
        ):
            with self.subTest(heading=heading):
                html = (
                    '<section class="algo-sr"><div class="compTitle">'
                    '<a href="https://example.com"><span class="title-url">Example</span></a>'
                    + heading + '</div><div class="compText">CPU body</div></section>'
                )
                rows = utils._YahooCompatibleResults().extract_results(html)
                self.assertEqual(rows[0].title, "CPU")
                self.assertEqual(rows[0].href, "https://example.com/cpu")

    def search(self, rows=(), error=None, proxy_env="", platform_proxies=None, **kwargs):
        with (
            patch.dict(os.environ, {"LANGSMITH_TRACING": "false", "DDGS_PROXY": proxy_env}),
            patch.object(utils, "getproxies", return_value=platform_proxies or {}),
            patch.object(utils, "DDGS") as ddgs,
            self.assertLogs(utils.logger, level="INFO") as logs,
        ):
            client = ddgs.return_value.__enter__.return_value
            client.text.return_value = rows
            client.text.side_effect = error
            result = utils.duckduckgo_search("CPU 工作原理", **kwargs)
            self.client_called = ddgs.called
            if ddgs.called:
                proxies = platform_proxies or {}
                expected_proxy = proxy_env or proxies.get("https") or proxies.get("http")
                if expected_proxy and "://" not in expected_proxy:
                    expected_proxy = "http://" + expected_proxy
                ddgs.assert_called_once_with(proxy=expected_proxy, timeout=kwargs.get("timeout", 15))
                client.text.assert_called_once_with(
                    "CPU 工作原理", max_results=3, backend=kwargs.get("backend", "auto")
                )

        start = json.loads(logs.records[0].getMessage().split(" ", 1)[1])
        finished = json.loads(logs.records[-1].getMessage().split(" ", 1)[1])
        self.assertEqual(start["search_id"], finished["search_id"])
        self.assertEqual(finished, result["diagnostics"])
        self.assertGreaterEqual(finished["elapsed_ms"], 0)
        return result, "\n".join(logs.output)

    def test_success_and_filtering_preserve_results(self):
        rows = [
            {"title": "CPU", "href": "https://example.com/cpu", "body": "CPU 的介绍"},
            {"title": "缺少链接", "body": "PRIVATE_PAGE_CONTENT"},
        ]
        result, logs = self.search(rows)
        info = result["diagnostics"]
        self.assertEqual(info["status"], "success")
        self.assertEqual((info["raw_count"], info["valid_count"], info["dropped_count"]), (2, 1, 1))
        self.assertEqual(info["dropped_results"], [{"index": 1, "missing_fields": ["href"]}])
        self.assertEqual(result["results"][0]["url"], rows[0]["href"])
        self.assertEqual(utils.format_sources(result), "* CPU : https://example.com/cpu")
        self.assertNotIn("PRIVATE_PAGE_CONTENT", logs)

    def test_empty_and_filtered_empty_are_distinct(self):
        result, _ = self.search()
        self.assertEqual(result["diagnostics"]["status"], "empty")
        self.assertEqual(result["diagnostics"]["raw_count"], 0)

        result, _ = self.search([{"title": "CPU", "href": "https://example.com", "body": " "}])
        self.assertEqual(result["diagnostics"]["status"], "filtered_empty")
        self.assertEqual(result["diagnostics"]["raw_count"], 1)
        self.assertEqual(result["results"], [])

    def test_timeout_has_unknown_raw_count_and_safe_error(self):
        error = TimeoutException(
            "Request failed https://user:proxy-password@www.mojeek.com/search?token=URL_SECRET "
            "operation timed out; api_key=PLAIN_SECRET; Bearer BEARER_SECRET"
        )
        result, logs = self.search(error=error)
        info = result["diagnostics"]
        self.assertEqual(info["status"], "request_error")
        self.assertEqual(info["error_type"], "TimeoutException")
        self.assertEqual(info["observed_error_host"], "www.mojeek.com")
        self.assertIsNone(info["raw_count"])
        self.assertIn("timed out", info["error_message"])
        for secret in ("proxy-password", "URL_SECRET", "PLAIN_SECRET", "BEARER_SECRET"):
            self.assertNotIn(secret, logs)
            self.assertNotIn(secret, info["error_message"])

    def test_unavailable_backend_fails_before_request(self):
        result, _ = self.search(backend="definitely_unavailable")
        self.assertEqual(result["diagnostics"]["status"], "validation_error")
        self.assertEqual(result["diagnostics"]["requested_backend"], "definitely_unavailable")
        self.assertFalse(self.client_called)

    def test_quoted_and_plain_credentials_are_redacted(self):
        secrets = ("JSON_SECRET", "PASS SECRET", "ACCESS_SECRET", 'ESCAPED"SECRET', "BASIC_SECRET")
        error = RuntimeError(
            json.dumps(dict(zip(("api_key", "password", "access_token", "client_secret"), secrets)))
            + "; Basic BASIC_SECRET"
        )
        result, logs = self.search(error=error)
        for secret in secrets:
            self.assertNotIn(secret, result["diagnostics"]["error_message"])
            self.assertNotIn(secret, logs)

    def test_url_credentials_with_parentheses_are_redacted(self):
        error = RuntimeError("https://user:PASS(WORD)@example.com/path?auth=URL_SECRET timed out")
        result, logs = self.search(error=error)
        self.assertEqual(result["diagnostics"]["observed_error_host"], "example.com")
        for secret in ("PASS", "WORD", "URL_SECRET"):
            self.assertNotIn(secret, logs)

    def test_platform_proxy_is_used_without_logging_credentials(self):
        proxy = "http://user:PROXY_PASSWORD@127.0.0.1:1234"
        result, logs = self.search(platform_proxies={"https": proxy})
        self.assertEqual(result["diagnostics"]["proxy_source"], "platform")
        self.assertNotIn("PROXY_PASSWORD", logs)
        self.assertNotIn("127.0.0.1:1234", logs)

    def test_ddgs_proxy_environment_takes_priority(self):
        result, logs = self.search(
            proxy_env="socks5://user:ENV_PASSWORD@127.0.0.1:1234",
            platform_proxies={"https": "http://127.0.0.1:5678"},
        )
        self.assertEqual(result["diagnostics"]["proxy_source"], "DDGS_PROXY")
        self.assertNotIn("ENV_PASSWORD", logs)

    def test_platform_proxy_without_scheme_is_normalized(self):
        result, _ = self.search(platform_proxies={"http": "127.0.0.1:1234"})
        self.assertEqual(result["diagnostics"]["proxy_source"], "platform")

    def test_configured_backend_reaches_graph_search_node(self):
        from deep_research_agent import graph as app
        from deep_research_agent.state import SummaryState

        with (
            patch.dict(os.environ, {
                "SEARCH_API": "duckduckgo", "DDGS_BACKEND": "yahoo", "FETCH_FULL_PAGE": "false",
            }),
            patch.object(app, "duckduckgo_search", return_value={"results": []}) as search,
        ):
            result = app.web_research(SummaryState(search_query="LangGraph"), {})
        search.assert_called_once_with("LangGraph", max_results=3, fetch_full_page=False, backend="yahoo")
        self.assertFalse(result["last_search_has_results"])

    def test_malformed_rows_are_counted_without_crashing(self):
        result, _ = self.search([None, {"title": 123, "href": "https://example.com", "body": "CPU"}])
        self.assertEqual(result["diagnostics"]["status"], "filtered_empty")
        self.assertEqual(result["diagnostics"]["dropped_count"], 2)

    def test_full_page_failure_does_not_lose_search_snippet(self):
        row = {"title": "CPU", "href": "https://example.com", "body": "CPU 的介绍"}
        with patch.object(utils, "fetch_raw_content", return_value=None):
            result, _ = self.search([row], fetch_full_page=True)
        self.assertEqual(result["diagnostics"]["status"], "success")
        self.assertEqual(result["diagnostics"]["full_page_failed_count"], 1)
        self.assertEqual(result["results"][0]["content"], row["body"])

    def test_page_fetch_error_is_correlated_and_redacted(self):
        url = "https://user:PAGE_PASSWORD@example.com/page?token=PAGE_TOKEN"
        row = {"title": "CPU", "href": url, "body": "CPU 的介绍"}
        with patch.object(utils.httpx, "Client") as client:
            client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError(
                f"TLS handshake failed: {url}"
            )
            result, logs = self.search([row], fetch_full_page=True)
        self.assertIn("page_fetch_failed", logs)
        self.assertIn(result["diagnostics"]["search_id"], logs)
        self.assertEqual(result["diagnostics"]["full_page_failed_count"], 1)
        for secret in ("PAGE_PASSWORD", "PAGE_TOKEN"):
            self.assertNotIn(secret, logs)
        with patch("builtins.print") as output:
            utils.deduplicate_and_format_sources(result, max_tokens_per_source=1000, fetch_full_page=True)
        output.assert_not_called()


if __name__ == "__main__":
    unittest.main()
