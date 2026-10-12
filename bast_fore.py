"""Bäst före – visar vilka appnycklar och certifikat i Entra som snart går ut.

    python bast_fore.py --demo
    python bast_fore.py
    python bast_fore.py --html rapport.html
"""

import argparse
import os
import sys

from graph import Graph, GraphFel, token_fran_app, token_fran_az
from kontroller import bedom_alla, samla
from rapport import skriv_html, skriv_terminal


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="Visar vilka appnycklar och certifikat i Entra som snart går ut.")
    p.add_argument("--demo", action="store_true", help="använd påhittad data, ingen inloggning")
    p.add_argument("--html", metavar="FIL", help="skriv även rapporten som HTML")
    p.add_argument("--tenant", help="logga in som app i den här tenanten i stället för via az")
    p.add_argument("--klient-id", help="appens klient-ID (hemligheten läses från BASTFORE_KLIENTHEMLIGHET)")
    a = p.parse_args()

    if a.demo:
        from demo import demo_objekt
        objekt, organisation = demo_objekt(), "Nordvik AB (demo)"
    else:
        if a.tenant and a.klient_id:
            hemlighet = os.environ.get("BASTFORE_KLIENTHEMLIGHET")
            if not hemlighet:
                raise SystemExit("Sätt miljövariabeln BASTFORE_KLIENTHEMLIGHET.")
            token = token_fran_app(a.tenant, a.klient_id, hemlighet)
        else:
            token = token_fran_az()
        graph = Graph(token)
        try:
            organisation = graph.hamta("/organization?$select=displayName")["value"][0]["displayName"]
        except (GraphFel, IndexError, KeyError):
            organisation = ""
        try:
            objekt = samla(graph)
        except GraphFel as fel:
            if fel.status == 403:
                raise SystemExit("Saknar behörighet att läsa appar (Application.Read.All).")
            raise SystemExit(str(fel))

    fynd = bedom_alla(objekt)
    skriv_terminal(fynd, len(objekt), organisation)
    if a.html:
        skriv_html(fynd, len(objekt), organisation, a.html)
        print(f"HTML-rapport: {os.path.abspath(a.html)}")


if __name__ == "__main__":
    main()
