# Changelog / 变更日志

## [0.1.0] - 2026-03-29

### Added / 新增

- **latex2kb** 核心转换工具，支持将任意 LaTeX 项目转为结构化 Markdown 知识库
- 8 阶段转换管线：项目扫描 → 宏解析 → AST 构建 → Markdown 转换 → 交叉引用解析 → 文献处理 → 图片处理 → 输出组装
- 环境转换器：math、theorem、algorithm、table、figure、list
- 交叉引用解析：`\ref` / `\eqref` → 跨文件 Markdown 链接
- 文献处理：BibTeX → `references.md` + 内联 `[Author, Year]` 链接
- 图片处理：自动复制 + 可选 AI 图片描述
- 元数据提取：支持常见学术论文模板和标准 LaTeX 元数据
- CLI 接口：`latex2kb <input> <output>` + 多个选项

### Known Limitations / 已知限制

- 复杂 algorithm2e 嵌套块格式可能粗糙
- `\multicolumn` 表格降级为文本提取
- 需要 Python >= 3.10
