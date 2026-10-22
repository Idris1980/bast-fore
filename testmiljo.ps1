<#
Bygger en Logic App med en koppling inloggad med ditt eget konto, så att Bäst före har något att hitta.
Logic Appen är avstängd och kör aldrig, så den kostar i stort sett ingenting. Riv den ändå när du är klar.

    .\testmiljo.ps1         bygger
    .\testmiljo.ps1 -Riv    tar bort allt
#>
param([switch]$Riv)

$ErrorActionPreference = "Stop"
$rg = "rg-bastfore-test"
$plats = "swedencentral"
$arm = "https://management.azure.com"

if ($Riv) {
    az group delete -n $rg --yes
    Write-Host "Resursgruppen $rg är borttagen."
    return
}

$sub = az account show --query id -o tsv
$tenant = az account show --query tenantId -o tsv
$jag = az ad signed-in-user show --query id -o tsv
$fil = (New-TemporaryFile).FullName

function Skicka($metod, $sokvag, $kropp, $fraga = $null) {
    $kropp | ConvertTo-Json -Depth 20 | Set-Content $fil -Encoding utf8
    $argument = @("rest", "--method", $metod, "--url", "$arm$sokvag", "--body", "@$fil")
    if ($fraga) { $argument += @("--query", $fraga, "-o", "tsv") }
    az @argument
    if ($LASTEXITCODE -ne 0) { throw "az rest misslyckades: $metod $sokvag" }
}

Write-Host "1/5 Registrerar Logic Apps och kopplingar i prenumerationen (kan ta en minut första gången)"
az provider register --namespace Microsoft.Logic --wait
az provider register --namespace Microsoft.Web --wait

Write-Host "2/5 Skapar resursgruppen $rg"
az group create -n $rg -l $plats -o none

Write-Host "3/5 Skapar kopplingen arm-test (Azure Resource Manager)"
$apiId = "/subscriptions/$sub/providers/Microsoft.Web/locations/$plats/managedApis/arm"
$kopplingId = "/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.Web/connections/arm-test"
Skicka put "${kopplingId}?api-version=2016-06-01" @{
    location   = $plats
    properties = @{ displayName = "arm-test"; api = @{ id = $apiId } }
} | Out-Null

Write-Host "4/5 Skapar Logic Appen la-bastfore-test (avstängd)"
$logicAppId = "/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.Logic/workflows/la-bastfore-test"
Skicka put "${logicAppId}?api-version=2019-05-01" @{
    location   = $plats
    properties = @{
        state      = "Disabled"
        definition = @{
            '$schema'      = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"
            contentVersion = "1.0.0.0"
            parameters     = @{ '$connections' = @{ defaultValue = @{}; type = "Object" } }
            triggers       = @{ Varje_dag = @{ type = "Recurrence"; recurrence = @{ frequency = "Day"; interval = 1 } } }
            actions        = @{
                Lista_prenumerationer = @{
                    type     = "ApiConnection"
                    runAfter = @{}
                    inputs   = @{
                        host    = @{ connection = @{ name = '@parameters(''$connections'')[''arm''][''connectionId'']' } }
                        method  = "get"
                        path    = "/subscriptions"
                        queries = @{ "x-ms-api-version" = "2016-06-01" }
                    }
                }
            }
        }
        parameters = @{
            '$connections' = @{ value = @{ arm = @{ connectionId = $kopplingId; connectionName = "arm-test"; id = $apiId } } }
        }
    }
} | Out-Null

Write-Host ""
Write-Host "Kopplingen finns nu men är inte inloggad. Vill du se den som trasig i Bäst före,"
Write-Host "kör python bast_fore.py i ett annat fönster innan du fortsätter."
Read-Host "Tryck Enter för att logga in kopplingen"

Write-Host "5/5 Loggar in kopplingen med ditt konto"
$redirect = "https://ema1.exp.azure.com/ema/default/authredirect"
$lank = Skicka post "${kopplingId}/listConsentLinks?api-version=2016-06-01" @{
    parameters = @(@{ parameterName = "token"; redirectUrl = $redirect; objectId = $jag; tenantId = $tenant })
} "value[0].link"
Start-Process $lank
Write-Host "Logga in i webbläsaren som öppnades. Efteråt visar webbläsaren att sidan inte kan nås."
Write-Host "Det är väntat: adressen innehåller code=, och det är den som behövs."
Write-Host "Kopiera hela adressen i adressfältet och klistra in den här direkt, koden gäller bara en kort stund."
$adress = Read-Host "Adress"
if ($adress -notmatch "[?&]code=([^&#]+)") {
    throw "Hittar ingen code= i adressen. Logga in kopplingen i portalen i stället: arm-test, Edit API connection, Authorize, Save."
}
Skicka post "${kopplingId}/confirmConsentCode?api-version=2016-06-01" @{
    tenantId = $tenant; objectId = $jag; code = [uri]::UnescapeDataString($Matches[1])
} | Out-Null

Remove-Item $fil
Write-Host ""
Write-Host "Klart. Så här beskriver Azure kopplingen (det är de här fälten Bäst före läser):"
az rest --method get --url "$arm${kopplingId}?api-version=2016-06-01" `
    --query "{konto: properties.authenticatedUser, status: properties.statuses}"
Write-Host ""
Write-Host "Kör nu: python bast_fore.py"
Write-Host "Riv när du är klar: .\testmiljo.ps1 -Riv"
