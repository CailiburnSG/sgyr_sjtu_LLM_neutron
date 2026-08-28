# config.py
import ollama
from openai import OpenAI

# 1. 接入我的大脑 (Gemini API)
#client = OpenAI(
#    api_key="AIzaSyB6En3K-JMuqmCzdgyinFKDU3d8hZMBSLc", 
    # 🌟 关键：填入 Gemini 专属的兼容接口地址
#    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
#)
# 2. 选一个我的分身
# 推荐用 flash，速度极快且完全胜任你的路由和拆解任务
#MODEL_NAME = "gemini-1.5-flash"

client = ollama.Client(host='http://127.0.0.1:11434')
MODEL_NAME = "qwen2.5:7b" 
# 全局共享的黑板状态
global_state = {
    #"current_file_path": "/home/sda/sgyr/yjs_data_2026_2/data/中子测量电流2/A2_1_sorted.csv"
# config.py 的改动
    # 使用列表保存历史文件，最后一个元素 [-1] 永远是“当前最新焦点”
    "file_history": [
        "/home/sda/sgyr/yjs_data_2026_2/data/中子测量电流2/A2_1_sorted.csv" 
    ]
}

def get_llm_response(system_prompt, user_text):
    """统一的 LLM 调用接口，所有 Agent 都通过这里发请求"""
    response = client.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        options={"temperature": 0.1}
    )
    return response['message']['content'].strip()
# config.py 的其余部分保持不变...

def get_llm_response_GEMINI(system_prompt, user_text):
    # 🌟 必须改成 .chat.completions.create(...)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        temperature=0.1
    )
    
    # 🌟 提取文本的路径也要换成 OpenAI 的标准路径
    output = response.choices[0].message.content.strip()
    
    # 过滤可能出现的 Markdown 代码块标记
    return output.replace("```json", "").replace("```", "").strip()
# 基础格式要求，所有 Agent 共用
BASE_FORMAT_RULES = """
【输出格式规范】
仅输出 JSON，单步为 {}，多步为 [{}] 数组。
{"action": "目标工具名称", "parameters": {"参数名": "值"}}
【🔴 最高级强制纪律 🔴】
1. 纯净输出：回复【仅包含 JSON】,严禁任何解释。
2. 路径继承：如果用户未指定路径，必须使用提示中的 [当前上下文路径]。
"""