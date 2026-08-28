# agent/tool_schemas.py

"""
零先验盲测 Agent 的工具注册表
定义了 6 个核心物理探针的 JSON Schema，供大模型 Function Calling 使用。
"""

REGISTRY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_data_files_tool",
            "description": "当用户未指定具体文件路径时调用。用于查看 data/ 文件夹下有哪些可用的数据文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "要查看的目录路径，例如 'data'"
                    }
                },
                "required": ["directory"]
            }
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "load_and_profile_csv_tool",
            "description": "【入口工具】流程的第一步！用于加载目标 CSV 文件，自动按时间排序，并输出基础的数据健康度体检报告（规模、频率、缺失值、死机传感器）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "要读取的 CSV 文件路径，例如 'data/ria_scram_data.csv'"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "zero_prior_discovery_tool",
            "description": "【全局纵向扫描】零先验统计特征扫描工具。当你需要了解变量的物理角色时调用此工具。它能盲测分辨出“离散控制端(如阀门)”、“高惯性响应端(如温度)”和“高敏波动端(如通量)”，并能发现高度共线的冗余传感器或物理子回路。",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_dir": {
                        "type": "string",
                        "description": "当前目标工作区文件夹的绝对路径（例如 '/home/.../A2_1_workspace'）。工具会自动从该工作区内的 state.json 中读取最新的激活数据文件进行扫描，无需手动传入 CSV 路径。"
                    }
                },
                "required": ["workspace_dir"]
            }
        }
    },
   {
        "type": "function",
        "function": {
            "name": "anomaly_detector",
            "description": "【波形与工况诊断】核心异常诊断与工况切分工具。当你发现某些变量波动剧烈，需要确认其物理真实性时调用此工具。它能精确识别出突变尖峰(Spikes)、零值闪断(Zeros)，并将时间序列切分为不同的稳态和暂态工况阶段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_dir": {
                        "type": "string",
                        "description": "当前目标工作区文件夹的绝对路径（例如 '/home/.../A2_1_workspace'）。工具会自动从该工作区内的 state.json 中读取最新的激活数据文件进行扫描，无需手动传入 CSV 路径。"
                    }
                },
                "required": ["workspace_dir"]
            }
        }
    },
{
        "type": "function",
        "function": {
            "name": "global_time_lag_scan_tool",
            "description": "【全局因果与滞后扫描】一口气对所有数值变量进行交叉互相关(Cross-Correlation)计算。用于找出系统中所有的上下游物理传导链路（例如：谁是驱动源，谁是滞后的响应端）。扫描结果会自动写入长报告和知识图谱。",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_dir": {
                        "type": "string",
                        "description": "当前目标工作区文件夹路径。"
                    }
                },
                "required": ["workspace_dir"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "global_extremes_scan_tool",
            "description": "【全景极值扫描】一口气扫描数据集中所有数值变量，找出它们各自的全局最大值、最小值，以及发生这些极值的精确时间戳。结果会自动记入报告和系统知识图谱中。",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_dir": {
                        "type": "string",
                        "description": "当前目标工作区文件夹路径。"
                    }
                },
                "required": ["workspace_dir"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_spatial_snapshot_tool",
            "description": "【空间快照截取】截取系统在某一精确时间点，所有传感器/变量的横向快照状态。通常在找到极值 timestamp 后调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_dir": {
                        "type": "string",
                        "description": "当前目标工作区文件夹路径。"
                    },
                    "timestamp": {
                        "type": "string",
                        "description": "目标时间字符串 (应使用 find_global_event_timestamp_tool 找到的精确时间)"
                    }
                },
                "required": ["workspace_dir", "timestamp"]
            }
        }
    }
]