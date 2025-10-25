# GoQuorum Private Network Experiment Plan

## Objective
Establish a repeatable, end-to-end environment on Ubuntu 20.04+ that launches GoQuorum private networks (Clique, IBFT, Raft), deploys a voting smart contract, and benchmarks transaction throughput with supporting observability.

## Phase 1 – Environment Preparation
- Update the system and install Docker, Docker Compose, Git, Node.js, npm, Python 3, and pip.
- Enable and verify Docker services.
- Install Python packages: `web3`, `requests`, `matplotlib`, `pandas`.
- Confirm toolchain versions (Docker, Docker Compose, Node.js, Python).

## Phase 2 – Retrieve GoQuorum Examples
- Clone `https://github.com/ConsenSys/quorum-examples.git`.
- Review docker-compose files for Clique, IBFT, and Raft configurations.

## Phase 3 – Network Deployment Workflows
- **Clique**: `docker-compose -f docker-compose-clique.yml up -d`; validate 4 nodes (`quorum-node1`–`4`).
- **IBFT**: `docker-compose down -v`, then `docker-compose -f docker-compose-ibft.yml up -d`; validate 4 nodes running IBFT.
- **Raft**: `docker-compose down -v`, then `docker-compose -f docker-compose-raft.yml up -d`; validate 7 Raft nodes.
- Inspect node logs (`docker logs -f quorum-nodeX`) to ensure consensus health.

## Phase 4 – Smart Contract Deployment
- Author `VotingWithNFT.sol` that issues an ERC-721 vote certificate via OpenZeppelin when a ballot is cast, including a `hasVoted` guard to prevent duplicates.
- Initialize Node.js project; install `web3`, `solc`, and `@openzeppelin/contracts` (or add the dependency to the existing package manifest).
- Implement `deploy.js` to compile the contract with Solidity imports resolved and deploy it to the active network via RPC (`http://localhost:8545`).
- Run `node deploy.js` and record the deployed contract address, ABI, and NFT collection metadata (name/symbol) for later validation.

## Phase 5 – Performance Benchmarking
- Build `benchmark.py` using `web3.py` for transaction submission, TPS calculation, and NFT mint receipt tracking.
- Accept contract address input and embed ABI from deployment output.
- Execute benchmark runs (default 100 transactions) per consensus setup, capturing TPS, elapsed time, NFT mint counts, and per-transaction gas usage.

## Phase 6 – Monitoring & Visualization
- Install Prometheus and configure `prometheus.yml` to scrape GoQuorum node metrics.
- Install Grafana, start the service, and connect to Prometheus as a data source.
- Create dashboards tracking TPS, block time, CPU, and other relevant metrics.

## Phase 7 – Experiment Execution
- Run benchmarks across Clique, IBFT, and Raft with consistent parameters (transactions, node counts).
- Capture TPS, latency, and resource metrics for each run.
- Use Python/Matplotlib to generate comparative charts (e.g., bar chart of TPS per consensus algorithm).

## Phase 8 – Results Synthesis
- Summarize metrics in tabular form (TPS, block time, finality characteristics, CPU usage).
- Interpret suitability of each consensus type (e.g., IBFT for trust, Raft for performance, Clique for tests).
- Document reproducibility notes and potential automation enhancements (e.g., Bash script for orchestration).
