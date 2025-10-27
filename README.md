# 🛰️ fping_exporter — Exportador de métricas de latência e perda de pacotes para Prometheus

Este projeto é um **exportador Prometheus** simples escrito em Python, que executa o comando [`fping`](https://fping.org/) periodicamente contra múltiplos destinos e expõe as métricas de **latência, perda de pacotes, pacotes enviados e recebidos** em um endpoint HTTP, pronto para ser coletado pelo Prometheus.

---

## 🚀 Funcionalidades

- Mede latência mínima, média e máxima (min/avg/max)
- Mede perda de pacotes (%)
- Mede pacotes enviados e recebidos
- Exporta as métricas no formato Prometheus
- Log detalhado de execução (`/tmp/fping_exporter.log`)
- Configuração simples por lista de alvos no código

---

## 📋 Pré-requisitos

Antes de rodar o script, você precisa ter:

- **Python 3.6+**
- **fping** instalado  
  (No Ubuntu/Debian, você pode instalar com:)
  ```bash
  sudo apt install fping
  ```
- Biblioteca Python `prometheus_client`:
  ```bash
  pip install prometheus_client
  ```

---

## ⚙️ Instalação

Clone este repositório:

```bash
git clone https://github.com/seu-usuario/fping_exporter.git
cd fping_exporter
```

Dê permissão de execução ao script:

```bash
chmod +x fping_exporter.py
```

---

## 🧠 Configuração

Dentro do arquivo `fping_exporter.py`, você pode definir os alvos a serem monitorados:

```python
TARGETS = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
```

Você pode adicionar quantos IPs ou hostnames desejar.

---

## ▶️ Execução

Inicie o exportador com:

```bash
./fping_exporter.py
```

Por padrão, ele inicia um servidor HTTP local na porta **8000** e expõe as métricas no endpoint:

👉 [http://localhost:8000/metrics](http://localhost:8000/metrics)

Exemplo de saída:
```
# HELP fping_latency Latency in ms
# TYPE fping_latency gauge
fping_latency{target="8.8.8.8",type="avg"} 12.4
fping_latency{target="8.8.8.8",type="min"} 10.3
fping_latency{target="8.8.8.8",type="max"} 15.2
fping_loss{target="8.8.8.8"} 0.0
```

Os logs são salvos em `/tmp/fping_exporter.log`.

---

## 📊 Integração com Prometheus

Adicione o job no seu `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: "fping_exporter"
    static_configs:
      - targets: ["localhost:8000"]
```

Reinicie o Prometheus e acesse o endpoint `/targets` para confirmar se o `fping_exporter` está sendo coletado corretamente.

---

## 📈 Dashboard no Grafana (opcional)

Você pode criar um painel no Grafana com gráficos como:

- Latência média por destino (`fping_latency{type="avg"}`)
- Perda de pacotes (`fping_loss`)
- Pacotes enviados/recebidos (`fping_sent`, `fping_received`)
- Tempo de execução de cada loop (`loop_duration_seconds`)

---

## 🪵 Logs

O script grava logs detalhados tanto na saída padrão quanto no arquivo:

```
/tmp/fping_exporter.log
```

Esses logs ajudam na depuração e mostram os resultados de cada execução do `fping`.

---

## 🧩 Métricas exportadas

| Métrica | Descrição | Labels |
|----------|------------|--------|
| `fping_latency` | Latência em milissegundos | `target`, `type` (`min`, `avg`, `max`) |
| `fping_loss` | Perda de pacotes (%) | `target` |
| `fping_sent` | Pacotes enviados | `target` |
| `fping_received` | Pacotes recebidos | `target` |
| `loop_duration_seconds` | Tempo total de uma iteração | *(sem labels)* |

---

## 🧰 Execução em background (opcional)

Para rodar como serviço no Linux:

```bash
nohup ./fping_exporter.py &
```

Ou crie um serviço systemd em `/etc/systemd/system/fping_exporter.service`:

```ini
[Unit]
Description=Prometheus fping exporter
After=network.target

[Service]
ExecStart=/usr/bin/python3 /caminho/para/fping_exporter.py
Restart=always
User=nobody

[Install]
WantedBy=multi-user.target
```

---

## 🧑‍💻 Autor

**Ewdson Tiago**  
📧 Contato: [ewdsontiago@gmail.com]  
💻 GitHub: [https://github.com/ewdson7](https://github.com/ewdson7)

---

## 📜 Licença

Distribuído sob a licença **MIT**. Veja o arquivo `LICENSE` para mais informações.
