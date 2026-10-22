"""Hämtar en token och läser från Microsoft Graph. Bara standardbiblioteket."""

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.microsoft.com/v1.0"

# Graph ber oss ibland vänta (429) eller är tillfälligt nere (503, 504). Då försöker vi igen.
FORSOK = 5
VANTA_IGEN = {429, 503, 504}


class GraphFel(Exception):
    def __init__(self, status, text):
        super().__init__(f"Graph svarade {status}: {text}")
        self.status = status


def token_fran_az():
    """Lånar den inloggade användarens token från Azure CLI (az login)."""
    az = shutil.which("az")
    if not az:
        raise SystemExit("Hittar inte az. Installera Azure CLI eller logga in som app (se README).")
    svar = subprocess.run(
        [az, "account", "get-access-token", "--resource-type", "ms-graph",
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True,
    )
    if svar.returncode != 0:
        raise SystemExit("az kunde inte ge en token. Kör az login först.\n" + svar.stderr.strip())
    return svar.stdout.strip()


def token_fran_app(tenant, klient_id, hemlighet):
    """Loggar in som en app med egen hemlighet, så som produkten kommer att köra."""
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": klient_id,
        "client_secret": hemlighet,
        "scope": "https://graph.microsoft.com/.default",
    }).encode()
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data)) as svar:
            return json.load(svar)["access_token"]
    except urllib.error.HTTPError as fel:
        raise SystemExit("Inloggningen som app misslyckades:\n" + fel.read().decode(errors="replace"))


def vantetid(retry_after, forsok):
    """Sekunder att vänta: det Graph säger i Retry-After, annars 1, 2, 4, 8 ... högst 60."""
    if retry_after and retry_after.strip().isdigit():
        return min(int(retry_after), 60)
    return min(2 ** forsok, 60)


class Graph:
    def __init__(self, token):
        self.token = token

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
                raise GraphFel(fel.code, fel.read().decode(errors="replace")) from None

    def hamta(self, sokvag):
        return self._get(GRAPH + sokvag)

    def lista(self, sokvag):
        """Går igenom alla sidor (@odata.nextLink) och lämnar ut posterna en i taget."""
        url = GRAPH + sokvag
        while url:
            sida = self._get(url)
            yield from sida.get("value", [])
            url = sida.get("@odata.nextLink")
