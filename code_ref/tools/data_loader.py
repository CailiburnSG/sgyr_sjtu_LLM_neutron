import os
import pandas as pd
import json
from datetime import datetime
# tools/data_loader.py 补充
def list_data_files_tool(directory="data"):
    """
    用途：列出指定目录下的所有 CSV 文件。
    当用户没有提供具体文件路径时，Agent 应该先调用此工具。
    """
    if not os.path.exists(directory):
        return f"❌ 目录 {directory} 不存在。"
    
    files = [f for f in os.listdir(directory) if f.endswith('.csv')]
    if not files:
        return f"📁 在 {directory} 目录中没发现任何 CSV 文件。"
    
    return f"📁 发现以下可供分析的文件：{', '.join(files)}"



def load_and_profile_csv_tool(file_path):
    """
    数据预处理与体检综合工具：
    自动读取文件 -> 解析时间 -> 按时间排序 -> 保存清洗后的文件 -> 生成健康度报告。
    """
    
    print(f"\n[系统动作] 正在执行数据初始化与体检: {file_path}")
    file_path = file_path.strip('"').strip("'").strip()
    
    if not os.path.exists(file_path):
        # 返回这个，看它还怎么编！
        return f"🚨 【致命错误】：在路径 {file_path} 下根本找不到文件！请检查你的 Action Input 路径参数是否正确。当前目录下只有：{os.listdir('.')}"
        
    try:
        # 1. 兼容读取
        try:
            df = pd.read_csv(file_path, encoding='gbk')
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='utf-8')

        # 2. 时间解析与排序
        time_col = df.columns[0]
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.sort_values(by=time_col, ascending=True).reset_index(drop=True)

        # 3. 自动保存排序后的标准文件
        #base, ext = os.path.splitext(file_path)
        #out_path = f"{base}_sorted{ext}"
        #df.to_csv(out_path, index=False, encoding='gbk')

        # 3. 自动创建 workspace 并保存排序后的标准文件
        # 提取目录路径、带后缀的文件名、纯文件名
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        name_only, ext = os.path.splitext(base_name)  
        # 拼装专属 workspace 文件夹路径 (例如: /home/.../data/A2_1_workspace)
        workspace_dir = os.path.join(dir_name, f"{name_only}_workspace")
        # 物理创建文件夹 (exist_ok=True 保证如果文件夹已存在也不会报错)
        os.makedirs(workspace_dir, exist_ok=True)
        # 拼装排序后文件的完整输出路径
        out_path = os.path.join(workspace_dir, f"{name_only}_sorted{ext}")
        # 存入 DataFrame
        df.to_csv(out_path, index=False, encoding='gbk')
        print(f"✅ 文件已排序并保存至工作区: {out_path}")

        # 4. 健康度体检核心计算
        num_rows, num_cols = df.shape
        start_time, end_time = df[time_col].min(), df[time_col].max()

        # 频率计算
        time_diffs = df[time_col].diff().dropna()
        freq_str = str(time_diffs.mode()[0]) if not time_diffs.empty else "未知"

        # 缺失值检测 (简洁写法)
        missing_cols = df.isnull().sum()[lambda x: x > 0]
        missing_str = "✅ 无缺失" if missing_cols.empty else f"⚠️ 缺失预警: {', '.join([f'{k}({v}行)' for k, v in missing_cols.items()])}"

        # 僵尸传感器检测 (仅看数值列)
        numeric_cols = df.select_dtypes(include='number').columns
        dead_cols = [col for col in numeric_cols if df[col].nunique() <= 1]
        dead_str = "✅ 均有波动" if not dead_cols else f"⚠️ 僵尸传感器: {', '.join(dead_cols[:5])}{' 等' if len(dead_cols)>5 else ''}"

        # 5. 生成高密度 Agent 报告
    #    report = (
    #        f"【数据初始化与体检报告】\n"
    #        f"✅ 文件已按时间排序并另存为: {os.path.basename(out_path)}\n"
    #        f"- 规模: {num_rows} 行 x {num_cols} 列\n"
    #        f"- 时间跨度: {start_time} 至 {end_time} (频率: {freq_str})\n"
    #        f"- 完整度: {missing_str}\n"
    #        f"- 活跃度: {dead_str}\n"
    #        f"*(后续工具请默认使用此 _sorted 文件进行分析)*"
    #    )
    #    return report,out_path
        # 5. 生成高密度 Agent 报告并保存为 txt
        report = (
            f"【数据初始化与体检报告】\n"
            f"✅ 文件已按时间排序并另存为: {os.path.basename(out_path)}\n"
            f"- 规模: {num_rows} 行 x {num_cols} 列\n"
            f"- 时间跨度: {start_time} 至 {end_time} (频率: {freq_str})\n"
            f"- 完整度: {missing_str}\n"
            f"- 活跃度: {dead_str}\n"
            f"*(后续工具请默认使用此 _sorted 文件进行分析)*"
        )

    
        # 6. 【硬核导出】保存 report.txt
        report_path = os.path.join(workspace_dir, "report.txt") # 定义报告的保存路径 (保存在之前创建的 workspace_dir 中)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ 文本报告已生成并存至: {report_path}")
        
       # 7. 【自动挂载】初始化并保存 state.json (Blackboard)        
        state_path = os.path.join(workspace_dir, "state.json")
        initial_state = {
            "project_meta": {
                "project_id": f"{name_only}_Analysis",
                "raw_source": file_path,
                "workspace_dir": workspace_dir
            },
            "file_registry": {
                "current_active_file": out_path  # 以后所有工具都从这里读路径
            },
            "workflow_history": [
                {
                    "step_index": 1,
                    "tool": "load_and_profile_csv_tool",
                    "status": "completed",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            ],
            "integrated_conclusions": {
                "step_1_profile": f"工作区已建立。完成时间排序，数据规模为 {num_rows}x{num_cols}。"
            },
            "knowledge_graph": {
                "initial_data_stats": {
                    "rows": num_rows,
                    "columns": num_cols,
                    "frequency": freq_str
                }
            }
        }

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(initial_state, f, ensure_ascii=False, indent=4)

        # 8. 极简返回给调度脚本 (不再返回长文本 report)
        result = {
            "status": "success",
            "active_file": out_path,
            "workspace": workspace_dir,
            "info": "排序完成，看板已初始化，报告已导出。"
        }       
        return json.dumps(result, ensure_ascii=False) 
        # 返回 report 文本和 sorted 后的文件路径
        #return report, out_path
    except Exception as e:
        return f"❌ 初始化与体检失败: {str(e)}"