import json
import re
import os
import ollama
from tools.registry import LOCAL_TOOL_ROUTER # 直接引用你的路由表
from agents.tool_schemas import ZERO_PRIOR_TOOLS
from agents.system_prompt import ZERO_PRIOR_SYSTEM_PROMPT
# ==========================================
# 1. 配置区
# ==========================================
MODEL_NAME = "qwen2.5:7b"
OLLAMA_HOST = 'http://127.0.0.1:11434' # 确认你的 Ollama 端口
client = ollama.Client(host=OLLAMA_HOST)

# ==========================================
# 2. 核心提示词：JSON-Native ReAct
# ==========================================
SYSTEM_PROMPT = ZERO_PRIOR_SYSTEM_PROMPT


# ==========================================
# 3. 核心引擎函数
# ==========================================
def run_nuclear_agent(user_query, file_path):
    # 初始化历史纪录
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"【初始指令】: {user_query}\n【锁定路径】: {file_path}"}
    ]
    
    print(f"☢️  Agent 启动成功，正在对目标文件进行深度诊断...")
    
    max_turns = 10
    for turn in range(max_turns):
        print(f"\n--- 🔄 第 {turn + 1} 轮推理 ---")
        
        # 调用 Ollama
        response = client.chat(
            model=MODEL_NAME,
            messages=messages,
            options={"temperature": 0} # 极致稳定性
        )
        
        raw_output = response['message']['content'].strip()
        
        # 强制提取 JSON 部分 (防止模型输出 ```json ... ```)
        json_str = re.sub(r"```json\n?|```", "", raw_output).strip()
        # 过滤掉 JSON 前可能出现的 Thought: 等文本
        json_str = re.search(r'(\{.*\}|\[.*\])', json_str, re.DOTALL)
        if not json_str:
            print(f"❌ 模型未按格式输出 JSON: {raw_output}")
            messages.append({"role": "user", "content": "格式错误！请仅输出 JSON 对象。"})
            continue
        
        try:
            res = json.loads(json_str.group(1))
        except json.JSONDecodeError:
            print(f"❌ JSON 解析失败: {raw_output}")
            continue

        # 情况 1：最终答案
        if "final_answer" in res:
            ans = res["final_answer"]
            print("\n" + "█" * 60)
            print("📊 最终物理诊断报告")
            print(f"1. 拓扑重构: {ans.get('topology')}")
            print(f"2. 事故分析: {ans.get('incident_analysis')}")
            print(f"3. 空间快照: {ans.get('spatial_snapshot')}")
            print("█" * 60)
            return

        # 情况 2：执行工具
        action = res.get("action")
        thought = res.get("thought", "思考中...")
        params = res.get("parameters", {})

        if action:
            print(f"💭 思考: {thought}")
            print(f"⚙️  执行: {action}...")
            
            # 从 registry 获取真实的函数
            func = LOCAL_TOOL_ROUTER.get(action)
            if func:
                try:
                    observation = func(**params)
                except Exception as e:
                    observation = f"❌ 执行报错: {str(e)}"
            else:
                observation = f"❌ 注册表中无此工具: {action}"
            
            print(f"👁️  结果: {str(observation)[:100]}...")
            
            # 将 Thought 和 Observation 存入历史，进入下一轮
            messages.append({"role": "assistant", "content": json.dumps(res)})
            messages.append({"role": "user", "content": f"Observation: {observation}"})
        else:
            messages.append({"role": "user", "content": "未检测到 action，请选择工具或给出最终结论。"})

    print("❌ 达到最大推理步数。")

# ==========================================
# 4. 执行入口 (Main)
# ==========================================
if __name__ == "__main__":
    # 模拟输入：你可以根据需要修改这里
    FILE_PATH = "/home/sda/sgyr/my_dataprocess_assistant2.0/data/A1_1.csv"
    TASK = "请帮我分析这段中子测量电流数据。首先对文件排序，然后查明 01:00:00 到 01:00:20 之间是否存在异常动作，并给出物理诊断。"

    # 简单检查文件是否存在
    if not os.path.exists(FILE_PATH):
        print(f"🚨 警告：本地未找到文件 {FILE_PATH}，Agent 可能会在执行第一步时报错。")
    
    run_nuclear_agent(TASK, FILE_PATH)