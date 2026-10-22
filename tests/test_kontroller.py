import unittest
from datetime import datetime, timedelta, timezone

import kontroller
from graph import GraphFel
from kontroller import (AGARE, INOM_14, INOM_60, OK, STADA, TRASIGT, Agare, Nyckel, Objekt,
                        bedom, bedom_alla, dagar_kvar, fran_graph, samla)

# Mitt på dagen, så att hela dagar framåt och bakåt blir samma datum i alla tidszoner vi bryr oss om.
NU = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)


def om(dagar, timmar=0):
    return NU + timedelta(days=dagar, hours=timmar)


def app(*nycklar, agare=None):
    return Objekt("App", "Test", "app-id", list(nycklar), "obj-id", agare)


def hemlighet(slut, namn="h"):
    return Nyckel("hemlighet", namn, slut)


def nivaer(fynd):
    return [f.niva for f in fynd]


class Grupper(unittest.TestCase):
    def test_nyckel_langt_fram_ar_ok(self):
        fynd = bedom(app(hemlighet(om(200))), NU)
        self.assertEqual(nivaer(fynd), [OK])
        self.assertEqual(fynd[0].dagar, 200)

    def test_gransen_14_dagar(self):
        self.assertEqual(nivaer(bedom(app(hemlighet(om(14))), NU)), [INOM_14])
        self.assertEqual(nivaer(bedom(app(hemlighet(om(15))), NU)), [INOM_60])

    def test_gransen_60_dagar(self):
        self.assertEqual(nivaer(bedom(app(hemlighet(om(60))), NU)), [INOM_60])
        self.assertEqual(nivaer(bedom(app(hemlighet(om(61))), NU)), [OK])

    def test_alla_utgangna_nyligen_ar_trasigt(self):
        fynd = bedom(app(hemlighet(om(-10)), hemlighet(om(-30))), NU)
        self.assertEqual(nivaer(fynd), [TRASIGT])
        self.assertEqual(fynd[0].dagar, -10)
        self.assertTrue(fynd[0].utgangen)

    def test_gransen_90_dagar_mot_stada(self):
        self.assertEqual(nivaer(bedom(app(hemlighet(om(-90))), NU)), [TRASIGT])
        self.assertEqual(nivaer(bedom(app(hemlighet(om(-91))), NU)), [STADA])

    def test_utgangen_tidigare_idag_ar_trasigt_och_utgangen(self):
        fynd = bedom(app(hemlighet(om(0, timmar=-2))), NU)
        self.assertEqual(nivaer(fynd), [TRASIGT])
        self.assertEqual(fynd[0].dagar, 0)
        self.assertTrue(fynd[0].utgangen)

    def test_gar_ut_senare_idag_ar_inte_utgangen(self):
        fynd = bedom(app(hemlighet(om(0, timmar=2))), NU)
        self.assertEqual(nivaer(fynd), [INOM_14])
        self.assertFalse(fynd[0].utgangen)


class GammalOchNyNyckel(unittest.TestCase):
    def test_varnar_for_gammal_nyckel_trots_ny(self):
        gammal, ny = hemlighet(om(9), "gammal"), hemlighet(om(700), "ny")
        fynd = bedom(app(gammal, ny), NU)
        self.assertEqual(nivaer(fynd), [INOM_14])
        self.assertIs(fynd[0].nyckel, gammal)
        self.assertIn("nyare hemlighet", fynd[0].notering)

    def test_utgangen_gammal_nyckel_ignoreras_nar_ny_galler(self):
        fynd = bedom(app(hemlighet(om(-5)), hemlighet(om(300))), NU)
        self.assertEqual(nivaer(fynd), [OK])
        self.assertEqual(fynd[0].dagar, 300)

    def test_ok_visar_nyaste_och_antal(self):
        fynd = bedom(app(hemlighet(om(100)), hemlighet(om(400))), NU)
        self.assertEqual(fynd[0].dagar, 400)
        self.assertEqual(fynd[0].notering, "2 hemligheter.")

    def test_blandade_typer_heter_nycklar(self):
        fynd = bedom(app(hemlighet(om(100)), Nyckel("certifikat", "c", om(400))), NU)
        self.assertEqual(fynd[0].notering, "2 nycklar.")


class Agarskap(unittest.TestCase):
    def agarfynd(self, agare, *nycklar):
        fynd = bedom(app(*(nycklar or [hemlighet(om(200))]), agare=agare), NU)
        return [f for f in fynd if f.niva == AGARE]

    def test_inte_kontrollerat_ger_inget(self):
        self.assertEqual(self.agarfynd(None), [])

    def test_ingen_agare(self):
        fynd = self.agarfynd([])
        self.assertEqual(len(fynd), 1)
        self.assertIn("ingen ägare", fynd[0].notering)
        self.assertEqual(fynd[0].dagar, 200)

    def test_aktiv_agare_ger_inget(self):
        self.assertEqual(self.agarfynd([Agare("person", "Anna", "anna@x", True)]), [])

    def test_inaktiverad_agare(self):
        fynd = self.agarfynd([Agare("person", "Pelle", "pelle@x", False)])
        self.assertIn("Ägaren Pelle (pelle@x) är inaktiverad", fynd[0].notering)

    def test_alla_inaktiverade(self):
        fynd = self.agarfynd([Agare("person", "A", aktiv=False), Agare("person", "B", aktiv=False)])
        self.assertIn("Alla ägare är inaktiverade", fynd[0].notering)

    def test_en_aktiv_bland_inaktiverade_racker(self):
        self.assertEqual(self.agarfynd([Agare("person", "A", aktiv=False), Agare("person", "B", aktiv=True)]), [])

    def test_okand_status_raknas_som_kvar(self):
        self.assertEqual(self.agarfynd([Agare("person", "A", aktiv=None)]), [])

    def test_app_som_agare_racker(self):
        self.assertEqual(self.agarfynd([Agare("app", "pipeline", aktiv=True), Agare("person", "A", aktiv=False)]), [])

    def test_utgangen_app_far_ingen_agarvarning(self):
        self.assertEqual(self.agarfynd([], hemlighet(om(-10))), [])

    def test_agarvarning_pekar_pa_nyaste_nyckeln(self):
        fynd = self.agarfynd([], hemlighet(om(9)), hemlighet(om(300)))
        self.assertEqual(fynd[0].dagar, 300)

    def test_agarvarning_ersatter_i_ordning(self):
        fynd = bedom(app(hemlighet(om(200)), agare=[]), NU)
        self.assertEqual(nivaer(fynd), [AGARE])

    def test_agarvarning_ersatter_inte_andra_varningar(self):
        fynd = bedom(app(hemlighet(om(10)), hemlighet(om(200)), agare=[]), NU)
        self.assertEqual(nivaer(fynd), [INOM_14, AGARE])

    def test_systemhanterade_appar_far_ingen_agarvarning(self):
        for namn in ("P2P Server", "ConnectSyncProvisioning_SRV-AD01_256851fc36df"):
            obj = Objekt("App", namn, "app-id", [hemlighet(om(84))], "obj-id", [])
            self.assertEqual(nivaer(bedom(obj, NU)), [OK])

    def test_systemhanterade_appar_varnar_fortfarande_for_nycklar(self):
        obj = Objekt("App", "P2P Server", "app-id", [hemlighet(om(10))], "obj-id", [])
        self.assertEqual(nivaer(bedom(obj, NU)), [INOM_14])


class Tidszon(unittest.TestCase):
    def tearDown(self):
        kontroller.ZON = None

    def test_dagar_raknas_i_lokal_tid(self):
        # 23.30 UTC är 01.30 nästa dag i Sverige på sommartid.
        nyckel = hemlighet(datetime(2026, 7, 1, 23, 30, tzinfo=timezone.utc))
        nu = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
        kontroller.ZON = timezone.utc
        self.assertEqual(dagar_kvar(nyckel, nu), 0)
        kontroller.ZON = timezone(timedelta(hours=2))
        self.assertEqual(dagar_kvar(nyckel, nu), 1)


class FranGraph(unittest.TestCase):
    def test_sju_decimaler_och_saml_dubbletter(self):
        post = {
            "id": "obj", "appId": "app", "displayName": "SSO",
            "passwordCredentials": [{"displayName": None, "endDateTime": "2027-01-01T10:00:00.1234567Z"}],
            "keyCredentials": [
                {"displayName": "CN=sso", "endDateTime": "2027-05-01T00:00:00Z"},
                {"displayName": "CN=sso", "endDateTime": "2027-05-01T00:00:00Z"},
            ],
        }
        obj = fran_graph(post, "Företagsapp")
        self.assertEqual(obj.id, "obj")
        self.assertEqual(len(obj.nycklar), 2)
        self.assertEqual(obj.nycklar[0].namn, "namnlös")
        self.assertEqual(obj.nycklar[0].slut, datetime(2027, 1, 1, 10, tzinfo=timezone.utc))

    def test_nyckel_utan_slutdatum_hoppas_over(self):
        obj = fran_graph({"appId": "a", "passwordCredentials": [{"displayName": "x"}]}, "App")
        self.assertEqual(obj.nycklar, [])
        self.assertEqual(obj.namn, "a")


class FalskGraph:
    def __init__(self, svar, fel=None):
        self.svar, self.fel, self.anrop = svar, fel or {}, []

    def lista(self, sokvag):
        self.anrop.append(sokvag)
        bas = sokvag.split("?")[0]
        if bas in self.fel:
            raise GraphFel(self.fel[bas], "nej")
        return iter(self.svar.get(bas, []))


def nyckelpost(id, slut="2027-06-01T00:00:00Z", **extra):
    return {"id": id, "appId": id, "displayName": id,
            "passwordCredentials": [{"displayName": "p", "endDateTime": slut}], **extra}


class Samla(unittest.TestCase):
    def test_hoppar_over_microsoft_och_appar_utan_nycklar(self):
        graph = FalskGraph({
            "/applications": [nyckelpost("a1"), {"id": "a2", "appId": "a2"}],
            "/servicePrincipals": [
                nyckelpost("sp1"),
                nyckelpost("ms", appOwnerOrganizationId="f8cdef31-a31e-4b4a-93e4-5f571e91255a"),
            ],
        })
        objekt, anteckningar = samla(graph, med_agare=False, nu=NU)
        self.assertEqual([(o.slag, o.id) for o in objekt], [("App", "a1"), ("Företagsapp", "sp1")])
        self.assertEqual(anteckningar, [])

    def test_lasar_agare_bara_for_appar_som_fungerar(self):
        graph = FalskGraph({
            "/applications": [nyckelpost("lever"), nyckelpost("dod", slut="2020-01-01T00:00:00Z")],
            "/applications/lever/owners": [
                {"@odata.type": "#microsoft.graph.user", "displayName": "Pelle",
                 "userPrincipalName": "pelle@x", "accountEnabled": False},
                {"@odata.type": "#microsoft.graph.servicePrincipal", "displayName": "pipeline"},
            ],
        })
        objekt, _ = samla(graph, nu=NU)
        lever, dod = objekt
        self.assertEqual(lever.agare, [Agare("person", "Pelle", "pelle@x", False),
                                       Agare("app", "pipeline", "", True)])
        self.assertIsNone(dod.agare)
        self.assertFalse(any("/dod/" in a for a in graph.anrop))

    def test_foretagsapp_lases_fran_servicePrincipals(self):
        graph = FalskGraph({"/servicePrincipals": [nyckelpost("sp1")]})
        samla(graph, nu=NU)
        self.assertIn("/servicePrincipals/sp1/owners", [a.split("?")[0] for a in graph.anrop])

    def test_403_stoppar_agarkontrollen(self):
        graph = FalskGraph({"/applications": [nyckelpost("a1"), nyckelpost("a2")]},
                           fel={"/applications/a1/owners": 403})
        objekt, anteckningar = samla(graph, nu=NU)
        self.assertTrue(all(o.agare is None for o in objekt))
        self.assertIn("behörighet", anteckningar[0])
        self.assertFalse(any("/a2/owners" in a for a in graph.anrop))

    def test_annat_fel_raknas_och_resten_fortsatter(self):
        graph = FalskGraph({"/applications": [nyckelpost("a1"), nyckelpost("a2")]},
                           fel={"/applications/a1/owners": 500})
        objekt, anteckningar = samla(graph, nu=NU)
        self.assertIsNone(objekt[0].agare)
        self.assertEqual(objekt[1].agare, [])
        self.assertEqual(anteckningar, ["Kunde inte läsa ägare för 1 av 2 appar."])


class BedomAlla(unittest.TestCase):
    def test_sorteras_efter_dagar(self):
        fynd = bedom_alla([app(hemlighet(om(300))), app(hemlighet(om(-5))), app(hemlighet(om(10)))], NU)
        self.assertEqual([f.dagar for f in fynd], [-5, 10, 300])


if __name__ == "__main__":
    unittest.main()
