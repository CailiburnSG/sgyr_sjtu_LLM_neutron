import os
import json
import pandas as pd
import itertools
from datetime import datetime

def global_time_lag_scan_tool(workspace_dir: str):
    """
    用途：全局因果发现！扫描所有变量组合，寻找时间滞后关系，构建系统级的上下游传导链路。
    """
    print(f"\n[系统动作] 正在执行全局变量因果与时间滞后扫描...")
    
    # 1. 自动从“黑板”获取当前文件
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
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col]) and col != time_col]
        
        if len(numeric_cols) < 2:
            return json.dumps({"status": "error", "message": "数值变量不足，无法进行配对分析。"}, ensure_ascii=False)

        # ==========================================
        # ⚡ 【核心算法】：全组合交叉互相关计算
        # ==========================================
        max_lag = 15 # 最大往前/往后找 15 个点
        
        causality_links = []  # 存储确诊的上下游链路
        sync_links = []       # 存储同步变化的链路
        
        # itertools.combinations 会生成所有不重复的两两组合
        for col_A, col_B in itertools.combinations(numeric_cols, 2):
            best_corr = df[col_A].corr(df[col_B])
            best_lag = 0
            lead_var, lag_var = None, None
            
            # 处理 NaN 的情况（如果有全空列会导致 corr 为 NaN）
            if pd.isna(best_corr):
                continue

            # 假设 A 是上游 (A 提前，B 滞后)
            for lag in range(1, max_lag + 1):
                corr_A_leads = df[col_A].corr(df[col_B].shift(-lag))
                if not pd.isna(corr_A_leads) and corr_A_leads > best_corr:
                    best_corr = corr_A_leads
                    best_lag = lag
                    lead_var, lag_var = col_A, col_B

            # 假设 B 是上游 (B 提前，A 滞后)
            for lag in range(1, max_lag + 1):
                corr_B_leads = df[col_B].corr(df[col_A].shift(-lag))
                if not pd.isna(corr_B_leads) and corr_B_leads > best_corr:
                    best_corr = corr_B_leads
                    best_lag = lag
                    lead_var, lag_var = col_B, col_A

            # ----------------------------------------
            # 过滤筛选：只记录强相关的“硬逻辑”链路
            # ----------------------------------------
            if best_lag > 0 and best_corr > 0.85:
                causality_links.append({
                    "upstream": lead_var,
                    "downstream": lag_var,
                    "lag_steps": best_lag,
                    "correlation": best_corr
                })
            elif best_lag == 0 and best_corr > 0.90:
                sync_links.append({
                    "col_A": col_A,
                    "col_B": col_B,
                    "correlation": best_corr
                })

        # 按相关度降序排序，让最强的物理规律排在最前面
        causality_links.sort(key=lambda x: x["correlation"], reverse=True)
        sync_links.sort(key=lambda x: x["correlation"], reverse=True)

        # ==========================================
        # 📝 【落盘 1】：追加到人类可读报告 (report.txt)
        # ==========================================
        report_path = os.path.join(workspace_dir, "report.txt")
        
        report_lines = [
            f"\n\n==================================================",
            f"🔗 【系统传导链路与因果分析报告】",
            f"=================================================="
        ]
        
        if causality_links:
            report_lines.append("\n🌊 【确诊因果传导链路 (具有明显时间滞后)】:")
            for link in causality_links:
                report_lines.append(f"  - ➡️ 上游 [{link['upstream']}] 领先于 下游 [{link['downstream']}] | 滞后周期: {link['lag_steps']} 步 | 吻合度: {link['correlation']:.4f}")
        else:
            report_lines.append("\n🌊 【确诊因果传导链路】: 未发现具有明显滞后且高度吻合的上下游变量。")

        if sync_links:
            report_lines.append("\n👯 【高度同步变动群组 (瞬间同步，无明显滞后)】:")
            # 为了避免报告太长，只取前 15 对最强的同步关系
            for link in sync_links[:15]:
                report_lines.append(f"  - ⚡ [{link['col_A']}] 与 [{link['col_B']}] | 瞬间吻合度: {link['correlation']:.4f}")

        report_lines.append("==================================================\n")
        
        with open(report_path, "a", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

        # ==========================================
        # 🧠 【落盘 2】：将因果链路注入图谱 (state.json)
        # ==========================================
        step_idx = len(state.get("workflow_history", [])) + 1
        state.setdefault("workflow_history", []).append({
            "step_index": step_idx,
            "tool": "global_time_lag_scan_tool",
            "status": "completed",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        state.setdefault("integrated_conclusions", {})[f"step_{step_idx}_causality"] = f"因果扫描完成。发现 {len(causality_links)} 条具有时间滞后的物理传导链路。"
        
        # 将传导链路永久写入知识图谱，供未来推理使用
        kg = state.setdefault("knowledge_graph", {})
        kg["causality_chains"] = causality_links
        kg["synchronous_pairs"] = sync_links
        
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=4)
            
        # ==========================================
        # 🤖 【极简返回】：给大模型看的摘要
        # ==========================================
        result = {
            "status": "success",
            "message": f"全局滞后扫描完成！成功提取出 {len(causality_links)} 条确诊因果链路，详细列表已存入 report.txt 与图谱 kg['causality_chains'] 中。",
            "top_causality": causality_links[:3] # 返回前3条最强的给大模型看看，帮它找灵感
        }
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"因果扫描失败: {str(e)}"}, ensure_ascii=False)