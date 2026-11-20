#!/usr/bin/env bash
# =============================================================================
# Grupo: Joel Felipe dos Santos Gonçalves, Luiz Eduardo Pageu Leite e Gabriel Ribeiro
#
# Gera tráfego na aplicação e mostra quantas requisições cada réplica atendeu
# (prova do balanceamento de carga). Também cria tarefas no banco, o que
# produz métricas, logs e traces para o Grafana.
#
# Uso:  ./scripts/gerar-trafego.sh [URL] [quantidade]
#   ex: ./scripts/gerar-trafego.sh "$(minikube service app-service --url)" 50
# =============================================================================
set -euo pipefail
URL="${1:-$(minikube service app-service --url | head -n 1)}"
N="${2:-40}"

echo "Aplicação: $URL"
echo "Criando 5 tarefas via API..."
for i in 1 2 3 4 5; do
  curl -s -X POST "$URL/api/tarefas" -H 'Content-Type: application/json' \
       -d "{\"titulo\": \"Tarefa de teste $i ($(date +%H:%M:%S))\"}"
  echo
done

echo
echo "Enviando $N requisições para /api/info (cada uma abre uma nova conexão)..."
for _ in $(seq 1 "$N"); do
  curl -s "$URL/api/info" | sed -E 's/.*"pod":"([^"]+)".*/\1/'
  curl -s -o /dev/null "$URL/"
done | sort | uniq -c | awk '{printf "  %-40s %s requisições\n", $2, $1}'

echo
echo "Total de tarefas gravadas no banco:"
curl -s "$URL/api/info"; echo
