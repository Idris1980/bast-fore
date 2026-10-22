import re
import unittest
import urllib.parse

from graph import GraphFel
from kopplingar import (OK, PERSONLIGT, SLUTAT, TRASIG, Koppling, Person, anslutna, bedom_koppling,
                        bedom_kopplingar, fran_arm, resursgrupp, samla_kopplingar)

KID = "/subscriptions/s1/resourceGroups/rg-lon/providers/Microsoft.Web/connections/sharepoint"


def koppling(konto="", person=None, status="Connected", fel="", namn="k"):
    return Koppling(KID, namn, "SharePoint", "rg-lon", "Prod", konto, status, fel, [], person)


class FranArm(unittest.TestCase):
    def test_personlig_koppling(self):
        k = fran_arm({
            "id": KID, "name": "sharepoint",
            "properties": {
                "displayName": "pelle@nordvik.se",
                "api": {"name": "sharepointonline", "displayName": "SharePoint"},
                "authenticatedUser": {"name": "pelle@nordvik.se"},
                "statuses": [{"status": "Connected"}],
            },
        }, "Prod")
        self.assertEqual((k.namn, k.api, k.resursgrupp, k.konto, k.status, k.fel),
                         ("pelle@nordvik.se", "SharePoint", "rg-lon", "pelle@nordvik.se", "Connected", ""))

    def test_fel_och_tom_anvandare(self):
        k = fran_arm({
            "id": KID, "name": "sharepoint",
            "properties": {
                "authenticatedUser": {},
                "statuses": [{"status": "Connected"}, {"status": "Error", "error": {"code": "Unauthorized"}}],
            },
        }, "Prod")
        self.assertEqual((k.namn, k.konto, k.status, k.fel), ("sharepoint", "", "Error", "Unauthorized"))

    def test_overallstatus_som_reserv(self):
        k = fran_arm({"id": KID, "properties": {"overallStatus": "Connected"}}, "Prod")
        self.assertEqual(k.status, "Connected")

    def test_resursgrupp(self):
        self.assertEqual(resursgrupp(KID), "rg-lon")
        self.assertEqual(resursgrupp("/subscriptions/s1"), "")


class Anslutna(unittest.TestCase):
    def test_laser_connections_parametern(self):
        la = {"properties": {"parameters": {"$connections": {"value": {
            "sharepoint": {"connectionId": KID, "id": "/api"},
            "trasig": "inte ett objekt",
        }}}}}
        self.assertEqual(anslutna(la), [KID])

    def test_utan_kopplingar(self):
        self.assertEqual(anslutna({"properties": {}}), [])


class Bedom(unittest.TestCase):
    def test_utan_konto_ar_ok(self):
        self.assertEqual(bedom_koppling(koppling()).niva, OK)

    def test_aktiv_person_ar_personligt(self):
        f = bedom_koppling(koppling("a@x", Person("a@x", "A", True, True)))
        self.assertEqual(f.niva, PERSONLIGT)
        self.assertIn("a@x", f.notering)

    def test_okand_person_ar_personligt(self):
        self.assertEqual(bedom_koppling(koppling("a@x", None)).niva, PERSONLIGT)
        self.assertEqual(bedom_koppling(koppling("a@x", Person("a@x"))).niva, PERSONLIGT)

    def test_inaktiverad_person(self):
        f = bedom_koppling(koppling("a@x", Person("a@x", "A", True, False)))
        self.assertEqual(f.niva, SLUTAT)
        self.assertIn("inaktiverat", f.notering)

    def test_person_finns_inte(self):
        f = bedom_koppling(koppling("a@x", Person("a@x", finns=False)))
        self.assertEqual(f.niva, SLUTAT)
        self.assertIn("finns inte i katalogen", f.notering)

    def test_fel_gar_fore_allt_annat(self):
        f = bedom_koppling(koppling("a@x", Person("a@x", finns=False), "Error", "Token gick ut"))
        self.assertEqual(f.niva, TRASIG)
        self.assertIn("Token gick ut", f.notering)
        self.assertIn("finns inte längre", f.notering)

    def test_fel_utan_konto(self):
        self.assertEqual(bedom_koppling(koppling(status="Error")).notering, "Kopplingen har fel.")

    def test_ordning(self):
        fynd = bedom_kopplingar([
            koppling(namn="ok"),
            koppling("a@x", Person("a@x", "A", True, True), namn="b-personlig"),
            koppling("a@x", Person("a@x", "A", True, True), namn="a-personlig"),
            koppling(status="Error", namn="trasig"),
        ])
        self.assertEqual([f.koppling.namn for f in fynd], ["trasig", "a-personlig", "b-personlig", "ok"])


class FalskArm:
    """Svarar som Azure Resource Manager. Resurslistor filtreras på resourceType som det riktiga API:et."""

    def __init__(self, prenumerationer, resurser, fel=None):
        self.prenumerationer, self.resurser, self.fel = prenumerationer, resurser, fel or {}

    def lista(self, sokvag):
        bas, _, fraga = sokvag.partition("?")
        if bas in self.fel:
            raise GraphFel(self.fel[bas], "nej", "Azure")
        if bas == "/subscriptions":
            return iter(self.prenumerationer)
        sub = bas.split("/")[2]
        typ = re.search(r"resourceType eq '([^']+)'", urllib.parse.unquote(fraga)).group(1)
        return iter([{"id": r["id"], "name": r["name"]} for r in self.resurser
                     if r["typ"] == typ and r["id"].split("/")[2] == sub])

    def hamta(self, sokvag):
        bas = sokvag.partition("?")[0]
        if bas in self.fel:
            raise GraphFel(self.fel[bas], "nej", "Azure")
        return next(r["post"] for r in self.resurser if r["id"] == bas)


class FalskGraph:
    def __init__(self, anvandare, fel=None):
        self.anvandare, self.fel, self.anrop = anvandare, fel, []

    def lista(self, sokvag):
        self.anrop.append(sokvag)
        if self.fel:
            raise GraphFel(self.fel, "nej")
        egenskap, varde = re.search(r"\$filter=(\w+) eq '(.*)'&", urllib.parse.unquote(sokvag)).groups()
        varde = varde.replace("''", "'")
        return iter([u for u in self.anvandare if (u.get(egenskap) or "").lower() == varde.lower()])


def kopplingsresurs(sub, namn, konto="", status="Connected"):
    id = f"/subscriptions/{sub}/resourceGroups/rg/providers/Microsoft.Web/connections/{namn}"
    post = {"id": id, "name": namn, "properties": {
        "api": {"displayName": "Office 365 Outlook"},
        "authenticatedUser": {"name": konto} if konto else {},
        "statuses": [{"status": status}],
    }}
    return {"typ": "Microsoft.Web/connections", "id": id, "name": namn, "post": post}


def logic_app(sub, namn, *kopplings_id):
    id = f"/subscriptions/{sub}/resourceGroups/rg/providers/Microsoft.Logic/workflows/{namn}"
    varden = {f"k{i}": {"connectionId": k} for i, k in enumerate(kopplings_id)}
    post = {"id": id, "name": namn, "properties": {"parameters": {"$connections": {"value": varden}}}}
    return {"typ": "Microsoft.Logic/workflows", "id": id, "name": namn, "post": post}


PRENUMERATIONER = [{"subscriptionId": "s1", "displayName": "Prod"}, {"subscriptionId": "s2", "displayName": "Test"}]


class Samla(unittest.TestCase):
    def test_hela_kedjan(self):
        k1 = kopplingsresurs("s1", "outlook", "pelle@nordvik.se")
        k2 = kopplingsresurs("s1", "blob")
        k3 = kopplingsresurs("s2", "gast", "kund@extern.se")
        arm = FalskArm(PRENUMERATIONER, [
            k1, k2, k3,
            # Versalerna skiljer sig ibland mellan Logic Appen och kopplingen.
            logic_app("s1", "la-faktura", k1["id"].upper(), k2["id"]),
            logic_app("s1", "la-lon", k1["id"]),
        ])
        graph = FalskGraph([
            {"userPrincipalName": "pelle@nordvik.se", "displayName": "Pelle", "accountEnabled": False},
            {"userPrincipalName": "kund_extern.se#EXT#@nordvik.onmicrosoft.com", "mail": "kund@extern.se",
             "displayName": "Kund", "accountEnabled": True},
        ])
        kopplingar, anteckningar = samla_kopplingar(arm, graph)
        self.assertEqual(anteckningar, [])
        per_namn = {k.namn: k for k in kopplingar}

        self.assertEqual(per_namn["outlook"].anvands_av, ["la-faktura", "la-lon"])
        self.assertEqual(per_namn["outlook"].person, Person("pelle@nordvik.se", "Pelle", True, False))
        self.assertEqual(per_namn["outlook"].prenumeration, "Prod")
        self.assertEqual(per_namn["blob"].anvands_av, ["la-faktura"])
        self.assertIsNone(per_namn["blob"].person)
        self.assertEqual(per_namn["gast"].anvands_av, [])
        self.assertEqual(per_namn["gast"].person.namn, "Kund")

    def test_samma_konto_slas_upp_en_gang(self):
        arm = FalskArm(PRENUMERATIONER[:1], [kopplingsresurs("s1", "a", "x@y"), kopplingsresurs("s1", "b", "X@y")])
        graph = FalskGraph([])
        kopplingar, _ = samla_kopplingar(arm, graph)
        self.assertEqual(len(graph.anrop), 2)   # en gång på inloggningsnamn och en på e-post
        self.assertEqual([k.person.finns for k in kopplingar], [False, False])

    def test_apostrof_i_konto(self):
        arm = FalskArm(PRENUMERATIONER[:1], [kopplingsresurs("s1", "a", "o'hara@y")])
        graph = FalskGraph([{"userPrincipalName": "o'hara@y", "accountEnabled": True}])
        kopplingar, _ = samla_kopplingar(arm, graph)
        self.assertTrue(kopplingar[0].person.finns)
        self.assertIn("o%27%27hara", graph.anrop[0])

    def test_inga_prenumerationer(self):
        kopplingar, anteckningar = samla_kopplingar(FalskArm([], []), FalskGraph([]))
        self.assertEqual(kopplingar, [])
        self.assertIn("Inga Azure-prenumerationer", anteckningar[0])

    def test_prenumeration_som_inte_gar_att_lasa_hoppas_over(self):
        arm = FalskArm(PRENUMERATIONER, [kopplingsresurs("s2", "a")], fel={"/subscriptions/s1/resources": 403})
        kopplingar, anteckningar = samla_kopplingar(arm, FalskGraph([]))
        self.assertEqual([k.namn for k in kopplingar], ["a"])
        self.assertIn("prenumerationen Prod (403)", anteckningar[0])

    def test_koppling_som_inte_gar_att_lasa_raknas(self):
        k = kopplingsresurs("s1", "a")
        arm = FalskArm(PRENUMERATIONER[:1], [k, kopplingsresurs("s1", "b")], fel={k["id"]: 404})
        kopplingar, anteckningar = samla_kopplingar(arm, FalskGraph([]))
        self.assertEqual([k.namn for k in kopplingar], ["b"])
        self.assertEqual(anteckningar, ["Kunde inte läsa 1 koppling."])

    def test_logic_app_som_inte_gar_att_lasa_ger_okand_anvandning(self):
        la = logic_app("s1", "la", "x")
        arm = FalskArm(PRENUMERATIONER[:1], [kopplingsresurs("s1", "a"), la], fel={la["id"]: 500})
        kopplingar, anteckningar = samla_kopplingar(arm, FalskGraph([]))
        self.assertIsNone(kopplingar[0].anvands_av)
        self.assertIn("Kunde inte läsa alla Logic Apps", anteckningar[0])

    def test_403_mot_entra_ger_okanda_personer(self):
        arm = FalskArm(PRENUMERATIONER[:1], [kopplingsresurs("s1", "a", "x@y")])
        kopplingar, anteckningar = samla_kopplingar(arm, FalskGraph([], fel=403))
        self.assertIsNone(kopplingar[0].person)
        self.assertIn("saknar behörighet att läsa användare", anteckningar[0])
        self.assertEqual(bedom_koppling(kopplingar[0]).niva, PERSONLIGT)


if __name__ == "__main__":
    unittest.main()
