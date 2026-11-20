# INSTALL.md — Instalação do Minikube e implantação do ambiente

> **Desenvolvimento de Sistemas Distribuídos · ADS4 · Faculdade SENAI FATESG**
> Grupo: **Joel Felipe dos Santos Gonçalves**, **Luiz Eduardo Pageu Leite** e **Gabriel Ribeiro**

Este guia leva do computador "zerado" até o cluster Kubernetes local rodando o banco, a aplicação com 2 réplicas e a stack de observabilidade. Para entender a aplicação e ver as evidências, consulte o [README.md](README.md).

---

## Sumário

1. [Requisitos de hardware](#1-requisitos-de-hardware)
2. [Instalar Docker, kubectl e Minikube](#2-instalar-docker-kubectl-e-minikube)
3. [Iniciar o cluster](#3-iniciar-o-cluster-etapa-1)
4. [Construir a imagem da aplicação](#4-construir-a-imagem-da-aplicação)
5. [Implantar o banco de dados](#5-implantar-o-banco-de-dados-etapa-2)
6. [Implantar a stack de observabilidade](#6-implantar-a-stack-de-observabilidade-etapa-4)
7. [Implantar a aplicação replicada](#7-implantar-a-aplicação-replicada-etapa-3)
8. [Acessar e validar](#8-acessar-e-validar-etapa-5)
9. [Atalho: script único](#9-atalho-script-único)
10. [Solução de problemas](#10-solução-de-problemas)
11. [Limpeza](#11-limpeza)

---

## 1. Requisitos de hardware

| Recurso | Mínimo | Recomendado |
|---|---|---|
| CPU | 2 núcleos | 4 núcleos |
| Memória RAM livre para o Minikube | 4 GB | 6 GB |
| Disco livre | 20 GB | 30 GB |
| Virtualização | habilitada na BIOS (VT-x / AMD-V) | — |

No Windows e no macOS, o Docker Desktop precisa ter essa memória liberada em *Settings → Resources*.

## 2. Instalar Docker, kubectl e Minikube

### Windows 10/11 (PowerShell como Administrador)

```powershell
# Docker Desktop (usa WSL 2; reinicie o PC se for pedido)
winget install -e --id Docker.DockerDesktop

# kubectl e Minikube
winget install -e --id Kubernetes.kubectl
winget install -e --id Kubernetes.minikube
```

Abra o Docker Desktop e espere o ícone ficar verde ("Engine running"). Feche e reabra o terminal para o `PATH` ser atualizado.

### Linux (Ubuntu/Debian)

```bash
# Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```

### macOS (Homebrew)

```bash
brew install --cask docker      # abra o Docker Desktop depois de instalar
brew install kubectl minikube
```

### Conferir as versões

```bash
docker --version
kubectl version --client
minikube version
```

## 3. Iniciar o cluster (Etapa 1)

```bash
minikube start --driver=docker --cpus=4 --memory=6144
```

> Com menos recursos: `minikube start --driver=docker --cpus=2 --memory=4096` também funciona.

Verificar se o nó está ativo e pronto:

```bash
kubectl get nodes
```

Saída esperada:

```
NAME       STATUS   ROLES           AGE   VERSION
minikube   Ready    control-plane   1m    v1.3x.x
```

Clone o repositório e entre na pasta (todos os comandos a seguir rodam na raiz dele):

```bash
git clone https://github.com/<usuario>/<repositorio>.git
cd <repositorio>
```

## 4. Construir a imagem da aplicação

A aplicação é um código próprio (pasta `app/`). A imagem é construída **dentro** do Minikube, então não precisa de Docker Hub:

```bash
minikube image build -t tarefas-app:1.0 ./app
minikube image ls | grep tarefas-app        # PowerShell: minikube image ls | Select-String tarefas-app
```

## 5. Implantar o banco de dados (Etapa 2)

PostgreSQL 16 com credenciais em Secret e dados em volume persistente:

```bash
kubectl apply -f k8s/banco-secret.yaml
kubectl apply -f k8s/banco-pvc.yaml
kubectl apply -f k8s/banco-deployment.yaml
kubectl apply -f k8s/banco-service.yaml

kubectl rollout status deployment/banco
kubectl get pods -l app=banco
kubectl get svc banco-service
```

## 6. Implantar a stack de observabilidade (Etapa 4)

> Aplicamos a observabilidade **antes** da aplicação para que os primeiros traces e logs já tenham para onde ir. A ordem inversa (como no roteiro) também funciona: a aplicação só começa a enviar telemetria quando o Collector fica disponível.

Todos os manifestos estão em `k8s/observabilidade/` (YAML puro, sem Helm) e são aplicados de uma vez, em ordem numérica:

```bash
kubectl apply -f k8s/observabilidade/
```

| Arquivo | O que cria |
|---|---|
| `00-namespace.yaml` | namespace `observabilidade` |
| `01-kube-state-metrics.yaml` | métricas de estado dos pods (Running, réplicas) |
| `02-prometheus.yaml` | Prometheus + regras de coleta (scrape) + permissões RBAC |
| `03-loki.yaml` | Loki (armazenamento de logs) |
| `04-tempo.yaml` | Tempo (armazenamento de traces) |
| `05-otel-collector.yaml` | OpenTelemetry Collector (DaemonSet): recebe traces/métricas da app e lê os logs dos pods |
| `06-grafana.yaml` | Grafana com as fontes Prometheus, Loki e Tempo já configuradas |
| `07-grafana-dashboard.yaml` | dashboard pronto do trabalho |

Aguarde tudo ficar `Running` (o primeiro download das imagens leva alguns minutos):

```bash
kubectl get pods -n observabilidade -w        # Ctrl+C para sair
```

## 7. Implantar a aplicação replicada (Etapa 3)

```bash
kubectl apply -f k8s/app-deployment.yaml
kubectl apply -f k8s/app-service.yaml

kubectl rollout status deployment/app
kubectl get pods
```

Saída esperada — **2 réplicas da aplicação + 1 banco**:

```
NAME                     READY   STATUS    RESTARTS   AGE
app-6c9b8f7d4-7xk2p      1/1     Running   0          40s
app-6c9b8f7d4-qm9zt      1/1     Running   0          40s
banco-5d8c7b9f6-h4n8w    1/1     Running   0          3m
```

## 8. Acessar e validar (Etapa 5)

### Aplicação

```bash
minikube service app-service --url
```

> No Windows/macOS (driver docker) o comando **fica rodando** para manter o túnel aberto — deixe esse terminal aberto e use outro para os próximos comandos. No Linux ele imprime a URL e termina (`http://<ip-do-minikube>:30080`).

Abra a URL no navegador, crie tarefas e recarregue a página com **Ctrl+F5**: o nome do pod no topo alterna entre as duas réplicas.

Teste do balanceamento pela linha de comando:

```bash
# Linux / macOS / Git Bash
./scripts/gerar-trafego.sh http://127.0.0.1:XXXXX 40

# Windows PowerShell
.\scripts\gerar-trafego.ps1 -Url http://127.0.0.1:XXXXX -Quantidade 40
```

### Grafana

```bash
minikube service grafana -n observabilidade --url
```

Login **admin / admin123**. O dashboard *Tarefas Distribuídas — Kubernetes + Observabilidade* abre como página inicial.

### Prometheus (opcional)

```bash
minikube service prometheus -n observabilidade --url
```

Em *Status → Targets*, todos os alvos (`otel-collector`, `kube-state-metrics`, `kubelet-cadvisor`, `loki`, `tempo`) devem estar **UP**.

## 9. Atalho: script único

Faz os passos 3 a 7 de uma vez (Linux, macOS, Git Bash ou WSL):

```bash
chmod +x scripts/*.sh
./scripts/subir-tudo.sh
```

## 10. Solução de problemas

| Sintoma | Causa provável | Como resolver |
|---|---|---|
| Pod `app` em `ErrImagePull` / `ImagePullBackOff` | imagem não foi construída no Minikube | `minikube image build -t tarefas-app:1.0 ./app` e depois `kubectl rollout restart deployment/app` |
| Pod `app` em `0/1 Running` por muito tempo | banco ainda não está pronto (a readiness checa o banco) | `kubectl logs deploy/app`; aguarde o `banco` ficar `1/1` |
| Pods em `Pending` | pouca memória/CPU no Minikube | `minikube delete` e `minikube start --cpus=4 --memory=6144` |
| Grafana sem dados de métricas da app | ainda não houve requisições | rode `scripts/gerar-trafego` e espere ~30 s |
| Painel de logs vazio | Collector ainda iniciando | `kubectl logs -n observabilidade ds/otel-collector` |
| Sempre o mesmo pod responde no navegador | o navegador reaproveita a conexão (keep-alive) | use Ctrl+F5, aba anônima ou o script de tráfego |
| `kubectl port-forward` sempre cai no mesmo pod | o port-forward fixa um único pod | use `minikube service app-service --url` (passa pelo Service e balanceia) |

Comandos úteis:

```bash
kubectl describe pod <nome-do-pod>
kubectl logs -f deployment/app
kubectl logs deployment/banco
kubectl get all -n observabilidade
minikube dashboard            # painel web do próprio Kubernetes
```

## 11. Limpeza

```bash
./scripts/limpar.sh           # remove os recursos e mantém o cluster
minikube stop                 # desliga o cluster
minikube delete               # apaga o cluster
```
