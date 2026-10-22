"""Hämtar en token och läser från Microsoft Graph och Azure Resource Manager. Bara standardbiblioteket."""

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.microsoft.com/v1.0"
ARM = "https://management.azure.com"

# Graph ber oss ibland vänta (429) eller är tillfälligt nere (503, 504). Då försöker vi igen.
FORSOK = 5
VANTA_IGEN = {429, 503, 504}


class GraphFel(Exception):
    def __init__(self, status, text, kalla="Graph"):
        super().__init__(f"{kalla} svarade {status}: {text}")
        self.status = status


class InloggningsFel(Exception):
    pass


def token_fran_az(resurstyp="ms-graph"):
    """Lånar den inloggade användarens token från Azure CLI (az login). resurstyp: ms-graph eller arm."""
    az = shutil.which("az")
    if not az:
        raise InloggningsFel("Hittar inte az. Installera Azure CLI eller logga in som app (se README).")
    svar = subprocess.run(
        [az, "account", "get-access-token", "--resource-type", resurstyp,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True,
    )
    if svar.returncode != 0:
        raise InloggningsFel("az kunde inte ge en token. Kör az login först.\n" + svar.stderr.strip())
    return svar.stdout.strip()


def token_fran_app(tenant, klient_id, hemlighet, scope="https://graph.microsoft.com/.default"):
    """Loggar in som en app med egen hemlighet, så som produkten kommer att köra."""
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": klient_id,
        "client_secret": hemlighet,
        "scope": scope,
    }).encode()
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data)) as svar:
            return json.load(svar)["access_token"]
    except urllib.error.HTTPError as fel:
        raise InloggningsFel("Inloggningen som app misslyckades:\n" + fel.read().decode(errors="replace"))


def vantetid(retry_after, forsok):
    """Sekunder att vänta: det Graph säger i Retry-After, annars 1, 2, 4, 8 ... högst 60."""
    if retry_after and retry_after.strip().isdigit():
        return min(int(retry_after), 60)
    return min(2 ** forsok, 60)


class Graph:
    """Läser från Graph, eller från Azure Resource Manager med bas=ARM. Båda delar upp svar i sidor."""

    def __init__(self, token, bas=GRAPH):
        self.token = token
        self.bas = bas
        self.kalla = "Azure" if bas == ARM else "Graph"

    def _get(self, url):
        for forsok in range(FORSOK):
            fraga = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}"})
            try:
                with urllib.request.urlopen(fraga) as svar:
                    return json.load(svar)
            except urllib.error.HTTPError as fel:
                if fel.code in VANTA_IGEN and forsok < FORSOK - 1:
                    time.sleep(vantetid(fel.headers.get("Retry-After"), forsok))
                    continue
                raise GraphFel(fel.code, fel.read().decode(errors="replace"), self.kalla) from None

    def hamta(self, sokvag):
        return self._get(self.bas + sokvag)

    def lista(self, sokvag):
        """Går igenom alla sidor (@odata.nextLink i Graph, nextLink i ARM) och lämnar ut posterna en i taget."""
        url = self.bas + sokvag
        while url:
            sida = self._get(url)
            yield from sida.get("value", [])
            url = sida.get("@odata.nextLink") or sida.get("nextLink")
