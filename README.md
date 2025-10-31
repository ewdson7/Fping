# 🎯 FPing Exporter com Interface Web

Um **exporter leve e simples** que executa *pings ICMP (fping)* para
múltiplos destinos, exporta métricas no formato do **Prometheus** e
oferece uma **interface web** para gerenciar os alvos (CRUD).

------------------------------------------------------------------------

## 🚀 Visão Geral

Este projeto permite: - Monitorar **latência** e **perda de pacotes** de
múltiplos hosts via `fping`. - Exportar métricas compatíveis com
**Prometheus**. - Adicionar, editar e remover *targets* dinamicamente
via **API REST** ou **interface web** (estática). - Integrar facilmente
com **Grafana** para visualizações.

------------------------------------------------------------------------

## 🧩 Funcionalidades

✅ Coleta automática de métricas ICMP com `fping`\
✅ Métricas no formato Prometheus (`/metrics`)\
✅ Interface web moderna em TailwindCSS\
✅ API REST completa (CRUD) para gerenciamento de targets\
✅ Atualização dinâmica da lista de alvos sem reiniciar o processo\
✅ Exclusão de métricas de targets removidos

------------------------------------------------------------------------

## 🛠️ Requisitos

-   Python 3.8+
-   fping instalado no sistema (`sudo apt install fping`)
-   Dependências Python (instaladas via
    `pip install -r requirements.txt`)

------------------------------------------------------------------------

## 📦 Instalação

``` bash
# Clone o repositório
git clone https://github.com/seu-usuario/fping-exporter.git
cd fping-exporter

# Instale as dependências
pip install -r requirements.txt
```

> 💡 Caso ainda não tenha um `requirements.txt`, utilize este conteúdo:
>
> ``` text
> fastapi
> uvicorn
> prometheus_client
> numpy
> ```

------------------------------------------------------------------------

## ⚙️ Configuração

Os principais parâmetros estão definidos no início do arquivo
`fping.py`:

  --------------------------------------------------------------------------
  Variável                 Descrição                  Padrão
  ------------------------ -------------------------- ----------------------
  `FPING_PATH`             Caminho do binário `fping` `/usr/bin/fping`

  `COLLECTION_INTERVAL`    Intervalo entre coletas    `20`
                           (segundos)                 

  `FPING_COUNT`            Número de pacotes enviados `20`
                           por coleta                 

  `FPING_PKT_TIMEOUT`      Timeout de cada pacote     `500`
                           (ms)                       

  `EXPORTER_PORT`          Porta de métricas          `8000`
                           Prometheus                 

  `API_PORT`               Porta da interface web/API `8080`

  `TARGETS_FILE`           Caminho do arquivo JSON de `fping_targets.json`
                           alvos                      
  --------------------------------------------------------------------------

------------------------------------------------------------------------

## ▶️ Execução

``` bash
python3 fping.py
```

Isso iniciará: - o **Prometheus exporter** em
`http://localhost:8000/metrics` - a **interface web** e **API REST** em
`http://localhost:8080/`

------------------------------------------------------------------------

## 🌐 Interface Web

Acesse no navegador:

    http://localhost:8080/

A interface permite: - Adicionar novos alvos (IP ou hostname) - Editar
endereços existentes - Remover alvos e limpar métricas associadas

Os alvos são persistidos no arquivo `fping_targets.json`.

------------------------------------------------------------------------

## 📡 Endpoints da API

  ---------------------------------------------------------------------------
  Método             Endpoint                   Descrição
  ------------------ -------------------------- -----------------------------
  `GET`              `/targets`                 Lista todos os targets

  `POST`             `/targets`                 Adiciona um novo target
                                                (JSON:
                                                `{ "address": "8.8.8.8" }`)

  `PUT`              `/targets/{old}`           Atualiza o endereço de um
                                                target

  `DELETE`           `/targets/{addr}`          Remove um target e apaga suas
                                                métricas

  `GET`              `/`                        Página inicial (interface
                                                web)
  ---------------------------------------------------------------------------

------------------------------------------------------------------------

## 📊 Integração com Prometheus

Adicione o *job* ao seu `prometheus.yml`:

``` yaml
scrape_configs:
  - job_name: 'fping_exporter'
    static_configs:
      - targets: ['localhost:8000']
```

Métricas principais exportadas: - `fping_latency_ms{target,percentile}`\
- `fping_packets_sent_total{target}`\
- `fping_packets_received_total{target}`\
- `fping_packets_lost_total{target}`\
- `fping_loss_percent{target}`

------------------------------------------------------------------------

## 📈 Dashboard Grafana (sugestão)

Crie um painel com: - **Latência P50, P95 e P5** com *sombras* (bandas
de variação) - **Perda de Pacotes (%)** com alerta visual

Exemplo de query PromQL:

``` promql
fping_loss_percent{target="8.8.8.8"}
```

E para latência:

``` promql
fping_latency_ms{target="8.8.8.8", percentile="p50"}
```

------------------------------------------------------------------------

## 🧹 Persistência e Limpeza de Métricas

Ao remover um alvo via API ou interface: - O endereço é apagado de
`fping_targets.json` - Todas as métricas associadas são **removidas
dinamicamente** da memória

------------------------------------------------------------------------

## 📁 Estrutura do Projeto

    fping-exporter/
    ├── fping.py              # Script principal (exporter + API)
    ├── fping_targets.json    # Lista persistente de targets
    ├── static/
    │   └── index.html        # Interface web (CRUD)
    └── requirements.txt      # Dependências Python

------------------------------------------------------------------------

## 🧑‍💻 Autor

**Ewdson Tiago**\
💼 Projeto pessoal de monitoramento com Prometheus + FPing\
📧 Contribuições e melhorias são bem-vindas!

------------------------------------------------------------------------

## 🪪 Licença

Distribuído sob a licença MIT.\
Sinta-se à vontade para usar, modificar e contribuir!
