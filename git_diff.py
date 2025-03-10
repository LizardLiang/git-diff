#!/usr/bin/env python
import subprocess
import sys
import os
import json
import requests
from loguru import logger
import dotenv
import shlex
import locale
import re

dotenv.load_dotenv()

# 设置环境变量，确保Git输出使用UTF-8编码
os.environ['PYTHONIOENCODING'] = 'utf-8'

def get_last_commit_diff():
    """获取最近一次提交的差异"""
    try:
        # 获取最近一次提交的hash
        last_commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], encoding='utf-8').strip()
        # 获取上一次提交的hash
        previous_commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD~1'], encoding='utf-8').strip()
        # 获取两次提交之间的差异
        diff = subprocess.check_output(['git', 'diff', previous_commit_hash, last_commit_hash], encoding='utf-8')
        return diff
    except subprocess.CalledProcessError as e:
        logger.error(f"获取最近提交差异时出错: {e}")
        return None

def get_staged_diff():
    """获取暂存区的差异"""
    try:
        diff = subprocess.check_output(['git', 'diff', '--staged'], encoding='utf-8')
        return diff
    except subprocess.CalledProcessError as e:
        logger.error(f"获取暂存区差异时出错: {e}")
        return None

def add_all_changes():
    """执行git add .命令，将所有更改添加到暂存区"""
    try:
        logger.info("执行 git add . 命令...")
        subprocess.run(['git', 'add', '.'], check=True)
        logger.info("所有更改已添加到暂存区")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"执行 git add . 命令时出错: {e}")
        return False

def get_file_changes():
    """获取文件变更状态"""
    try:
        status_output = subprocess.check_output(['git', 'status', '--porcelain'], encoding='utf-8').splitlines()
        
        # 分类文件变更
        new_files = []
        modified_files = []
        deleted_files = []

        for line in status_output:
            if line.startswith('A ') or line.startswith('?? '):  # 新增的文件
                new_files.append(line[3:])
            elif line.startswith('M '):  # 修改的文件
                modified_files.append(line[3:])
            elif line.startswith('D '):  # 删除的文件
                deleted_files.append(line[3:])
        
        return {
            'new_files': new_files,
            'modified_files': modified_files,
            'deleted_files': deleted_files
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"获取文件变更状态时出错: {e}")
        return None


def request_open_ai(diff_content, file_changes, model):
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.warning('未设置OPENAI_API_KEY环境变量，无法调用API生成提交消息')
        return None

    # 准备API请求内容
    prompt = f"""
    请根据以下Git变更内容生成一个符合GitHub标准格式的提交消息：
    
    变更差异:
    {diff_content[:5000]}  # 限制长度以避免超出API限制
    
    文件变更:
    新增: {', '.join(file_changes['new_files'][:10])}
    修改: {', '.join(file_changes['modified_files'][:10])}
    删除: {', '.join(file_changes['deleted_files'][:10])}
    
    请生成一个符合以下格式的提交消息:
    
    1. 第一行必须是一个总结性的提交消息，以下列前缀之一开头:
       - feat: 新功能
       - fix: 修复bug
       - docs: 文档变更
       - style: 代码格式变更，不影响代码功能
       - refactor: 代码重构，不新增功能或修复bug
       - perf: 性能优化
       - test: 测试相关
       - build: 构建系统或外部依赖变更
       - ci: CI配置文件和脚本变更
       - chore: 其他变更
    
    2. 第一行格式为: '前缀: 简短描述'，例如:
       fix: 修正错误响应格式，添加空字符串作为默认数据字段
    
    3. 如果有多个变更，请在第一行后空一行，然后使用列表形式列出详细变更:
       - 第一项变更
       - 第二项变更
       - 第三项变更
    
    4. 不要使用任何代码块标记（如```或`），不要使用任何特殊格式标记
    
    5. 确保第一行是最重要的变更总结，后面的列表是详细说明

    6. 除前缀以外，主要使用此語言 {os.environ.get('LANGUAGE', '中文')} 总结
    """

    try:
        response = requests.post(
            f'{os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')}/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model if model.startswith('gpt') else 'gpt-4o',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7,
                'max_tokens': 2000,
            },
        )

        if response.status_code == 200:
            result = response.json()
            commit_message = result['choices'][0]['message']['content'].strip()

            # 清理提交消息，移除可能的代码块标记
            commit_message = re.sub(r'^```.*?\n', '', commit_message)  # 移除开头的```
            commit_message = re.sub(r'\n```$', '', commit_message)  # 移除结尾的```
            commit_message = commit_message.replace('`', '')  # 移除所有的`符号

            return commit_message
        else:
            logger.error(f"API调用失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"调用API时出错: {e}")
        return None


def request_claude_ai(diff_content, file_changes, model):
    api_key = os.environ.get('CLAUDE_API_KEY')
    if not api_key:
        logger.warning('未设置CLAUDE_API_KEY环境变量，无法调用API生成提交消息')
        return None

    # 准备API请求内容
    prompt = f"""
    请根据以下Git变更内容生成一个符合GitHub标准格式的提交消息：
    
    变更差异:
    {diff_content[:20000]}  # 限制长度以避免超出API限制
    
    文件变更:
    新增: {', '.join(file_changes['new_files'][:10])}
    修改: {', '.join(file_changes['modified_files'][:10])}
    删除: {', '.join(file_changes['deleted_files'][:10])}
    
    请生成一个符合以下格式的提交消息:
    
    1. 第一行必须是一个总结性的提交消息，以下列前缀之一开头:
       - feat: 新功能
       - fix: 修复bug
       - docs: 文档变更
       - style: 代码格式变更，不影响代码功能
       - refactor: 代码重构，不新增功能或修复bug
       - perf: 性能优化
       - test: 测试相关
       - build: 构建系统或外部依赖变更
       - ci: CI配置文件和脚本变更
       - chore: 其他变更
    
    2. 第一行格式为: "前缀: 简短描述"，例如:
       fix: 修正错误响应格式，添加空字符串作为默认数据字段
    
    3. 如果有多个变更，请在第一行后空一行，然后使用列表形式列出详细变更:
       - 第一项变更
       - 第二项变更
       - 第三项变更
    
    4. 不要使用任何代码块标记（如```或`），不要使用任何特殊格式标记
    
    5. 确保第一行是最重要的变更总结，后面的列表是详细说明

    6. 除前缀以外，主要使用此語言 {os.environ.get('LANGUAGE', '中文')} 总结

    7. 只需要回覆與提交訊息相關的內容不需要重複複述任何我的指令，請再三確認回覆符合所有規範，並且保證第一行一定是對於此次修改的簡短描述
    """

    try:
        response = requests.post(
            f'{os.environ.get('ANTHROPIC_API_BASE', 'https://api.anthropic.com')}/v1/messages',
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": (model if model.startswith("claude") else "claude-3-7-sonnet-20250219"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
        )

        if response.status_code == 200:
            result = response.json()
            commit_message = result['content'][0]['text'].strip()

            # 清理提交消息，移除可能的代码块标记
            commit_message = re.sub(r'^```.*?\n', '', commit_message)  # 移除开头的```
            commit_message = re.sub(r'\n```$', '', commit_message)  # 移除结尾的```
            commit_message = commit_message.replace('`', '')  # 移除所有的`符号

            return commit_message
        else:
            logger.error(f"API调用失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"调用API时出错: {e}")
        return None


def summarize_changes_with_api(diff_content, file_changes):
    '''调用API对变更内容进行总结，生成提交消息'''
    # 这里替换为实际的API调用
    # 示例使用OpenAI API，需要设置环境变量OPENAI_API_KEY
    model = os.environ.get('MODEL', 'OPEN_AI')
    if model == 'OPEN_AI' or model.startswith('gpt'):
        return request_open_ai(diff_content, file_changes, model)
    elif model == 'CLAUDE' or model.startswith('claude'):
        return request_claude_ai(diff_content, file_changes, model)
    else:
        logger.error('未知的API模型')
        return None


def format_commit_message(commit_message):
    """格式化提交消息，确保格式正确"""
    # 分割消息行
    lines = commit_message.strip().split('\n')
    # 确保第一行是总结性内容
    if not lines:
        return "chore: 自动生成的提交消息"
    # 检查第一行是否包含前缀
    first_line = lines[0]
    prefixes = ['feat:', 'fix:', 'docs:', 'style:', 'refactor:', 'perf:', 'test:', 'build:', 'ci:', 'chore:']
    has_prefix = any(first_line.startswith(prefix) for prefix in prefixes)
    if not has_prefix:
        # 尝试从消息中推断前缀
        if any('修复' in line or '修正' in line or 'fix' in line.lower() for line in lines):
            first_line = f"fix: {first_line}"
        elif any('新增' in line or '添加' in line or 'feat' in line.lower() or 'add' in line.lower() for line in lines):
            first_line = f"feat: {first_line}"
        elif any('文档' in line or 'doc' in line.lower() for line in lines):
            first_line = f"docs: {first_line}"
        elif any('重构' in line or 'refactor' in line.lower() for line in lines):
            first_line = f"refactor: {first_line}"
        else:
            first_line = f"chore: {first_line}"

    # 重新组合消息
    formatted_lines = [first_line]

    # 如果有多行，确保第一行和后面的内容之间有空行
    if len(lines) > 1:
        if lines[1].strip():  # 如果第二行不是空行
            formatted_lines.append('')  # 添加空行

        # 添加剩余的行
        for line in lines[1:]:
            if line.strip():  # 跳过空行
                # 如果行不是以'-'开头，添加'-'前缀
                if not line.strip().startswith('-') and not line.strip().startswith('*'):
                    formatted_lines.append(f"- {line.strip()}")
                else:
                    formatted_lines.append(line)

    return '\n'.join(formatted_lines)

def escape_commit_message(message):
    """转义提交消息中的特殊字符，使其在命令行中安全"""
    # 对于Windows，使用双引号并转义内部的双引号
    if os.name == 'nt':
        return message.replace('"', '\\"')
    # 对于Unix/Linux，使用单引号并转义内部的单引号
    else:
        return message.replace("'", "'\\''")

def commit_changes(commit_message):
    """使用给定的提交消息提交更改"""
    try:
        # 创建临时文件存储提交消息
        temp_file = os.path.join(os.getcwd(), 'temp_commit_msg.txt')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(commit_message)
        
        # 使用临时文件提交
        logger.info("执行git commit命令...")
        
        # 在Windows上设置编码为UTF-8
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # 使用UTF-8编码处理输出
        result = subprocess.run(
            ['git', 'commit', '-F', temp_file], 
            check=True, 
            capture_output=True, 
            text=True,
            encoding='utf-8',
            env=env
        )
        
        # 删除临时文件
        os.remove(temp_file)
        
        logger.info(f"提交成功: {result.stdout}")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"提交失败: {e.stderr}")
        # 尝试删除临时文件
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False, e.stderr
    except Exception as e:
        logger.error(f"提交过程中出错: {e}")
        # 尝试删除临时文件
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False, str(e)

def main():
    # 解析命令行参数
    auto_commit = '--auto-commit' in sys.argv
    confirm_commit = '--confirm' in sys.argv
    no_add_commit = '--no-add' in sys.argv
    
    # 首先执行git add .命令
    if not no_add_commit and not add_all_changes():
        logger.warning("无法添加所有更改，继续执行脚本...")
    
    # 确定要分析的是暂存区还是最近一次提交
    if '--last-commit' in sys.argv:
        logger.info("分析最近一次提交的变更...")
        diff_content = get_last_commit_diff()
        mode = "last_commit"
    else:
        logger.info("分析暂存区的变更...")
        diff_content = get_staged_diff()
        mode = "staged"
    
    if not diff_content:
        logger.error("无法获取差异内容")
        sys.exit(1)
    
    # 输出差异内容
    print("变更内容:")
    print("-" * 50)
    print(diff_content)
    print("-" * 50)
    
    # 获取文件变更状态
    file_changes = get_file_changes()
    if not file_changes:
        logger.error("无法获取文件变更状态")
        sys.exit(1)
    
    # 输出文件变更统计 - 修复f-string中的换行符问题
    if file_changes['new_files']:
        logger.info("新增文件:")
        for file in file_changes['new_files']:
            logger.info(f"  - {file}")
    
    if file_changes['modified_files']:
        logger.info("修改文件:")
        for file in file_changes['modified_files']:
            logger.info(f"  - {file}")
    
    if file_changes['deleted_files']:
        logger.info("删除文件:")
        for file in file_changes['deleted_files']:
            logger.info(f"  - {file}")
    
    # 统计修改的文件类型
    all_files = file_changes['new_files'] + file_changes['modified_files'] + file_changes['deleted_files']
    file_types = {}
    for file in all_files:
        ext = file.split('.')[-1] if '.' in file else 'other'
        file_types[ext] = file_types.get(ext, 0) + 1
    
    type_summary = f"变更了 {', '.join([f'{count} 个 {ext} 文件' for ext, count in file_types.items()])}"
    logger.info(type_summary)
    
    # 调用API生成提交消息
    raw_commit_message = summarize_changes_with_api(diff_content, file_changes)
    
    if raw_commit_message:
        # 格式化提交消息
        commit_message = format_commit_message(raw_commit_message)
        
        logger.info("生成的提交消息:")
        print("\n" + "-" * 50)
        print(commit_message)
        print("-" * 50 + "\n")
        
        # 如果是分析暂存区，提供使用此消息进行提交的命令
        if mode == "staged":
            if auto_commit:
                # 自动提交
                success, result = commit_changes(commit_message)
                if success:
                    print(f"自动提交成功！\n{result}")
                else:
                    print(f"自动提交失败：\n{result}")
                    print("\n可以手动执行以下命令提交:")
                    print(f'git commit -F- <<EOF\n{commit_message}\nEOF')
            elif confirm_commit:
                # 确认后提交
                print("是否使用此提交消息进行提交？(y/n): ", end="")
                choice = input().strip().lower()
                if choice == 'y' or choice == 'yes':
                    success, result = commit_changes(commit_message)
                    if success:
                        print(f"提交成功！\n{result}")
                    else:
                        print(f"提交失败：\n{result}")
                        print("\n可以手动执行以下命令提交:")
                        print(f'git commit -F- <<EOF\n{commit_message}\nEOF')
                else:
                    print("已取消提交。")
                    print("\n可以手动执行以下命令提交:")
                    print(f'git commit -F- <<EOF\n{commit_message}\nEOF')
            else:
                # 只显示命令
                print(f'可以使用以下命令提交:')
                print(f'git commit -F- <<EOF\n{commit_message}\nEOF')
                print("\n或者运行此脚本并添加 --confirm 参数来确认提交:")
                print(f"python {sys.argv[0]} --confirm")
                print("\n或者运行此脚本并添加 --auto-commit 参数来自动提交:")
                print(f"python {sys.argv[0]} --auto-commit")
    else:
        logger.warning("无法生成提交消息，请手动编写")

if __name__ == "__main__":
    # 你可以继续使用以下命令来运行脚本：
    # 1. 基本用法：python git-diff.py
    # 2. 确认后提交：python git-diff.py --confirm
    # 3, 自动提交：python git-diff.py --auto-commit
    main()