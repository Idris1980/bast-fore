"""Skriver resultatet till terminalen och som HTML-fil."""

import html
from datetime import datetime

import kopplingar as kp
from kontroller import AGARE, INOM_14, INOM_60, OK, STADA, TRASIGT

GRUPPER = [
    (TRASIGT, "🔴", "TRASIGT NU"),
    (INOM_14, "🟠", "INOM 14 DAGAR"),
    (INOM_60, "🟡", "INOM 60 DAGAR"),
    (AGARE, "👤", "INGEN ÄGARE KVAR"),
    (STADA, "⚪", "STÄDA BORT"),
    (OK, "🟢", "I ORDNING"),
]

# Kopplingar i ordning visas bara som en siffra, annars drunknar resten.
KGRUPPER = [
    (kp.TRASIG, "🔴", "TRASIG KOPPLING"),
    (kp.SLUTAT, "🟠", "KONTOT FINNS INTE KVAR"),
    (kp.PERSONLIGT, "🟡", "INLOGGAD SOM EN PERSON"),
]


def bara_ok(fynd):
    return all(f.niva == OK for f in fynd)


def nar(f):
    datum = f"{f.nyckel.slut:%Y-%m-%d}"
    if f.dagar < 0:
        return f"gick ut {datum} (för {-f.dagar} dagar sedan)"
    if f.dagar == 0:
        return f"gick ut {datum} (idag)" if f.utgangen else f"går ut {datum} (idag)"
    return f"går ut {datum} (om {f.dagar} dagar)"


def rad(f):
    return f'{f.objekt.slag} "{f.objekt.namn}" – {f.nyckel.typ} "{f.nyckel.namn}" {nar(f)}'


def koppling_rad(f):
    k = f.koppling
    text = f'Koppling "{k.namn}"'
    if k.api:
        text += f" ({k.api})"
    if k.resursgrupp:
        text += f" i {k.resursgrupp}"
    if k.konto:
        text += f" – inloggad som {k.konto}"
    return text


def anvandning(k):
    if k.anvands_av is None:
        return ""
    if not k.anvands_av:
        return "Ingen Logic App (förbrukningsplan) använder den."
    return "Används av " + ", ".join(k.anvands_av) + "."


def antal_ok(kfynd):
    return sum(1 for f in kfynd if f.niva == kp.OK)


def skriv_terminal(fynd, antal_objekt, organisation, anteckningar=(), kfynd=None):
    vecka = datetime.now().isocalendar().week
    print(f"\nBÄST FÖRE – {organisation or 'okänd organisation'}    vecka {vecka}\n")
    if bara_ok(fynd):
        print("   Inget går ut inom 60 dagar.\n")
    for niva, ikon, rubrik in GRUPPER:
        i_gruppen = [f for f in fynd if f.niva == niva]
        if not i_gruppen:
            continue
        print(f"{ikon} {rubrik}")
        for f in i_gruppen:
            print(f"   {rad(f)}")
            if f.notering:
                print(f"      {f.notering}")
        print()

    if kfynd:
        print("── LOGIC APPS-KOPPLINGAR ──\n")
        for niva, ikon, rubrik in KGRUPPER:
            i_gruppen = [f for f in kfynd if f.niva == niva]
            if not i_gruppen:
                continue
            print(f"{ikon} {rubrik}")
            for f in i_gruppen:
                print(f"   {koppling_rad(f)}")
                for extra in (anvandning(f.koppling), f.notering):
                    if extra:
                        print(f"      {extra}")
            print()
        if antal_ok(kfynd):
            print(f"🟢 {antal_ok(kfynd)} kopplingar loggar inte in som en person.\n")

    print(f"{antal_objekt} appar med nycklar kontrollerade.")
    if kfynd is not None:
        print(f"{len(kfynd)} kopplingar i Logic Apps kontrollerade.")
    for a in anteckningar:
        print(a)
    print()


def html_grupp(ikon, rubrik, niva, rader, antal):
    return (f'<section class="{niva}"><h2>{ikon} {rubrik} <span>{antal}</span></h2>'
            f"<table>{rader}</table></section>")


def skriv_html(fynd, antal_objekt, organisation, sokvag, anteckningar=(), kfynd=None):
    e = html.escape
    delar = []
    for niva, ikon, rubrik in GRUPPER:
        i_gruppen = [f for f in fynd if f.niva == niva]
        if not i_gruppen:
            continue
        rader = "".join(
            f"<tr><td>{e(f.objekt.slag)}</td><td><b>{e(f.objekt.namn)}</b><br><small>{e(f.objekt.app_id or '')}</small></td>"
            f"<td>{e(f.nyckel.typ)} \"{e(f.nyckel.namn)}\"</td><td>{e(nar(f))}"
            f"{'<br><small>' + e(f.notering) + '</small>' if f.notering else ''}</td></tr>"
            for f in i_gruppen
        )
        delar.append(html_grupp(ikon, rubrik, niva, rader, len(i_gruppen)))
    innehall = ("<p>Inget går ut inom 60 dagar.</p>" if bara_ok(fynd) else "") + "".join(delar)

    if kfynd:
        innehall += "<h1 class=\"del\">Logic Apps-kopplingar</h1>"
        for niva, ikon, rubrik in KGRUPPER:
            i_gruppen = [f for f in kfynd if f.niva == niva]
            if not i_gruppen:
                continue
            rader = "".join(
                f"<tr><td><b>{e(f.koppling.namn)}</b><br><small>{e(f.koppling.api)}</small></td>"
                f"<td>{e(f.koppling.resursgrupp)}<br><small>{e(f.koppling.prenumeration)}</small></td>"
                f"<td>{e(f.koppling.konto)}</td>"
                f"<td>{e(f.notering)}"
                f"{'<br><small>' + e(anvandning(f.koppling)) + '</small>' if anvandning(f.koppling) else ''}</td></tr>"
                for f in i_gruppen
            )
            innehall += html_grupp(ikon, rubrik, niva, rader, len(i_gruppen))
        if antal_ok(kfynd):
            innehall += f"<p>🟢 {antal_ok(kfynd)} kopplingar loggar inte in som en person.</p>"

    innehall += "".join(f'<p class="under">{e(a)}</p>' for a in anteckningar)
    vecka = datetime.now().isocalendar().week
    kopplingstext = f" · {len(kfynd)} kopplingar kontrollerade" if kfynd is not None else ""

    with open(sokvag, "w", encoding="utf-8") as fil:
        fil.write(f"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bäst före – {e(organisation or '')}</title>
<style>
:root {{ --bg:#fafaf9; --kort:#fff; --text:#1c1917; --svag:#78716c; --linje:#e7e5e4; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#1c1917; --kort:#292524; --text:#f5f5f4; --svag:#a8a29e; --linje:#44403c; }}
}}
body {{ background:var(--bg); color:var(--text); font:15px/1.5 system-ui, sans-serif; margin:0; padding:24px 16px; }}
main {{ max-width:900px; margin:0 auto; }}
h1 {{ margin:0 0 4px; }} .under {{ color:var(--svag); margin:0 0 24px; }}
h1.del {{ font-size:20px; margin:48px 0 0; padding-top:24px; border-top:1px solid var(--linje); }}
h2 {{ font-size:16px; margin:28px 0 8px; }} h2 span {{ color:var(--svag); font-weight:normal; }}
table {{ width:100%; border-collapse:collapse; background:var(--kort); border:1px solid var(--linje); border-radius:8px; }}
td {{ padding:10px 12px; border-top:1px solid var(--linje); vertical-align:top; overflow-wrap:anywhere; }}
tr:first-child td {{ border-top:none; }}
small {{ color:var(--svag); }}
.ok {{ color:var(--svag); }} .ok b {{ font-weight:600; }}
</style></head><body><main>
<h1>Bäst före – {e(organisation or 'okänd organisation')}</h1>
<p class="under">Vecka {vecka} · {antal_objekt} appar med nycklar kontrollerade{kopplingstext} · {datetime.now():%Y-%m-%d %H:%M}</p>
{innehall}
</main></body></html>
""")
