# tools/registry.py

# 1. 导入你散落在各个文件里的工具函数
from tools.anomaly_detector import anomaly_detector
from tools.data_loader import list_data_files_tool,load_and_profile_csv_tool
from tools.spatial_analyzer import global_extremes_scan_tool, get_spatial_snapshot_tool
from tools.stat_analyzer import zero_prior_discovery_tool
from tools.temporal_analyzer import global_time_lag_scan_tool
#from tools.workspace import create_workspace,write_state_json
# from tools.anomaly_detector import advanced_segment_all_tool

# 2. 组装成唯一的本地路由表
LOCAL_TOOL_ROUTER = {
    "anomaly_detector": anomaly_detector,#ok
    "list_data_files_tool": list_data_files_tool,
    "load_and_profile_csv_tool": load_and_profile_csv_tool,#ok
    "global_extremes_scan_tool": global_extremes_scan_tool,#ok
    "get_spatial_snapshot_tool": get_spatial_snapshot_tool,#ok
    "zero_prior_discovery_tool": zero_prior_discovery_tool,#ok
    "global_time_lag_scan_tool": global_time_lag_scan_tool,

    #"create_workspace_tool":create_workspace,
    #"write_state_json_tool":write_state_json,
    # "advanced_segment_all_tool": advanced_segment_all_tool
}

# 3. 提供一个安全的获取接口（可选，但推荐）
def get_tool_function(tool_name):
    """根据大模型提供的字符串名称，返回对应的 Python 函数对象"""
    return LOCAL_TOOL_ROUTER.get(tool_name, None)