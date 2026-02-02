import streamlit as st
import pandas as pd
from datetime import datetime

# ================= 1. 系统配置与常量 =================
st.set_page_config(page_title="双时点基金指挥官 v3.0", layout="wide", page_icon="⚔️")

# 月度主题库 (根据你的需求文档)
MONTHLY_THEMES = {
    1: "年报预增 / 高股息 / 春节消费",
    2: "春节错位 / 避险 / 两会前博弈",
    3: "两会 (新质生产力/科技)",
    4: "一季报业绩验证",
    6: "半年报 / 电力夏峰 / 苹果链",
    7: "中报行情 / 军工",
    9: "金九银十 / 华为链",
    12: "估值切换 / 机构排名战"
}

# ================= 2. 数据初始化 (Session State) =================
if 'portfolio' not in st.session_state:
    # 默认示例数据
    default_data = {
        "基金名称": ["华夏电网设备", "国泰油气ETF", "华夏A500", "永赢半导体", "华安黄金联接", "华夏科创50"],
        "代码": ["012345", "513350", "019000", "005678", "000216", "588000"],
        "类型": ["场外", "场内", "场外", "场外", "场外", "场外"],
        "持有天数": [15, 2, 3, 45, 5, 2],
        "持仓成本": [1.1500, 1.4300, 1.2450, 1.3500, 3.8500, 1.000],
        "昨日净值": [1.2189, 1.4026, 1.2414, 1.6878, 3.6984, 0.980],
        "持有份额": [20000, 10000, 30000, 10000, 5000, 20000], # 新增份额用于算市值
        "对应指数": ["特高压", "油气", "沪深300", "半导体", "黄金", "科创50"]
    }
    st.session_state.portfolio = pd.DataFrame(default_data)

# ================= 3. 侧边栏：指挥与输入 =================
with st.sidebar:
    st.header("🎛️ 战术控制台")
    
    # A. 模式选择
    time_mode = st.radio("当前战术时点", ["09:00 盘前预埋", "14:30 盘中执行"], index=1)
    
    st.divider()
    
    # B. 市场环境输入
    st.subheader("📡 市场情报录入")
    current_month = datetime.now().month
    theme = MONTHLY_THEMES.get(current_month, "业绩/政策真空期")
    st.info(f"📅 **本月主题**: {theme}")
    
    st.markdown("---")
    st.caption("👇 输入实时涨跌幅 (用于盲盒估算)")
    
    # 动态生成指数输入框
    unique_indices = st.session_state.portfolio["对应指数"].unique()
    index_changes = {}
    col_input1, col_input2 = st.columns(2)
    
    for i, idx in enumerate(unique_indices):
        with (col_input1 if i % 2 == 0 else col_input2):
            index_changes[idx] = st.number_input(f"{idx}%", value=0.0, step=0.1, format="%.2f")

# ================= 4. 核心计算引擎 =================
def process_portfolio(df, inputs):
    res = df.copy()
    
    # A. 基础计算
    res["实时涨跌幅"] = res["对应指数"].map(inputs).fillna(0)
    # 盲盒估算公式：昨日 * (1 + 指数涨跌 * 0.95)
    res["预估净值"] = res.apply(lambda x: x["昨日净值"] * (1 + (x["实时涨跌幅"]/100) * 0.95), axis=1)
    res["当前市值"] = res["预估净值"] * res["持有份额"]
    res["预估盈亏%"] = (res["预估净值"] - res["持仓成本"]) / res["持仓成本"] * 100
    
    # B. 费率与状态判定
    def get_status(row):
        if row["类型"] == "场内":
            return "⚡ 场内", "blue", 0, 1.0 # 1.0是进度条满
        
        days = row["持有天数"]
        if days < 7:
            return "🔴 禁区(1.5%)", "red", 1.5, min(days/7, 1.0)
        elif days < 30:
            return "🟡 警示(0.5%)", "orange", 0.5, min(days/30, 1.0)
        else:
            return "🟢 自由(0%)", "green", 0.0, 1.0

    status_res = res.apply(get_status, axis=1, result_type='expand')
    res[["状态文本", "状态颜色", "赎回费率", "解禁进度"]] = status_res
    
    return res

# 执行计算
processed_df = process_portfolio(st.session_state.portfolio, index_changes)

# ================= 5. 主界面布局 =================
st.title("🚀 双时点基金战术指挥官 v3.0")

# --- 顶栏：资产概览 ---
total_assets = processed_df["当前市值"].sum()
otc_assets = processed_df[processed_df["类型"]=="场外"]["当前市值"].sum()
etf_assets = processed_df[processed_df["类型"]=="场内"]["当前市值"].sum()

m1, m2, m3 = st.columns(3)
m1.metric("🛡️ 组合总市值", f"¥{total_assets:,.0f}")
m2.metric("📦 场外战略仓 (70%)", f"¥{otc_assets:,.0f}", f"占比 {otc_assets/total_assets*100:.1f}%")
m3.metric("⚔️ 场内战术仓 (30%)", f"¥{etf_assets:,.0f}", f"占比 {etf_assets/total_assets*100:.1f}%")

st.divider()

# --- 核心功能区 (Tabs) ---
tab1, tab2, tab3 = st.tabs(["📊 战术看板 (Visual)", "📝 自动剧本 (Text)", "⚙️ 持仓管理 (Data)"])

with tab1:
    # 场外监控区
    st.subheader("📦 场外持仓监控 (重点看红绿灯)")
    
    for _, row in processed_df[processed_df["类型"]=="场外"].iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            
            # 列1：基础信息
            c1.markdown(f"**{row['基金名称']}**")
            c1.caption(f"指数：{row['对应指数']} | 成本：{row['持仓成本']:.4f}")
            
            # 列2：持有天数与进度条
            c2.markdown(f"持有 **{row['持有天数']}** 天")
            c2.progress(row['解禁进度'], text=row['状态文本'])
            
            # 列3：估值数据
            val_color = "red" if row['预估盈亏%'] < 0
