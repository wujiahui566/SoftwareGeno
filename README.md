# Geno

Geno 是一个确定性的软件基因提取与构建平台。当前仓库包含 Python 基础框架、确定性标识符、
MongoDB 持久化以及 Git 仓库获取功能。C/C++ 解析、规范化、特征提取和演化分析功能尚未实现。

## 环境要求

- Python 3.12
- Git 2.29 或更高版本
- Docker 和 Docker Compose
- GNU Make（可选；也可以直接运行底层命令）

## 本地安装

创建隔离环境，并安装 Geno 及其开发工具：

```shell
make install
```

等效命令如下：

```shell
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --editable '.[dev]'
```

试用初始命令行界面：

```shell
.venv/bin/geno --help
.venv/bin/geno version
.venv/bin/geno config show
```

MongoDB 可用后，可以注册并查看本地或网络 Git 仓库：

```shell
.venv/bin/geno repo add /absolute/path/to/local-repository
.venv/bin/geno repo add https://github.com/owner/repository.git
.venv/bin/geno repo list
.venv/bin/geno repo show repo_<sha256>
.venv/bin/geno repo update repo_<sha256>
.venv/bin/geno repo refs repo_<sha256>
```

Geno 支持通过 HTTPS、SSH、原生 Git 协议和 SCP 风格的 SSH 地址访问 GitHub、GitLab、Gitee
及通用 Git 服务器。身份验证应使用凭据助手、环境作用域的凭据助手或 SSH 代理。Geno 在保存
仓库地址或镜像远程地址前会移除 URL 中的凭据，并在诊断信息中隐藏凭据。

启动 MongoDB 服务后，可以初始化并检查其持久化状态：

```shell
.venv/bin/geno database init
.venv/bin/geno database check
.venv/bin/geno database stats
```

## 配置

Geno 按以下顺序加载设置，优先级从高到低：

1. 全局命令行选项；
2. `GENO_*` 环境变量；
3. TOML 配置文件；
4. 内置默认值。

如果工作目录中存在 `configs/default.toml`，Geno 会自动加载该文件。可以使用
`--config PATH` 或 `GENO_CONFIG_FILE` 选择其他文件。命令行选项是全局选项，因此应放在
子命令之前：

```shell
.venv/bin/geno --config configs/default.toml --maximum-worker-count 8 config show
```

如需为 Docker Compose 提供变量插值，请将 `.env.example` 复制为 `.env`，或在 shell 中导出
相应变量。Geno 本身不会隐式加载 `.env`，以避免引入额外且含义不明确的配置来源。

支持的环境变量如下：

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

`geno config show` 会以 JSON 格式显示经过验证的最终配置，并隐藏 MongoDB URI 中嵌入的凭据。

## MongoDB

验证并启动本地 MongoDB 服务：

```shell
make compose-validate
make mongo-up
```

MongoDB 默认监听 `localhost:27017`，并将数据存储在具名 Docker 数据卷中。可以使用以下命令
停止服务而不删除数据：

```shell
make mongo-down
```

运行由 Docker 提供 MongoDB 支持的集成测试：

```shell
make integration
```

集成测试目标会启动 MongoDB，等待其健康检查通过，然后运行标记为 `integration` 的测试。
单元测试使用内存中的模拟仓库实现，不需要 Docker。

## 开发检查

运行全部验收检查：

```shell
make check
```

也可以单独运行以下命令：

```shell
make format
make format-check
make lint
make typecheck
make test
```

修改代码前，请阅读 `docs/` 目录下的文档。特别需要注意的是，软件基因的身份
语义已明确推迟到后续的 ADR 中定义，不得在基础代码中隐式引入相关语义。
