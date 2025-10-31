#!/usr/bin/env python3
import time
import logging
import subprocess
import threading
import re
from fastapi import FastAPI, HTTPException
from prometheus_client import start_http_server, Gauge, Counter
from pydantic import BaseModel
import numpy as np

# ==============================================================
# CONFIGURAÇÕES
# ==============================================================
FPING_PATH = "/usr/bin/fping"
COLLECTION_INTERVAL = 20  # segundos
FPING_TIMEOUT = 40        # segundos - tempo limite do Python
FPING_COUNT = 20          # número de pacotes por target
FPING_PKT_TIMEOUT = 500   # ms por pacote (-t)
EXPORTER_PORT = 8000
API_PORT = 8080

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

# Latência unificada com label "percentile"
fping_latency_ms = Gauge(
    "fping_latency_ms",
    "ICMP latency per target and percentile",
    ["target", "percentile"]
)

# Pacotes enviados / recebidos / perdidos
fping_sent_total  = Counter("fping_packets_sent_total",     "Total ICMP packets sent",     ["target"])
fping_recv_total  = Counter("fping_packets_received_total", "Total ICMP packets received", ["target"])
fping_lost_total  = Counter("fping_packets_lost_total",     "Total ICMP packets lost",     ["target"])

# Percentual de perda
fping_loss_percent = Gauge("fping_loss_percent", "Packet loss percentage per target", ["target"])

# ==============================================================
# FASTAPI CONFIG
# ==============================================================
app = FastAPI(title="FPing Exporter API", version="2.3.0")

class Target(BaseModel):
    address: str

TARGETS = set(["8.8.8.8", "1.1.1.1", "8.8.4.4"])

# ==============================================================
# FUNÇÕES DE COLETA / PARSER
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
        if "=" in tail and len(nums) < 2:
            continue

        samples = []
        for n in nums:
            try:
                samples.append(float(n))
            except:
                pass

        if len(samples) >= 1:
            if len(samples) >= FPING_COUNT:
                found_seq = None
                for i in range(0, len(samples) - FPING_COUNT + 1):
                    seq = samples[i:i+FPING_COUNT]
                    if all(v >= 0 for v in seq):
                        found_seq = seq
                        break
                if found_seq is None:
                    found_seq = samples[-FPING_COUNT:]
                metrics[target] = found_seq
            else:
                metrics[target] = samples
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
# LOOP DE COLETA
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
                    percentis = {
                        "p95": float(np.percentile(arr, 95)),
                        "p50": float(np.percentile(arr, 50)),
                        "p5":  float(np.percentile(arr, 5)),
                    }
                    for p, val in percentis.items():
                        fping_latency_ms.labels(target=tgt, percentile=p).set(val)

                    recv = len(latencies)
                    loss = sent - recv
                    loss_percent = (loss / sent) * 100.0 if sent > 0 else 0.0
                    fping_loss_percent.labels(target=tgt).set(loss_percent)

                    fping_sent_total.labels(target=tgt).inc(sent)
                    fping_recv_total.labels(target=tgt).inc(recv)
                    if loss > 0:
                        fping_lost_total.labels(target=tgt).inc(loss)
                else:
                    logging.warning(f"No latency samples for target {tgt} (marking 100% loss)")
                    # Zera as latências
                    for p in ["p95", "p50", "p5"]:
                        fping_latency_ms.labels(target=tgt, percentile=p).set(0)

                    recv = 0
                    loss = sent - recv
                    loss_percent = 100.0 if sent > 0 else 0.0
                    fping_loss_percent.labels(target=tgt).set(loss_percent)

                    fping_sent_total.labels(target=tgt).inc(sent)
                    fping_lost_total.labels(target=tgt).inc(sent)
        except Exception:
            logging.exception("Erro no loop de coleta")
        time.sleep(COLLECTION_INTERVAL)

# ==============================================================
# ENDPOINTS API (CRUD)
# ==============================================================
@app.get("/targets")
def list_targets():
    return {"targets": sorted(list(TARGETS))}

@app.post("/targets")
def add_target(target: Target):
    if target.address in TARGETS:
        raise HTTPException(status_code=400, detail="Alvo já existe")
    TARGETS.add(target.address)
    logging.info(f"Alvo adicionado: {target.address}")
    return {"message": "Alvo adicionado com sucesso", "targets": sorted(list(TARGETS))}

@app.delete("/targets/{address}")
def delete_target(address: str):
    if address not in TARGETS:
        raise HTTPException(status_code=404, detail="Alvo não encontrado")
    TARGETS.remove(address)
    logging.info(f"Alvo removido: {address}")
    return {"message": "Alvo removido", "targets": sorted(list(TARGETS))}

@app.put("/targets/{old_address}")
def update_target(old_address: str, new_target: Target):
    if old_address not in TARGETS:
        raise HTTPException(status_code=404, detail="Alvo não encontrado")
    TARGETS.remove(old_address)
    TARGETS.add(new_target.address)
    logging.info(f"Alvo atualizado: {old_address} -> {new_target.address}")
    return {"message": "Alvo atualizado", "targets": sorted(list(TARGETS))}

# ==============================================================
# MAIN
# ==============================================================
def main():
    logging.info(f"Iniciando FPing Exporter (Prometheus: {EXPORTER_PORT}, API: {API_PORT})")
    start_http_server(EXPORTER_PORT)
    threading.Thread(target=collect_metrics, daemon=True).start()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)

if __name__ == "__main__":
    main()
