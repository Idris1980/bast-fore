"""Påhittad tenant för att visa rapporten utan att logga in. Datumen räknas från idag."""

from datetime import datetime, timedelta, timezone

from kontroller import Nyckel, Objekt


def demo_objekt():
    nu = datetime.now(timezone.utc)

    def om(dagar):
        return nu + timedelta(days=dagar)

    return [
        Objekt("App", "Fakturaimport", "3f2a9c1e-0000-4000-8000-000000000001",
               [Nyckel("hemlighet", "prod", om(-10))]),
        Objekt("App", "Fortnox-integration", "3f2a9c1e-0000-4000-8000-000000000002",
               [Nyckel("hemlighet", "nyckel 2024", om(12))]),
        Objekt("App", "Lönefilsexport", "3f2a9c1e-0000-4000-8000-000000000003",
               [Nyckel("hemlighet", "gammal", om(9)), Nyckel("hemlighet", "ny", om(700))]),
        Objekt("Företagsapp", "Visma SSO", "3f2a9c1e-0000-4000-8000-000000000004",
               [Nyckel("certifikat", "CN=Microsoft Azure Federated SSO Certificate", om(45))]),
        Objekt("App", "Bokningssystem", "3f2a9c1e-0000-4000-8000-000000000005",
               [Nyckel("certifikat", "CN=bokning", om(300))]),
        Objekt("App", "Hyresportal", "3f2a9c1e-0000-4000-8000-000000000007",
               [Nyckel("hemlighet", "deploy", om(178)), Nyckel("hemlighet", "deploy", om(179))]),
        Objekt("App", "Testapp Pelle 2021", "3f2a9c1e-0000-4000-8000-000000000006",
               [Nyckel("hemlighet", "test", om(-900))]),
    ]
