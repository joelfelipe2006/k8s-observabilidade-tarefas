# Como capturar as evidências

> Grupo: Joel Felipe dos Santos Gonçalves, Luiz Eduardo Pageu Leite e Gabriel Ribeiro

Salve cada captura **nesta pasta, com exatamente estes nomes**. O README.md já aponta para eles.

| Arquivo | O que deve aparecer | Como gerar |
|---|---|---|
| `01-kubectl-get-nodes.png` | nó `minikube` com STATUS `Ready` | `minikube status` e `kubectl get nodes` |
| `02-kubectl-get-pods.png` | **2 pods `app-...` e 1 pod `banco-...` em `Running` 1/1** | `kubectl get pods -o wide` |
| `03-kubectl-get-pods-observabilidade.png` | prometheus, loki, tempo, otel-collector, grafana e kube-state-metrics em `Running` | `kubectl get pods -n observabilidade` |
| `04-aplicacao-navegador.png` | app aberta no navegador, com tarefas na lista e a barra da URL visível | `minikube service app-service --url`, abrir a URL e criar 3 ou 4 tarefas |
| `05-balanceamento.png` | saída do script com os 2 pods recebendo requisições (pode juntar com a tela mostrando "Criada pelo pod" com pods diferentes) | `./scripts/gerar-trafego.sh <URL> 40` ou `.\scripts\gerar-trafego.ps1 -Url <URL>` |
| `06-grafana-metricas.png` | parte de cima do dashboard: réplicas Running, pods ativos, req/s por pod, CPU e memória | Grafana → dashboard "Tarefas Distribuídas" |
| `07-grafana-logs.png` | painéis de logs da app e do PostgreSQL com linhas recentes | role o dashboard até a seção "Logs (Loki)" |
| `08-grafana-traces.png` | um trace aberto mostrando `POST /tarefas → salvar-tarefa → INSERT` | clique em um Trace ID do painel "Traces recentes" |

**Dicas**

- Rode o script de tráfego **antes** de capturar o Grafana e espere ~30 s para os gráficos se preencherem.
- No Grafana, use o intervalo "Last 15 minutes" (canto superior direito).
- Para a 08, prefira um trace com raiz `POST /tarefas`, que mostra o INSERT no banco.
- Uma captura extra que valoriza: `Explore → Loki`, expandir uma linha com `trace_id=` e mostrar o botão **"Ver trace no Tempo"** (correlação log ↔ trace).
