import os
import re
import json
import ollama
from collections import Counter
from llama_index.core import StorageContext, load_index_from_storage, Settings
from llama_index.embeddings.ollama import OllamaEmbedding

# ==========================================
# ⚙️ 1. 基础配置与 RAG 引擎初始化
# ==========================================
MODEL_NAME = "qwen2.5:7b"
OLLAMA_HOST = "http://127.0.0.1:11434"
client = ollama.Client(host=OLLAMA_HOST)

# 配置词向量模型（检索必备）
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text", base_url=OLLAMA_HOST)

# 加载本地知识库 (storage 文件夹需在当前目录下)
CUR_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(CUR_DIR, "ragtest3","storage")

print("🔌 正在连接本地 Markdown 知识库...")
retriever = None
if os.path.exists(STORAGE_DIR):
    storage_context = StorageContext.from_defaults(persist_dir=STORAGE_DIR)
    index = load_index_from_storage(storage_context)
    # 单次 retrieve 的候选数；最终片段条数在 analyze_json_with_llm 里再合并去重
    retriever = index.as_retriever(similarity_top_k=8)
    print("✅ 知识库连接成功！")
else:
    print("⚠️ 警告: 未找到 storage 文件夹，本次诊断将仅依靠大模型自身常识。")

# ==========================================
# 📊 2. TXT 转 JSON 数据降维 (保持你的优秀正则逻辑)
# ==========================================
def parse_report_to_json(txt_content):
    if "📊 变量:" not in txt_content: return "[]"
    
    all_parsed_data = []
    for block in txt_content.split("📊 变量:")[1:]:
        if not block.strip(): continue
        
        lines = block.strip().split('\n')
        var_name = lines[0].strip()
        
        # 提取零值与突变
        zeros_match = re.search(r"定位时间:\s*([^\n]+)", block)
        isolated_zeros = re.findall(r"\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}", zeros_match.group(1)) if zeros_match else []
        spikes_raw = re.findall(r"📍\s*\[.*?\]\s*峰值:([\d.]+),\s*持续:(\d+)秒", block)
        
        total_spikes = len(spikes_raw)
        top_peaks, duration_range = {}, []
        
        if total_spikes > 0:
            peak_values = [float(v) for v, s in spikes_raw]
            durations = [int(s) for v, s in spikes_raw]
            most_common = Counter(peak_values).most_common()
            
            # 精简：一行代码搞定 Top 3
            top_peaks = {str(val): count for val, count in most_common[:3]}
            if len(most_common) > 3:
                top_peaks["others"] = sum(count for _, count in most_common[3:])
            duration_range = [min(durations), max(durations)]

        all_parsed_data.append({
            "var_name": var_name,
            "alerts": {
                "isolated_zeros": isolated_zeros,
                "spikes_summary": {"total_count": total_spikes, "top_peaks": top_peaks, "duration_range_sec": duration_range}
            }
        })
    return json.dumps(all_parsed_data, ensure_ascii=False, indent=2)


def parse_workspace_report_to_json(txt_content):
    """
    解析「数据初始化 / 零先验特征 / 进阶全局工况 / 传导链路 / 极值档案」类 workspace 报告（如 A1_1 report.txt），
    输出带 meta 与 variables 列表的 JSON 字符串；variables 中每行含 var_name、alerts（与 parse_report_to_json 对齐字段），
    便于下游 RAG 与多轮对话复用。
    """
    text = txt_content or ""

    def _sect_between(start_pat, end_pats):
        m = re.search(start_pat, text)
        if not m:
            return ""
        start = m.end()
        rest = text[start:]
        end_off = len(rest)
        for ep in end_pats:
            em = re.search(ep, rest)
            if em:
                end_off = min(end_off, em.start())
        return rest[:end_off]

    data_init = {}
    m_sorted = re.search(r"另存为:\s*(\S+)", text)
    if m_sorted:
        data_init["sorted_csv"] = m_sorted.group(1).strip()
    m_shape = re.search(r"规模:\s*(\d+)\s*行\s*x\s*(\d+)\s*列", text)
    if m_shape:
        data_init["rows"] = int(m_shape.group(1))
        data_init["cols"] = int(m_shape.group(2))
    m_span = re.search(r"时间跨度:\s*([^\n(]+)", text)
    if m_span:
        data_init["time_span"] = m_span.group(1).strip()
    m_freq = re.search(r"频率:\s*([^)]+)\)", text)
    if m_freq:
        data_init["sample_frequency"] = m_freq.group(1).strip()
    m_complete = re.search(r"完整度:\s*([^\n]+)", text)
    if m_complete:
        data_init["completeness"] = m_complete.group(1).strip()
    m_active = re.search(r"活跃度:\s*([^\n]+)", text)
    if m_active:
        data_init["activity"] = m_active.group(1).strip()
    m_var_total = re.search(r"变量总数:\s*(\d+)", text)
    variable_total = int(m_var_total.group(1)) if m_var_total else None

    morph_block = _sect_between(
        r"---\s*1\.\s*变量形态分类\s*---",
        [r"---\s*2\.\s*系统拓扑", r"={10,}"],
    )
    var_morph = []
    for line in morph_block.splitlines():
        mm = re.match(
            r"变量\s+(.+?):\s*唯一值数量=(\d+),\s*波动率=([\d.]+)\s*->\s*归类:\s*(.+?)\s*\((.+)\)\s*$",
            line.strip(),
        )
        if mm:
            var_morph.append(
                {
                    "var_name": mm.group(1).strip(),
                    "unique_values": int(mm.group(2)),
                    "volatility": float(mm.group(3)),
                    "category": mm.group(4).strip(),
                    "category_hint": mm.group(5).strip(),
                }
            )

    topo_block = _sect_between(
        r"---\s*2\.\s*系统拓扑与冗余分析\s*---",
        [r"={10,}", r"✅\s*进阶全局工况"],
    )
    collinear_pairs = []
    for line in topo_block.splitlines():
        pm = re.search(
            r"\(([^&]+)\s*&\s*([^,]+),\s*相关度:\s*([\d.]+)\)",
            line,
        )
        if pm:
            collinear_pairs.append(
                {
                    "var_a": pm.group(1).strip(),
                    "var_b": pm.group(2).strip(),
                    "correlation": float(pm.group(3)),
                }
            )

    alert_spikes = []
    for line in text.splitlines():
        sm = re.search(r"[-–]\s*(.+?):\s*发生了\s*(\d+)\s*个完整突变事件", line)
        if sm:
            alert_spikes.append(
                {"var_name": sm.group(1).strip(), "spike_events": int(sm.group(2))}
            )

    alert_zeros = []
    for line in text.splitlines():
        zm = re.search(r"[-–]\s*(.+?):\s*闪断了\s*(\d+)\s*次", line)
        if zm:
            alert_zeros.append(
                {"var_name": zm.group(1).strip(), "zero_dropout_count": int(zm.group(2))}
            )

    alert_regime = []
    for line in text.splitlines():
        rm = re.search(r"[-–]\s*(.+?):\s*切换了\s*(\d+)\s*个工况阶段", line)
        if rm:
            alert_regime.append(
                {"var_name": rm.group(1).strip(), "regime_changes": int(rm.group(2))}
            )

    causal_block = _sect_between(
        r"🔗\s*【系统传导链路与因果分析报告】",
        # 勿用「====」作结束：该段开头就有分隔线，否则会把传导/同步块几乎截空。
        [r"📍\s*【系统全景极值档案】"],
    )
    causal_diagnosis_line = None
    for line in causal_block.splitlines():
        if "确诊因果传导链路" in line:
            causal_diagnosis_line = line.strip()
            break
    sync_groups = []
    for line in causal_block.splitlines():
        gm = re.search(
            r"\[([^\]]+)\]\s*与\s*\[([^\]]+)\].*?吻合度:\s*([\d.]+)",
            line,
        )
        if gm:
            sync_groups.append(
                {
                    "var_a": gm.group(1).strip(),
                    "var_b": gm.group(2).strip(),
                    "sync_score": float(gm.group(3)),
                }
            )

    extrema_block = _sect_between(
        r"📍\s*【系统全景极值档案】",
        [r"={10,}\s*\Z"],
    )
    extrema_by_var = {}
    _num_re = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    for line in extrema_block.splitlines():
        em = re.search(
            rf"🔹\s*(.+?)\s*\|\s*极大:\s*({_num_re})\s*\[@\s*([^\]]+)\]\s*\|\|\s*极小:\s*({_num_re})\s*\[@\s*([^\]]+)\]",
            line,
        )
        if em:
            vn = em.group(1).strip()

            def _to_float(s):
                try:
                    return float(s.strip().replace(" ", ""))
                except ValueError:
                    return None

            extrema_by_var[vn] = {
                "max_value": _to_float(em.group(2)),
                "max_at": em.group(3).strip(),
                "min_value": _to_float(em.group(4)),
                "min_at": em.group(5).strip(),
            }

    spike_map = {x["var_name"]: x["spike_events"] for x in alert_spikes}
    zero_map = {x["var_name"]: x["zero_dropout_count"] for x in alert_zeros}
    regime_map = {x["var_name"]: x["regime_changes"] for x in alert_regime}
    morph_map = {x["var_name"]: x for x in var_morph}

    all_names = list(
        dict.fromkeys(
            list(morph_map.keys())
            + list(spike_map.keys())
            + list(zero_map.keys())
            + list(regime_map.keys())
            + list(extrema_by_var.keys())
        )
    )

    variables_out = []
    for vn in all_names:
        morph = morph_map.get(vn, {})
        zc = zero_map.get(vn, 0)
        sc = spike_map.get(vn, 0)
        rc = regime_map.get(vn, 0)
        row = {
            "var_name": vn,
            "morphology": morph or None,
            "alerts": {
                "isolated_zeros": [],
                "zero_dropout_count": zc,
                "spikes_summary": {
                    "total_count": sc,
                    "top_peaks": {},
                    "duration_range_sec": [],
                },
                "regime_change_count": rc,
            },
            "extrema": extrema_by_var.get(vn),
        }
        variables_out.append(row)

    snapshot = {
        "report_kind": "workspace_scan_v1",
        "variable_total_declared": variable_total,
        "data_initialization": data_init or None,
        "topology": {"high_collinearity_pairs": collinear_pairs},
        "alert_rankings": {
            "spike_events_top": alert_spikes,
            "zero_dropout_top": alert_zeros,
            "regime_change_top": alert_regime,
        },
        "causal": {
            "diagnosis_line": causal_diagnosis_line,
            "synchronous_groups": sync_groups,
        },
        "variables": variables_out,
    }
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


def build_rag_queries_from_json(json_data_str):
    """
    用当前报告里的变量名与异常类型拼检索句，避免全年只用同一句固定 query 导致向量匹配飘。
    每条 query 在中文后追加英文关键词，便于命中 data/lib_md 中以英文为主的 IAEA / EPRI 类手册。
    """
    queries = []
    try:
        parsed = json.loads(json_data_str)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict) and "variables" in parsed:
        rows = parsed["variables"] or []
    elif isinstance(parsed, list):
        rows = parsed
    else:
        rows = []

    var_names = [str(r.get("var_name", "")).strip() for r in rows if r.get("var_name")]
    var_part = " ".join(var_names[:12])  # 防止极长报告撑爆上下文

    has_zeros = any(
        (r.get("alerts", {}).get("isolated_zeros") or [])
        or (r.get("alerts", {}).get("zero_dropout_count") or 0) > 0
        for r in rows
    )
    has_spikes = any(
        (r.get("alerts", {}).get("spikes_summary") or {}).get("total_count", 0) > 0
        for r in rows
    )

    # ① 与「具体通道/变量」强绑定（手册里若含点名更容易命中）
    en_ch = (
        "neutron monitoring ex-core detector neutron current "
        "sensor channel fault troubleshooting maintenance I&C instrumentation"
    )
    if var_part:
        queries.append(
            f"{var_part} 核测 中子 电流 传感器 通道 故障 排查 维护 {en_ch}"
        )

    # ② 与「症状类型」绑定（零值 / 尖峰在手册里常用词不同）
    symptom_bits = []
    en_symptom_bits = []
    if has_zeros:
        symptom_bits.append("孤立零值 信号丢失 通信中断 掉线 无效数据")
        en_symptom_bits.append(
            "isolated zero invalid data loss of signal communication dropout "
            "bad quality stale data I&C channel"
        )
    if has_spikes:
        symptom_bits.append("突变峰值 尖峰 削顶 饱和 干扰 噪声 仪表响应")
        en_symptom_bits.append(
            "spike peak clipping saturation EMI noise interference "
            "instrument response transmitter drift surge"
        )
    if symptom_bits:
        en_sym = " ".join(en_symptom_bits)
        queries.append(
            " ".join(symptom_bits) + f" 仪控 诊断 处理 {en_sym} diagnostics mitigation surveillance"
        )

    # ③ 保底泛化（与原固定句接近，避免 JSON 为空时完全无检索）
    queries.append(
        "中子传感器 突变峰值 削顶 孤立零值 故障排查 指南 "
        "neutron detector spike clipping isolated zeros troubleshooting "
        "online monitoring OLM calibration surveillance instrument channel"
    )

    # 去重且保持顺序
    seen = set()
    out = []
    for q in queries:
        q = " ".join(q.split())
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _json_rows_from_string(json_data_str):
    """从列表 JSON 或 workspace 快照 JSON 中取出变量行列表。"""
    if not json_data_str or not json_data_str.strip():
        return []
    try:
        parsed = json.loads(json_data_str)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict) and "variables" in parsed:
        return list(parsed["variables"] or [])
    if isinstance(parsed, list):
        return list(parsed)
    return []


def build_rag_queries_merged(json_global_str, workspace_snapshot_str=None):
    """进阶全局 + report 快照合并抽变量与症状，用于检索 query。"""
    rows = _json_rows_from_string(json_global_str) + _json_rows_from_string(
        workspace_snapshot_str or ""
    )
    if not rows:
        return build_rag_queries_from_json("[]")
    return build_rag_queries_from_json(json.dumps(rows, ensure_ascii=False))


def build_stage3_rag_queries(workspace_snapshot_str):
    """
    第三阶段专用：仅针对 report / 零先验快照 JSON 向量化检索，
    并补充拓扑/冗余/同步等词，便于命中 IAEA 类手册。
    """
    base = build_rag_queries_from_json(workspace_snapshot_str or "{}")
    extra = [
        "冗余通道 高度共线 传感器同步 redundant channel collinearity parity cross-check",
        "工况切换 数据质量 historian compression surveillance instrumentation anomaly",
    ]
    seen = set()
    out = []
    for q in base + extra:
        q = " ".join(q.split())
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _format_stage3_rag_user_prefix(nodes):
    """
    将第三阶段追加检索结果格式化为用户消息前缀；编号 R1、R2…，避免与系统里第一路检索的 [1][2] 混淆。
    返回 (前缀文本, 附录用证据行列表)。
    """
    if not nodes:
        return "", []
    legend_lines = ["【第三阶段·知识库追加检索】", "（本段正文引用手册请用 **R1、R2…**，勿与系统提示中的 **[1][2]…** 混用）", ""]
    blocks = []
    evidence_lines = ["【第三阶段追加检索依据】"]
    for i, nws in enumerate(nodes, start=1):
        node = _underlying_node(nws)
        meta = getattr(node, "metadata", None) or {}
        fname = meta.get("file_name", "未知")
        legend_lines.append(f"  [R{i}] {fname}")
        blocks.append(f"----- R{i} 文件: {fname} -----\n{_node_text(node)}")
        sc = getattr(nws, "score", None)
        if sc is not None:
            evidence_lines.append(f"  [R{i}] {fname}（检索得分 {sc:.4f}）")
        else:
            evidence_lines.append(f"  [R{i}] {fname}")
    legend = "\n".join(legend_lines)
    body = "\n\n【第三阶段手册摘录】\n" + "\n\n".join(blocks)
    return legend + body + "\n\n---\n\n", evidence_lines


def discover_case_reports(folder_path):
    """
    在目录下查找：
    - 任意以「进阶全局工况报告.txt」结尾的 txt（如 A2_1_sorted_进阶全局工况报告.txt）
    - 同目录下的 report.txt
    返回 (进阶报告路径或 None, report.txt 路径或 None)
    """
    folder = os.path.abspath(folder_path.strip('"\''))
    if not os.path.isdir(folder):
        return None, None
    adv_candidates = []
    for name in os.listdir(folder):
        if name.endswith("进阶全局工况报告.txt"):
            adv_candidates.append(os.path.join(folder, name))
    adv = sorted(adv_candidates)[0] if adv_candidates else None
    rep = os.path.join(folder, "report.txt")
    if not os.path.isfile(rep):
        rep = None
    return adv, rep


def _underlying_node(nws):
    """兼容 NodeWithScore 与裸 Node。"""
    return getattr(nws, "node", nws)


def _node_text(node):
    if hasattr(node, "get_content"):
        return node.get_content()
    return getattr(node, "text", "") or ""


def _node_dedupe_key(node_with_score):
    n = _underlying_node(node_with_score)
    return getattr(n, "node_id", None) or getattr(n, "id_", None) or hash(_node_text(n))


def retrieve_with_queries(retriever, queries, final_top_k=5):
    """多 query 各检索一段，按最高分去重合并，提高召回与相关性。"""
    best_by_key = {}
    for q in queries:
        for nws in retriever.retrieve(q):
            key = _node_dedupe_key(nws)
            score = getattr(nws, "score", None)
            if score is None:
                score = 0.0
            prev = best_by_key.get(key)
            if prev is None or score > prev[0]:
                best_by_key[key] = (score, nws)

    ranked = sorted(best_by_key.values(), key=lambda x: x[0], reverse=True)
    return [nws for _, nws in ranked[:final_top_k]]

# ==========================================
# 🧠 3. 大模型多轮推理引擎 (精简版)
# ==========================================
OUTPUT_STYLE_RULES = """
【文风（必须遵守）】
- 像有经验的工程师当面讨论一样写：**连贯叙述**，少用刻板小标题和条目堆砌；分段清楚即可。
- 严禁客服式致谢、联系方式、署名落款等；写完技术内容就收笔。

【承接与去重（必须遵守）】
- **只有第一阶段**可以详细罗列变量名、时间点、尖峰条数等数据细节；从第二阶段起**禁止**再粘贴或改写同一套枚举清单（不要用「具体表现为：1.2.3.」把现象再讲一遍）。
- 后续如需指代，用「前述通道」「上面提到的零值/尖峰」等概括即可。
"""

CITATION_RULES_RAG = """
【知识库出处 [n]】
- [1][2]… 与片段前【手册引用代号对照】中的**文件名**一一对应；正文里写观点时句末可标 [n]。
- 第二阶段须显式写出：**参考了哪份文献（写出文件名或 [n]）里的哪类要点**（用自己的话概括条文要义即可），再衔接机理分析；勿单独堆一段纯摘录。
"""

CITATION_RULES_NO_RAG = """
【说明】
- 当前未接入知识库片段，不存在手册出处编号；请基于 JSON 与专业常识展开完整推理，勿虚构 [1][2] 等手册引用。
"""


def analyze_json_with_llm(json_global_str, workspace_snapshot_str=None):
    print("\n📚 [RAG 启动] 正在根据数据特征，翻阅后台 Markdown 手册...")

    evidence_str = "（本次未注入知识库检索片段）"
    evidence_stage3_extra = ""
    has_rag_chunks = False
    sys_prompt = (
        "你是一位经验丰富的核电仪控与反应堆物理专家。请以专业语气解答现场工程师的问题。\n"
        "本对话涉及的现场数据为 **中子通量（中子水平）** 相关测量通道（RIC 等命名按核测理解）。\n"
        + OUTPUT_STYLE_RULES
        + "\n【多数据源分工】\n"
        "- **第一、二阶段**仅依据「进阶全局工况」JSON；系统提示中的【官方手册片段】与 **[1][2]…** 编号**仅服务于第二阶段的机理与手册对照**。\n"
        "- **第三阶段**仅依据「零先验 / report」JSON；若用户消息中含 **R1、R2…** 的追加检索摘录，则第三阶段引用手册时**必须使用 R 编号**，勿与 [1][2] 混用。\n"
        "- **第四阶段**须**以第二阶段「异常机理剖析」中已给出的机理与手册结论为主轴**编写对策；可对照系统提示中的 [n]。**不要**把第三阶段里讨论的变量间统计/物理量关系当作对策的主线。\n"
        "\n【本案例物理前提（第三及以后阶段须遵守）】\n"
        "- 各通道时序数据在工程上视为 **中子通量（中子水平）** 测量链上的读数（如 RIC 等命名亦按堆芯/堆外中子探测理解），而非一般温度或流量过程量。\n"
        "- 第三阶段对共线、同步、极值、工况切换等的解读，应放在 **中子测量、仪控链路、冗余与标定** 等语境下展开。\n"
    )

    # 第一路 RAG：仅按进阶全局 JSON 检索（与原先第一、二阶段体验一致）
    if retriever:
        rag_queries = build_rag_queries_from_json(json_global_str)
        nodes = retrieve_with_queries(retriever, rag_queries, final_top_k=8)
        has_rag_chunks = bool(nodes)
        if has_rag_chunks:
            legend_lines = []
            blocks = []
            evidence_lines = []
            for i, nws in enumerate(nodes, start=1):
                node = _underlying_node(nws)
                meta = getattr(node, "metadata", None) or {}
                fname = meta.get("file_name", "未知")
                legend_lines.append(f"  [{i}] {fname}")
                blocks.append(f"----- 片段 [{i}] 文件: {fname} -----\n{_node_text(node)}")
                sc = getattr(nws, "score", None)
                if sc is not None:
                    evidence_lines.append(f"  [{i}] {fname}（检索得分 {sc:.4f}）")
                else:
                    evidence_lines.append(f"  [{i}] {fname}")
            legend = "【手册引用代号对照】\n" + "\n".join(legend_lines)
            context_text = legend + "\n\n【官方手册片段】\n" + "\n\n".join(blocks)
            sys_prompt += (
                "\n"
                + CITATION_RULES_RAG
                + "\n\n⚠️ 【必须参考的官方手册片段】（供**第二、四**阶段使用，编号 [1][2]…）\n"
                + context_text
                + "\n\n第二阶段须交代「参考了哪条手册、哪句要义」；勿伪造 [n]。"
            )
            evidence_str = "【知识库检索依据（编号对应上文片段）】\n" + "\n".join(evidence_lines)
        else:
            sys_prompt += (
                "\n"
                + CITATION_RULES_NO_RAG
                + "\n（知识库已连接但本次检索未返回片段，全文勿使用手册编号 [n]。）"
            )
            evidence_str = "（知识库已连接但本次检索无命中片段）"
    else:
        sys_prompt += "\n" + CITATION_RULES_NO_RAG

    has_workspace = bool(workspace_snapshot_str and workspace_snapshot_str.strip())
    stage3_rag_prefix = ""
    if has_workspace and retriever:
        n3 = retrieve_with_queries(
            retriever, build_stage3_rag_queries(workspace_snapshot_str), final_top_k=8
        )
        if n3:
            stage3_rag_prefix, ev3_lines = _format_stage3_rag_user_prefix(n3)
            evidence_stage3_extra = "\n" + "\n".join(ev3_lines) + "\n"
            print("📚 [第三阶段] 已针对 report JSON 追加检索知识库片段。")
        else:
            stage3_rag_prefix = (
                "【第三阶段·知识库追加检索】\n"
                "（本次针对 report 的追加检索未返回片段，本阶段请仅凭下方 JSON 与工程常识推断。）\n\n---\n\n"
            )

    messages = [{"role": "system", "content": sys_prompt}]
    if has_rag_chunks:
        print("🧠 [AI 专家已注入知识库片段（进阶工况检索），开始深度探讨]...")
    elif retriever:
        print("🧠 [AI 专家开始深度探讨]（知识库已连接但进阶工况检索无命中片段）...")
    else:
        print("🧠 [AI 专家开始深度探讨]（未配置本地知识库）...")

    if has_workspace:
        stage3_tail = (
            "【第三阶段任务】\n"
            "【物理前提】本 report 与进阶 JSON 对应的是 **中子通量（中子水平）** 相关测点；共线、同步、极值、工况切换等统计现象须在 **中子探测/仪控链路/冗余与标定** 语境下解释，勿按无关工艺量臆断。\n"
            "1）若本消息开头附有【第三阶段手册摘录】与 **R1…** 编号：请先说明**哪些摘录**与 report 中的现象（共线、同步、排行、极值等）**可能相关**，并标 **R 编号**；"
            "勿使用系统提示里的 [1][2] 指代本段摘录。\n"
            "2）随后用 **2～3 段连贯叙述** 写工程推断（勿按 JSON 章节复读表格）：从高度共线/同步群组/传导/极值中提炼 **1～2 条**最可信的系统级解释及优先理由；"
            "写清与第一、二阶段（进阶 JSON）是互相印证还是存在张力。\n"
            "3）写出 **1～2 个关键不确定点** 及各自一句验证思路（勿展开成第四阶段的排查清单）。\n"
        )
        stage3_body = stage3_rag_prefix + (
            "【前提】以下分析默认数据来自 **中子通量（中子水平）** 测量链（堆芯或堆外探测通道）；变量名中的 RIC 等按核测中子电流/通量类信号理解。\n\n"
            "下面这份 JSON 来自同案例目录下的 **report.txt**（零先验体检、拓扑、排行、传导与极值等）。\n"
            f"```json\n{workspace_snapshot_str}\n```\n\n"
            + stage3_tail
        )
    else:
        stage3_body = (
            "当前目录**未提供** report.txt 转化而来的 JSON。"
            "请用一小段说明缺失，并仅根据前两阶段已讨论的进阶全局结论作**有限**推断；**禁止**编造拓扑共线、传导链路或极值档案等未给出的数据。"
        )

    stage4_body = (
        "本阶段**只服务于第二阶段「异常机理剖析」**：对策必须**沿着该阶段已写明的三种机理、手册要点与未决点**展开（例如链路/采集/通信 vs 物理中子场变化等），"
        "用 **一两段话** 写出**优先排查与操作建议**（查什么、为什么），对准机理里**最可疑的一两处**即可。\n"
        "**禁止**以第三阶段为重点去编排对策主线（例如不要把「高度共线=1、同步群组形态、极值数值对比」等**第三阶段的统计/物理量关系叙述**当作排查顺序的主体）；第三阶段仅供背景，若与第二阶段机理矛盾，**仅用一句**说明以何者为准及理由，**正文仍以第二阶段机理为主轴**。\n"
        "**不要**再罗列第一阶段的变量/时间表。\n"
        + (
            " 与手册对应的动作须点明依据哪份文献、[n] 及条文要义（概括即可）。"
            if has_rag_chunks
            else " 基于工程判断写出优先动作即可。"
        )
    )

    dialogue_steps = [
        (
            "【第一阶段：数据基础总览】",
            (
                f"这是一份 JSON 数据：\n```json\n{json_global_str}\n```\n"
                "包含几个变量？报警频率高吗？请读取 json 分别将每个变量发生的状况不同罗列一下。"
                f"请在叙述阶段按照如下格式：**{{变量名}}**：孤立零点有n个，尖峰总计m次，最高峰值为x各出现a次，其余尖峰事件共b次。持续时间从s秒到t秒不等。"
                "注意：isolated_zeros 是零值的意思。spikes_summary 是尖峰统计。此外需要引用其它变量时请使用变量名。"
            ),
        ),
        (
            "【第二阶段：异常机理剖析】",
            "承接上文，**不要复述**第一阶段已罗列的变量清单和时间点。"
            + (
                " 请先明确写出：你**参考了对照表中哪几条手册（写出文件名，并标 [1][2]…）**，各摘录里**哪句话/哪类规定**与当前现象相关（用概括转述，勿大段照抄）；"
                "然后再给出三种最有可能的机理，每种机理单独成一段自然叙述。"
                if has_rag_chunks
                else " 当前无手册：委婉地说明无法对照条文；再基于 JSON 与工程常识给出三种可能机理，每种单独成一段；勿使用 [n]。"
            ),
        ),
        (
            "【第三阶段：零先验与拓扑/传导综合】",
            stage3_body,
        ),
        (
            "【第四阶段：针对第二阶段机理的排查建议】",
            stage4_body,
        ),
    ]

    final_report = ""
    for stage_title, prompt in dialogue_steps:
        print(f"\n👨‍💻 厂长提问: {stage_title.strip('【】')}...")
        messages.append({"role": "user", "content": prompt})

        reply = client.chat(model=MODEL_NAME, messages=messages, options={"temperature": 0.2})['message']['content']
        print(f"🤖 专家回复完成。")

        messages.append({"role": "assistant", "content": reply})
        final_report += f"{stage_title}\n{reply}\n\n"

    full_evidence = evidence_str + (evidence_stage3_extra if evidence_stage3_extra else "")
    final_report += f"--------------------------------------------------\n【附录：知识库出处编号与文献条目】\n{full_evidence}\n"
    return final_report

# ==========================================
# 🚀 4. 主流程控制器
# ==========================================
def process_report(filepath):
    filepath = filepath.strip('"\' ')
    if not os.path.exists(filepath):
        print(f"❌ 错误：找不到文件 {filepath}")
        return
    
    file_dir, file_name = os.path.split(filepath)
    name_no_ext = os.path.splitext(file_name)[0]
    out_txt = os.path.join(file_dir, f"{name_no_ext}_AI专家诊断书.txt")
    out_json = os.path.join(file_dir, f"{name_no_ext}_数据快照.json")
    
    print(f"\n🚀 [启动任务] 读取报告: {file_name}")
    with open(filepath, 'r', encoding='utf-8') as f:
        txt_content = f.read()
        
    print("⚙️ [数据降维] 提取核心特征生成 JSON...")
    if "【零先验特征提取报告】" in txt_content or "【数据初始化与体检报告】" in txt_content:
        snapshot_str = parse_workspace_report_to_json(txt_content)
        with open(out_json, "w", encoding="utf-8") as jf:
            jf.write(snapshot_str)
        final_diagnosis = analyze_json_with_llm("[]", snapshot_str)
    else:
        json_data = parse_report_to_json(txt_content)
        with open(out_json, "w", encoding="utf-8") as jf:
            jf.write(json_data)
        final_diagnosis = analyze_json_with_llm(json_data, None)

    print("📝 [生成报告] 正在写入最终诊断书...")
    with open(out_txt, 'w', encoding='utf-8') as f:
        f.write("==================================================\n")
        f.write("      核测中子电流 - AI 首席专家诊断书\n")
        f.write("==================================================\n\n")
        f.write(final_diagnosis)
        
    print(f"✅ [任务完成] 报告已保存至: {out_txt}")


def process_folder(folder_path):
    """在文件夹内自动查找 *进阶全局工况报告.txt 与 report.txt，双 JSON 驱动四阶段诊断。"""
    folder = os.path.abspath(folder_path.strip('"\''))
    if not os.path.isdir(folder):
        print(f"❌ 不是有效目录: {folder_path}")
        return

    adv, rep = discover_case_reports(folder)
    if not adv and not rep:
        print(
            "❌ 目录内未找到任何数据源。需要至少其一：\n"
            "  · 文件名以「进阶全局工况报告.txt」结尾的文件\n"
            "  · 同目录下的 report.txt"
        )
        return

    json_global = "[]"
    if adv:
        with open(adv, "r", encoding="utf-8") as f:
            json_global = parse_report_to_json(f.read())
        print(f"   ✓ 进阶全局: {os.path.basename(adv)}")
    else:
        print("   ⚠ 未找到 *进阶全局工况报告.txt — 第一、二阶段将仅有空进阶 JSON（[]）")

    workspace_snap = None
    if rep:
        with open(rep, "r", encoding="utf-8") as f:
            workspace_snap = parse_workspace_report_to_json(f.read())
        print(f"   ✓ report: {os.path.basename(rep)}")
    else:
        print("   ⚠ 未找到 report.txt — 第三阶段将说明缺失，仅作有限推断")

    base = os.path.basename(folder.rstrip(os.sep))
    out_json_adv = os.path.join(folder, f"{base}_进阶全局工况_数据快照.json")
    out_json_rep = os.path.join(folder, f"{base}_report_数据快照.json")
    out_txt = os.path.join(folder, f"{base}_AI专家诊断书.txt")

    with open(out_json_adv, "w", encoding="utf-8") as jf:
        jf.write(json_global)
    if workspace_snap:
        with open(out_json_rep, "w", encoding="utf-8") as jf:
            jf.write(workspace_snap)

    print(f"\n🚀 [文件夹任务] 目录: {folder}\n   输出前缀: {base}")
    final_diagnosis = analyze_json_with_llm(json_global, workspace_snap)

    print("📝 [生成报告] 正在写入最终诊断书...")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("==================================================\n")
        f.write("      核测中子电流 - AI 首席专家诊断书\n")
        f.write("==================================================\n\n")
        f.write(final_diagnosis)

    print(f"✅ [任务完成] 诊断书: {out_txt}")
    print(f"   进阶全局 JSON: {out_json_adv}")
    if workspace_snap:
        print(f"   report 快照 JSON: {out_json_rep}")

if __name__ == "__main__":
    print("=" * 55)
    print("☢️ 核电智能预检台 (文件夹双报告 / 单 TXT -> JSON -> LLM+RAG) 已就绪")
    print("=" * 55)
    while True:
        target = input("\n📁 请输入案例文件夹路径，或单个 TXT 文件路径 (输入 quit 退出): ")
        if target.lower() in ['quit', 'exit']:
            break
        p = target.strip('"\'')
        if os.path.isdir(p):
            process_folder(p)
        else:
            process_report(p)