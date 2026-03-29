# Contributing to Transform Factory / 贡献指南

感谢你对 Transform Factory 项目的兴趣！以下是参与贡献的指南。

Thank you for your interest in contributing to Transform Factory!

## 如何贡献 / How to Contribute

### 报告 Bug / Bug Reports

1. 在 Issues 中搜索是否已有相同问题
2. 创建新 Issue，包含：
   - 复现步骤
   - 期望行为 vs 实际行为
   - 你的环境信息（Python 版本、操作系统）
   - 如可能，附上触发问题的 LaTeX 片段

### 功能建议 / Feature Requests

在 Issues 中描述你希望的功能，以及使用场景。

### 提交代码 / Pull Requests

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 编写代码和测试
4. 确保测试通过：`pytest`
5. 提交 PR，描述你的改动

## 开发环境 / Development Setup

```bash
git clone <your-fork-url>
cd Transform_factory/latex2kb
pip install -e ".[dev]"
pytest  # 确认测试通过
```

## 代码规范 / Code Style

- Python 3.10+ 语法（`match`、`type | None`、`from __future__ import annotations`）
- 函数和模块需要 docstring
- 变量命名遵循 PEP 8

## 添加新环境支持 / Adding New Environment Handlers

这是最常见的贡献方式。步骤：

1. 在 `src/latex2kb/environments/` 下创建新模块（如 `listing.py`）
2. 实现 `convert_xxx()` 函数
3. 在 `converter.py` 的 `_convert_environment()` 中注册
4. 在 `parser_core.py` 的 `build_context_db()` 中注册环境的参数规范
5. 添加测试用例

## 测试 / Testing

```bash
# 运行全部测试
pytest

# 运行特定模块测试
pytest tests/test_converter.py

# 在示例项目上运行集成测试
latex2kb ../holders/your_project /tmp/output -v
```

## 项目结构简述 / Architecture Overview

```
pipeline.py          # 编排 8 个阶段
project_scanner.py   # \input/\include 解析
macro_resolver.py    # \newcommand 发现
parser_core.py       # pylatexenc AST
converter.py         # AST → Markdown（核心）
environments/        # 各环境的转换逻辑
crossref.py          # \ref/\label 解析
bibliography.py      # .bib → references.md
figures.py           # 图片复制 + AI 描述
output_writer.py     # 目录结构写入
```

## License / 许可证

贡献的代码将遵循 [MIT License](LICENSE)。
