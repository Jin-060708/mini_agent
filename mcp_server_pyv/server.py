import datetime

from mcp.server.mcpserver import MCPServer
from simpleeval import simple_eval
from pathlib import Path

mcp = MCPServer("my-tools")
ROOT = Path("e:/agent_project/miniagent").resolve()

def _safe_path(file_path: str) -> Path:
    p = (ROOT / file_path).resolve()
    if not str(p).startswith(str(ROOT)):
        raise ValueError("路径越界")
    return p

@mcp.tool()
def calculator(expression: str) -> str:
    """计算表达式"""
    return str(simple_eval(expression))

@mcp.tool()
def get_time() -> str:
    """获取当前时间"""
    return str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@mcp.tool()
def read_file(file_path: str) -> str:
    """读取文件"""
    p = _safe_path(file_path)
    return p.read_text(encoding="utf-8")
    
@mcp.tool()
def write_file(file_path: str, content: str) -> str:
    p = _safe_path(file_path)
    p.write_text(content, encoding="utf-8")
    return {"file_path": str(p), "content": content}

@mcp.tool()
def edit_file(file_path: str, old_text: str, new_text: str) -> str:
    """把文件中的 old_text 替换为 new_text"""
    p = _safe_path(file_path)
    content = p.read_text(encoding="utf-8")
    if old_text not in content:
        return "未找到要替换的内容"
    if content.count(old_text) > 1:
        return "匹配到多处，请提供更精确的 old_text"
    p.write_text(content.replace(old_text, new_text), encoding="utf-8")
    return "替换成功"

@mcp.tool()
def create_directory(dir_path: str) -> str:
    """创建目录"""
    p = _safe_path(dir_path)
    p.mkdir(parents=True, exist_ok=True)
    return f"目录已创建: {p}"

@mcp.tool()
def delete_directory(dir_path: str) -> str:
    """删除目录"""
    p = _safe_path(dir_path)
    p.rmdir()
    return f"目录已删除: {p}"

@mcp.tool()
def create_file(file_path: str) -> str:
    """创建文件"""
    p = _safe_path(file_path)
    p.write_text("", encoding="utf-8")
    return f"文件已创建: {p}"

@mcp.tool()
def delete_file(file_path: str) -> str:
    """删除文件"""
    p = _safe_path(file_path)
    p.unlink()
    return f"文件已删除: {p}"

@mcp.tool()
def move_file(src: str, dst: str) -> str:
    """移动文件"""
    p = _safe_path(src)
    p.rename(_safe_path(dst))
    return f"文件已移动: {p} -> {dst}"

@mcp.tool()
def copy_file(src: str, dst: str) -> str:
    """复制文件"""
    p = _safe_path(src)
    p.copy(_safe_path(dst))
    return f"文件已复制: {p} -> {dst}"

@mcp.tool()
def rename_directory(src: str, dst: str) -> str:
    """重命名目录"""
    p = _safe_path(src)
    p.rename(_safe_path(dst))
    return f"目录已重命名: {p} -> {dst}"

@mcp.tool()
def rename_file(src: str, dst: str) -> str:
    """重命名文件"""
    p = _safe_path(src)
    p.rename(_safe_path(dst))
    return f"文件已重命名: {p} -> {dst}"

@mcp.tool()
def list_files(dir_path: str = ".") -> str:
    """列出目录下的所有文件"""
    p = _safe_path(dir_path)
    files = [str(f) for f in p.iterdir() if f.is_file()]
    return "\n".join(files)

@mcp.tool()
def list_directories(dir_path: str = ".") -> str:
    """列出目录下的所有目录"""
    p = _safe_path(dir_path)
    directories = [str(d) for d in p.iterdir() if d.is_dir()]
    return "\n".join(directories)

@mcp.tool()
def list_directory(dir_path: str = ".") -> str:
    """列出目录内容"""
    p = _safe_path(dir_path)
    entries = []
    for item in sorted(p.iterdir()):
        kind = "DIR " if item.is_dir() else "FILE"
        entries.append(f"{kind} {item.name}")
    return "\n".join(entries)

@mcp.tool()
def list_files(dir_path: str = ".") -> str:
    """列出目录下的所有文件"""
    p = _safe_path(dir_path)
    return "\n".join([str(f) for f in p.iterdir() if f.is_file()])

@mcp.tool()
def search_file(file_path: str) -> str:
    """搜索文件"""
    p = _safe_path(file_path)
    return f"文件路径: {p}"

@mcp.tool()
def search_code(code: str) -> str:
    """搜索代码"""
    p = _safe_path(code)
    return p.read_text(encoding="utf-8")

@mcp.tool()
def run_command(command: str) -> str:
    """在项目目录执行 shell 命令"""
    import subprocess
    result = subprocess.run(
        command, shell=True, cwd=ROOT,
        capture_output=True, text=True, timeout=30
    )
    return f"exit={result.returncode}\n{result.stdout}\n{result.stderr}"

if __name__ == "__main__":
    mcp.run()
