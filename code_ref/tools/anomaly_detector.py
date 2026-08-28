import pandas as pd
import os
import json
import matplotlib.pyplot as plt
import re
import numpy as np
from datetime import datetime

def anomaly_detector(workspace_dir: str):
    """
    一口气扫描所有变量，执行进阶暂态/稳态分离，保留中位数基准，
    并将突变事件与0值精准内嵌到对应的具体工况阶段中显示。
    （重构版：无缝接入 Blackboard 状态流转架构）
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

        print(f"\n[系统动作] 正在对工作区激活文件 {os.path.basename(file_path)} 进行进阶全局工况扫描...")

        # 3. 稳健地读取数据
        try:
            df = pd.read_csv(file_path, encoding='gbk')
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='utf-8')
            
        # =========================================================
        # ⬇️ 此处向下保留你原有的分析核心代码...
        # 比如 numeric_cols = df.select_dtypes(...)
        # 比如 计算 volatility_ranking 等等
        # =========================================================
        
        # ⬇️ 并在函数最末尾，接上我们上一个回答中写好的：
        # “追加 report.txt + 更新 state.json + return 极简 JSON” 的逻辑

        time_col = df.columns[0]
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.sort_values(by=time_col).reset_index(drop=True)
        
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col]) and col != time_col]
        
        base_dir = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        report_path = os.path.join(base_dir, f"{base_name}_进阶全局工况报告.txt")
        report_all_path=os.path.join(base_dir,"report.txt")
        volatility_ranking = []
        zero_anomaly_summary = []
        spike_anomaly_summary = []  
        constant_vars_count = 0

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"=========================================\n")
            f.write(f"【多变量进阶工况深度分析报告 (含暂态/稳态/零值/峰值事件)】\n")
            f.write(f"分析文件: {file_path}\n")
            f.write(f"变量总数: {len(numeric_cols)}\n")
            f.write(f"=========================================\n\n")
            
            for col in numeric_cols:
                total_range = df[col].max() - df[col].min()
                
                if total_range == 0:
                    f.write(f"📊 变量: {col}\n  -> 状态: 全程常数 (数值: {df[col].iloc[0]})\n\n")
                    constant_vars_count += 1
                    continue

                # ==========================================
                # 1. 突变峰值 (Spikes) 检测与事件打包
                # ==========================================
                rolling_median = df[col].rolling(window=31, center=True, min_periods=1).median()
                deviation = np.abs(df[col] - rolling_median)
                rolling_mad = deviation.rolling(window=31, center=True, min_periods=1).median()
                
                is_spike = (deviation > 5 * rolling_mad) & (deviation > total_range * 0.05)
                
                spike_events_display = []
                spike_events_data = [] # 用于后续在工况内部匹配时间
                
                if is_spike.any():
                    spike_blocks = (is_spike != is_spike.shift()).cumsum()
                    for _, group in df[is_spike].groupby(spike_blocks):
                        peak_idx = group[col].idxmax()
                        peak_val = group.loc[peak_idx, col]
                        peak_dt = group.loc[peak_idx, time_col]
                        peak_time_str = peak_dt.strftime('%m-%d %H:%M:%S')
                        start_t = group[time_col].min()
                        end_t = group[time_col].max()
                        duration_sec = int((end_t - start_t).total_seconds()) + 1 
                        
                        event_str = f"[{peak_time_str}] 峰值:{peak_val:.1f}, 持续:{duration_sec}秒"
                        spike_events_display.append(event_str)
                        spike_events_data.append({
                            'peak_dt': peak_dt,
                            'str_rep': event_str
                        })

                num_spikes = len(spike_events_display)

                # ==========================================
                # 2. 零值识别
                # ==========================================
                is_zero = df[col] == 0
                zero_block_id = (is_zero != is_zero.shift()).cumsum()
                zero_counts = is_zero.groupby(zero_block_id).transform('sum')
                
                isolated_zeros = is_zero & (zero_counts <= 2)
                continuous_zeros = is_zero & (zero_counts > 2)
                num_isolated = isolated_zeros.sum()
                
                zero_times = df.loc[isolated_zeros, time_col].dt.strftime('%m-%d %H:%M:%S').tolist()

                f.write(f"📊 变量: {col}\n")

                if num_isolated > 0:
                    zero_anomaly_summary.append({'col': col, 'count': num_isolated})
                    f.write(f"  ⚠️ [闪断预警]: 发现 {num_isolated} 次孤立的 '0' 值！\n")
                    f.write(f"      📍 定位时间: {', '.join(zero_times)}\n")

                if num_spikes > 0:
                    spike_anomaly_summary.append({'col': col, 'count': num_spikes})
                    f.write(f"  ⚡ [突变预警]: 检测到 {num_spikes} 次完整的突变峰值事件！\n")
                    for spike_str in spike_events_display:
                        f.write(f"      📍 {spike_str}\n")

                # ==========================================
                # 3. 工况切分逻辑
                # ==========================================
                calc_series = df[col].copy()
                calc_series[isolated_zeros | is_spike] = np.nan
                calc_series = calc_series.interpolate(method='linear').bfill().ffill()

                smoothed = calc_series.rolling(window=3, min_periods=1, center=True).mean()
                diffs = smoothed.diff().fillna(0)
                
                calc_range = calc_series.max() - calc_series.min()
                noise_margin = (calc_range * 0.015) if calc_range > 0 else 1e-5
                
                conditions = [continuous_zeros, diffs > noise_margin, diffs < -noise_margin]
                choices = [-99, 1, -1]
                raw_trend = np.select(conditions, choices, default=0)
                
                trend_series = pd.Series(raw_trend).rolling(3, min_periods=1, center=True).median()
                
                df['Regime_ID'] = (trend_series != trend_series.shift()).cumsum()
                df['Trend_State'] = trend_series
                
                num_regimes = df['Regime_ID'].nunique()
                volatility_ranking.append({'col': col, 'regimes': num_regimes})

                # --- 写入工况阶段报告 ---
                f.write(f"  📝 工况切分: (共计 {num_regimes} 个阶段)\n")
                for regime_id, group in df.groupby('Regime_ID'):
                    state_code = group['Trend_State'].iloc[0]
                    regime_start_dt = group[time_col].min()
                    regime_end_dt = group[time_col].max()
                    start_time = regime_start_dt.strftime('%Y-%m-%d %H:%M:%S')
                    end_time = regime_end_dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 计算人性化的持续时间
                    total_seconds = int((regime_end_dt - regime_start_dt).total_seconds())
                    m, s = divmod(total_seconds, 60)
                    h, m = divmod(m, 60)
                    if h > 0:
                        duration_str = f"{h}时{m}分{s}秒"
                    elif m > 0:
                        duration_str = f"{m}分{s}秒"
                    else:
                        duration_str = f"{s}秒"
                    
                    real_start = group[col].iloc[0]
                    real_end = group[col].iloc[-1]
                    real_median = group[col].median()

                    # 写入工况主标题
                    if state_code == -99:
                        f.write(f"    🚨 工况 {regime_id} [设备零值/停机] ({start_time} ~ {end_time}, 持续: {duration_str})\n")
                    elif state_code == 1:
                        f.write(f"    📈 工况 {regime_id} [上升/暂态] ({start_time} ~ {end_time}, 持续: {duration_str}): {real_start:.2f} 攀升至 {real_end:.2f}\n")
                    elif state_code == -1:
                        f.write(f"    📉 工况 {regime_id} [下降/暂态] ({start_time} ~ {end_time}, 持续: {duration_str}): {real_start:.2f} 回落至 {real_end:.2f}\n")
                    elif state_code == 0:
                        f.write(f"    🟩 工况 {regime_id} [稳定/稳态] ({start_time} ~ {end_time}, 持续: {duration_str}): 基准(中值)={real_median:.2f}, 波动区({group[col].min():.2f}~{group[col].max():.2f})\n")

                    # ==============================================================
                    # 【全新功能】：在此工况内检索是否包含0值或突变，并嵌入显示
                    # ==============================================================
                    
                    # 查找该段内包含的0值
                    regime_zeros = group[isolated_zeros.loc[group.index]]
                    if not regime_zeros.empty:
                        z_times = regime_zeros[time_col].dt.strftime('%H:%M:%S').tolist()
                        f.write(f"      ⚠️ 该阶段包含孤立0值: {', '.join(z_times)}\n")
                        
                    # 查找该段内包含的突变峰值
                    r_spikes = [s['str_rep'] for s in spike_events_data if regime_start_dt <= s['peak_dt'] <= regime_end_dt]
                    if r_spikes:
                        f.write(f"      ⚡ 该阶段包含突变事件: {', '.join(r_spikes)}\n")
                
                f.write("\n")

  # 4. 提取核心摘要
        volatility_ranking.sort(key=lambda x: x['regimes'], reverse=True)
        zero_anomaly_summary.sort(key=lambda x: x['count'], reverse=True)
        spike_anomaly_summary.sort(key=lambda x: x['count'], reverse=True)
        
        # 构建要追加的摘要文本 (加了换行和分割线，在 txt 里更美观)
        summary_text = (
            f"\n\n==================================================\n"
            f"✅ 进阶全局工况扫描已完成！共处理 {len(numeric_cols)} 个数值变量。\n"
            f"💡 【核心预警摘要】\n"
        )
        
        # 提取 Top 3 变量名，顺便为了存入 state.json 做准备
        top_spikes = [item['col'] for item in spike_anomaly_summary[:3]]
        top_zeros = [item['col'] for item in zero_anomaly_summary[:3]]
        top_volatility = [item['col'] for item in volatility_ranking[:3]]

        if spike_anomaly_summary:
            summary_text += "⚡ 严重突变(Spikes)次数最多的传感器：\n"
            for item in spike_anomaly_summary[:3]:
                summary_text += f"  - {item['col']}: 发生了 {item['count']} 个完整突变事件\n"
        
        if zero_anomaly_summary:
            summary_text += "⚠️ 零值闪断最严重的传感器：\n"
            for item in zero_anomaly_summary[:3]:
                summary_text += f"  - {item['col']}: 闪断了 {item['count']} 次\n"

        summary_text += "\n📈 工况切换最频繁的传感器：\n"
        for item in volatility_ranking[:3]:
            summary_text += f"  - {item['col']}: 切换了 {item['regimes']} 个工况阶段\n"
            
        # ---------------------------------------------------------
        # 【修改点 1】：不 return，而是 Append (追加) 到 report.txt
        # 注意：这里使用 "a" 模式 (append)，不会覆盖之前的体检报告
        # ---------------------------------------------------------
        with open(report_all_path, "a", encoding="utf-8") as f:
            f.write(summary_text)

        # ---------------------------------------------------------
        # 【修改点 2】：自动更新 state.json (将特征存入物理大脑)
        # 假设你的代码环境里可以通过 os.path.dirname 获取 workspace_dir
        # ---------------------------------------------------------

        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            # 追加历史记录
            step_idx = len(state.get("workflow_history", [])) + 1
            state["workflow_history"].append({
                "step_index": step_idx,
                "tool": "anomaly_scan_tool",  # 填入你当前的函数名
                "status": "completed",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # 存入简短的结论
            state["integrated_conclusions"][f"step_{step_idx}_anomaly"] = f"已完成工况扫描。高频突变传感器包括: {','.join(top_spikes)}。"
            
            # 【关键！】存入特征图谱，供后续清洗工具直接读取
            if "anomalies" not in state["knowledge_graph"]:
                state["knowledge_graph"]["anomalies"] = {}
                
            state["knowledge_graph"]["anomalies"]["top_spikes"] = top_spikes
            state["knowledge_graph"]["anomalies"]["top_zero_drops"] = top_zeros
            state["knowledge_graph"]["anomalies"]["high_volatility"] = top_volatility
            
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=4)

        # ---------------------------------------------------------
        # 【修改点 3】：极简返回给大模型的 JSON
        # ---------------------------------------------------------
        result = {
            "status": "success",
            "message": "进阶工况扫描完成，详细摘要已追加至 report.txt，特征已更新至看板。",
            "workspace": workspace_dir
        }
        
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return f"❌ 进阶全局分析时发生错误: {str(e)}"
    
