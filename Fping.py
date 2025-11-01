#!/usr/bin/env python3
import time
import logging
import subprocess
import threading
import re
import json
import os
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import start_http_server, Gauge, Counter
from pydantic import BaseModel
import uvicorn

# ==============================================================
# CONFIGURAÇÕES
# ==============================================================
FPING_PATH = "/usr/bin/fping"
COLLECTION_INTERVAL = 20
FPING_TIMEOUT = 40
FPING_COUNT = 20
FPING_PKT_TIMEOUT = 500
EXPORTER_PORT = 8000
API_PORT = 8080
TARGETS_FILE = "fping_targets.json"

# ==============================================================
# LOGGING
# ==============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ==============================================================
# PROMETHEUS MÉTRICAS
# ==============================================================
fping_latency_ms = Gauge(
    "fping_latency_ms",
    "ICMP latency per target and percentile",
    ["target", "percentile"]
)
fping_sent_total  = Counter("fping_packets_sent_total",     "Total ICMP packets sent",     ["target"])
fping_recv_total  = Counter("fping_packets_received_total", "Total ICMP packets received", ["target"])
fping_lost_total  = Counter("fping_packets_lost_total",     "Total ICMP packets lost",     ["target"])
fping_loss_percent = Gauge("fping_loss_percent", "Packet loss percentage per target", ["target"])

# ==============================================================
# FASTAPI + FRONT-END
# ==============================================================
app = FastAPI(title="FPing Exporter API", version="3.0.0")

# Pasta estática (HTML + JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

class Target(BaseModel):
    address: str

# ==============================================================
# FUNÇÕES DE PERSISTÊNCIA
# ==============================================================
def load_targets():
    if os.path.exists(TARGETS_FILE):
        try:
            with open(TARGETS_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set(["8.8.8.8", "1.1.1.1", "8.8.4.4"])

def save_targets():
    with open(TARGETS_FILE, "w") as f:
        json.dump(sorted(list(TARGETS)), f, indent=2)

TARGETS = load_targets()

# ==============================================================
# FPING EXECUÇÃO / PARSER
# ==============================================================
float_re = re.compile(r'(-?\d+(?:\.\d+)?)')

def parse_fping_output(output):
    metrics = {}
    for line in (output or "").splitlines():
        line = line.strip()
        if not line or "xmt/rcv/%loss" in line or "min/avg/max" in line or ":" not in line:
            continue
        target_part, tail = line.split(":", 1)
        target = target_part.strip()
        tail = tail.strip()
        nums = float_re.findall(tail)
        samples = [float(n) for n in nums if n]
        if len(samples) > 0:
            metrics[target] = samples[-FPING_COUNT:]
    return metrics

def run_fping(targets):
    if not targets:
        return {}
    try:
        cmd = [FPING_PATH, "-C", str(FPING_COUNT), "-t", str(FPING_PKT_TIMEOUT), "-q"] + list(targets)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=FPING_TIMEOUT)
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return parse_fping_output(combined)
    except subprocess.TimeoutExpired:
        logging.error("fping excedeu o tempo limite!")
        return {}
    except Exception as e:
        logging.exception(f"Erro ao executar fping: {e}")
        return {}

# ==============================================================
# COLETA
# ==============================================================
def collect_metrics():
    while True:
        try:
            results = run_fping(TARGETS)
            for tgt in list(TARGETS):
                latencies = results.get(tgt)
                sent = FPING_COUNT
                if latencies and len(latencies) > 0:
                    arr = np.array(latencies, dtype=float)
                    for p, val in {"p95": 95, "p50": 50, "p5": 5}.items():
                        fping_latency_ms.labels(target=tgt, percentile=p).set(float(np.percentile(arr, val)))

                    recv = len(latencies)
                    loss = sent - recv
                    loss_percent = (loss / sent) * 100.0 if sent > 0 else 0.0
                    fping_loss_percent.labels(target=tgt).set(loss_percent)

                    fping_sent_total.labels(target=tgt).inc(sent)
                    fping_recv_total.labels(target=tgt).inc(recv)
                    if loss > 0:
                        fping_lost_total.labels(target=tgt).inc(loss)
                else:
                    logging.warning(f"Sem amostras válidas para {tgt}")
                    for p in ["p95", "p50", "p5"]:
                        fping_latency_ms.labels(target=tgt, percentile=p).set(0)
                    fping_loss_percent.labels(target=tgt).set(100.0)
                    fping_sent_total.labels(target=tgt).inc(sent)
                    fping_lost_total.labels(target=tgt).inc(sent)
        except Exception:
            logging.exception("Erro no loop de coleta")
        time.sleep(COLLECTION_INTERVAL)

# ==============================================================
# API REST (CRUD)
# ==============================================================
@app.get("/")
def serve_front():
    return FileResponse("static/index.html")

@app.get("/targets")
def list_targets():
    return {"targets": sorted(list(TARGETS))}

@app.post("/targets")
def add_target(target: Target):
    if target.address in TARGETS:
        raise HTTPException(status_code=400, detail="Alvo já existe")

    TARGETS.add(target.address)
    save_targets()
    logging.info(f"Alvo adicionado: {target.address}")

    # 🟢 Força coleta imediata (sem esperar COLLECTION_INTERVAL)
    try:
        results = run_fping([target.address])
        latencies = results.get(target.address)
        sent = FPING_COUNT
        if latencies and len(latencies) > 0:
            arr = np.array(latencies, dtype=float)
            for p, val in {"p95": 95, "p50": 50, "p5": 5}.items():
                fping_latency_ms.labels(target=target.address, percentile=p).set(float(np.percentile(arr, val)))

            recv = len(latencies)
            loss = sent - recv
            loss_percent = (loss / sent) * 100.0 if sent > 0 else 0.0
            fping_loss_percent.labels(target=target.address).set(loss_percent)

            fping_sent_total.labels(target=target.address).inc(sent)
            fping_recv_total.labels(target=target.address).inc(recv)
            if loss > 0:
                fping_lost_total.labels(target=target.address).inc(loss)
        else:
            # Se não há amostras válidas
            for p in ["p95", "p50", "p5"]:
                fping_latency_ms.labels(target=target.address, percentile=p).set(0)
            fping_loss_percent.labels(target=target.address).set(100.0)
            fping_sent_total.labels(target=target.address).inc(sent)
            fping_lost_total.labels(target=target.address).inc(sent)

        logging.info(f"Coleta imediata concluída para {target.address}")
    except Exception as e:
        logging.exception(f"Erro ao coletar métricas iniciais para {target.address}: {e}")

    return {"message": f"Alvo {target.address} adicionado e coletado imediatamente", "targets": sorted(list(TARGETS))}


@app.delete("/targets/{address}")
def delete_target(address: str):
    if address not in TARGETS:
        raise HTTPException(status_code=404, detail="Alvo não encontrado")

    # Remove o alvo da lista
    TARGETS.remove(address)
    save_targets()
    logging.info(f"Alvo removido: {address}")

    # 🔥 Remove todas as métricas do alvo deletado
    try:
        fping_latency_ms.remove(address, "p95")
        fping_latency_ms.remove(address, "p50")
        fping_latency_ms.remove(address, "p5")
        fping_loss_percent.remove(address)
        fping_sent_total.remove(address)
        fping_recv_total.remove(address)
        fping_lost_total.remove(address)
    except Exception as e:
        logging.warning(f"Não foi possível remover métricas do alvo {address}: {e}")

    return {"message": "Alvo removido e métricas limpas", "targets": sorted(list(TARGETS))}


@app.put("/targets/{old_address}")
def update_target(old_address: str, new_target: Target):
    if old_address not in TARGETS:
        raise HTTPException(status_code=404, detail="Alvo não encontrado")
    TARGETS.remove(old_address)
    TARGETS.add(new_target.address)
    save_targets()
    logging.info(f"Alvo atualizado: {old_address} -> {new_target.address}")
    return {"message": "Alvo atualizado", "targets": sorted(list(TARGETS))}

# ==============================================================
# MAIN
# ==============================================================
def main():
    logging.info(f"Iniciando FPing Exporter (Prometheus: {EXPORTER_PORT}, API/Front: {API_PORT})")
    start_http_server(EXPORTER_PORT)
    threading.Thread(target=collect_metrics, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)

if __name__ == "__main__":
    main()
