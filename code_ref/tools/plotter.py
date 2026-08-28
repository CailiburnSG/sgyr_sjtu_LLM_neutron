import matplotlib.pyplot as plt
import pandas as pd
import os
import re


def plot_csv_tool(file_path):
    print(f"\n[系统动作] 正在读取数据并为每个变量生成独立图表: {file_path}")
    
    # 清理路径字符串
    file_path = file_path.strip('"').strip("'").strip()
    
    if not os.path.exists(file_path):
        return f"❌ 画图失败：找不到文件 {file_path}"
        
    try:
        # 1. 读取数据，处理编码：保留 gbk 和 utf-8 两种可能
        try:
            df = pd.read_csv(file_path, encoding='gbk')
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='utf-8')


        # 2. 将第一列（时间）转为时间格式并设为 X 轴 (索引)
        time_column = df.columns[0]
        df[time_column] = pd.to_datetime(df[time_column])
        # 按照时间列进行升序排序，确保折线图不会来回“乱跳”
        df = df.sort_values(by=time_column, ascending=True)
        df.set_index(time_column, inplace=True)
        
        # 3. 创建子文件夹
        # 获取 CSV 所在的目录和文件名（不含后缀）
        base_dir = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        # 拼接出新文件夹的路径，例如: /home/.../A1_4_sorted_plots
        output_folder = os.path.join(base_dir, f"{base_name}_plots")
        
        # exist_ok=True 表示如果文件夹已经存在，不会报错，直接继续用
        os.makedirs(output_folder, exist_ok=True) 
        
        plot_count = 0  # 记录成功画了多少张图
        
        # 4. 遍历数值列，为每一列单独画图
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                # 【关键】把创建画布放在循环内部，每次画图都是一张全新的白纸
                plt.figure(figsize=(12, 6))
                
                # 画单条折线
                plt.plot(df.index, df[col], label=col, color='tab:blue')
                
                # 设置标题和标签
                plt.title(f'Sensor Data: {col}')
                plt.xlabel('Time')
                plt.ylabel('Value')
                plt.grid(True)
                
                # 【关键】清理列名，防止包含 \ / : * ? " < > | 等不能做文件名的字符
                safe_col_name = re.sub(r'[\\/*?:"<>|]', "_", str(col))
                
                # 拼接每张图片的完整保存路径
                output_image = os.path.join(output_folder, f"{safe_col_name}.png")
                
                # 保存并关闭画布（必须 close，否则循环画几十张图会导致内存溢出卡死）
                plt.tight_layout()
                plt.savefig(output_image)
                plt.close()
                
                plot_count += 1
                
        return f"📊 画图完成！共生成 {plot_count} 张图表，已保存至文件夹: {output_folder}"
        
    except Exception as e:
        return f"❌ 画图时发生严重错误: {str(e)}"