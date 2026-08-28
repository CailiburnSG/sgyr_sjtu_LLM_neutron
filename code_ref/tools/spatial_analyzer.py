import os
import json
import pandas as pd
from datetime import datetime

def global_extremes_scan_tool(workspace_dir: str):
    """
    用途：一口气扫描所有数值变量，找出它们各自的全局最大值、最小值以及发生的精确时间戳。
    并将极值档案写入报告与知识图谱。
    """
    print(f"\n[系统动作] 正在执行全局变量极值全景扫描...")
    
    state_path = os.path.join(workspace_dir, "state.json")
    if not os.path.exists(state_path):
        return json.dumps({"status": "error", "message": "找不到 state.json 看板"}, ensure_ascii=False)
        
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        filepath = state.get("file_registry", {}).get("current_active_file", "")
        
        try:
            df = pd.read_csv(filepath, encoding='gbk')
        except:
            df = pd.read_csv(filepath, encoding='utf-8')
            
        time_col = df.columns[0]
        # 筛选出所有数值列，排除时间列
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col]) and col != time_col]
        
        if not numeric_cols:
            return json.dumps({"status": "error", "message": "未找到有效的数值变量列。"}, ensure_ascii=False)

        # ==========================================
        # ⚡ 【核心算法】：批量提取极值与时间
        # ==========================================
        extremes_dict = {}
        report_lines = []
        
        for col in numeric_cols:
            max_idx = df[col].idxmax()
            min_idx = df[col].idxmin()
            
            max_val = df[col].max()
            min_val = df[col].min()
            
            # 提取对应的时间戳
            max_time = str(df.iloc[max_idx][time_col])
            min_time = str(df.iloc[min_idx][time_col])
            
            # 存入给 JSON 用的字典
            extremes_dict[col] = {
                "max": {"value": float(max_val), "timestamp": max_time},
                "min": {"value": float(min_val), "timestamp": min_time}
            }
            
            # 存入给人类看的美观文本
            report_lines.append(f"  🔹 {col.ljust(10)} | 极大: {max_val:>10.4f} [@ {max_time}] || 极小: {min_val:>10.4f} [@ {min_time}]")

        # ==========================================
        # 📝 【落盘 1】：追加到人类可读报告 (report.txt)
        # ==========================================
        report_path = os.path.join(workspace_dir, "report.txt")
        summary_text = (
            f"\n\n==================================================\n"
            f"📍 【系统全景极值档案】 (共扫描 {len(numeric_cols)} 个变量)\n"
            f"==================================================\n"
            + "\n".join(report_lines) +
            f"\n==================================================\n"
        )
        with open(report_path, "a", encoding="utf-8") as f:
            f.write(summary_text)

        # ==========================================
        # 🧠 【落盘 2】：将极值档案直接注入知识图谱 (state.json)
        # ==========================================
        step_idx = len(state.get("workflow_history", [])) + 1
        state.setdefault("workflow_history", []).append({
            "step_index": step_idx,
            "tool": "global_extremes_scan_tool",
            "status": "completed",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        state.setdefault("integrated_conclusions", {})[f"step_{step_idx}_extremes"] = f"全局极值扫描完成。已提取 {len(numeric_cols)} 个变量的巅峰与谷底时间戳。"
        
        # 极值数据永久存入大脑
        kg = state.setdefault("knowledge_graph", {})
        kg["global_extremes"] = extremes_dict
        
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
            
        # ==========================================
        # 🤖 【极简返回】：给大模型看精华
        # ==========================================
        # 为了不撑爆 LLM，我们可以只返回极值时间分布最多的一些关键时刻，或者直接告诉它去图谱里拿
        result = {
            "status": "success",
            "message": f"成功扫描 {len(numeric_cols)} 个变量的极值，详细榜单已追加至 report.txt，并已存入知识图谱的 knowledge_graph['global_extremes'] 中。",
            "action_advice": "你可以从上述结果中挑选感兴趣的时间戳，调用 get_spatial_snapshot_tool 获取切面数据。"
        }
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"全局极值扫描失败: {str(e)}"}, ensure_ascii=False)


def get_spatial_snapshot_tool(workspace_dir: str, timestamp: str):
    """
    用途：时间暂停！截取系统在某一精确时间点，所有传感器/变量的横向快照，并追加到诊断报告。
    """
    print(f"\n[系统动作] 正在截取系统时刻 [{timestamp}] 的全景空间快照...")
    
    state_path = os.path.join(workspace_dir, "state.json")
    if not os.path.exists(state_path):
        return json.dumps({"status": "error", "message": "找不到 state.json 看板"}, ensure_ascii=False)
        
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        filepath = state.get("file_registry", {}).get("current_active_file", "")
        
        try:
            df = pd.read_csv(filepath, encoding='gbk')
        except:
            df = pd.read_csv(filepath, encoding='utf-8')
            
        time_col = df.columns[0]
        df[time_col] = df[time_col].astype(str)
        
        target_row = df[df[time_col].str.contains(str(timestamp).strip(), na=False)]
        
        if target_row.empty:
            return json.dumps({"status": "error", "message": f"未找到匹配时间 [{timestamp}] 的记录。"}, ensure_ascii=False)
            
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col]) and col != time_col]
        
        snapshot = target_row.iloc[0][numeric_cols].to_dict()

        # ==========================================
        # 📝 【新增】：人类可读报告落盘 (把字典转成优美的列表)
        # ==========================================
        snapshot_str = "\n".join([f"  - {k}: {v:.4f}" for k, v in snapshot.items()])
        report_path = os.path.join(workspace_dir, "report.txt")
        summary_text = (
            f"\n\n==================================================\n"
            f"📸 【全局空间切面快照】\n"
            f"⏰ 冻结时刻: [{timestamp}]\n"
            f"📊 各传感器/变量读数分布:\n"
            f"{snapshot_str}\n"
            f"==================================================\n"
        )
        with open(report_path, "a", encoding="utf-8") as f:
            f.write(summary_text)
        
        result = {
            "status": "success",
            "target_timestamp": timestamp,
            "snapshot_data": snapshot,
            "message": "已成功截取该时刻的空间快照数据，并已完整追加至 report.txt 中。"
        }
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"截取快照失败: {str(e)}"}, ensure_ascii=False)