"""Samlar in appar med nycklar och bedömer när de går sönder."""

from dataclasses import dataclass
from datetime import datetime, timezone

# Microsofts egna appar finns i varje tenant men är inte kundens ansvar.
MICROSOFT_TENANTER = {
    "f8cdef31-a31e-4b4a-93e4-5f571e91255a",
    "72f988bf-86f1-41af-91ab-2d7cd011db47",
}

TRASIGT = "trasigt"
INOM_14 = "inom14"
INOM_60 = "inom60"
STADA = "stada"
OK = "ok"

# En app vars sista nyckel gick ut för mer än så här länge sedan används troligen inte.
DAGAR_INNAN_DOD = 90


@dataclass
class Nyckel:
    typ: str        # "hemlighet" eller "certifikat"
    namn: str
    slut: datetime


@dataclass
class Objekt:
    slag: str       # "App" (appregistrering) eller "Företagsapp" (service principal)
    namn: str
    app_id: str
    nycklar: list


@dataclass
class Fynd:
    niva: str
    objekt: Objekt
    nyckel: Nyckel
    dagar: int      # negativt = redan utgånget
    notering: str = ""


def tid(text):
    # Graph skickar ibland sju decimaler, så sekunderna räcker.
    return datetime.fromisoformat(text[:19]).replace(tzinfo=timezone.utc)


def dagar_kvar(nyckel, nu):
    # Räknas i hela kalenderdagar, annars blir "om 12 dagar" ibland "om 11".
    return (nyckel.slut.date() - nu.date()).days


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
    return Objekt(slag, post.get("displayName") or post.get("appId"), post.get("appId"), list(unika.values()))


def samla(graph):
    objekt = []
    for app in graph.lista("/applications?$select=displayName,appId,passwordCredentials,keyCredentials&$top=999"):
        objekt.append(fran_graph(app, "App"))
    for sp in graph.lista("/servicePrincipals?$select=displayName,appId,appOwnerOrganizationId,"
                          "passwordCredentials,keyCredentials&$top=999"):
        if sp.get("appOwnerOrganizationId") in MICROSOFT_TENANTER:
            continue
        objekt.append(fran_graph(sp, "Företagsapp"))
    return [o for o in objekt if o.nycklar]


def bedom(obj, nu):
    giltiga = [n for n in obj.nycklar if n.slut > nu]

    if not giltiga:
        senaste = max(obj.nycklar, key=lambda n: n.slut)
        dagar = dagar_kvar(senaste, nu)
        if dagar >= -DAGAR_INNAN_DOD:
            return [Fynd(TRASIGT, obj, senaste, dagar, "Alla nycklar har gått ut.")]
        return [Fynd(STADA, obj, senaste, dagar,
                     "Alla nycklar gick ut för länge sedan. Troligen oanvänd, kan tas bort.")]

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
    return fynd


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
