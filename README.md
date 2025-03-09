# Git提交助手

这是一个基于AI的Git提交助手工具，可以自动分析您的代码变更并生成符合规范的提交消息。

## 功能特点

- 自动分析暂存区或最近一次提交的代码变更
- 使用AI（通过OpenAI API）生成符合规范的提交消息
- 支持自动添加所有变更到暂存区
- 提供文件变更统计信息（新增、修改、删除的文件）
- 支持自动提交或确认后提交
- 生成的提交消息遵循约定式提交规范（Conventional Commits）

## 安装要求

- Python 3.6+
- Git

### 依赖库

```
requests
loguru
python-dotenv
```

## 安装步骤

1. 克隆或下载此仓库
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 创建`.env`文件并设置OpenAI API密钥：

```
OPENAI_API_KEY=your_api_key_here
```

## 使用方法

### 基本用法

```bash
python git-diff.py
```

这将分析暂存区的变更，并生成提交消息建议，但不会自动提交。

### 分析最近一次提交

```bash
python git-diff.py --last-commit
```

分析最近一次提交的变更，而不是暂存区。

### 确认后提交

```bash
python git-diff.py --confirm
```

分析暂存区变更，生成提交消息，并在确认后提交。

### 自动提交

```bash
python git-diff.py --auto-commit
```

分析暂存区变更，生成提交消息，并自动提交（无需确认）。

## 提交消息格式

生成的提交消息遵循以下格式：

```
类型: 简短描述

- 详细变更1
- 详细变更2
- 详细变更3
```

支持的类型前缀包括：
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档变更
- `style`: 代码格式变更，不影响代码功能
- `refactor`: 代码重构，不新增功能或修复bug
- `perf`: 性能优化
- `test`: 测试相关
- `build`: 构建系统或外部依赖变更
- `ci`: CI配置文件和脚本变更
- `chore`: 其他变更

## 注意事项

- 确保您的工作目录是一个有效的Git仓库
- 需要有效的OpenAI API密钥才能生成提交消息
- 在Windows系统上，确保设置了正确的编码以支持中文输出

## 许可证

[MIT](LICENSE) 