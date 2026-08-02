# Operations

Plexa ships one Docker Compose production stack with two supported entry paths.

| Goal | Command | Address |
| --- | --- | --- |
| Local production smoke test | `deploy/smoke-local-prod.sh --model <model>` | `http://localhost:8080` |
| Institutional deployment | `deploy/deploy-production.sh <options>` | Your HTTPS domain |

## Local production

The smoke script generates local production configuration, builds the images,
runs migrations, starts the stack, seeds maintained development data, and checks
inference from both the host and application container.

```bash
deploy/smoke-local-prod.sh --model llama3.1
```

Use this path to validate Caddy, container networking, production runtime
checks, PostgreSQL, and real inference without replacing the normal development
environment.

## Institutional production

A domain deployment requires DNS, ports 80 and 443, an ACME contact, an
OpenAI-compatible inference endpoint, an institutional OIDC registration, and
an approved positive log-retention period.

```bash
deploy/deploy-production.sh \
  --domain plexa.example.edu \
  --email admin@example.edu \
  --inference-url https://inference.example.edu/v1 \
  --model llama3.1 \
  --oidc-authority https://login.example.edu \
  --oidc-client-id plexa \
  --oidc-audience plexa-api \
  --admin-user initial-admin-subject \
  --retention-days 365
```

```{warning}
Do not add Uvicorn workers or service replicas to this release. The supported
topology is one Plexa web worker.
```

## Canonical procedures

The [deployment guide](https://github.com/kjgb001/Plexa/blob/main/deploy/README.md)
is the source of truth for DNS, OIDC registration, inference networking,
generated secrets, backups, restoration, upgrades, and troubleshooting.

The [maintenance guide](https://github.com/kjgb001/Plexa/blob/main/maintainence/README.md)
covers dependency updates, local CI, workflow security, and release checks.
