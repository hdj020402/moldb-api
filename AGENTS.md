# AGENTS.md - moldb-api 项目上下文指南

## 项目概述

moldb-api 是一个高性能分子结构数据存储和查询服务，支持多构象存储和查询。项目支持两种存储后端：

- **LMDB** (Lightning Memory-Mapped Database): 优化读密集型工作负载，适合大规模数据
- **SQLite**: 部署简单，适合大多数使用场景

### 关键特性

- **构象感知存储**: 每个分子可存储多个构象
- **Fixed-H InChI 支持**: 区分互变异构体
- **批量操作**: 高效的数据导入和查询

### 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.12 |
| Web 框架 | FastAPI |
| ASGI 服务器 | uvicorn |
| 高性能存储 | LMDB |
| 关系型存储 | SQLite |
| 数据处理 | Pandas, NumPy |
| 测试 | pytest |

## 项目结构

```
moldb-api/
├── pyproject.toml          # 包配置
├── config.json             # 全局配置文件
├── main.py                 # 遗留入口点
├── README.md
├── API_DOCUMENTATION.md
└── src/moldb/
    ├── __init__.py
    ├── cli.py              # CLI 入口点
    ├── core/               # 核心存储实现
    │   ├── lmdb.py         # LMDBMoleculeStore 类
    │   └── sqlite.py       # SQLiteMoleculeStore 类
    ├── api/                # FastAPI 服务
    │   ├── lmdb.py         # LMDB 后端 API 服务
    │   └── sqlite.py       # SQLite 后端 API 服务
    ├── builder/            # 数据库构建工具
    │   ├── lmdb.py         # 从 XYZ 文件构建 LMDB 数据库
    │   └── sqlite.py       # 从 XYZ 文件构建 SQLite 数据库
    ├── config/             # 配置管理
    │   └── config.py       # Config 类
    └── util/               # 工具函数
        └── query_molecule.py
```

## 核心概念

### Fixed-H InChI

**数据库必须使用非标准（Fixed-H）InChI 作为键**。

**格式规则**：
- `InChI=1S/...` - 标准 InChI（**不能**有 `/f/h` 层）
- `InChI=1/...` - 非标准 InChI（如果有 ambiguous 氢，会有 `/f/h` 层）

标准 InChI 在处理互变异构体时会将氢原子视为等价，例如 `(H2,4,5)` 表示 2 个氢原子在 4、5 号位置等价。这导致实际结构不同的互变异构体被归为同一 InChI。

非标准 InChI 可通过 Fixed-H 层（`/f/h`）指定精确的氢原子位置：
- 标准: `InChI=1S/C3H7NO/...` - 歧义，无法区分互变异构体
- 非标准（无歧义氢）: `InChI=1/H2O/h1H2`
- 非标准 Fixed-H（歧义氢被固定）: `InChI=1/C3H7NO/.../f/h4H2` - 精确

### 存储结构

每个分子的构象以复合键形式存储：

```
Key: {fixed_h_inchi}::meta    → {"count": N}
Key: {fixed_h_inchi}::conf_0  → "xyz_string_0"
...
Key: {fixed_h_inchi}::conf_{N-1}  → "xyz_string_{N-1}"
```

这种设计的优点：
- 避免单个 value 过大（1000 构象时可能 100KB-10MB）
- 支持高效的范围查询
- 内存占用可控

## 核心模块说明

### 1. 存储层 (`core/`)

**LMDBMoleculeStore** (`core/lmdb.py`):
- 高性能键值存储
- 支持批量写入 `put_many_conformers()`
- 默认 map_size: 30GB

主要方法:
- `get_conformers(inchi) -> dict` - 获取分子所有构象
- `put_conformers(inchi, conformers: list[str])` - 写入构象列表
- `put_many_conformers(items)` - 批量写入
- `delete(inchi)` - 删除分子及所有构象

**SQLiteMoleculeStore** (`core/sqlite.py`):
- 使用 WAL 模式提升并发性能
- 线程安全，使用 thread-local 连接
- 主要方法与 LMDB 一致

### 2. API 层 (`api/`)

两个后端共享相同的 API 端点设计：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 健康检查 |
| `/molecule/{inchi}` | GET | 通过 Fixed-H InChI 查询单个分子 |
| `/molecules/batch` | POST | 批量查询多个分子 |

**返回格式**:
```json
{
  "inchi": "InChI=...",
  "count": 3,
  "conformers": ["xyz_1", "xyz_2", "xyz_3"]
}
```

### 3. 构建工具 (`builder/`)

从 XYZ 文件批量构建数据库：

**CSV 格式要求**:
```csv
xyz_path,fixed_h_inchi
/path/to/mol1_conf1.xyz,InChI=.../f/h4H2
/path/to/mol1_conf2.xyz,InChI=.../f/h4H2
```

## 构建和运行命令

### 环境准备

```bash
# 创建虚拟环境
conda create -n moldb-api python=3.12
conda activate moldb-api

# 安装
pip install -e .
```

### 构建数据库

```bash
# LMDB 后端
moldb builder lmdb --mapping conformers.csv --output molecules.lmdb

# SQLite 后端
moldb builder sqlite --mapping conformers.csv --output molecules.db
```

### 启动 API 服务

```bash
# LMDB 服务 (默认端口 8000)
moldb api lmdb

# SQLite 服务 (默认端口 8001)
moldb api sqlite
```

### 直接调用 API

```python
from moldb.core.lmdb import LMDBMoleculeStore

store = LMDBMoleculeStore("molecules.lmdb")

# 写入
store.put_conformers("InChI=.../f/h", ["xyz_1", "xyz_2"])

# 查询
data = store.get_conformers("InChI=.../f/h")
print(f"Count: {data['count']}")
```

## 配置管理

配置优先级（从高到低）：
1. 命令行参数
2. 环境变量
3. `config.json` 文件
4. 默认值

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `MOLECULES_LMDB_PATH` | LMDB 数据库路径 |
| `MOLECULES_DB_PATH` | SQLite 数据库路径 |
| `MOLECULES_API_HOST` | API 服务主机 |
| `MOLECULES_LMDB_API_PORT` | LMDB API 端口 |
| `MOLECULES_SQLITE_API_PORT` | SQLite API 端口 |

## 开发规范

### 代码风格

- 使用 Python 3.12 类型注解
- 类和函数使用 Google 风格文档字符串

### 架构约定

1. **分层架构**: core (存储) → api (服务) → cli (入口)
2. **配置集中管理**: 通过 `config.Config` 类统一管理配置
3. **API 只读**: API 服务设计为只读，不提供写入端点
4. **批量操作优先**: 大数据量操作使用批量处理方法

### 错误处理

- API 层捕获异常并返回适当的 HTTP 状态码
- 批量查询时，未找到的分子返回 `null` 而非报错
- Builder 层记录错误但继续处理其他文件

## 数据格式

### 输入文件要求

**XYZ 文件**:
- 内容: 分子坐标数据（文本格式）

**Conformer 映射 CSV**:
- 必需列: `xyz_path`, `fixed_h_inchi`
- 用于将 XYZ 文件映射到 Fixed-H InChI 标识符

### API 响应格式

```json
// 单个分子查询
{
  "inchi": "InChI=.../f/h",
  "count": 3,
  "conformers": ["xyz_1", "xyz_2", "xyz_3"]
}

// 批量查询
{
  "InChI=.../f/h": {"inchi": "...", "count": 3, "conformers": [...]},
  "InChI=.../f/h2": null  // 未找到
}
```

## 性能优化建议

- LMDB: 使用 `sync=False` 和 `writemap=True` 加速批量写入
- SQLite: 已启用 WAL 模式和 `synchronous=NORMAL`
- 批量查询: 优先使用 `get_many_conformers()` 而非多次调用 `get_conformers()`
- 批量写入: 使用 `put_many_conformers()` 而非多次调用 `put_conformers()`