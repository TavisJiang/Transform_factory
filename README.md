# Transform Factory

**将 LaTeX 学术项目转化为 AI 优化的结构化 Markdown 知识库。**

*Transform LaTeX academic projects into AI-optimized structured Markdown knowledge bases.*

---

## 为什么需要这个工具？ / Why?

直接将 PDF 喂给 AI 会导致：
- 公式被当作图片，无法参与推理
- 章节结构丢失，AI 无法定位上下文
- 交叉引用（`\ref`、`\label`）断裂
- 图表与正文脱节
- 参考文献无法关联

**Transform Factory** 将 LaTeX 源码转为结构化 Markdown，让 AI 真正 *理解* 你的论文——比"喂 PDF"高一个层级。

Feeding PDFs to AI loses structure: formulas become images, cross-references break, figures disconnect from text. **Transform Factory** converts LaTeX source into structured Markdown so AI can truly *understand* your papers — one level above raw PDF.

## 核心工具：latex2kb / Core Tool

`latex2kb` 是一个 Python CLI 工具，可将任意 LaTeX 项目文件夹自动转化为结构化知识库。输出自动生成在 `<输出目录>/<项目名>_2kb/` 下：

```
output/my_thesis_2kb/
├── index.md              # 知识库入口：标题、元数据、目录链接
├── chapters/
│   ├── 01-introduction.md
│   ├── 02-methods.md
│   └── ...
├── figures/              # 复制的图片文件
├── references.md         # 完整参考文献（仅收录被引用条目）
└── metadata.yaml         # 结构化元数据
```

### 特性 / Features

| 特性 | 说明 |
|------|------|
| **数学公式保留** | `$...$` 和 `$$...$$` 中的 LaTeX 语法原样保留，AI 原生理解 |
| **交叉引用解析** | `\ref` / `\eqref` → Markdown 链接，支持跨章节跳转 |
| **文献内联展开** | `\cite{key}` → `[Author, Year](references.md#key)` 可点击链接 |
| **图片处理** | 自动复制 + 保留 caption 和 label；可选 AI 生成图片描述 |
| **自定义宏展开** | 自动发现 `\newcommand`，math 宏保留、text 宏展开为 Markdown |
| **定理环境** | theorem / lemma / proof → 带编号的 blockquote 格式 |
| **算法伪代码** | algorithm2e → 可读的 Markdown 伪代码 |
| **表格转换** | booktabs tabular → Markdown 管道表格 |
| **通用性** | 适用于任意 LaTeX 项目，不限于特定模板 |

---

## 使用步骤 / Step-by-Step Usage

### Step 1: 安装 / Install

```bash
cd latex2kb
pip install -e .
```

### Step 2: 转换 / Convert

```bash
latex2kb <LaTeX项目文件夹> <输出目录>
```

输出会自动生成在 `<输出目录>/<项目文件夹名>_2kb/` 下。例如：

```bash
latex2kb path/to/my_thesis output/
#  → output/my_thesis_2kb/
#       ├── index.md
#       ├── chapters/
#       ├── figures/
#       ├── references.md
#       └── metadata.yaml
```

对任意 LaTeX 项目同理：

```bash
latex2kb /path/to/my_thesis output/
#  → output/my_thesis_2kb/

latex2kb /path/to/ICML_paper output/
#  → output/ICML_paper_2kb/
```

### Step 3: 查看结果 / View Results

```bash
# 先看 index.md（知识库入口）
cat output/my_thesis_2kb/index.md

# 或者把整个文件夹丢给 AI
# Just feed the entire folder to AI
```

### Step 4 (可选): AI 图片描述 / Optional: AI Image Descriptions

如果希望 AI 为图片生成文字描述：

```bash
# 安装 AI 依赖
pip install -e ".[ai]"

# 方式一：环境变量（推荐，安全）
export ANTHROPIC_API_KEY=your-api-key
latex2kb project/ output/ --image-descriptions

# 方式二：用 OpenAI
export OPENAI_API_KEY=sk-你的key
latex2kb project/ output/ --image-descriptions --provider openai

# 方式三：命令行直接传 key
latex2kb project/ output/ --image-descriptions --api-key your-api-key

# 方式四：配置文件（适合反复使用，详见下方）
latex2kb project/ output/ --config latex2kb.yaml --image-descriptions
```

---

## CLI 选项 / CLI Options

```
latex2kb <input_dir> <output_dir> [OPTIONS]

Options:
  --config FILE            YAML 配置文件（见 latex2kb.example.yaml）
  --main-tex FILE          指定主 .tex 文件（默认自动检测）
  --image-descriptions     启用 AI 图片描述
  --provider [anthropic|openai|openai-compatible]
                           AI 提供商（默认 anthropic）
  --api-key KEY            API Key（也可通过环境变量设置）
  --no-copy-images         不复制图片，仅保留引用路径
  --encoding ENCODING      源文件编码（默认 utf-8）
  -v, --verbose            详细日志输出
  --dry-run                预览模式，不写入文件
  --version                显示版本号
```

## 配置文件 / Config File

适合需要反复使用 AI 功能的场景。复制示例配置并按需修改：

```bash
cp latex2kb/latex2kb.example.yaml latex2kb.yaml
# 编辑 latex2kb.yaml，填写 provider、model 等
```

配置文件可管理：AI 提供商、模型选择、提示词、超时等参数。API Key **推荐通过环境变量设置**（不要写进配置文件提交到 git）：

```bash
# Anthropic
export ANTHROPIC_API_KEY=your-anthropic-key

# OpenAI
export OPENAI_API_KEY=your-openai-key

# 通用（覆盖以上所有）
export LATEX2KB_API_KEY=your-openai-key
```

配置优先级：**命令行参数 > 环境变量 > 配置文件 > 默认值**

工具会自动检测项目目录或当前目录下的 `latex2kb.yaml`，也可用 `--config` 显式指定。

详见 [`latex2kb.example.yaml`](latex2kb/latex2kb.example.yaml)。

---

## 转换示例 / Conversion Example

### LaTeX 输入

```latex
\section{Gradient Descent}
\label{sec:gradient}

The core idea of gradient descent~\cite{Cauchy1847} is to iteratively
update parameters in the direction of steepest descent, as illustrated
in Figure~\ref{fig:loss_landscape}.

Given a loss function $\mathcal{L}(\theta)$, the update rule is:

\begin{equation}
  \theta_{t+1} = \theta_t - \eta \nabla_\theta \mathcal{L}(\theta_t)
  \label{eq:sgd}
\end{equation}

where $\eta$ is the learning rate. See Table~\ref{tab:hyperparams}
for recommended values.
```

### Markdown 输出

```markdown
## Gradient Descent

<a id="sec-gradient"></a>

The core idea of gradient descent [Cauchy, 1847](references.md#Cauchy1847)
is to iteratively update parameters in the direction of steepest descent,
as illustrated in [Figure 2.1](#fig-loss_landscape).

Given a loss function $\mathcal{L}(\theta)$, the update rule is:

<a id="eq-sgd"></a>

$$
\theta_{t+1} = \theta_t - \eta \nabla_\theta \mathcal{L}(\theta_t)
$$

where $\eta$ is the learning rate. See [Table 2.1](#tab-hyperparams)
for recommended values.
```

---

## 技术架构 / Architecture

`latex2kb` 采用 8 阶段流水线：

```
[1] 项目扫描 → [2] 宏解析 → [3] AST 构建 → [4] Markdown 转换
                                                      ↓
[8] 写入输出 ← [7] 图片处理 ← [6] 文献处理 ← [5] 交叉引用解析
```

- **解析器**: pylatexenc 2.x（纯 Python，无需安装 pandoc）
- **宏处理**: 自动从 `.tex` / `.cls` / `.sty` 中发现 `\newcommand` 定义
- **交叉引用**: 两遍处理——先收集 `\label`，再解析 `\ref` 为 Markdown 链接
- **文献**: bibtexparser 解析 `.bib`，生成独立 `references.md`

详细技术文档见 [latex2kb/README.md](latex2kb/README.md)。

## 项目结构 / Project Structure

```
Transform_factory/
├── latex2kb/                  # 核心 Python 包
│   ├── src/latex2kb/          # 源码（14 个模块）
│   ├── config/                # 内置宏定义
│   ├── tests/                 # 测试套件（55 个测试）
│   ├── latex2kb.example.yaml  # 配置文件模板
│   └── pyproject.toml
├── holders/                   # 放置你的 LaTeX 项目（已 gitignore）
├── CONTRIBUTING.md            # 贡献指南
├── CHANGELOG.md               # 变更日志
├── LICENSE                    # MIT
└── README.md                  # ← 你正在读的文件
```

## 系统要求 / Requirements

- Python >= 3.10
- 无需安装 LaTeX 发行版或 pandoc

## 开发 / Development

```bash
git clone <repo-url>
cd Transform_factory/latex2kb
pip install -e ".[dev]"

# 运行测试（55 个）
pytest

# 在示例项目上测试
latex2kb ../holders/your_project ../output -v
```

## 路线图 / Roadmap

- [x] Markdown 输出
- [x] 多 AI 提供商支持（Anthropic / OpenAI / OpenAI-compatible）
- [x] YAML 配置文件
- [ ] Typst 输出格式
- [ ] 更多 LaTeX 模板的测试覆盖
- [ ] GitHub Actions CI/CD
- [ ] PyPI 发布
- [ ] 批量处理多项目
- [ ] Web UI

## 许可证 / License

[MIT License](LICENSE)
