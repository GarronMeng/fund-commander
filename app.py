import streamlit as st
import pandas as pd
from datetime import datetime

# ================= 1. 系统配置与常量 =================
st.set_page_config(page_title="双时点基金指挥官 v3.1", layout="wide", page_icon="⚔️")

# 月度主题库
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
        "持有份额": [20000, 10000, 30000, 10000, 5000, 20000],
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
    if not st.session_state.portfolio.empty:
        unique_indices = st.session_state.portfolio["对应指数"].unique()
        index_changes = {}
        col_input1, col_input2 = st.columns(2)
        
        for i, idx in enumerate(unique_indices):
            with (col_input1 if i % 2 == 0 else col_input2):
                index_changes[idx] = st.number_input(f"{idx}%", value=0.0, step=0.1, format="%.2f")
    else:
        index_changes = {}

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
            return "⚡ 场内", "blue", 0, 1.0 
        
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
if not st.session_state.portfolio.empty:
    processed_df = process_portfolio(st.session_state.portfolio, index_changes)
else:
    processed_df = pd.DataFrame()

# ================= 5. 主界面布局 =================
st.title("🚀 双时点基金战术指挥官 v3.1")

if processed_df.empty:
    st.warning("⚠️ 请先在【持仓管理】Tab中添加持仓数据")
else:
    # --- 顶栏：资产概览 ---
    total_assets = processed_df["当前市值"].sum()
    otc_assets = processed_df[processed_df["类型"]=="场外"]["当前市值"].sum()
    etf_assets = processed_df[processed_df["类型"]=="场内"]["当前市值"].sum()

    m1, m2, m3 = st.columns(3)
    m1.metric("🛡️ 组合总市值", f"¥{total_assets:,.0f}")
    if total_assets > 0:
        m2.metric("📦 场外战略仓 (70%)", f"¥{otc_assets:,.0f}", f"占比 {otc_assets/total_assets*100:.1f}%")
        m3.metric("⚔️ 场内战术仓 (30%)", f"¥{etf_assets:,.0f}", f"占比 {etf_assets/total_assets*100:.1f}%")

    st.divider()

    # --- 核心功能区 (Tabs) ---
    tab1, tab2, tab3 = st.tabs(["📊 战术看板 (Visual)", "📝 自动剧本 (Text)", "⚙️ 持仓管理 (Data)"])

    with tab1:
        # 场外监控区
        st.subheader("📦 场外持仓监控 (重点看红绿灯)")
        
        otc_df = processed_df[processed_df["类型"]=="场外"]
        if not otc_df.empty:
            for _, row in otc_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                    
                    # 列1：基础信息
                    c1.markdown(f"**{row['基金名称']}**")
                    c1.caption(f"指数：{row['对应指数']} | 成本：{row['持仓成本']:.4f}")
                    
                    # 列2：持有天数与进度条
                    c2.markdown(f"持有 **{row['持有天数']}** 天")
                    c2.progress(row['解禁进度'], text=row['状态文本'])
                    
                    # 列3：估值数据 (这里修复了语法错误)
                    val_color = "red" if row['预估盈亏%'] < 0 else "green"
                    c3.metric("预估净值", f"{row['预估净值']:.4f}", f"{row['预估盈亏%']:.2f}%")
                    
                    # 列4：AI建议图标
                    if "禁区" in row['状态文本']:
                        c4.error("🔒 锁仓")
                    elif row['预估盈亏%'] < -5 and "自由" in row['状态文本']:
                        c4.warning("👀 关注")
                    else:
                        c4.success("✅ 持有")
        else:
            st.info("暂无场外持仓")

        # 场内监控区
        st.subheader("⚔️ 场内ETF监控")
        etf_df = processed_df[processed_df["类型"]=="场内"]
        if not etf_df.empty:
            col_etf = st.columns(3)
            for i, (_, row) in enumerate(etf_df.iterrows()):
                with col_etf[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{row['基金名称']}**")
                        change = row['实时涨跌幅']
                        st.metric("实时涨跌", f"{change}%")
                        
                        if time_mode == "14:30 盘中执行":
                            if change > 2:
                                st.markdown("🔥 **热点**: 5日线持有")
                            elif change < -2:
                                st.markdown("❄️ **走弱**: 注意止损")
                            else:
                                st.markdown("⚖️ **震荡**: 观望")
        else:
            st.info("暂无场内持仓")

    with tab2:
        st.subheader("📜 AI 战术剧本生成器")
        st.caption("直接复制下方文本，用于复盘或记录")
        
        report_text = f"""
# 📅 {datetime.now().strftime('%Y-%m-%d')} {time_mode} 战术剧本

## 🔥 热点雷达
- **本月主线**：{theme}
- **今日盘面**：{', '.join([f"{k} {v}%" for k,v in index_changes.items() if abs(v)>0.1])}

## 📊 禁区监控 (场外)
"""
        # 禁区逻辑生成
        locked_funds = processed_df[(processed_df["类型"]=="场外") & (processed_df["持有天数"]<7)]
        if not locked_funds.empty:
            report_text += "- 🔴 **绝对禁止赎回 (<7天)**：\n"
            for _, f in locked_funds.iterrows():
                report_text += f"  - {f['基金名称']} (持有{f['持有天数']}天，预估{f['预估盈亏%']:.2f}%)\n"
        else:
            report_text += "- 🟢 无处于7天禁区内的基金\n"

        report_text += "\n## 🎯 交易指令\n"
        
        if time_mode == "09:00 盘前预埋":
            report_text += "**【场外部分】**\n- 今日重点观察指数关键点位，若大跌不破支撑可考虑追加。\n- 警惕 <7天 持仓的赎回费刺客。\n\n**【场内部分】**\n- 制定预埋单：若热点板块回踩5日线，可分批通过ETF介入。"
        else:
            # 14:30 逻辑
            report_text += "**【场内ETF执行】**\n"
            for _, f in processed_df[processed_df["类型"]=="场内"].iterrows():
                act = "持有"
                if f['实时涨跌幅'] > 2: act = "确认强势，继续持有或加仓"
                elif f['实时涨跌幅'] < -2: act = "趋势走坏，考虑止损"
                report_text += f"- {f['基金名称']}: 当前{f['实时涨跌幅']}% → 建议：{act}\n"
                
            report_text += "\n**【场外赎回决策】**\n"
            free_funds = processed_df[(processed_df["类型"]=="场外") & (processed_df["持有天数"]>=30)]
            if not free_funds.empty:
                for _, f in free_funds.iterrows():
                    if f['实时涨跌幅'] < -1.5:
                        report_text += f"- {f['基金名称']}: 跌幅扩大，且费率为0，可考虑赎回避险。\n"
                    else:
                        report_text += f"- {f['基金名称']}: 趋势正常，建议锁仓。\n"
            else:
                report_text += "- 无可自由赎回的场外基金。\n"

        st.code(report_text, language="markdown")

    with tab3:
        st.markdown("### 📝 数据编辑器")
        edited_df = st.data_editor(
            st.session_state.portfolio,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "类型": st.column_config.SelectboxColumn(options=["场外", "场内"], required=True),
                "持有份额": st.column_config.NumberColumn(help="用于计算总市值"),
            }
        )
        st.session_state.portfolio = edited_df
        if st.button("💾 保存数据更改"):
            st.success("数据已更新，请切换Tab查看最新分析")

    # ================= 6. 底部：费用计算器 =================
    with st.expander("🧮 交易费用预演 (必点)", expanded=True):
        col_c1, col_c2, col_c3 = st.columns([2,1,1])
        with col_c1:
            # 安全检查：确保有数据可选
            fund_options = processed_df["基金名称"].unique()
            target = st.selectbox("拟操作标的", fund_options) if len(fund_options) > 0 else None
        
        if target:
            # 查找数据
            t_row = processed_df[processed_df["基金名称"]==target].iloc[0]
            
            with col_c2:
                amt = st.number_input("拟赎回金额", value=10000)
            
            fee = amt * (t_row["赎回费率"]/100)
            
            with col_c3:
                st.metric("预计手续费损耗", f"¥{fee:.1f}")
                if t_row["赎回费率"] >= 1.5:
                    st.error("🛑 **禁止操作**")
                elif t_row["赎回费率"] > 0:
                    st.warning("⚠️ **谨慎**")
                else:
                    st.success("✅ **通行**")
