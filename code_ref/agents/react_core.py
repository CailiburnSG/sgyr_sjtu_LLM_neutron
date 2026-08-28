import json
import ollama  # 使用本地 Ollama 库
from agents.system_prompt import ZERO_PRIOR_SYSTEM_PROMPT
from agents.tool_schemas import ZERO_PRIOR_TOOLS
from tools.registry import get_tool_function
import os
# 1. 初始化本地 Ollama 客户端
client = ollama.Client(host='http://127.0.0.1:11434')
MODEL_NAME = "qwen2.5:7b"

def run_agent(user_query, file_path):
    """
    基于 Ollama 本地模型的 ReAct 调度引擎
    """
    # 初始化对话上下文
    messages = [
        {"role": "system", "content": ZERO_PRIOR_SYSTEM_PROMPT},
        {"role": "user", "content": f"【目标文件】: {file_path}\n【分析任务】: {user_query}"}
    ]
    
    print(f"🚀 本地 Agent 启动！模型: {MODEL_NAME} | 目标: {os.path.basename(file_path)}")
    
    max_turns = 10
    for turn in range(max_turns):
        print(f"\n--- 🔄 第 {turn + 1} 轮思考 ---")
        
        # 2. 调用本地模型
        # 注意：ZERO_PRIOR_TOOLS 的格式与 Ollama 要求的 tools 格式完全兼容
        response = client.chat(
            model=MODEL_NAME,
            messages=messages,
            tools=ZERO_PRIOR_TOOLS,
        )
        
        response_msg = response['message']
        messages.append(response_msg) # 将模型的回复加入历史

        # 3. 检查是否给出最终结论 (Final Answer)
        content = response_msg.get('content', '')
        if content and "Final Answer:" in content:
            return content

        # 4. 检查是否需要调用工具
        if 'tool_calls' in response_msg and response_msg['tool_calls']:
            for tool_call in response_msg['tool_calls']:
                # Ollama 的 tool_call 结构：{'function': {'name': '...', 'arguments': {...}}}
                tool_name = tool_call['function']['name']
                tool_args = tool_call['function']['arguments']
                
                print(f"🛠️  本地模型申请调用工具: {tool_name}")
                
                # 5. 路由并执行本地 Python 函数
                func = get_tool_function(tool_name)
                if func:
                    try:
                        observation = func(**tool_args)
                    except Exception as e:
                        observation = f"❌ 本地工具运行报错: {str(e)}"
                else:
                    observation = f"❌ 注册表中未找到工具: {tool_name}"
                
                print(f"👁️  工具执行结果: {str(observation)[:80]}...")

                # 6. 将 Observation 反馈给模型
                messages.append({
                    'role': 'tool',
                    'content': str(observation),
                    'name': tool_name # 有些版本的 Ollama 需要这个字段对齐
                })
        else:
            # 如果模型既没调工具也没给最终答案，可能在自言自语，推它一把
            if not content:
                messages.append({"role": "user", "content": "请根据以上信息继续分析，或直接给出 Final Answer。"})
            else:
                print(f"💭 模型思考中: {content[:100]}...")

    return "❌ 达到最大步数，本地模型未能收敛出结论。"