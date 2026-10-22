"""Påhittad tenant för att visa rapporten utan att logga in. Datumen räknas från idag."""

from datetime import datetime, timedelta, timezone

from kontroller import Agare, Nyckel, Objekt
from kopplingar import Koppling, Person


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


def demo_kopplingar():
    def koppling(namn, api, rg, konto="", person=None, status="Connected", fel="", anvands_av=()):
        return Koppling(f"/subscriptions/demo/resourceGroups/{rg}/providers/Microsoft.Web/connections/{namn}",
                        namn, api, rg, "Nordvik produktion", konto, status, fel, list(anvands_av), person)

    pelle = Person("pelle.holm@nordvik.se", "Pelle Holm", True, False)
    erik = Person("erik.lund@nordvik.se", "Erik Lund", True, True)
    sara = Person("sara.ek@nordvik.se", finns=False)

    return [
        koppling("teams-driftlarm", "Microsoft Teams", "rg-drift", sara.konto, sara, "Error",
                 "The refresh token has expired due to inactivity.", ["la-driftlarm"]),
        koppling("sharepoint-lon", "SharePoint", "rg-lon", pelle.konto, pelle, anvands_av=["la-lonefiler"]),
        koppling("office365-fakturor", "Office 365 Outlook", "rg-ekonomi", erik.konto, erik,
                 anvands_av=["la-fakturamejl", "la-paminnelser"]),
        koppling("office365-test", "Office 365 Outlook", "rg-ekonomi", erik.konto, erik),
        koppling("blob-lon", "Azure Blob Storage", "rg-lon", anvands_av=["la-lonefiler"]),
        koppling("servicebus-order", "Service Bus", "rg-ekonomi", anvands_av=["la-fakturamejl"]),
    ]
