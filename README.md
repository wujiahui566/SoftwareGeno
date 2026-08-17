# Geno

Geno is a deterministic software-gene extraction and construction platform. The current
repository contains the Python foundation, deterministic identifiers, MongoDB persistence, and Git
repository acquisition. C/C++ parsing, normalization, feature extraction, and evolution analysis
are not implemented yet.

## Requirements

- Python 3.12
- Git 2.29 or newer
- Docker with Docker Compose
- GNU Make (optional; the underlying commands can be run directly)

## Local setup

Create an isolated environment and install Geno with its development tools:

```shell
make install
```

Equivalent commands:

```shell
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --editable '.[dev]'
```

Exercise the initial CLI:

```shell
.venv/bin/geno --help
.venv/bin/geno version
.venv/bin/geno config show
```

Register and inspect a local or network Git repository after MongoDB is available:

```shell
.venv/bin/geno repo add /absolute/path/to/local-repository
.venv/bin/geno repo add https://github.com/owner/repository.git
.venv/bin/geno repo list
.venv/bin/geno repo show repo_<sha256>
.venv/bin/geno repo update repo_<sha256>
.venv/bin/geno repo refs repo_<sha256>
```

GitHub, GitLab, Gitee, and generic Git servers are supported through HTTPS, SSH, native Git, and
SCP-style SSH locators. Authentication should use a credential helper, environment-scoped helper,
or SSH agent. Geno strips URL credentials before persisting a locator or mirror remote and redacts
credentials from diagnostics.

Initialize and inspect MongoDB persistence after starting the service:

```shell
.venv/bin/geno database init
.venv/bin/geno database check
.venv/bin/geno database stats
```

## Configuration

Geno loads settings in this order, from highest to lowest precedence:

1. global CLI options;
2. `GENO_*` environment variables;
3. a TOML configuration file;
4. built-in defaults.

When present, `configs/default.toml` is loaded automatically from the working directory. Select a
different file with `--config PATH` or `GENO_CONFIG_FILE`. CLI options are global and therefore
appear before the subcommand:

```shell
.venv/bin/geno --config configs/default.toml --maximum-worker-count 8 config show
```

Copy `.env.example` to `.env` for Docker Compose interpolation or export the variables in your
shell. Geno itself does not implicitly load `.env`; this avoids an additional, ambiguous
configuration source.

Supported environment variables are:

- `GENO_MONGODB_URI`
- `GENO_MONGODB_DATABASE`
- `GENO_WORKSPACE_DIRECTORY`
- `GENO_REPOSITORY_CACHE_DIRECTORY`
- `GENO_TEMPORARY_DIRECTORY`
- `GENO_MAXIMUM_WORKER_COUNT`
- `GENO_GIT_COMMAND_TIMEOUT_SECONDS`
- `GENO_LOG_LEVEL`
- `GENO_FAIL_FAST`
- `GENO_CONFIG_FILE`

`geno config show` renders the effective validated configuration as JSON and redacts credentials
embedded in the MongoDB URI.

## MongoDB

Validate and start the local MongoDB service:

```shell
make compose-validate
make mongo-up
```

MongoDB listens on `localhost:27017` by default and stores data in a named Docker volume. Stop it
without deleting its data using:

```shell
make mongo-down
```

Run the Docker-backed MongoDB integration tests with:

```shell
make integration
```

The integration target starts MongoDB, waits for its health check, and runs tests marked
`integration`. Unit tests use in-memory fake repository implementations and do not require Docker.

## Development checks

Run every acceptance check:

```shell
make check
```

Individual commands are also available:

```shell
make format
make format-check
make lint
make typecheck
make test
```

Read `CODEX.md` and the documents under `docs/` before making changes. In particular, software-gene
identity semantics are intentionally deferred to a later ADR and must not be introduced implicitly
in foundation code.
