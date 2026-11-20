# =============================================================================
# Desenvolvimento de Sistemas Distribuídos - ADS4 - Faculdade SENAI FATESG
# Trabalho: Kubernetes (Minikube) + Observabilidade (Prometheus, Loki, Tempo,
#           OpenTelemetry e Grafana)
# Grupo:
#   - Joel Felipe dos Santos Gonçalves
#   - Luiz Eduardo Pageu Leite
#   - Gabriel Ribeiro
#
# Aplicação "Tarefas Distribuídas": lista de tarefas em Flask que grava no
# PostgreSQL. Cada página mostra QUAL POD atendeu a requisição, o que permite
# comprovar o balanceamento de carga entre as réplicas.
# Telemetria:
#   - Traces  -> OpenTelemetry SDK -> OTel Collector -> Tempo
#   - Métricas-> OpenTelemetry SDK -> OTel Collector -> Prometheus
#   - Logs    -> stdout do container -> OTel Collector (filelog) -> Loki
# =============================================================================
import logging
import os
import socket
import time

import psycopg2
from flask import Flask, jsonify, redirect, render_template, request, url_for
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

POD_NAME = os.getenv("POD_NAME", socket.gethostname())
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "app-tarefas")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "banco-service"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "tarefas"),
    "user": os.getenv("DB_USER", "tarefas"),
    "password": os.getenv("DB_PASSWORD", ""),
    "connect_timeout": 3,
}


# ---------------------------------------------------------------------------
# Logs: uma linha por evento, com trace_id para correlacionar Loki -> Tempo
# ---------------------------------------------------------------------------
class TraceIdFilter(logging.Filter):
    def filter(self, record):
        ctx = trace.get_current_span().get_span_context()
        record.trace_id = format(ctx.trace_id, "032x") if ctx.is_valid else "-"
        record.pod = POD_NAME
        return True


handler = logging.StreamHandler()
handler.addFilter(TraceIdFilter())
handler.setFormatter(
    logging.Formatter(
        "%(asctime)s level=%(levelname)s pod=%(pod)s trace_id=%(trace_id)s msg=\"%(message)s\""
    )
)
log = logging.getLogger("app")
log.setLevel(logging.INFO)
log.addHandler(handler)
log.propagate = False


# ---------------------------------------------------------------------------
# OpenTelemetry: traces e métricas enviados via OTLP/gRPC ao Collector
# (o endpoint vem da variável padrão OTEL_EXPORTER_OTLP_ENDPOINT)
# ---------------------------------------------------------------------------
resource = Resource.create(
    {
        "service.name": SERVICE_NAME,
        "service.instance.id": POD_NAME,
        "k8s.pod.name": POD_NAME,
        "k8s.namespace.name": os.getenv("POD_NAMESPACE", "default"),
    }
)

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(insecure=True)))
trace.set_tracer_provider(tracer_provider)

meter_provider = MeterProvider(
    resource=resource,
    metric_readers=[
        PeriodicExportingMetricReader(OTLPMetricExporter(insecure=True), export_interval_millis=10000)
    ],
)
metrics.set_meter_provider(meter_provider)

tracer = trace.get_tracer("app-tarefas")
meter = metrics.get_meter("app-tarefas")
contador_requisicoes = meter.create_counter(
    "app.requisicoes", description="Requisições HTTP atendidas por este pod"
)
contador_tarefas = meter.create_counter(
    "app.tarefas.operacoes", description="Operações de escrita no banco (criar/concluir/excluir)"
)

# Cria um span para cada query SQL. skip_dep_check: a checagem procura o pacote
# "psycopg2", mas a imagem usa "psycopg2-binary" (mesmo módulo).
Psycopg2Instrumentor().instrument(skip_dep_check=True)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app, excluded_urls="health")  # span por requisição HTTP


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------
def conectar():
    return psycopg2.connect(**DB_CONFIG)


def criar_tabela():
    """Cria a tabela na subida do pod; tenta de novo enquanto o banco não estiver pronto.

    As réplicas sobem ao mesmo tempo: o advisory lock garante que só uma
    executa o CREATE TABLE por vez (sem ele o Postgres acusa chave duplicada).
    """
    for tentativa in range(1, 31):
        try:
            with conectar() as conn, conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(424242)")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tarefas (
                        id         SERIAL PRIMARY KEY,
                        titulo     VARCHAR(200) NOT NULL,
                        concluida  BOOLEAN      NOT NULL DEFAULT FALSE,
                        criada_por VARCHAR(100) NOT NULL,
                        criada_em  TIMESTAMP    NOT NULL DEFAULT NOW()
                    )
                    """
                )
            log.info("Conectado ao banco %s:%s e tabela pronta", DB_CONFIG["host"], DB_CONFIG["port"])
            return
        except psycopg2.Error as erro:
            log.warning("Banco indisponível (tentativa %d/30): %s", tentativa, str(erro).strip())
            time.sleep(2)
    raise RuntimeError("Não foi possível conectar ao banco de dados")


@app.before_request
def contar_requisicao():
    if request.path != "/health":
        contador_requisicoes.add(1, {"rota": request.path, "metodo": request.method})


# ---------------------------------------------------------------------------
# Rotas web
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, titulo, concluida, criada_por, criada_em FROM tarefas ORDER BY id DESC"
        )
        tarefas = cur.fetchall()
        cur.execute("SELECT version()")
        versao_banco = cur.fetchone()[0].split(",")[0]
    log.info("Listagem de tarefas: %d registros", len(tarefas))
    return render_template(
        "index.html",
        tarefas=tarefas,
        pod=POD_NAME,
        banco=f"{DB_CONFIG['host']}:{DB_CONFIG['port']}",
        versao_banco=versao_banco,
    )


@app.route("/tarefas", methods=["POST"])
def criar():
    titulo = (request.form.get("titulo") or "").strip()[:200]
    if titulo:
        with tracer.start_as_current_span("salvar-tarefa") as span:
            span.set_attribute("tarefa.titulo", titulo)
            with conectar() as conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tarefas (titulo, criada_por) VALUES (%s, %s) RETURNING id",
                    (titulo, POD_NAME),
                )
                novo_id = cur.fetchone()[0]
            span.set_attribute("tarefa.id", novo_id)
        contador_tarefas.add(1, {"operacao": "criar"})
        log.info("Tarefa %d criada: %s", novo_id, titulo)
    return redirect(url_for("index"))


@app.route("/tarefas/<int:tarefa_id>/concluir", methods=["POST"])
def concluir(tarefa_id):
    with conectar() as conn, conn.cursor() as cur:
        cur.execute("UPDATE tarefas SET concluida = NOT concluida WHERE id = %s", (tarefa_id,))
    contador_tarefas.add(1, {"operacao": "concluir"})
    log.info("Tarefa %d alterada", tarefa_id)
    return redirect(url_for("index"))


@app.route("/tarefas/<int:tarefa_id>/excluir", methods=["POST"])
def excluir(tarefa_id):
    with conectar() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM tarefas WHERE id = %s", (tarefa_id,))
    contador_tarefas.add(1, {"operacao": "excluir"})
    log.info("Tarefa %d excluída", tarefa_id)
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# API (usada pelos scripts de teste de balanceamento)
# ---------------------------------------------------------------------------
@app.route("/api/info")
def info():
    with conectar() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tarefas")
        total = cur.fetchone()[0]
    log.info("Consulta /api/info")
    return jsonify(pod=POD_NAME, banco=DB_CONFIG["host"], total_tarefas=total)


@app.route("/api/tarefas", methods=["GET", "POST"])
def api_tarefas():
    if request.method == "POST":
        titulo = ((request.get_json(silent=True) or {}).get("titulo") or "").strip()[:200]
        if not titulo:
            return jsonify(erro="campo 'titulo' é obrigatório"), 400
        with conectar() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tarefas (titulo, criada_por) VALUES (%s, %s) RETURNING id",
                (titulo, POD_NAME),
            )
            novo_id = cur.fetchone()[0]
        contador_tarefas.add(1, {"operacao": "criar"})
        log.info("Tarefa %d criada via API: %s", novo_id, titulo)
        return jsonify(id=novo_id, titulo=titulo, criada_por=POD_NAME), 201

    with conectar() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, titulo, concluida, criada_por FROM tarefas ORDER BY id")
        linhas = cur.fetchall()
    return jsonify(
        atendido_por=POD_NAME,
        tarefas=[
            {"id": i, "titulo": t, "concluida": c, "criada_por": p} for i, t, c, p in linhas
        ],
    )


@app.route("/health")
def health():
    """Usado pelas probes do Kubernetes: só fica 'pronto' se o banco responder."""
    try:
        with conectar() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify(status="ok", pod=POD_NAME)
    except psycopg2.Error as erro:
        log.error("Health check falhou: %s", str(erro).strip())
        return jsonify(status="erro", detalhe=str(erro).strip()), 503


criar_tabela()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
