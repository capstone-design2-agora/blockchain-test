# Quorum Dev Quickstart

Please go to our [official docs](https://consensys.net/docs/goquorum/en/latest/tutorials/quorum-dev-quickstart/)


## Moving to production

When you are ready to move to production, please create new keys for your nodes using the
[Quorum Genesis Tool](https://www.npmjs.com/package/quorum-genesis-tool) and read through the the
[GoQuorum documentation](https://consensys.net/docs/goquorum/en/latest/deploy/install/)

## Running individual consensus profiles

Each consensus now has its own compose file under the repo root:

- `docker-compose-ibft.yml` – 7-validator IBFT (Istanbul) network
- `docker-compose-qbft.yml` – 7-validator QBFT network
- `docker-compose-raft.yml` – 7-validator Raft network

Launch the one you need with `docker compose -f <file> up -d`, for example:

```bash
docker compose -f docker-compose-ibft.yml up -d
```
