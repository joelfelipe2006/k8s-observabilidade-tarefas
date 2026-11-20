# Grupo: Joel Felipe dos Santos Gonçalves, Luiz Eduardo Pageu Leite e Gabriel Ribeiro
# Imagem da aplicação "Tarefas Distribuídas".
# Build direto dentro do Minikube:  minikube image build -t tarefas-app:1.0 ./app
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates ./templates

RUN useradd --uid 1000 --no-create-home appuser
USER 1000

EXPOSE 8080
# 1 processo com 4 threads: o SDK do OpenTelemetry é iniciado dentro do worker
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--access-logfile", "-", "app:app"]
