import streamlit as st
import pandas as pd
from datetime import datetime

# ================= 页面配置 =================
st.set_page_config(page_title="双时点基金指挥官", layout="wide", page_icon="📈")

# ================= 初始化 Session State (数据持久化) =================
# 如果是第一次打开，初始化一个默认的示例数据
if 'portfolio' not in st.session_state:
    default_data = {
        "基金名称": ["华夏电网设备", "国泰油气ETF", "华夏A500", "永赢半导体", "华安黄金联接"],
        "代码": ["012345", "513350", "019000", "005678", "000216"],
        "类型": ["场外", "场内", "场外", "场外", "场外"],
        "持有天数": [15, 2, 3, 45, 5],
        "持仓成本": [1.1500, 1.4300, 1.2450, 1.3500, 3.8500],
        "昨日净值": [1.2189, 1.4026, 1.2414, 1.6878, 3.6984],
        "对应指数": ["特高压", "油气", "沪深300", "半导体", "黄金"]
    }
    st.session_state.portfolio = pd.DataFrame(default_data)

# ================= 侧边栏：指挥官控制台 =================
st.sidebar.header("🎛️ 战术控制台")
time_mode = st.sidebar.radio("当前战术时点", ["09:00 盘前预埋", "14:30 盘中执行"], index=1)

st.sidebar.divider()
st.sidebar.subheader("📊 实时指数录入")
st.sidebar.caption("请手动输入当前看盘软件上的指数涨跌幅")

# 动态提取数据中出现过的指数，生成输入框
unique_indices = st.session_state.portfolio["对应指数"].unique()
index_changes = {}
for idx in unique_indices:
    # 默认给一个0.0的初始值
    index_changes[idx] = st.sidebar.number_input(f"{idx} 涨跌幅(%)", value=0.0, step=0.1, format="%.2f")

# ================= 核心逻辑函数 =================
def calculate_status(row):
    # 1. 计算预估净值
    change_pct = index_changes.get(row["对应指数"], 0)
    est_nav = row["昨日净值"] * (1 + (change_pct / 100) * 0.95) # 0.95为估算折扣
    est_profit_pct = (est_nav - row["持仓成本"]) / row["持仓成本"] * 100
    
    # 2. 判断费率禁区
    fee_status = "🟢 自由"
    fee_color = "green"
    fee_rate = 0.0
    
    if row["类型"] == "场外":
        if row["持有天数"] < 7:
            fee_status = "🔴 禁区(<7天)"
            fee_color = "red"
            fee_rate = 1.5
        elif 7 <= row["持有天数"] < 30:
            fee_status = "🟡 警示(7-30天)"
            fee_color = "orange"
            fee_rate = 0.5
    else:
        fee_status = "⚡ 场内T+0/1"
        fee_color = "blue"

    # 3. 生成战术指令
    instruction = "持有"
    if fee_color == "red":
        instruction = "🔒 锁仓 (规避1.5%惩罚)"
    elif fee_color == "green" and change_pct < -3:
        instruction = "✂️ 建议赎回 (避险)"
    elif row["类型"] == "场内" and abs(change_pct) > 2:
        instruction = "🔥 波动操作 (网格/T)"
        
    return pd.Series([est_nav, est_profit_pct, fee_status, fee_rate, instruction])

# ================= 主界面 =================
st.title("🚀 双时点基金战术指挥官 v2.0")

# --- 模块1: 持仓数据管理 (可编辑!) ---
with st.expander("📝 **点击管理持仓数据 (可像Excel一样直接修改)**", expanded=False):
    st.caption("每天开盘前，请在此更新【持有天数】和【昨日净值】")
    # 数据编辑器
    edited_df = st.data_editor(
        st.session_state.portfolio,
        num_rows="dynamic", # 允许添加/删除行
        use_container_width=True,
        column_config={
            "类型": st.column_config.SelectboxColumn(options=["场外", "场内"], required=True),
            "对应指数": st.column_config.TextColumn(help="填入如：半导体、沪深300、黄金"),
        }
    )
    # 实时保存修改到 Session State
    st.session_state.portfolio = edited_df

# --- 模块2: 战术大屏 ---
if not edited_df.empty:
    # 应用计算逻辑
    result_df = edited_df.copy()
    result_df[["预估今日净值", "预估总盈亏%", "费率状态", "赎回费率%", "AI指令"]] = result_df.apply(calculate_status, axis=1)

    # 分栏展示
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🛡️ 场外战略仓 (盲盒透视)")
        otc_df = result_df[result_df["类型"] == "场外"]
        
        for _, row in otc_df.iterrows():
            # 颜色逻辑
            color = "red" if "禁区" in row["费率状态"] else ("orange" if "警示" in row["费率状态"] else "green")
            
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 3])
                c1.markdown(f"**{row['基金名称']}**")
                c1.caption(f"持有 {row['持有天数']} 天 | {row['对应指数']}")
                
                c2.metric("实时涨跌", f"{index_changes.get(row['对应指数'], 0)}%", delta_color="normal")
                c3.metric("预估净值", f"{row['预估今日净值']:.4f}", f"{row['预估总盈亏%']:.2f}%")
                
                c4.markdown(f":{color}[**{row['费率状态']}**]")
                if "锁仓" in row['AI指令']:
                    c4.error(row['AI指令'])
                else:
                    c4.info(row['AI指令'])

    with col2:
        st.subheader("⚔️ 场内战术仓")
        etf_df = result_df[result_df["类型"] == "场内"]
        for _, row in etf_df.iterrows():
             with st.container(border=True):
                st.markdown(f"**{row['基金名称']}**")
                change = index_changes.get(row['对应指数'], 0)
                st.metric("实时涨跌", f"{change}%")
                if abs(change) > 2:
                    st.warning("⚠️ 触发波动操作阈值")

else:
    st.info("请先在上方👆添加持仓数据")

# ================= 底部：费用计算器 =================
st.divider()
st.markdown("### 🧮 智能费用拦截器")

cal_col1, cal_col2 = st.columns(2)
with cal_col1:
    selected_fund_name = st.selectbox("选择要测试赎回的基金", result_df["基金名称"].unique() if not result_df.empty else [])

if selected_fund_name:
    # 找到该基金数据
    fund_data = result_df[result_df["基金名称"] == selected_fund_name].iloc[0]
    
    with cal_col2:
        redeem_amt = st.number_input("打算赎回金额 (¥)", value=10000, step=1000)
    
    cost = redeem_amt * (fund_data["赎回费率%"] / 100)
    real_loss = 0
    if fund_data["预估总盈亏%"] < 0:
        real_loss = redeem_amt * (abs(fund_data["预估总盈亏%"])/100)

    st.write(f"当前状态：**{fund_data['费率状态']}**")
    
    if fund_data["赎回费率%"] > 0.5:
        st.error(f"🛑 **严重警告**：赎回将直接损失手续费 ¥{cost:.2f}！\n加上市值亏损，实际离场损失约 ¥{cost + real_loss:.2f}。")
    elif fund_data["赎回费率%"] > 0:
        st.warning(f"⚠️ **提醒**：赎回手续费 ¥{cost:.2f}。")
    else:
        st.success("✅ **通过**：当前无赎回手续费，可自由操作。")