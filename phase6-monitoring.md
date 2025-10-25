# Phase 6 – Monitoring & Visualization Implementation Guide

## 6.1 Prometheus Setup
1. **Install Prometheus** (Ubuntu example):
   ```bash
   sudo useradd --no-create-home --shell /bin/false prometheus
   sudo mkdir -p /etc/prometheus /var/lib/prometheus
   curl -fsSL https://github.com/prometheus/prometheus/releases/download/v2.52.0/prometheus-2.52.0.linux-amd64.tar.gz -o /tmp/prometheus.tar.gz
   tar -xf /tmp/prometheus.tar.gz -C /tmp
   sudo cp /tmp/prometheus-2.52.0.linux-amd64/prometheus /usr/local/bin/
   sudo cp /tmp/prometheus-2.52.0.linux-amd64/promtool /usr/local/bin/
   sudo cp -r /tmp/prometheus-2.52.0.linux-amd64/{consoles,console_libraries} /etc/prometheus/
   sudo chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus /usr/local/bin/prometheus /usr/local/bin/promtool
   ```

2. **Create configuration** (`/etc/prometheus/prometheus.yml`):
   ```yaml
   global:
     scrape_interval: 5s
     evaluation_interval: 15s

   scrape_configs:
     - job_name: quorum-nodes
       metrics_path: /metrics
       static_configs:
         - targets:
             - 127.0.0.1:9101  # quorum-node1 exporter
             - 127.0.0.1:9102  # quorum-node2 exporter
             - 127.0.0.1:9103  # quorum-node3 exporter
             - 127.0.0.1:9104  # quorum-node4 exporter
             - 127.0.0.1:9105  # optional extra nodes
             - 127.0.0.1:9106
             - 127.0.0.1:9107
       relabel_configs:
         - source_labels: [__address__]
           target_label: instance
   ```
   *Update target list to match actual exporter ports. For the 7-node example, expose `/metrics` via node exporters or `quorum-acceptor` where available.*

3. **Systemd unit** (`/etc/systemd/system/prometheus.service`):
   ```ini
   [Unit]
   Description=Prometheus
   Wants=network-online.target
   After=network-online.target

   [Service]
   User=prometheus
   Group=prometheus
   Type=simple
   ExecStart=/usr/local/bin/prometheus \
     --config.file=/etc/prometheus/prometheus.yml \
     --storage.tsdb.path=/var/lib/prometheus \
     --web.console.templates=/etc/prometheus/consoles \
     --web.console.libraries=/etc/prometheus/console_libraries
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```

4. **Enable and start**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now prometheus
   sudo systemctl status prometheus
   ```

5. **Verify scrape**: `curl http://localhost:9090/targets` should list the quorum exporters as `UP`. Capture the output to `logs/06_prometheus_targets.json` for records.

## 6.2 Grafana Setup
1. **Install Grafana OSS**:
   ```bash
   sudo apt-get install -y apt-transport-https software-properties-common
   sudo mkdir -p /etc/apt/keyrings
   curl -fsSL https://packages.grafana.com/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/grafana.gpg
   echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
   sudo apt-get update
   sudo apt-get install -y grafana
   sudo systemctl enable --now grafana-server
   sudo systemctl status grafana-server
   ```

2. **Initial login**: Open `http://localhost:3000`, log in with `admin/admin`, then set a new password. Document the new password in a secure location (not in repository).

3. **Add Prometheus data source**:
   - Navigate to *Connections → Data sources → Add data source → Prometheus*.
   - Set URL to `http://localhost:9090`.
   - Save & test. Screenshot the success message for Phase 6 logs (`logs/06_grafana_datasource.png`).

4. **Create dashboard**:
   Suggested panels:
   - **TPS (Votes/sec)**: Query `rate(quorum_voting_tx_total[1m])` or calculate from `web3` metrics. If custom exporter required, consider a lightweight script that exposes vote transaction counts via Prometheus Pushgateway.
   - **Block Time**: `increase(eth_block_time_seconds_sum[5m]) / increase(eth_block_time_seconds_count[5m])` or use `quorum_block_interval_seconds` if available.
   - **Node CPU/Memory**: Import node exporter dashboard (e.g., Grafana ID 1860) when using `node_exporter` containers.
   - **Pending Transactions**: `eth_txpool_pending` gauge to visualize queue buildup during bursts.

   Save the dashboard as `Quorum TPS` and export JSON to `logs/06_grafana_dashboard.json`.

5. **Automate exporter wiring**:
   - For each node container, add Prometheus-compatible metrics—either by enabling built-in node metrics (`--metrics --pprof`) or running `quorumengineering/quorum-node-exporter` alongside nodes.
   - Example Docker Compose snippet for node exporter:
     ```yaml
     node1-exporter:
       image: prom/node-exporter
       command:
         - '--collector.textfile.directory=/var/lib/node_exporter/textfile_collector'
       ports:
         - '9101:9100'
       volumes:
         - /proc:/host/proc:ro
         - /sys:/host/sys:ro
         - /:/rootfs:ro
       restart: always
     ```
   - Update `prometheus.yml` targets accordingly.

## 6.3 Validation & Reporting
- Confirm Prometheus target health (`/targets`) and scrape metrics with timestamps.
- Load the Grafana dashboard and capture a screenshot during a Phase 5 run (`logs/06_grafana_dashboard.png`).
- Document any issues (e.g., exporter ports unavailable, TLS setup) in `logs/issues.md` with timestamp.
- Summarize monitoring results and remaining action items in `reports/phase6-monitoring.md`.

## 6.4 Next Steps
- Consider templating dashboards via Grafana provisioning for reproducibility.
- If multi-host testing is needed, secure Prometheus and Grafana endpoints (auth, firewall rules).
- Integrate alerting (Grafana or Alertmanager) to notify when TPS drops or block time spikes.
