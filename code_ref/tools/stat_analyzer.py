import os
import json
import pandas as pd
from datetime import datetime

def zero_prior_discovery_tool(workspace_dir: str):
    """
    零先验数据发现工具：纯靠统计学特征，扒出变量的隐藏角色和拓扑关系。
    """
    print(f"\n[Debug] 大模型传进来的 workspace_dir 是: {workspace_dir}")
    # 1. 定位并读取“黑板” (state.json)
    state_path = os.path.join(workspace_dir, "state.json")
    
    if not os.path.exists(state_path):
        # 返回极简 JSON 报错，让大模型知道前置步骤出了问题
        return json.dumps({"status": "error", "message": "找不到 state.json 看板，请先执行初始化工具。"}, ensure_ascii=False)

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
            
        # 2. 自动从“黑板”获取当前应该分析的最新文件路径
        file_path = state.get("file_registry", {}).get("current_active_file", "")
        
        if not file_path or not os.path.exists(file_path):
            return json.dumps({"status": "error", "message": f"看板中记录的文件无效或不存在: {file_path}"}, ensure_ascii=False)

        print(f"\n[系统动作] 正在对工作区激活文件 {os.path.basename(file_path)} 进行零先验数据扫描...")

        try:
            df = pd.read_csv(file_path, encoding='gbk')
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='utf-8')

        time_col = df.columns[0]
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col]) and col != time_col]
        df = df[numeric_cols].dropna() # 简易清洗
        
        report_lines = []
        report_lines.append(f"【零先验特征提取报告】")
        report_lines.append(f"变量总数: {len(numeric_cols)}\n")

        # ==========================================
        # 1. 变量角色反向侦查 (唯一值与波动率)
        # ==========================================
        report_lines.append("--- 1. 变量形态分类 ---")
        
        # [新增] 专门用于存入 JSON 黑板的字典
        role_dict = {"discrete": [], "slow_lag": [], "highly_volatile": [], "normal": []}
        
        for col in numeric_cols:
            unique_count = df[col].nunique()
            mean_val = df[col].mean()
            cv = (df[col].std() / mean_val) if mean_val != 0 else df[col].std()
            
            if unique_count <= 5: 
                role = "阶跃/离散型 (疑似系统控制指令或状态位)"
                role_dict["discrete"].append(col)
            elif abs(cv) < 0.05: 
                role = "高惯性/迟滞型 (疑似大体积热工参数，如水温、结构温度)"
                role_dict["slow_lag"].append(col)
            elif abs(cv) > 0.5:  
                role = "高敏/剧烈波动型 (疑似流体参数或高敏电信号，如流量、中子通量)"
                role_dict["highly_volatile"].append(col)
            else:
                role = "常规连续型"
                role_dict["normal"].append(col)
                
            report_lines.append(f"变量 {col}: 唯一值数量={unique_count}, 波动率={cv:.4f} -> 归类: {role}")

        # ==========================================
        # 2. 隐藏关联与冗余发现 (皮尔逊相关系数)
        # ==========================================
        report_lines.append("\n--- 2. 系统拓扑与冗余分析 ---")
        corr_matrix = df.corr().abs()
        
        redundant_pairs = []
        subsystem_groups = []
        
        # [新增] 专门用于存入 JSON 黑板的数组
        json_redundant_pairs = []
        
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                col1 = corr_matrix.columns[i]
                col2 = corr_matrix.columns[j]
                corr_val = corr_matrix.iloc[i, j]
                
                if corr_val >= 0.99:
                    redundant_pairs.append(f"({col1} & {col2}, 相关度: {corr_val:.4f})")
                    json_redundant_pairs.append([col1, col2]) # 纯净的数据结构
                elif 0.85 <= corr_val < 0.99:
                    subsystem_groups.append(f"({col1} & {col2}, 相关度: {corr_val:.4f})")
                    
        if redundant_pairs:
            report_lines.append("🚨 发现极高度共线变量 (疑似同位置的冗余双重传感器):")
            report_lines.extend(redundant_pairs)
        else:
            report_lines.append("✅ 未发现极高度共线变量。")
            
        if subsystem_groups:
            report_lines.append("\n🔗 发现强绑定物理子群 (疑似处于同一热工流体回路或联动机制):")
            report_lines.extend(sorted(subsystem_groups, reverse=True))


        # ==========================================
        # [重构部分] 后处理：写 txt，写 json，极简返回
        # ==========================================
        
        # 1. 追加到 report.txt
        summary_text = "\n\n==================================================\n" + "\n".join(report_lines) + "\n"
        report_path = os.path.join(workspace_dir, "report.txt")
        with open(report_path, "a", encoding="utf-8") as f:
            f.write(summary_text)
            
        # 2. 更新状态看板 state.json
        step_idx = len(state.get("workflow_history", [])) + 1
        state.setdefault("workflow_history", []).append({
            "step_index": step_idx,
            "tool": "zero_prior_discovery_tool",
            "status": "completed",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 更新精简结论
        state.setdefault("integrated_conclusions", {})[f"step_{step_idx}_zero_prior"] = f"零先验扫描完成。发现 {len(json_redundant_pairs)} 对高度共线变量。"
        
        # 【核心操作】更新特征记忆库
        kg = state.setdefault("knowledge_graph", {})
        kg["variable_roles"] = role_dict
        kg["redundant_sensor_pairs"] = json_redundant_pairs
        
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
            
        # 3. 极简返回给 LLM
        result = {
            "status": "success",
            "message": "零先验盲测完成，长报告已追加至 report.txt，特征规律已记入知识图谱。",
            "workspace": workspace_dir
        }
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"status": "error", "message": f"执行扫描时发生内部错误: {str(e)}"}, ensure_ascii=False)