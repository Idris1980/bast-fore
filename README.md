# Bäst före

Visar vad i Microsoft Entra och Azure som snart slutar fungera, innan det stoppar en integration: appnycklar och certifikat som går ut, och kopplingar i Logic Apps som hänger på en persons konto.

Verktyget läser bara. Det ser aldrig själva hemligheterna, bara namn, slutdatum och vem som är inloggad.

## Vad den hittar

- **Appregistreringar** med hemligheter eller certifikat som går ut.
- **Företagsappar** (service principals), till exempel SAML-inloggning med certifikat som går ut.
- **Ägare som inte finns kvar**: appar som fortfarande fungerar men där ingen kommer att byta nyckeln.
- **Kopplingar i Logic Apps** som är inloggade med en persons konto (se nedan).

Resultatet delas in så här:

| Grupp | Betyder |
|---|---|
| 🔴 Trasigt nu | Alla nycklar har gått ut under de senaste 90 dagarna. Något har troligen redan slutat fungera. |
| 🟠 Inom 14 dagar | En nyckel som fortfarande gäller går ut inom två veckor. |
| 🟡 Inom 60 dagar | Samma sak, men med mer tid på sig. |
| 👤 Ingen ägare kvar | Appen har ingen ägare, eller så är alla ägare inaktiverade i Entra. Ingen ansvarar för att byta nyckeln. |
| ⚪ Städa bort | Alla nycklar gick ut för mer än 90 dagar sedan. Appen används troligen inte. |
| 🟢 I ordning | Inget går ut inom 60 dagar. Visar när appen slutar fungera, alltså när den nyaste nyckeln går ut. |

Har en app både en gammal och en ny nyckel varnar verktyget ändå för den gamla. Det är en vanlig fälla: någon skapade en ny nyckel men bytte aldrig i klienten.

Microsofts egna appar räknas inte med.

### Ägare

Ägarna kontrolleras bara för appar som fortfarande fungerar. För dem spelar det roll vem som byter nyckeln. En användare som har tagits bort försvinner ur ägarlistan, så den appen visas som "ingen ägare". Är ägaren en annan app, till exempel en pipeline, räknas det som att någon finns kvar.

Kontrollen gör ett anrop per app. Hoppa över den med `--utan-agare` om det går för långsamt.

### Kopplingar i Logic Apps

När någon bygger en Logic App som skickar mejl eller läser från SharePoint loggar de ofta in kopplingen med sitt eget konto. Allt fungerar tills personen slutar. Då slutar flödet fungera, ofta utan att någon märker det.

Verktyget går igenom alla Azure-prenumerationer du kan se, läser kopplingarna (`Microsoft.Web/connections`) och slår upp det inloggade kontot i Entra:

| Grupp | Betyder |
|---|---|
| 🔴 Trasig koppling | Azure säger att kopplingen har fel. Felmeddelandet visas. |
| 🟠 Kontot finns inte kvar | Kontot är inaktiverat eller finns inte i katalogen. Kopplingen slutar fungera när inloggningen behöver förnyas, om den inte redan har gjort det. |
| 🟡 Inloggad som en person | Fungerar nu, men slutar fungera när personen slutar. Byt till ett tjänstekonto, eller managed identity där kopplingen stöder det. |
| 🟢 | Kopplingar som inte loggar in som en person visas bara som en siffra. |

För varje koppling står vilka Logic Apps som använder den. Det gäller Logic Apps i förbrukningsplanen (Consumption). Logic Apps Standard syns inte än. Ett konto som inte hittas kan också vara ett konto utanför organisationen, till exempel ett privat Microsoft-konto.

Kopplingarna kräver läsbehörighet (Reader) i prenumerationerna. Saknas den, eller finns inga prenumerationer, står det sist i rapporten och resten körs som vanligt. Hoppa över delen med `--utan-kopplingar`.

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

Vanliga användare får som standard läsa appregistreringar, så administratörsrättigheter behövs oftast inte. För kopplingarna behöver du rollen Reader (eller mer) i prenumerationerna.

## Logga in som app

Så kommer produkten att köra: en egen app med läsbehörighet och ingen användare inloggad. Kräver en administratör för godkännandet.

```powershell
$graph = "00000003-0000-0000-c000-000000000000"
$lasApp = az ad sp show --id $graph --query "appRoles[?value=='Application.Read.All'].id" -o tsv
$lasOrg = az ad sp show --id $graph --query "appRoles[?value=='Organization.Read.All'].id" -o tsv
$lasAnv = az ad sp show --id $graph --query "appRoles[?value=='User.Read.All'].id" -o tsv

$appId = az ad app create --display-name "bast-fore-lasare" --query appId -o tsv
az ad sp create --id $appId
az ad app permission add --id $appId --api $graph --api-permissions "$lasApp=Role" "$lasOrg=Role" "$lasAnv=Role"
az ad app permission admin-consent --id $appId

# Läsrätt i prenumerationen, för kopplingarna i Logic Apps. Upprepa för varje prenumeration.
$prenumeration = az account show --query id -o tsv
az role assignment create --assignee $appId --role Reader --scope "/subscriptions/$prenumeration"

$env:BASTFORE_KLIENTHEMLIGHET = az ad app credential reset --id $appId --display-name "lokal test" --years 1 --query password -o tsv
$tenant = az account show --query tenantId -o tsv
python bast_fore.py --tenant $tenant --klient-id $appId
```

`User.Read.All` behövs för att se om en ägare är inaktiverad och för att slå upp kontona i kopplingarna. Utan den hittar verktyget fortfarande appar helt utan ägare, och kopplingar på personliga konton visas som 🟡.

Det kan ta någon minut efter godkännandet innan behörigheterna gäller. Hemligheten gäller i ett år, och verktyget varnar när den närmar sig sitt slutdatum.

Ta bort appen när du är klar. Rolltilldelningen försvinner när appen tas bort.

```powershell
az ad app delete --id $appId
```

## Filer

- `bast_fore.py` – startpunkten
- `graph.py` – inloggning och anrop mot Microsoft Graph och Azure Resource Manager
- `kontroller.py` – samlar in appar och bedömer när de går sönder
- `kopplingar.py` – samlar in kopplingar i Logic Apps och slår upp kontona i Entra
- `rapport.py` – terminalutskrift och HTML-rapport
- `demo.py` – påhittad tenant
- `tests/` – tester

## Tester

```powershell
python -m unittest
```

Testerna anropar aldrig Graph eller Azure och behöver ingen inloggning.

### Testmiljö för kopplingarna

`testmiljo.ps1` bygger en avstängd Logic App med en koppling inloggad med ditt konto, så att du kan se kopplingsdelen fungera mot riktig Azure. Ett steg sker i webbläsaren: Microsoft kräver att du själv loggar in kopplingen.

```powershell
az login
.\testmiljo.ps1
python bast_fore.py
.\testmiljo.ps1 -Riv
```
