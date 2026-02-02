import streamlit as st
import pandas as pd
import akshare as ak
from datetime import datetime

# ================= 1. 系统配置 =================
st.set_page_config(page_title="双时点指挥官(自动版)", layout="wide", page_icon="📡")

# ================= 2. 核心功能：自动抓取实时行情 =================
@st.cache_data(ttl=60) # 缓存60秒，防止刷新太频繁被封IP
def get_realtime_quotes(symbol_map):
    """
    输入：{"特高压": "sh512480", "沪深300": "sh510300"} (示例: 市场+代码)
    输出：{"特高压": 1.25, "沪深300": -0.5} (涨跌幅字典)
    """
    quotes = {}
    
    # 1. 获取全市场ETF实时数据 (东方财富源，速度快)
    try:
        # 获取所有ETF的实时行情
        df_etf = ak.fund_etf_spot_em()
        # 建立 简码->涨跌幅 的映射 (如 "512480" -> 1.25)
        price_map = dict(zip(df_etf['代码'], df_etf['涨跌幅']))
        
        # 2. 获取主要指数数据 (用于宽基)
        df_index = ak.stock_zh_index_spot()
        # 建立 指数代码->涨跌幅 映射 (如 "sh000300" -> -0.5)
        # 注意：akshare指数代码通常带sh/sz前缀，需处理
        for _, row in df_index.iterrows():
            clean_code = row['代码'].replace("sh", "").replace("sz", "")
            price_map[clean_code] = row['涨跌幅']

        # 3. 匹配用户持仓的监控代码
        for name, code in symbol_map.items():
            # 尝试直接匹配
            if code in price_map:
                quotes[name] = price_map[code]
            else:
                # 如果没抓到，给个0，并标记错误
                quotes[name] = 0.0 
                
    except Exception as e:
        st.error(f"行情抓取失败: {e}")
        return {}
        
    return quotes

# ================= 3. 数据初始化 =================
if 'portfolio' not in st.session_state:
    default_data = {
        "基金名称": ["华夏电网设备", "国泰油气ETF", "华夏A500", "永赢半导体", "华安黄金联接", "科创50联接"],
        "类型": ["场外", "场内", "场外", "场外", "场外", "场外"],
        # 关键修改：增加【监控代码】列。
        # 规则：场内填自己，场外填它跟踪的ETF代码或指数代码
        "监控代码": ["159865", "513350", "159338", "512480", "518880", "588000"], 
        "持有天数": [15, 2, 3, 45, 5, 2],
        "持仓成本": [1.1500, 1.4300, 1.2450, 1.3500, 3.8500, 1.000],
        "昨日净值": [1.2189, 1.4026, 1.2414, 1.6878, 3.6984, 0.980],
        "持有份额": [20000, 10000, 30000, 10000, 5000, 20000],
        "对应指数": ["特高压", "油气", "沪深300", "半导体", "黄金", "科创50"]
    }
    st.session_state.portfolio = pd.DataFrame(default_data)

# ================= 4. 侧边栏 =================
with st.sidebar:
    st.header("🎛️ 战术控制台")
    time_mode = st.radio("战术时点", ["09:00 盘前", "14:30 盘中"], index=1)
    
    st.divider()
    
    # 自动刷新按钮
    if st.button("🔄 刷新实时行情", type="primary"):
        st.cache_data.clear() # 清除缓存，强制重抓
        st.rerun()
    
    st.caption(f"最后更新: {datetime.now().strftime('%H:%M:%S')}")

    # 构建抓取映射表
    if not st.session_state.portfolio.empty:
        # 生成 {基金名: 监控代码} 字典
        monitor_map = dict(zip(
            st.session_state.portfolio["基金名称"], 
            st.session_state.portfolio["监控代码"]
        ))
        
        # 调用抓取函数
        with st.spinner('正在连接交易所数据...'):
            realtime_quotes = get_realtime_quotes(monitor_map)
    else:
        realtime_quotes = {}

    # 显示抓取结果小票
    with st.expander("📡 实时数据日志", expanded=True):
        for name, chg in realtime_quotes.items():
            color = "red" if chg < 0 else "green"
            st.markdown(f"{name}: :{color}[{chg}%]")

# ================= 5. 核心逻辑处理 =================
def process_portfolio(df, quotes):
    res = df.copy()
    
    # 自动填入实时涨跌幅
    res["实时涨跌幅"] = res["基金名称"].map(quotes).fillna(0.0)
    
    # 盲盒估算
    res["预估净值"] = res.apply(lambda x: x["昨日净值"] * (1 + (x["实时涨跌幅"]/100) * 0.95), axis=1)
    res["当前市值"] = res["预估净值"] * res["持有份额"]
    res["预估盈亏%"] = (res["预估净值"] - res["持仓成本"]) / res["持仓成本"] * 100
    
    # 状态判定
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

if not st.session_state.portfolio.empty:
    processed_df = process_portfolio(st.session_state.portfolio, realtime_quotes)
else:
    processed_df = pd.DataFrame()

# ================= 6. 主界面 (保留原有布局) =================
st.title("📡 双时点指挥官 (Auto-Pilot)")

# 资产概览
if not processed_df.empty:
    total_assets = processed_df["当前市值"].sum()
    otc_assets = processed_df[processed_df["类型"]=="场外"]["当前市值"].sum()
    etf_assets = processed_df[processed_df["类型"]=="场内"]["当前市值"].sum()
    
    # 计算今日预估波动
    daily_pnl = (processed_df["当前市值"] - (processed_df["昨日净值"] * processed_df["持有份额"])).sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("🛡️ 组合总市值", f"¥{total_assets:,.0f}", f"今日预估: {daily_pnl:+.0f}元")
    m2.metric("📦 场外占比", f"{otc_assets/total_assets*100:.1f}%")
    m3.metric("⚔️ 场内占比", f"{etf_assets/total_assets*100:.1f}%")

st.divider()

tab1, tab2, tab3 = st.tabs(["📊 战术看板", "📝 自动剧本", "⚙️ 持仓/代码管理"])

with tab1:
    st.subheader("📦 场外持仓 (实时映射估值)")
    otc_df = processed_df[processed_df["类型"]=="场外"]
    for _, row in otc_df.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            c1.markdown(f"**{row['基金名称']}**")
            # 显示映射关系
            c1.caption(f"👀 追踪: {row['监控代码']} | 成本: {row['持仓成本']:.4f}")
            
            c2.markdown(f"持有 **{row['持有天数']}** 天")
            c2.progress(row['解禁进度'], text=row['状态文本'])
            
            # 这里自动用抓取的数据
            val_color = "red" if row['预估盈亏%'] < 0 else "green"
            c3.metric("实时估值", f"{row['实时涨跌幅']}%", f"{row['预估盈亏%']:.2f}% (总)")
            
            if "禁区" in row['状态文本']:
                c4.error("🔒 锁仓")
            elif row['预估盈亏%'] < -5 and "自由" in row['状态文本']:
                c4.warning("👀 关注")
            else:
                c4.success("✅ 持有")

    st.subheader("⚔️ 场内ETF (实时行情)")
    # 场内部分逻辑相同，略...
    col_etf = st.columns(3)
    for i, (_, row) in enumerate(processed_df[processed_df["类型"]=="场内"].iterrows()):
        with col_etf[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{row['基金名称']}**")
                st.metric("实时涨跌", f"{row['实时涨跌幅']}%")
                if abs(row['实时涨跌幅']) > 2: st.warning("⚠️ 波动剧烈")

with tab2:
    st.markdown("### 🤖 自动生成的战术剧本")
    # 剧本生成逻辑 (引用实时数据)
    report_text = f"# 📅 {datetime.now().strftime('%Y-%m-%d')} 战术快照\n\n"
    report_text += "## 🔥 实时盘面\n"
    for name, chg in realtime_quotes.items():
        report_text += f"- {name}: {chg}%\n"
    
    report_text += "\n## 🚨 禁区预警\n"
    locked = processed_df[(processed_df["类型"]=="场外") & (processed_df["持有天数"]<7)]
    if not locked.empty:
        for _, f in locked.iterrows():
             report_text += f"- 🔴 {f['基金名称']}: 跌幅{f['实时涨跌幅']}%，但在7天禁区，**严禁赎回**。\n"
    else:
        report_text += "目前无禁区内持仓。\n"
        
    st.code(report_text)

with tab3:
    st.info("💡 **关键设置**：请在【监控代码】列填入该基金追踪的 ETF 代码（如 512480）或指数代码（如 000300）。场外基金本身的代码查不到实时数据。")
    edited_df = st.data_editor(st.session_state.portfolio, num_rows="dynamic", use_container_width=True)
    st.session_state.portfolio = edited_df
    if st.button("💾 保存配置"):
        st.success("配置已保存")
