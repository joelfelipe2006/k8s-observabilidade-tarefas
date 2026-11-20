#!/usr/bin/env bash
# Grupo: Joel Felipe dos Santos Gonçalves, Luiz Eduardo Pageu Leite e Gabriel Ribeiro
# Remove tudo o que foi aplicado (mantém o cluster). Para apagar o cluster: minikube delete
set -uo pipefail
cd "$(dirname "$0")/.."
kubectl delete -f k8s/app-service.yaml -f k8s/app-deployment.yaml --ignore-not-found
kubectl delete -f k8s/observabilidade/ --ignore-not-found
kubectl delete -f k8s/banco-service.yaml -f k8s/banco-deployment.yaml -f k8s/banco-pvc.yaml -f k8s/banco-secret.yaml --ignore-not-found
