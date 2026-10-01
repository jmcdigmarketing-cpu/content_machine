"""#921: the suite may not reach the network, and a test that tries fails by name.

Wave 49's CI failure was a pipeline test that scraped live NBA stats: CI has network,
the dev container does not, so the same test wrote `data/scraper_cache` on one and
waited out timeouts on the other. `tests/__init__.py` now refuses every connection and
name lookup that is not loopback (`NetworkBlocked`, an OSError, so fail-open code
behaves exactly as it does offline) and drops the proxy variables, which would
otherwise route a request through a loopback proxy and out. A test during which an
attempt was made is marked failed with the host, whatever the code under test did
with the error - so CI goes red on both legs, naming the test.
"""

from __future__ import annotations

import os
import socket
import unittest


class GuardTests(unittest.TestCase):
    def test_a_remote_connection_is_refused(self):
        from tests import NetworkBlocked, take_network_attempts

        with self.assertRaises(NetworkBlocked):
            socket.create_connection(("example.com", 80), timeout=1)
        take_network_attempts()  # this test made the attempt on purpose

    def test_loopback_still_works(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        try:
            client = socket.create_connection(server.getsockname(), timeout=1)
            client.close()
        finally:
            server.close()

    def test_no_proxy_carries_requests_out(self):
        names = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy")
        self.assertEqual([n for n in names if n in os.environ], [])

    def test_a_swallowed_attempt_still_fails_the_test(self):
        class Inner(unittest.TestCase):
            def test_fail_open_fetch(self):
                try:
                    socket.create_connection(("feeds.example.com", 443), timeout=1)
                except OSError:
                    pass  # the code under test fails open, as fetchers do

        result = unittest.TestResult()
        Inner("test_fail_open_fetch").run(result)
        self.assertEqual(len(result.failures), 1)
        self.assertIn("feeds.example.com", result.failures[0][1])


if __name__ == "__main__":
    unittest.main()
