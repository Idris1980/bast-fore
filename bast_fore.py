"""Bäst före – visar vad i Entra och Azure som snart slutar fungera.

    python bast_fore.py --demo
    python bast_fore.py
    python bast_fore.py --html rapport.html
"""

import argparse
import os
import sys

from graph import ARM, Graph, GraphFel, InloggningsFel, token_fran_app, token_fran_az
from kontroller import bedom_alla, samla
from kopplingar import bedom_kopplingar, samla_kopplingar
from rapport import skriv_html, skriv_terminal


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="Visar vad i Entra och Azure som snart slutar fungera.")
    p.add_argument("--demo", action="store_true", help="använd påhittad data, ingen inloggning")
    p.add_argument("--html", metavar="FIL", help="skriv även rapporten som HTML")
    p.add_argument("--tenant", help="logga in som app i den här tenanten i stället för via az")
    p.add_argument("--klient-id", help="appens klient-ID (hemligheten läses från BASTFORE_KLIENTHEMLIGHET)")
    p.add_argument("--utan-agare", action="store_true", help="hoppa över kontrollen av ägare (går fortare)")
    p.add_argument("--utan-kopplingar", action="store_true", help="hoppa över kopplingar i Logic Apps")
    a = p.parse_args()

    kopplingar = None
    if a.demo:
        from demo import demo_kopplingar, demo_objekt
        objekt, organisation, anteckningar = demo_objekt(), "Nordvik AB (demo)", []
        if a.utan_agare:
            for o in objekt:
                o.agare = None
        if not a.utan_kopplingar:
            kopplingar = demo_kopplingar()
    else:
        if a.tenant and a.klient_id:
            hemlighet = os.environ.get("BASTFORE_KLIENTHEMLIGHET")
            if not hemlighet:
                raise SystemExit("Sätt miljövariabeln BASTFORE_KLIENTHEMLIGHET.")

            def token(scope):
                return token_fran_app(a.tenant, a.klient_id, hemlighet, scope)
            graph_token = lambda: token("https://graph.microsoft.com/.default")
            arm_token = lambda: token("https://management.azure.com/.default")
        else:
            graph_token = lambda: token_fran_az("ms-graph")
            arm_token = lambda: token_fran_az("arm")

        try:
            graph = Graph(graph_token())
        except InloggningsFel as fel:
            raise SystemExit(str(fel))
        try:
            organisation = graph.hamta("/organization?$select=displayName")["value"][0]["displayName"]
        except (GraphFel, IndexError, KeyError):
            organisation = ""
        try:
            objekt, anteckningar = samla(graph, med_agare=not a.utan_agare)
        except GraphFel as fel:
            if fel.status == 403:
                raise SystemExit("Saknar behörighet att läsa appar (Application.Read.All).")
            raise SystemExit(str(fel))

        if not a.utan_kopplingar:
            # Kopplingarna är en extra: går de inte att läsa blir det en anteckning, inte ett avbrott.
            try:
                kopplingar, ant = samla_kopplingar(Graph(arm_token(), bas=ARM), graph)
                anteckningar += ant
            except (InloggningsFel, GraphFel) as fel:
                anteckningar.append(f"Logic Apps-kopplingar kontrollerades inte: {str(fel).splitlines()[0]}")

    fynd = bedom_alla(objekt)
    kfynd = bedom_kopplingar(kopplingar) if kopplingar is not None else None
    skriv_terminal(fynd, len(objekt), organisation, anteckningar, kfynd)
    if a.html:
        skriv_html(fynd, len(objekt), organisation, a.html, anteckningar, kfynd)
        print(f"HTML-rapport: {os.path.abspath(a.html)}")


if __name__ == "__main__":
    main()
