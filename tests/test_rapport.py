import contextlib
import io
import os
import tempfile
import unittest
from datetime import datetime, timezone

import kopplingar as kp
from kontroller import AGARE, OK, TRASIGT, Fynd, Nyckel, Objekt
from rapport import nar, skriv_html, skriv_terminal

SLUT = datetime(2026, 10, 22, 10, tzinfo=timezone.utc)


def fynd(niva, dagar, utgangen=False, namn="Test", notering=""):
    return Fynd(niva, Objekt("App", namn, "app-id", []), Nyckel("hemlighet", "h", SLUT), dagar, notering, utgangen)


class Nar(unittest.TestCase):
    def test_gick_ut_idag(self):
        self.assertEqual(nar(fynd(TRASIGT, 0, utgangen=True)), "gick ut 2026-10-22 (idag)")

    def test_gar_ut_idag(self):
        self.assertEqual(nar(fynd(OK, 0)), "går ut 2026-10-22 (idag)")

    def test_framat_och_bakat(self):
        self.assertEqual(nar(fynd(OK, 12)), "går ut 2026-10-22 (om 12 dagar)")
        self.assertEqual(nar(fynd(TRASIGT, -3, utgangen=True)), "gick ut 2026-10-22 (för 3 dagar sedan)")


class Terminal(unittest.TestCase):
    def skriv(self, *args, **kw):
        ut = io.StringIO()
        with contextlib.redirect_stdout(ut):
            skriv_terminal(*args, **kw)
        return ut.getvalue()

    def test_bara_ok(self):
        text = self.skriv([fynd(OK, 200)], 1, "Nordvik")
        self.assertIn("Inget går ut inom 60 dagar.", text)
        self.assertIn("🟢 I ORDNING", text)

    def test_agargrupp_och_anteckningar(self):
        text = self.skriv([fynd(AGARE, 30, notering="Appen har ingen ägare.")], 1, "", ["Kunde inte läsa ägare för 1 av 2 appar."])
        self.assertIn("👤 INGEN ÄGARE KVAR", text)
        self.assertIn("okänd organisation", text)
        self.assertIn("Kunde inte läsa ägare", text)


def kfynd(niva, namn="k", konto="", anvands_av=None, notering=""):
    k = kp.Koppling("/id", namn, "SharePoint", "rg-lon", "Prod", konto, anvands_av=anvands_av)
    return kp.KFynd(niva, k, notering)


class Kopplingar(unittest.TestCase):
    def skriv(self, kf):
        ut = io.StringIO()
        with contextlib.redirect_stdout(ut):
            skriv_terminal([fynd(OK, 200)], 1, "Nordvik", [], kf)
        return ut.getvalue()

    def test_inte_kontrollerat_syns_inte(self):
        self.assertNotIn("kopplingar", self.skriv(None))

    def test_grupper_och_ok_som_siffra(self):
        text = self.skriv([
            kfynd(kp.SLUTAT, "sp", "pelle@x", ["la-lon"], "Kontot är inaktiverat."),
            kfynd(kp.PERSONLIGT, "outlook", "erik@x", []),
            kfynd(kp.OK, "blob"), kfynd(kp.OK, "sb"),
        ])
        self.assertIn('🟠 KONTOT FINNS INTE KVAR\n   Koppling "sp" (SharePoint) i rg-lon – inloggad som pelle@x', text)
        self.assertIn("Används av la-lon.", text)
        self.assertIn("Ingen Logic App (förbrukningsplan) använder den.", text)
        self.assertIn("🟢 2 kopplingar loggar inte in som en person.", text)
        self.assertNotIn('"blob"', text)
        self.assertIn("4 kopplingar i Logic Apps kontrollerade.", text)

    def test_noll_kopplingar_ger_bara_summeringen(self):
        text = self.skriv([])
        self.assertNotIn("LOGIC APPS-KOPPLINGAR", text)
        self.assertIn("0 kopplingar i Logic Apps kontrollerade.", text)
        self.assertIn("1 app med nycklar kontrollerade.", text)

    def test_en_koppling_i_ental(self):
        text = self.skriv([kfynd(kp.OK, "blob")])
        self.assertIn("🟢 1 koppling loggar inte in som en person.", text)
        self.assertIn("1 koppling i Logic Apps kontrollerade.", text)

    def test_html(self):
        with tempfile.TemporaryDirectory() as mapp:
            sokvag = os.path.join(mapp, "r.html")
            skriv_html([], 0, "", sokvag, [], [kfynd(kp.TRASIG, "<b>", "a@x", ["la"])])
            with open(sokvag, encoding="utf-8") as f:
                text = f.read()
        self.assertIn("Logic Apps-kopplingar", text)
        self.assertIn("&lt;b&gt;", text)
        self.assertIn("1 koppling kontrollerad", text)


class Html(unittest.TestCase):
    def test_escapar_namn(self):
        with tempfile.TemporaryDirectory() as mapp:
            sokvag = os.path.join(mapp, "r.html")
            skriv_html([fynd(TRASIGT, -1, True, namn="<script>x</script>")], 1, "A & B", sokvag, ["not"])
            with open(sokvag, encoding="utf-8") as f:
                text = f.read()
        self.assertNotIn("<script>x", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("A &amp; B", text)
        self.assertIn('<p class="under">not</p>', text)


if __name__ == "__main__":
    unittest.main()
