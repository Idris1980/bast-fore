"""Påhittad tenant för att visa rapporten utan att logga in. Datumen räknas från idag."""

from datetime import datetime, timedelta, timezone

from kontroller import Agare, Nyckel, Objekt


def demo_objekt():
    nu = datetime.now(timezone.utc)

    def om(dagar):
        return nu + timedelta(days=dagar)

    anna = Agare("person", "Anna Berg", "anna.berg@nordvik.se", True)
    erik = Agare("person", "Erik Lund", "erik.lund@nordvik.se", True)
    pelle = Agare("person", "Pelle Holm", "pelle.holm@nordvik.se", False)

    return [
        Objekt("App", "Fakturaimport", "3f2a9c1e-0000-4000-8000-000000000001",
               [Nyckel("hemlighet", "prod", om(-10))], agare=[anna]),
        Objekt("App", "Fortnox-integration", "3f2a9c1e-0000-4000-8000-000000000002",
               [Nyckel("hemlighet", "nyckel 2024", om(12))], agare=[pelle]),
        Objekt("App", "Lönefilsexport", "3f2a9c1e-0000-4000-8000-000000000003",
               [Nyckel("hemlighet", "gammal", om(9)), Nyckel("hemlighet", "ny", om(700))], agare=[anna]),
        Objekt("Företagsapp", "Visma SSO", "3f2a9c1e-0000-4000-8000-000000000004",
               [Nyckel("certifikat", "CN=Microsoft Azure Federated SSO Certificate", om(45))], agare=[]),
        Objekt("App", "Bokningssystem", "3f2a9c1e-0000-4000-8000-000000000005",
               [Nyckel("certifikat", "CN=bokning", om(300))], agare=[erik, pelle]),
        Objekt("App", "Hyresportal", "3f2a9c1e-0000-4000-8000-000000000007",
               [Nyckel("hemlighet", "deploy", om(178)), Nyckel("hemlighet", "deploy", om(179))],
               agare=[Agare("app", "deploy-pipeline", aktiv=True)]),
        Objekt("App", "Testapp Pelle 2021", "3f2a9c1e-0000-4000-8000-000000000006",
               [Nyckel("hemlighet", "test", om(-900))], agare=[]),
    ]
