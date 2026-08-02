# Plexa documentation

Plexa is a lesson-centered AI platform for higher education. It gives
instructors control over learning goals, model behavior, reflections, and
completion while giving students a focused conversational workspace.

::::{grid} 1 1 3 3
:gutter: 2

:::{grid-item-card} Run Plexa
:link: operations
:link-type: doc

Deploy locally for a production smoke test or operate a domain-backed
institutional installation.
:::

:::{grid-item-card} Develop the server
:link: server/index
:link-type: doc

Understand the FastAPI runtime, session state machine, storage boundaries,
authentication, and inference routing.
:::

:::{grid-item-card} Develop the portal
:link: client/index
:link-type: doc

Work with the React student and instructor surfaces, API clients, auth, and
lesson authoring contracts.
:::
::::

## Start here

- [Getting started](getting-started.md) covers the shortest path to a working
  development environment.
- [Architecture](architecture.md) explains how requests, data, and inference
  move through the system.
- [HTTP API](http-api.md) documents authentication, errors, streaming, and the
  generated OpenAPI schema.

```{admonition} Production boundary
:class: important

The supported production topology currently uses one Plexa web worker. Do not
add workers or replicas until active-session coordination, stream ownership,
rate limits, and cleanup leases move to shared atomic infrastructure.
```

```{toctree}
:hidden:
:maxdepth: 2

getting-started
architecture
operations
http-api
server/index
client/index
```
