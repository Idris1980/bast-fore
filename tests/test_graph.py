import email.message
import io
import json
import unittest
import urllib.error
from unittest import mock

import graph
from graph import Graph, GraphFel, vantetid


def http_fel(kod, retry_after=None):
    huvuden = email.message.Message()
    if retry_after is not None:
        huvuden["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://x", kod, "fel", huvuden, io.BytesIO(b"text"))


def svar(data):
    return io.BytesIO(json.dumps(data).encode())


class Vantetid(unittest.TestCase):
    def test_foljer_retry_after(self):
        self.assertEqual(vantetid("7", 0), 7)

    def test_dubblas_utan_retry_after(self):
        self.assertEqual([vantetid(None, n) for n in range(4)], [1, 2, 4, 8])

    def test_tak_60_sekunder(self):
        self.assertEqual(vantetid("600", 0), 60)
        self.assertEqual(vantetid(None, 10), 60)

    def test_datum_i_retry_after_ignoreras(self):
        self.assertEqual(vantetid("Wed, 21 Oct 2026 07:28:00 GMT", 1), 2)


@mock.patch("graph.time.sleep")
class Forsok(unittest.TestCase):
    def test_429_forsoker_igen(self, sov):
        with mock.patch("graph.urllib.request.urlopen", side_effect=[http_fel(429, "3"), svar({"ok": 1})]):
            self.assertEqual(Graph("t").hamta("/x"), {"ok": 1})
        sov.assert_called_once_with(3)

    def test_ger_upp_efter_alla_forsok(self, sov):
        fel = [http_fel(503) for _ in range(graph.FORSOK)]
        with mock.patch("graph.urllib.request.urlopen", side_effect=fel):
            with self.assertRaises(GraphFel) as f:
                Graph("t").hamta("/x")
        self.assertEqual(f.exception.status, 503)
        self.assertEqual(sov.call_count, graph.FORSOK - 1)

    def test_403_forsoker_inte_igen(self, sov):
        with mock.patch("graph.urllib.request.urlopen", side_effect=[http_fel(403)]):
            with self.assertRaises(GraphFel):
                Graph("t").hamta("/x")
        sov.assert_not_called()

    def test_lista_foljer_nextlink(self, sov):
        sidor = [svar({"value": [1, 2], "@odata.nextLink": "https://n"}), svar({"value": [3]})]
        with mock.patch("graph.urllib.request.urlopen", side_effect=sidor):
            self.assertEqual(list(Graph("t").lista("/x")), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
