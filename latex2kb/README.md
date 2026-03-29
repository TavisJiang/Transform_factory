# latex2kb — LaTeX to Knowledge Base Converter

> 将 LaTeX 项目转化为结构化 Markdown 知识库的 Python 命令行工具。
>
> A Python CLI tool that converts LaTeX projects into structured Markdown knowledge bases.

## 安装 / Installation

```bash
# 从源码安装（推荐开发阶段）
pip install -e .

# 安装可选的 AI 图片描述依赖
pip install -e ".[ai]"

# 安装开发依赖
pip install -e ".[dev]"
```

## 使用方法 / Usage

### 命令行 / CLI

```bash
# 自动检测 main.tex 并转换
latex2kb /path/to/latex-project /path/to/output

# 指定主文件
latex2kb project/ output/ --main-tex thesis.tex

# 详细输出
latex2kb project/ output/ -v

# 预览模式（不写入文件）
latex2kb project/ output/ --dry-run

# 启用 AI 图片描述
latex2kb project/ output/ --image-descriptions --api-key sk-xxx
```

### 作为 Python 模块

```bash
python -m latex2kb /path/to/project /path/to/output
```

### 在代码中使用

```python
from pathlib import Path
from latex2kb.pipeline import run_pipeline, PipelineConfig

config = PipelineConfig(
    input_dir=Path("path/to/latex-project"),
    output_dir=Path("path/to/output"),
)
run_pipeline(config)
```

## 转换管线 / Pipeline

转换过程分为 8 个阶段，每个阶段对应一个独立模块：

### Stage 1: 项目扫描 (`project_scanner.py`)

- 自动发现包含 `\documentclass` 的主 `.tex` 文件
- 递归解析 `\input{}` / `\include{}` 依赖链
- 识别 `\frontmatter` / `\mainmatter` / `\backmatter` 结构边界
- 提取 `\graphicspath` 和 `\bibliography` 路径
- 正确处理中文文件名和 UTF-8 编码

### Stage 2: 宏解析 (`macro_resolver.py`)

- 从 `.tex`、`.cls`、`.sty` 文件中提取 `\newcommand` / `\renewcommand` / `\DeclareRobustCommand` 定义
- 解析参数个数和展开模板
- 区分 math 模式宏（保留为 LaTeX）和 text 模式宏（展开为 Markdown）
- 合并内置包宏定义（`config/default_macros.yaml`）

### Stage 3: AST 构建 (`parser_core.py`)

- 使用 pylatexenc 2.x 将每个章节解析为 AST（抽象语法树）
- 自定义 `LatexContextDb` 注册 physics、algorithm2e 等包的命令规范
- 正确处理嵌套花括号、数学模式和环境

### Stage 4: Markdown 转换 (`converter.py` + `environments/`)

核心转换模块，逐节点遍历 AST 并分派到环境处理器：

| LaTeX | Markdown |
|-------|----------|
| `\chapter{Title}` | `# Title` |
| `\section{Title}` | `## Title` |
| `$...$` | `$...$`（保留） |
| `\begin{equation}...\end{equation}` | `$$...$$` + anchor |
| `\begin{align}...\end{align}` | `$$\begin{align}...\end{align}$$` |
| `\textbf{X}` | `**X**` |
| `\cite{key}` | `<<CITE:key>>` (占位符) |
| `\ref{fig:X}` | `<<REF:fig:X>>` (占位符) |
| `\begin{theorem}...` | `> **Theorem N.M** ...` |
| `\begin{itemize}` | `- ...` |
| `\includegraphics{X}` | `![caption](figures/X)` |
| 未知命令 | 保留原文 + 日志警告 |

### Stage 5: 交叉引用解析 (`crossref.py`)

- 两遍处理：转换时收集 `\label` → 全局 `LabelRegistry`
- 转换后替换占位符 `<<REF:key>>` → `[Figure 1.1](#fig-name)` 或跨文件链接
- 支持 fig / eq / sec / chap / tab / thm 等类型
- 章节相对编号：`N.M`（N=章节号，M=章内序号）

### Stage 6: 文献处理 (`bibliography.py`)

- 使用 bibtexparser 解析 `.bib` 文件
- `\cite{key}` → `[Author, Year](references.md#key)` 可点击链接
- 生成独立 `references.md`，包含所有被引用条目
- 支持 DOI 链接和多作者格式

### Stage 7: 图片处理 (`figures.py`)

- 将引用的图片文件复制到输出目录
- PDF 图片以链接形式呈现（Markdown 渲染器通常不能内联显示 PDF）
- 可选：调用多模态 AI API 为图片生成文字描述（`--image-descriptions`）

### Stage 8: 输出组装 (`output_writer.py`)

- 创建完整目录结构
- 生成 `index.md`（带元数据和目录链接）
- 生成 `metadata.yaml`（结构化元数据）
- 章节文件命名：`{NN}-{slug}.md`

## 支持的 LaTeX 特性 / Supported Features

### 完全支持

- 文档结构：`\chapter`、`\section`、`\subsection`、`\subsubsection`、`\paragraph`
- 数学环境：`equation`、`align`、`multline`、`gather`、`split`、`cases`、`pmatrix`、`bmatrix`
- 行内数学：`$...$`
- 展示数学：`\[...\]`、`$$...$$`
- 文本格式：`\textbf`、`\textit`、`\emph`、`\texttt`、`\underline`
- 列表：`itemize`、`enumerate`、`description`
- 图片：`\includegraphics`、`figure` 环境、`\caption`、`\bicaption`
- 表格：`tabular`、`booktabs`（`\toprule`/`\midrule`/`\bottomrule`）、`threeparttable`、`longtable`
- 定理：`theorem`、`lemma`、`proposition`、`corollary`、`definition`、`fact`、`proof`
- 算法：`algorithm2e`（`\KwIn`、`\KwOut`、`\ForAll`、`\If`）
- 引用：`\cite`、`\citep`、`\citet`（natbib）
- 交叉引用：`\ref`、`\eqref`、`\label`
- 自定义命令：`\newcommand`、`\renewcommand`、`\DeclareRobustCommand`
- 脚注：`\footnote`
- 引用环境：`quote`、`quotation`、`mdframed`、`framed`
- Physics 包：`\ket`、`\bra`、`\braket`、`\ketbra`、`\proj`

### 部分支持

- 复杂 algorithm2e 块（深度嵌套可能格式粗糙）
- `\multicolumn` 表格（降级为文本提取）
- TikZ 图（保留为文本描述）

### 不支持（保留原文）

- 自定义绘图命令
- 复杂 `\def` / `\let` 条件宏

## 依赖 / Dependencies

**必需：**
- `pylatexenc >= 2.10` — LaTeX AST 解析（纯 Python，无需二进制依赖）
- `bibtexparser >= 1.4, < 2` — BibTeX 文件解析
- `pyyaml >= 6.0` — YAML 输出
- `click >= 8.0` — CLI 框架

**可选（AI 功能）：**
- `httpx >= 0.25` — HTTP 客户端
- `pillow >= 10.0` — 图片处理

**无需安装 LaTeX 发行版或 pandoc。**

## 配置 / Configuration

### 内置宏定义

`config/default_macros.yaml` 包含常用包的宏展开规则（physics、amsmath、siunitx）。可自定义扩展。

### 添加新环境支持

在 `src/latex2kb/environments/` 下添加新模块，实现转换函数后在 `converter.py` 的 `_convert_environment()` 中注册即可。

## 测试 / Testing

```bash
cd latex2kb
pip install -e ".[dev]"
pytest
pytest -v  # 详细输出
```

## 许可证 / License

MIT — 详见 [LICENSE](../LICENSE)
