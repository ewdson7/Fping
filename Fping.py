#!/usr/bin/env python3
import time
import logging
import subprocess
from prometheus_client import start_http_server, Gauge, Counter, Summary

# ==============================================================
# CONFIGURAÇÕES
# ==============================================================

TARGETS = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
FPING_PATH = "/usr/bin/fping"
COLLECTION_INTERVAL = 15   # segundos
FPING_TIMEOUT = 5          # segundos
EXPORTER_PORT = 8000

# ==============================================================
# LOGGING
# ==============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/var/log/fping_exporter.log"),
        logging.StreamHandler()
    ]
)

# ==============================================================
# MÉTRICAS PROMETHEUS
# ==============================================================

fping_latency_ms = Gauge("fping_latency_ms", "Latency in milliseconds", ["target", "type"])
fping_loss_pct = Gauge("fping_loss_percent", "Packet loss percentage", ["target"])

fping_sent_total = Counter("fping_packets_sent_total", "Total ICMP packets sent", ["target"])
fping_recv_total = Counter("fping_packets_received_total", "Total ICMP packets received", ["target"])
fping_lost_total = Counter("fping_packets_lost_total", "Total ICMP packets lost", ["target"])

collector_loop_duration = Summary("fping_collector_loop_duration_seconds", "Loop duration of fping collection")
collector_errors = Counter("fping_collector_errors_total", "Total number of collection errors")

# ==============================================================
# FUNÇÕES
# ==============================================================

def parse_fping_output(output):
    """
    Parseia saída do fping e retorna dict com métricas por target.
    """
    metrics = {}
    for line in output.splitlines():
        line = line.strip()
        if not line or "xmt/rcv/%loss" not in line:
            continue
        # Exemplo: 8.8.8.8 : xmt/rcv/%loss = 5/5/0%, min/avg/max = 12.3/14.1/15.5
        try:
            target = line.split()[0]
            sent_recv_loss = line.split('=')[1].split(',')[0].strip()
            sent, recv, loss = sent_recv_loss.replace('%', '').split('/')
            loss = float(loss)
            sent = int(sent)
            recv = int(recv)

            latency_part = line.split('=')[-1]
            min_, avg_, max_ = [float(x) for x in latency_part.split('/')]

            metrics[target] = {
                "sent": sent,
                "recv": recv,
                "loss": loss,
                "min": min_,
                "avg": avg_,
                "max": max_
            }
        except Exception as e:
            logging.warning(f"Falha ao interpretar linha '{line}': {e}")
    return metrics


def run_fping(targets):
    """
    Executa fping e retorna resultados parseados.
    """
    try:
        cmd = [FPING_PATH, "-c5", "-q"] + targets
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=FPING_TIMEOUT)
        combined_output = proc.stdout + "\n" + proc.stderr
        return parse_fping_output(combined_output)
    except subprocess.TimeoutExpired:
        logging.error("fping excedeu o tempo limite!")
        collector_errors.inc()
        return {}
    except Exception as e:
        logging.error(f"Erro ao executar fping: {e}")
        collector_errors.inc()
        return {}


@collector_loop_duration.time()
def collect_metrics():
    """
    Executa coleta e atualiza métricas Prometheus.
    """
    results = run_fping(TARGETS)
    for target, data in results.items():
        fping_latency_ms.labels(target=target, type="min").set(data["min"])
        fping_latency_ms.labels(target=target, type="avg").set(data["avg"])
        fping_latency_ms.labels(target=target, type="max").set(data["max"])
        fping_loss_pct.labels(target=target).set(data["loss"])

        fping_sent_total.labels(target=target).inc(data["sent"])
        fping_recv_total.labels(target=target).inc(data["recv"])
        lost_packets = data["sent"] - data["recv"]
        if lost_packets > 0:
            fping_lost_total.labels(target=target).inc(lost_packets)


def main():
    logging.info(f"Iniciando fping_exporter na porta {EXPORTER_PORT}")
    start_http_server(EXPORTER_PORT)
    while True:
        try:
            collect_metrics()
        except Exception as e:
            logging.error(f"Erro na coleta: {e}")
            collector_errors.inc()
        time.sleep(COLLECTION_INTERVAL)


if __name__ == "__main__":
    main()
