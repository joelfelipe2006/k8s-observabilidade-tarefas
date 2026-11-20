#!/usr/bin/env bash
# =============================================================================
# Grupo: Joel Felipe dos Santos Gonçalves, Luiz Eduardo Pageu Leite e Gabriel Ribeiro
#
# Sobe o ambiente completo do zero, na ordem do roteiro do trabalho:
#   1) Minikube  2) Banco  3) Aplicação (2 réplicas)  4) Observabilidade
# Uso (na raiz do repositório):  ./scripts/subir-tudo.sh
# No Windows, rode pelo Git Bash ou WSL (ou siga os comandos do INSTALL.md).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Etapa 1: iniciando o Minikube"
if ! minikube status >/dev/null 2>&1; then
  minikube start --driver=docker --cpus=4 --memory=6144
fi
kubectl get nodes

echo "==> Construindo a imagem da aplicação dentro do Minikube"
minikube image build -t tarefas-app:1.0 ./app

echo "==> Etapa 2: banco de dados"
kubectl apply -f k8s/banco-secret.yaml
kubectl apply -f k8s/banco-pvc.yaml
kubectl apply -f k8s/banco-deployment.yaml
kubectl apply -f k8s/banco-service.yaml
kubectl rollout status deployment/banco --timeout=180s

echo "==> Etapa 4 (antes da app, para os traces já terem destino): observabilidade"
kubectl apply -f k8s/observabilidade/
kubectl -n observabilidade rollout status deployment/tempo --timeout=300s
kubectl -n observabilidade rollout status deployment/loki --timeout=300s
kubectl -n observabilidade rollout status daemonset/otel-collector --timeout=300s
kubectl -n observabilidade rollout status deployment/prometheus --timeout=300s
kubectl -n observabilidade rollout status deployment/grafana --timeout=300s

echo "==> Etapa 3: aplicação com 2 réplicas"
kubectl apply -f k8s/app-deployment.yaml
kubectl apply -f k8s/app-service.yaml
kubectl rollout status deployment/app --timeout=180s

echo
kubectl get pods -o wide
echo
kubectl get pods -n observabilidade
echo
echo "Pronto! Abra as URLs com:"
echo "  minikube service app-service --url"
echo "  minikube service grafana -n observabilidade --url   (login admin / admin123)"
