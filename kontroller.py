"""Samlar in appar med nycklar och bedömer när de går sönder."""

from dataclasses import dataclass
from datetime import datetime, timezone

from graph import GraphFel

# Microsofts egna appar finns i varje tenant men är inte kundens ansvar.
MICROSOFT_TENANTER = {
    "f8cdef31-a31e-4b4a-93e4-5f571e91255a",
    "72f988bf-86f1-41af-91ab-2d7cd011db47",
}

TRASIGT = "trasigt"
INOM_14 = "inom14"
INOM_60 = "inom60"
AGARE = "agare"
STADA = "stada"
OK = "ok"

# Appar som skapas och sköts automatiskt i kundens egen tenant. De ska inte ha någon ägare,
# så ägarvarningen vore bara brus. Nycklarna kontrolleras ändå.
SYSTEMHANTERADE = {"P2P Server"}                        # fjärrinloggning på Entra-anslutna datorer
SYSTEMHANTERADE_PREFIX = ("ConnectSyncProvisioning_",)  # Entra Connect Sync

# En app vars sista nyckel gick ut för mer än så här länge sedan används troligen inte.
DAGAR_INNAN_DOD = 90

# Tidszon för att räkna dagar. None betyder datorns egen, så "idag" stämmer med läsarens kalender.
ZON = None


@dataclass
class Nyckel:
    typ: str        # "hemlighet" eller "certifikat"
    namn: str
    slut: datetime


@dataclass
class Agare:
    typ: str        # "person" eller "app"
    namn: str
    upn: str = ""
    aktiv: bool | None = None   # None = okänt, Graph gav inte ut accountEnabled


@dataclass
class Objekt:
    slag: str       # "App" (appregistrering) eller "Företagsapp" (service principal)
    namn: str
    app_id: str
    nycklar: list
    id: str = ""
    agare: list | None = None   # None = inte kontrollerat


@dataclass
class Fynd:
    niva: str
    objekt: Objekt
    nyckel: Nyckel
    dagar: int      # negativt = redan utgånget
    notering: str = ""
    utgangen: bool = False


def tid(text):
    # Graph skickar ibland sju decimaler, så sekunderna räcker.
    return datetime.fromisoformat(text[:19]).replace(tzinfo=timezone.utc)


def dagar_kvar(nyckel, nu):
    # Räknas i hela kalenderdagar, annars blir "om 12 dagar" ibland "om 11".
    return (nyckel.slut.astimezone(ZON).date() - nu.astimezone(ZON).date()).days


def fran_graph(post, slag):
    nycklar = [
        Nyckel("hemlighet", p.get("displayName") or "namnlös", tid(p["endDateTime"]))
        for p in post.get("passwordCredentials") or [] if p.get("endDateTime")
    ]
    nycklar += [
        Nyckel("certifikat", k.get("displayName") or "namnlöst", tid(k["endDateTime"]))
        for k in post.get("keyCredentials") or [] if k.get("endDateTime")
    ]
    # SAML-certifikat ligger dubbelt (signering + verifiering) med samma slutdatum.
    unika = {(n.typ, n.namn, n.slut): n for n in nycklar}
    return Objekt(slag, post.get("displayName") or post.get("appId"), post.get("appId"),
                  list(unika.values()), post.get("id", ""))


def agare_fran_graph(post):
    if post.get("@odata.type") == "#microsoft.graph.user":
        return Agare("person", post.get("displayName") or post.get("userPrincipalName") or "namnlös",
                     post.get("userPrincipalName") or "", post.get("accountEnabled"))
    return Agare("app", post.get("displayName") or "namnlös app", aktiv=True)


def samla(graph, med_agare=True, nu=None):
    """Returnerar objekten och en lista med anteckningar om sådant som inte gick att läsa."""
    objekt = []
    for app in graph.lista("/applications?$select=id,displayName,appId,passwordCredentials,keyCredentials&$top=999"):
        objekt.append(fran_graph(app, "App"))
    for sp in graph.lista("/servicePrincipals?$select=id,displayName,appId,appOwnerOrganizationId,"
                          "passwordCredentials,keyCredentials&$top=999"):
        if sp.get("appOwnerOrganizationId") in MICROSOFT_TENANTER:
            continue
        objekt.append(fran_graph(sp, "Företagsapp"))
    objekt = [o for o in objekt if o.nycklar]

    anteckningar = []
    if med_agare:
        anteckning = hamta_agare(graph, objekt, nu or datetime.now(timezone.utc))
        if anteckning:
            anteckningar.append(anteckning)
    return objekt, anteckningar


def hamta_agare(graph, objekt, nu):
    # Bara appar som fortfarande fungerar: för dem spelar det roll vem som byter nyckeln.
    aktuella = [o for o in objekt if o.id and any(n.slut > nu for n in o.nycklar)]
    misslyckade = 0
    for o in aktuella:
        bas = "/applications" if o.slag == "App" else "/servicePrincipals"
        try:
            o.agare = [agare_fran_graph(p) for p in graph.lista(
                f"{bas}/{o.id}/owners?$select=id,displayName,userPrincipalName,accountEnabled")]
        except GraphFel as fel:
            if fel.status == 403:
                for rest in aktuella:
                    rest.agare = None
                return "Ägare kontrollerades inte: saknar behörighet att läsa dem."
            misslyckade += 1
    if misslyckade:
        return f"Kunde inte läsa ägare för {misslyckade} av {len(aktuella)} appar."
    return None


def bedom(obj, nu):
    giltiga = [n for n in obj.nycklar if n.slut > nu]

    if not giltiga:
        senaste = max(obj.nycklar, key=lambda n: n.slut)
        dagar = dagar_kvar(senaste, nu)
        if dagar >= -DAGAR_INNAN_DOD:
            return [Fynd(TRASIGT, obj, senaste, dagar, "Alla nycklar har gått ut.", utgangen=True)]
        return [Fynd(STADA, obj, senaste, dagar,
                     "Alla nycklar gick ut för länge sedan. Troligen oanvänd, kan tas bort.", utgangen=True)]

    # Appen fungerar så länge minst en nyckel gäller, men klienten kanske
    # fortfarande använder en äldre nyckel som går ut före den nyaste.
    sista = max(giltiga, key=lambda n: n.slut)
    fynd = []
    for n in giltiga:
        dagar = dagar_kvar(n, nu)
        if dagar <= 14:
            niva = INOM_14
        elif dagar <= 60:
            niva = INOM_60
        else:
            continue
        notering = "" if n is sista else (
            f"Det finns en nyare {sista.typ} som gäller till {sista.slut:%Y-%m-%d}. "
            "Kontrollera att klienten har bytt till den.")
        fynd.append(Fynd(niva, obj, n, dagar, notering))

    # Inget att varna för: visa ändå när appen slutar fungera, alltså när den nyaste nyckeln går ut.
    if not fynd:
        notering = f"{len(giltiga)} {flertal(giltiga)}." if len(giltiga) > 1 else ""
        fynd.append(Fynd(OK, obj, sista, dagar_kvar(sista, nu), notering))

    agarfynd = bedom_agare(obj, nu)
    if agarfynd:
        # Ägarvarningen visar redan den nyaste nyckeln, så raden under "I ordning" vore en dubblett.
        fynd = [f for f in fynd if f.niva != OK] + [agarfynd]
    return fynd


def systemhanterad(obj):
    return obj.namn in SYSTEMHANTERADE or obj.namn.startswith(SYSTEMHANTERADE_PREFIX)


def bedom_agare(obj, nu):
    """Varnar när ingen finns kvar som kan byta nyckeln. Utgångna appar syns redan på annat håll."""
    giltiga = [n for n in obj.nycklar if n.slut > nu]
    if obj.agare is None or not giltiga or systemhanterad(obj):
        return None
    sista = max(giltiga, key=lambda n: n.slut)

    if not obj.agare:
        # En borttagen användare försvinner ur ägarlistan, så det här fångar även dem.
        text = "Appen har ingen ägare. Ingen ansvarar för att byta nyckeln innan den går ut."
    else:
        personer = [a for a in obj.agare if a.typ == "person"]
        # En app som ägare, eller en person vi inte vet något om, räknas som att någon finns kvar.
        if len(personer) < len(obj.agare) or any(a.aktiv is not False for a in personer):
            return None
        namn = ", ".join(f"{a.namn} ({a.upn})" if a.upn else a.namn for a in personer)
        if len(personer) == 1:
            text = f"Ägaren {namn} är inaktiverad och har troligen slutat."
        else:
            text = f"Alla ägare är inaktiverade och har troligen slutat: {namn}."
        text += " Ingen ansvarar för att byta nyckeln innan den går ut."
    return Fynd(AGARE, obj, sista, dagar_kvar(sista, nu), text)


def flertal(nycklar):
    typer = {n.typ for n in nycklar}
    if typer == {"hemlighet"}:
        return "hemligheter"
    if typer == {"certifikat"}:
        return "certifikat"
    return "nycklar"


def bedom_alla(objekt, nu=None):
    nu = nu or datetime.now(timezone.utc)
    fynd = [f for o in objekt for f in bedom(o, nu)]
    return sorted(fynd, key=lambda f: f.dagar)
