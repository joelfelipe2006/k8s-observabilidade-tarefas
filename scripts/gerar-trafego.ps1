# =============================================================================
# Grupo: Joel Felipe dos Santos Gonçalves, Luiz Eduardo Pageu Leite e Gabriel Ribeiro
#
# Versão PowerShell (Windows) do gerar-trafego.sh.
# Uso: em um terminal deixe rodando  minikube service app-service --url
#      e passe a URL mostrada:
#      .\scripts\gerar-trafego.ps1 -Url http://127.0.0.1:54321 -Quantidade 40
# =============================================================================
param(
  [Parameter(Mandatory = $true)][string]$Url,
  [int]$Quantidade = 40
)

Write-Host "Aplicação: $Url"
Write-Host "Criando 5 tarefas via API..."
1..5 | ForEach-Object {
  $corpo = @{ titulo = "Tarefa de teste $_ ($(Get-Date -Format HH:mm:ss))" } | ConvertTo-Json
  Invoke-RestMethod -Method Post -Uri "$Url/api/tarefas" -ContentType "application/json" -Body $corpo
}

Write-Host "`nEnviando $Quantidade requisições para /api/info..."
$pods = 1..$Quantidade | ForEach-Object {
  # DisableKeepAlive = nova conexão a cada requisição, para o Service balancear
  (Invoke-WebRequest -Uri "$Url/api/info" -DisableKeepAlive -UseBasicParsing).Content | ConvertFrom-Json | Select-Object -ExpandProperty pod
  Invoke-WebRequest -Uri "$Url/" -DisableKeepAlive -UseBasicParsing | Out-Null
}
$pods | Group-Object | Select-Object @{n = "Pod"; e = { $_.Name } }, @{n = "Requisições"; e = { $_.Count } } | Format-Table -AutoSize

Write-Host "Total de tarefas gravadas no banco:"
Invoke-RestMethod -Uri "$Url/api/info"

