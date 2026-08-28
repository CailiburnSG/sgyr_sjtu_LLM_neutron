import ollama
import os
import json

# ==========================================
# 第一部分：定义“手”（真正的 Python 执行函数）
# ==========================================
def create_workspace(raw_file_path: str) -> str:
    """工具1：创建一个专属工作区文件夹"""
    workspace_dir = f"{raw_file_path.split('.')[0]}_workspace"
    
    # 真正的操作系统级别执行
    os.makedirs(workspace_dir, exist_ok=True)
    print(f"💻 [底层执行]: 成功创建文件夹 -> {workspace_dir}")
    
    # 返回给大模型的执行结果
    return json.dumps({"status": "success", "workspace_dir": workspace_dir})

def write_state_json(workspace_dir: str, content: str) -> str:
    """工具2：将状态写入 state.json"""
    file_path = os.path.join(workspace_dir, "state.json")
    
    # 将大模型传来的字符串转为真正的 JSON 存入硬盘
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"💻 [底层执行]: 成功写入状态文件 -> {file_path}")
    
    return "Success: state.json 已更新。"



    {
        "type": "function",
        "function": {
            "name": "create_workspace_tool",
            "description": "【系统操作-环境初始化】根据用户提供的原始数据文件路径，自动在同级目录下创建一个专属的工作区文件夹。这是任何新分析任务必须执行的第一步。",
            "parameters": {
                "type": "object",
                "properties": {
                    "raw_file_path": {
                        "type": "string",
                        "description": "用户提供的原始数据文件的绝对或相对路径，例如 '/home/sda/sgyr/data/A2_1.csv'"
                    }
                },
                "required": ["raw_file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_state_json_tool",
            "description": "【系统操作-状态同步】将当前的任务进度、结论日志和特征图谱写入工作区内的 state.json 文件。在每次执行完数据分析工具后，必须调用此工具更新看板（Blackboard）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_dir": {
                        "type": "string",
                        "description": "当前目标工作区文件夹的绝对路径，例如 '/home/sda/sgyr/data/A2_1_workspace'"
                    },
                    "content": {
                        "type": "string",
                        "description": "需要写入 state.json 的完整 JSON 格式字符串。必须严格遵循预设的 Blackboard 数据结构（包含 project_meta, file_registry, workflow_history 等字段）。"
                    }
                },
                "required": ["workspace_dir", "content"]
            }
        }
    }