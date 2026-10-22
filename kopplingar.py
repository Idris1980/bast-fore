"""Kopplingar i Logic Apps som är inloggade med en persons konto och slutar fungera när personen slutar."""

import urllib.parse
from dataclasses import dataclass, field

from graph import GraphFel

TRASIG = "k_trasig"
SLUTAT = "k_slutat"
PERSONLIGT = "k_personligt"
OK = "k_ok"

API_PRENUMERATIONER = "2022-12-01"
API_RESURSER = "2021-04-01"
API_KOPPLING = "2016-06-01"
API_LOGIC_APP = "2019-05-01"


@dataclass
class Person:
    konto: str
    namn: str = ""
    finns: bool | None = None   # None = okänt, gick inte att slå upp
    aktiv: bool | None = None


@dataclass
class Koppling:
    id: str
    namn: str
    api: str                    # t.ex. "Office 365 Outlook"
    resursgrupp: str
    prenumeration: str
    konto: str = ""             # inloggat konto, tomt om kopplingen inte loggar in som en person
    status: str = ""            # "Connected", "Error" eller tomt
    fel: str = ""
    anvands_av: list | None = None   # None = Logic Apps kunde inte läsas
    person: Person | None = None


@dataclass
class KFynd:
    niva: str
    koppling: Koppling
    notering: str = ""


def filter_typ(typ):
    return "$filter=" + urllib.parse.quote(f"resourceType eq '{typ}'")


def resursgrupp(resurs_id):
    delar = resurs_id.split("/")
    return delar[4] if len(delar) > 4 and delar[3].lower() == "resourcegroups" else ""


def fran_arm(post, prenumeration):
    egenskaper = post.get("properties") or {}
    statusar = egenskaper.get("statuses") or []
    felstatus = next((s for s in statusar if s.get("status") == "Error"), None)
    if felstatus:
        status = "Error"
        fel = felstatus.get("error") or {}
        feltext = fel.get("message") or fel.get("code") or ""
    else:
        status = (statusar[0].get("status") if statusar else "") or egenskaper.get("overallStatus") or ""
        feltext = ""
    api = egenskaper.get("api") or {}
    return Koppling(
        id=post.get("id", ""),
        namn=egenskaper.get("displayName") or post.get("name", ""),
        api=api.get("displayName") or api.get("name") or "",
        resursgrupp=resursgrupp(post.get("id", "")),
        prenumeration=prenumeration,
        konto=(egenskaper.get("authenticatedUser") or {}).get("name") or "",
        status=status,
        fel=feltext,
    )


def anslutna(logic_app):
    """Id:n för kopplingarna som en Logic App (förbrukningsplan) använder."""
    parametrar = (logic_app.get("properties") or {}).get("parameters") or {}
    varden = (parametrar.get("$connections") or {}).get("value") or {}
    return [v["connectionId"] for v in varden.values() if isinstance(v, dict) and v.get("connectionId")]


def samla_kopplingar(arm, graph):
    """Returnerar kopplingarna och en lista med anteckningar om sådant som inte gick att läsa."""
    anteckningar = []
    prenumerationer = list(arm.lista(f"/subscriptions?api-version={API_PRENUMERATIONER}"))
    if not prenumerationer:
        return [], ["Inga Azure-prenumerationer synliga, så inga Logic Apps-kopplingar kontrollerades."]

    kopplingar, anvandning, misslyckade = [], {}, 0
    logic_apps_lasta = True
    for p in prenumerationer:
        sub = p["subscriptionId"]
        namn = p.get("displayName") or sub
        try:
            for r in arm.lista(f"/subscriptions/{sub}/resources?{filter_typ('Microsoft.Web/connections')}"
                               f"&api-version={API_RESURSER}"):
                try:
                    kopplingar.append(fran_arm(arm.hamta(f"{r['id']}?api-version={API_KOPPLING}"), namn))
                except GraphFel:
                    misslyckade += 1
        except GraphFel as fel:
            anteckningar.append(f"Kunde inte läsa kopplingar i prenumerationen {namn} ({fel.status}).")
            continue
        try:
            for r in arm.lista(f"/subscriptions/{sub}/resources?{filter_typ('Microsoft.Logic/workflows')}"
                               f"&api-version={API_RESURSER}"):
                logic_app = arm.hamta(f"{r['id']}?api-version={API_LOGIC_APP}")
                for k in anslutna(logic_app):
                    anvandning.setdefault(k.lower(), []).append(logic_app.get("name") or r.get("name", ""))
        except GraphFel:
            logic_apps_lasta = False

    if misslyckade:
        anteckningar.append(f"Kunde inte läsa {misslyckade} {'koppling' if misslyckade == 1 else 'kopplingar'}.")
    if not logic_apps_lasta:
        anteckningar.append("Kunde inte läsa alla Logic Apps, så det saknas uppgift om var vissa kopplingar används.")
    for k in kopplingar:
        anvands = anvandning.get(k.id.lower())
        k.anvands_av = sorted(set(anvands)) if anvands else ([] if logic_apps_lasta else None)

    anteckning = sla_upp_personer(graph, kopplingar)
    if anteckning:
        anteckningar.append(anteckning)
    return kopplingar, anteckningar


def sla_upp_personer(graph, kopplingar):
    personer = {}
    for k in kopplingar:
        if not k.konto:
            continue
        nyckel = k.konto.lower()
        if nyckel not in personer:
            try:
                personer[nyckel] = sla_upp(graph, k.konto)
            except GraphFel as fel:
                if fel.status == 403:
                    for rest in kopplingar:
                        rest.person = None
                    return "Kontona i kopplingarna kontrollerades inte mot Entra: saknar behörighet att läsa användare."
                personer[nyckel] = Person(k.konto)
        k.person = personer[nyckel]
    return None


def sla_upp(graph, konto):
    """Letar först på inloggningsnamn och sedan på e-post, så att även gäster hittas."""
    varde = konto.replace("'", "''")
    for egenskap in ("userPrincipalName", "mail"):
        filt = urllib.parse.quote(f"{egenskap} eq '{varde}'")
        traffar = list(graph.lista(f"/users?$filter={filt}&$select=displayName,userPrincipalName,accountEnabled"))
        if traffar:
            u = traffar[0]
            return Person(konto, u.get("displayName") or konto, True, u.get("accountEnabled"))
    return Person(konto, finns=False)


def bedom_koppling(k):
    if k.status == "Error":
        text = f"Kopplingen har fel: {k.fel}" if k.fel else "Kopplingen har fel."
        if k.person and k.person.finns is False:
            text += f" Kontot {k.konto} finns inte längre i katalogen."
        elif k.person and k.person.aktiv is False:
            text += f" Kontot {k.konto} är inaktiverat."
        return KFynd(TRASIG, k, text)
    if not k.konto:
        return KFynd(OK, k)
    if k.person and k.person.finns is False:
        return KFynd(SLUTAT, k, f"Kontot {k.konto} finns inte i katalogen. Personen kan ha tagits bort, "
                                "eller så är det ett konto utanför organisationen.")
    if k.person and k.person.aktiv is False:
        return KFynd(SLUTAT, k, f"Kontot {k.konto} är inaktiverat. Kopplingen slutar fungera när "
                                "inloggningen behöver förnyas.")
    return KFynd(PERSONLIGT, k, f"Slutar fungera när {k.konto} slutar eller tappar sin behörighet. "
                                "Byt till ett tjänstekonto, eller managed identity där kopplingen stöder det.")


def bedom_kopplingar(kopplingar):
    ordning = [TRASIG, SLUTAT, PERSONLIGT, OK]
    fynd = [bedom_koppling(k) for k in kopplingar]
    return sorted(fynd, key=lambda f: (ordning.index(f.niva), f.koppling.namn.lower()))
