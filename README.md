# Bäst före

Visar vilka appnycklar och certifikat i Microsoft Entra som snart går ut, innan de stoppar en integration.

Verktyget läser bara. Det ser aldrig själva hemligheterna, bara namn och slutdatum.

## Vad den hittar (etapp 1)

- **Appregistreringar** med hemligheter eller certifikat som går ut.
- **Företagsappar** (service principals), till exempel SAML-inloggning med certifikat som går ut.

Resultatet delas in så här:

| Grupp | Betyder |
|---|---|
| 🔴 Trasigt nu | Alla nycklar har gått ut under de senaste 90 dagarna. Något har troligen redan slutat fungera. |
| 🟠 Inom 14 dagar | En nyckel som fortfarande gäller går ut inom två veckor. |
| 🟡 Inom 60 dagar | Samma sak, men med mer tid på sig. |
| ⚪ Städa bort | Alla nycklar gick ut för mer än 90 dagar sedan. Appen används troligen inte. |
| 🟢 I ordning | Inget går ut inom 60 dagar. Visar när appen slutar fungera, alltså när den nyaste nyckeln går ut. |

Har en app både en gammal och en ny nyckel varnar verktyget ändå för den gamla. Det är en vanlig fälla: någon skapade en ny nyckel men bytte aldrig i klienten.

Microsofts egna appar räknas inte med.

## Kör

Kräver Python 3.11 eller senare. Inga paket behöver installeras.

Demo med påhittad data, ingen inloggning:

```powershell
python bast_fore.py --demo --html demo.html
```

Mot din egen tenant, med samma inloggning som Azure CLI:

```powershell
az login
python bast_fore.py --html rapport.html
```

Vanliga användare får som standard läsa appregistreringar, så administratörsrättigheter behövs oftast inte.

## Logga in som app

Så kommer produkten att köra: en egen app med läsbehörighet och ingen användare inloggad. Kräver en administratör för godkännandet.

```powershell
$graph = "00000003-0000-0000-c000-000000000000"
$lasApp = az ad sp show --id $graph --query "appRoles[?value=='Application.Read.All'].id" -o tsv
$lasOrg = az ad sp show --id $graph --query "appRoles[?value=='Organization.Read.All'].id" -o tsv

$appId = az ad app create --display-name "bast-fore-lasare" --query appId -o tsv
az ad sp create --id $appId
az ad app permission add --id $appId --api $graph --api-permissions "$lasApp=Role" "$lasOrg=Role"
az ad app permission admin-consent --id $appId

$env:BASTFORE_KLIENTHEMLIGHET = az ad app credential reset --id $appId --display-name "lokal test" --years 1 --query password -o tsv
$tenant = az account show --query tenantId -o tsv
python bast_fore.py --tenant $tenant --klient-id $appId
```

Det kan ta någon minut efter godkännandet innan behörigheterna gäller. Hemligheten gäller i ett år, och verktyget varnar när den närmar sig sitt slutdatum.

Ta bort appen när du är klar:

```powershell
az ad app delete --id $appId
```

## Filer

- `bast_fore.py` – startpunkten
- `graph.py` – inloggning och anrop mot Microsoft Graph
- `kontroller.py` – samlar in appar och bedömer när de går sönder
- `rapport.py` – terminalutskrift och HTML-rapport
- `demo.py` – påhittad tenant

## Nästa etapper

1. ~~Nycklar och certifikat i appregistreringar~~
2. Ägare: vem som äger appen och om personen finns kvar
3. Logic Apps-kopplingar inloggade med personliga konton
4. Certifikat i Key Vault och App Service
5. Stöd för flera kunder: godkännandeflöde och utskick varje vecka
6. Power Automate-flöden
