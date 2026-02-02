import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# ================= 1. 系统配置 =================
st.set_page_config(page_title="双时点指挥官(极速版)", layout="wide", page_icon="⚡")

# ================= 2. 核心功能：新浪财经极速接口 =================
def get_sina_quotes(symbol_map):
    """
    使用新浪财经接口抓取，速度极快。
    """
    quotes = {}
    
    # 1. 构建查询字符串
    # 规则：5/6开头->sh, 0/1/3开头->sz (简单粗暴但有效)
    query_list = []
    code_to_name = {} # 建立 code -> name 的反向索引
    
    for name, code in symbol_map.items():
        code_str = str(code).strip()
        # 自动补全前缀
        if code_str.startswith(('5', '6')):
            full_code = f"sh{code_str}"
        elif code_str.startswith(('0', '1', '3')):
            full_code = f"sz{code_str}"
        else:
            full_code = code_str # 如果用户自己填了前缀
            
        query_list.append(full_code)
        code_to_name[full_code] = name

    if not query_list:
        return {}

    # 2. 发送请求 (只需一次请求)
    url = f"http://hq.sinajs.cn/list={','.join(query_list)}"
    headers = {"Referer": "http://finance.sina.com.cn"}
    
    try:
        r = requests.get(url, headers=headers, timeout=3) # 3秒超时，防止卡死
        if r.status_code != 200:
            st.error("无法连接到行情服务器")
            return {}
            
        # 3. 解析数据
        # 返回格式：var hq_str_sh512480="半导体ETF,0.850,0.851,0.832...";
        lines = r.text.split('\n')
        for line in lines:
            if '="' in line:
                # 提取代码
                eq_code = line.split('="')[0].split('_')[-1] # sh512480
                # 提取数据串
                data_str = line.split('="')[1].strip('";')
                data_parts = data_str.split(',')
                
                if len(data_parts) > 3:
                    yesterday_close = float(data_parts[2])
                    current_price = float(data_parts[3])
                    
                    # 如果停牌或未开盘(current=0)，用昨日收盘价
                    if current_price == 0:
                        current_price = yesterday_close
                    
                    if yesterday_close > 0:
                        pct_change = ((current_price - yesterday_close) / yesterday_close) * 100
                        # 找到对应的基金名称
                        if eq_code in code_to_name:
                            quotes[code_to_name[eq_code]] = round(pct_change, 2)
                            
    except Exception as e:
        st.warning(f"行情抓取部分超时或失败，已自动切换为手动模式。错误: {e}")
        return {}
        
    return quotes

# ================= 3. 数据初始化 =================
if 'portfolio' not in st.session_state:
    default_data = {
        "基金名称": ["华夏电网设备", "国泰油气ETF", "华夏A500", "永赢半导体", "华安黄金联接", "科创50联接"],
        "类型": ["场外", "场内", "场外", "场外", "场外", "场外"],
        # 这里填纯数字代码即可，系统会自动识别 sh/sz
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
    
    if st.button("🔄 刷新行情 (Sina高速)", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    # 抓取逻辑
    if not st.session_state.portfolio.empty:
        monitor_map = dict(zip(
            st.session_state.portfolio["基金名称"], 
            st.session_state.portfolio["监控代码"]
        ))
        
        with st.spinner('连接新浪财经接口...'):
            realtime_quotes = get_sina_quotes(monitor_map)
    else:
        realtime_quotes = {}

    # 允许手动修正 (如果抓取失败，这里可以手动填)
    with st.expander("📡 实时数据校准", expanded=True):
        final_quotes = {}
        for name in st.session_state.portfolio["基金名称"].unique():
            auto_val = realtime_quotes.get(name, 0.0)
            # 如果抓取失败，这里仍然可以手动输入
            final_quotes[name] = st.number_input(
                f"{name} (%)", 
                value=float(auto_val), 
                step=0.1, 
                format="%.2f"
            )

# ================= 5. 核心逻辑处理 =================
def process_portfolio(df, quotes):
    res = df.copy()
    
    # 使用 final_quotes (包含自动抓取 + 手动修正)
    res["实时涨跌幅"] = res["基金名称"].map(quotes).fillna(0.0)
    
    res["预估净值"] = res.apply(lambda x: x["昨日净值"] * (1 + (x["实时涨跌幅"]/100) * 0.95), axis=1)
    res["当前市值"] = res["预估净值"] * res["持有份额"]
    res["预估盈亏%"] = (res["预估净值"] - res["持仓成本"]) / res["持仓成本"] * 100
    
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
    processed_df = process_portfolio(st.session_state.portfolio, final_quotes)
else:
    processed_df = pd.DataFrame()

# ================= 6. 主界面 =================
st.title("⚡ 双时点指挥官 (Sina Lite)")

if not processed_df.empty:
    total_assets = processed_df["当前市值"].sum()
    daily_pnl = (processed_df["当前市值"] - (processed_df["昨日净值"] * processed_df["持有份额"])).sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("🛡️ 组合总市值", f"¥{total_assets:,.0f}", f"今日预估: {daily_pnl:+.0f}元")
    
    # 颜色根据盈亏变
    pnl_color = "red" if daily_pnl < 0 else "green"
    if daily_pnl < -2000:
        st.warning(f"⚠️ 今日预估亏损较大，请检查【禁区监控】是否需要锁仓")

st.divider()

tab1, tab2, tab3 = st.tabs(["📊 战术看板", "📝 自动剧本", "⚙️ 持仓/代码管理"])

with tab1:
    st.subheader("📦 场外持仓 (盲盒透视)")
    otc_df = processed_df[processed_df["类型"]=="场外"]
    for _, row in otc_df.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            c1.markdown(f"**{row['基金名称']}**")
            c1.caption(f"追踪代码: {row['监控代码']}")
            
            c2.markdown(f"持有 **{row['持有天数']}** 天")
            c2.progress(row['解禁进度'], text=row['状态文本'])
            
            c3.metric("实时估值", f"{row['实时涨跌幅']}%", f"{row['预估盈亏%']:.2f}%")
            
            if "禁区" in row['状态文本']:
                c4.error("🔒 锁仓")
            elif row['预估盈亏%'] < -5 and "自由" in row['状态文本']:
                c4.warning("👀 关注")
            else:
                c4.success("✅ 持有")

    st.subheader("⚔️ 场内ETF")
    col_etf = st.columns(3)
    for i, (_, row) in enumerate(processed_df[processed_df["类型"]=="场内"].iterrows()):
        with col_etf[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{row['基金名称']}**")
                st.metric("实时涨跌", f"{row['实时涨跌幅']}%")

with tab2:
    st.markdown("### 🤖 战术剧本")
    report_text = f"# 📅 {datetime.now().strftime('%Y-%m-%d')} 战术快照\n\n## 🔥 实时盘面\n"
    for name, chg in final_quotes.items():
        if chg != 0: report_text += f"- {name}: {chg}%\n"
    
    report_text += "\n## 🚨 禁区预警\n"
    locked = processed_df[(processed_df["类型"]=="场外") & (processed_df["持有天数"]<7)]
    if not locked.empty:
        for _, f in locked.iterrows():
             report_text += f"- 🔴 {f['基金名称']}: 处于7天禁区，**严禁赎回**。\n"
    else:
        report_text += "目前无禁区内持仓。\n"
    
    st.code(report_text)

with tab3:
    st.info("提示：请在【监控代码】列填入纯数字代码（如 512480），系统会自动识别沪深市场。")
    edited_df = st.data_editor(st.session_state.portfolio, num_rows="dynamic", use_container_width=True)
    st.session_state.portfolio = edited_df
