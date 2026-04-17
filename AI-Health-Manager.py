import streamlit as st
import requests
from datetime import datetime
import json
import re

# ============= 页面配置 =============
st.set_page_config(page_title="AI个性化健康管理系统", layout="wide", page_icon="🏥")

# ============= 自定义CSS美化 =============
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #f0f2f6 0%, #e9ecef 100%);
    }
    [data-testid="stSidebar"] {
        background-color: #ffffffdd;
        backdrop-filter: blur(8px);
        border-right: 1px solid #dee2e6;
    }
    .chat-message {
        padding: 0.8rem 1rem;
        border-radius: 1.2rem;
        margin-bottom: 0.8rem;
        display: inline-block;
        max-width: 80%;
        clear: both;
        animation: fadeIn 0.2s ease;
    }
    .user-message {
        background-color: #0078ff;
        color: white;
        float: right;
        border-bottom-right-radius: 0.2rem;
    }
    .assistant-message {
        background-color: #e9ecef;
        color: #1e2a3a;
        float: left;
        border-bottom-left-radius: 0.2rem;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(5px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .chat-container {
        overflow-y: auto;
        padding: 1rem;
        background: #ffffffcc;
        border-radius: 1.5rem;
        margin-bottom: 1rem;
        max-height: 500px;
    }
    .stButton > button {
        border-radius: 2rem;
        transition: 0.2s;
    }
    .export-btn {
        background-color: #28a745;
        color: white;
        border: none;
        padding: 0.2rem 0.8rem;
        border-radius: 2rem;
        font-size: 0.8rem;
        margin-left: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ============= 阿里云百炼 API 配置 =============
DASHSCOPE_API_KEY = "sk-4e9118ea830c4ccb945532c51a08b27b"   # 请替换为真实Key
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "deepseek-v3"

# 活动系数映射
ACTIVITY_FACTORS = {
    "久坐（很少运动）": 1.2,
    "轻度（每周1-3天运动）": 1.375,
    "中度（每周3-5天运动）": 1.55,
    "高度（每周6-7天运动）": 1.725,
}

# ============= API调用函数 =============
def call_llm(messages, temperature=0.7):
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 2000
    }
    try:
        response = requests.post(f"{DASHSCOPE_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ API调用失败：{str(e)}"

# ============= 规则计算 =============
def calculate_bmr(height, weight, age, gender):
    if gender == "男":
        return 10 * weight + 6.25 * height - 5 * age + 5
    else:
        return 10 * weight + 6.25 * height - 5 * age - 161

def adjust_calories(tdee, goal):
    if goal == "减肥":
        return tdee - 400
    elif goal == "增肌":
        return tdee + 400
    else:
        return tdee

# ============= 生成健康方案 =============
def generate_health_plan(height, weight, age, gender, goal, activity_level, preference, feedback=""):
    bmr = calculate_bmr(height, weight, age, gender)
    tdee = bmr * ACTIVITY_FACTORS[activity_level]
    target_cal = adjust_calories(tdee, goal)
    prompt = f"""用户信息：身高{height}cm，体重{weight}kg，年龄{age}岁，性别{gender}，目标{goal}，活动水平{activity_level}，饮食偏好{preference if preference else '无'}，每日推荐热量约{target_cal}千卡。
请生成：
1. 一日三餐食谱（含食材、分量、估算热量）
2. 一周运动计划（类型、频率、时长、强度）
输出格式清晰，使用列表或标题。"""
    if feedback:
        prompt += f"\n用户反馈：{feedback}，请根据反馈调整方案。"
    messages = [{"role": "system", "content": "你是专业营养师和健身教练。"}, {"role": "user", "content": prompt}]
    content = call_llm(messages)
    header = f"📊 身体数据计算\n- 基础代谢(BMR): {bmr:.0f} 千卡/天\n- 每日总消耗(TDEE): {tdee:.0f} 千卡/天\n- 推荐每日摄入: {target_cal:.0f} 千卡\n\n"
    return header + content

# ============= 聊天函数（带记忆，默认联网） =============
def chat_with_memory(question, history, user_memory):
    memory_text = ""
    if user_memory:
        memory_text = "你已记住的用户信息：\n" + "\n".join([f"- {k}: {v}" for k, v in user_memory.items()]) + "\n"
    system = f"""你是AI健康助手，回答健康、营养、运动问题。简洁实用。
{memory_text}
如果用户告诉你新的个人信息（如名字、喜好、过敏等），请记住并在后续对话中使用。回复时可直接称呼用户名字（如果有）。
你可以通过联网搜索获取最新信息。"""
    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": question}]
    return call_llm(messages)

# ============= 文件文字识别 =============
def extract_text_from_file(uploaded_file):
    if uploaded_file.type == "text/plain":
        return uploaded_file.read().decode("utf-8")
    elif uploaded_file.type == "application/pdf":
        try:
            import PyPDF2
            from io import BytesIO
            pdf = PyPDF2.PdfReader(BytesIO(uploaded_file.read()))
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            return text if text else "PDF未提取到文字。"
        except:
            return "PDF解析失败，请安装PyPDF2或手动复制。"
    elif uploaded_file.type.startswith("image/"):
        return "【图片OCR】演示版暂未集成OCR服务，建议手动输入文字。实际项目可接入阿里云OCR。"
    else:
        return "不支持的文件类型。"

# ============= 提取用户记忆 =============
def extract_memory_from_text(text, current_memory):
    new_memory = current_memory.copy()
    # 匹配“我叫xxx”
    match_name = re.search(r'[我叫|我是|名字叫|称呼我?为?]\s*([\u4e00-\u9fa5a-zA-Z]+)', text)
    if match_name:
        name = match_name.group(1)
        new_memory["名字"] = name
    # 匹配“不喜欢吃...”
    dislike = re.search(r'不(喜欢|爱吃|要吃)\s*([\u4e00-\u9fa5]+)', text)
    if dislike:
        new_memory["忌口"] = dislike.group(2)
    return new_memory

# ============= 初始化会话状态 =============
if "history_records" not in st.session_state:
    st.session_state.history_records = []      # 存储历史方案
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = []        # 存储聊天会话列表 [{"session_id": "时间", "messages": [], "title": "..."}]
if "current_session_id" not in st.session_state:
    # 创建当前会话
    st.session_state.current_session_id = datetime.now().strftime("%Y%m%d%H%M%S")
    st.session_state.chat_sessions.append({
        "session_id": st.session_state.current_session_id,
        "title": "新对话",
        "messages": [],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
if "user_memory" not in st.session_state:
    st.session_state.user_memory = {}
if "last_plan" not in st.session_state:
    st.session_state.last_plan = ""

# 辅助函数：获取当前会话的消息列表
def get_current_messages():
    for sess in st.session_state.chat_sessions:
        if sess["session_id"] == st.session_state.current_session_id:
            return sess["messages"]
    return []

def set_current_messages(messages):
    for i, sess in enumerate(st.session_state.chat_sessions):
        if sess["session_id"] == st.session_state.current_session_id:
            st.session_state.chat_sessions[i]["messages"] = messages
            # 更新标题（取第一条用户消息的前20字）
            if messages and messages[0]["role"] == "user":
                title = messages[0]["content"][:20] + ("..." if len(messages[0]["content"]) > 20 else "")
                st.session_state.chat_sessions[i]["title"] = title
            break

def add_message(role, content):
    messages = get_current_messages()
    messages.append({"role": role, "content": content, "time": datetime.now().strftime("%H:%M:%S")})
    set_current_messages(messages)

# ============= 侧边栏：历史方案 + 聊天记录 =============
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/health.png", width=60)
    st.title("📜 历史方案")
    if not st.session_state.history_records:
        st.info("暂无历史方案，生成后自动保存")
    else:
        for idx, rec in enumerate(st.session_state.history_records):
            with st.expander(f"{rec['time']} - {rec['goal']}"):
                st.write(f"身高{rec['height']}cm / 体重{rec['weight']}kg")
                st.caption(rec['plan_text'][:150] + "...")
                if st.button("查看完整方案", key=f"view_{idx}"):
                    add_message("assistant", f"📋 历史方案 ({rec['time']})：\n\n{rec['plan_text']}")
                    st.rerun()
    if st.button("🗑️ 清空所有历史方案", use_container_width=True):
        st.session_state.history_records = []
        st.rerun()

    st.divider()
    st.subheader("💬 聊天记录")
    # 显示所有会话列表
    for sess in st.session_state.chat_sessions:
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(f"{sess['title']} ({sess['created_at']})", key=f"sess_{sess['session_id']}", use_container_width=True):
                st.session_state.current_session_id = sess["session_id"]
                st.rerun()
        with col2:
            if st.button("❌", key=f"del_{sess['session_id']}", help="删除此对话"):
                st.session_state.chat_sessions = [s for s in st.session_state.chat_sessions if s["session_id"] != sess["session_id"]]
                if st.session_state.current_session_id == sess["session_id"] and st.session_state.chat_sessions:
                    st.session_state.current_session_id = st.session_state.chat_sessions[0]["session_id"]
                st.rerun()
    if st.button("➕ 新建对话", use_container_width=True):
        new_id = datetime.now().strftime("%Y%m%d%H%M%S")
        st.session_state.chat_sessions.append({
            "session_id": new_id,
            "title": "新对话",
            "messages": [],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        st.session_state.current_session_id = new_id
        st.rerun()

# ============= 主区域 =============
st.title("🏥 基于AI的个性化健康管理系统")

# 上半部分：方案生成表单
with st.container():
    st.subheader("📝 生成专属健康方案")
    col1, col2 = st.columns(2)
    with col1:
        height = st.number_input("身高(厘米)", 100, 250, 170, key="form_height")
        weight = st.number_input("体重(千克)", 30, 200, 70, key="form_weight")
        age = st.number_input("年龄", 18, 100, 30, key="form_age")
    with col2:
        gender = st.selectbox("性别", ["男", "女"], key="form_gender")
        goal = st.selectbox("目标", ["减肥", "增肌", "补充营养"], key="form_goal")
        activity = st.selectbox("活动水平", list(ACTIVITY_FACTORS.keys()), key="form_activity")
    preference = st.text_input("饮食偏好/忌口（可选）", placeholder="例如：不吃辣、素食", key="form_preference")
    generate_btn = st.button("✨ 生成方案", use_container_width=True, type="primary")

    if generate_btn:
        with st.spinner("AI正在为您定制方案..."):
            plan = generate_health_plan(height, weight, age, gender, goal, activity, preference)
        # 保存历史方案
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "goal": goal,
            "plan_text": plan,
            "height": height,
            "weight": weight
        }
        st.session_state.history_records.insert(0, record)
        st.session_state.last_plan = plan
        # 添加到当前聊天
        add_message("assistant", f"🎉 已为您生成专属健康方案：\n\n{plan}")
        st.rerun()

# 下半部分：聊天对话区
st.divider()
st.subheader("💬 AI健康助手对话")

# 显示当前会话的消息（自定义气泡）
chat_container = st.container()
with chat_container:
    messages = get_current_messages()
    if not messages:
        st.info("暂无对话，开始提问吧！")
    else:
        chat_html = '<div style="overflow-y: auto; max-height: 500px; padding: 1rem;">'
        for msg in messages:
            if msg["role"] == "user":
                chat_html += f'<div style="text-align: right; margin-bottom: 12px;"><div style="display: inline-block; background-color: #0078ff; color: white; padding: 8px 16px; border-radius: 20px; border-bottom-right-radius: 4px; max-width: 80%;">{msg["content"]}</div><div style="font-size: 0.7rem; color: gray; margin-top: 2px;">{msg.get("time", "")}</div></div>'
            else:
                chat_html += f'<div style="text-align: left; margin-bottom: 12px;"><div style="display: inline-block; background-color: #e9ecef; color: #1e2a3a; padding: 8px 16px; border-radius: 20px; border-bottom-left-radius: 4px; max-width: 80%;">{msg["content"]}</div><div style="font-size: 0.7rem; color: gray; margin-top: 2px;">{msg.get("time", "")}</div></div>'
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

# 导出当前方案按钮
if st.session_state.last_plan:
    col_btn1, _ = st.columns([1, 5])
    with col_btn1:
        st.download_button(
            label="📥 导出当前方案",
            data=st.session_state.last_plan.encode("utf-8"),
            file_name=f"健康方案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )

# 输入区
col1, col2 = st.columns([5, 1])
with col1:
    user_input = st.text_input("输入您的问题...", key="chat_input", placeholder="例如：我叫张三，我喜欢吃什么...")
with col2:
    st.write("")
    send_btn = st.button("发送", use_container_width=True)

# 文件上传组件
uploaded_file = st.file_uploader("📎 上传文件（txt/pdf/图片），系统将识别文字并自动提问", type=["txt", "pdf", "png", "jpg", "jpeg"])
if uploaded_file is not None:
    with st.spinner("正在识别文字..."):
        file_text = extract_text_from_file(uploaded_file)
    if file_text and not file_text.startswith("❌"):
        question = f"请帮我分析以下内容：\n\n{file_text}"
        add_message("user", question)
        st.session_state.user_memory = extract_memory_from_text(question, st.session_state.user_memory)
        history = get_current_messages()[:-1]  # 去掉刚添加的用户消息
        # 转换为API需要的格式
        api_history = [{"role": m["role"], "content": m["content"]} for m in history]
        with st.spinner("AI思考中..."):
            answer = chat_with_memory(question, api_history, st.session_state.user_memory)
        add_message("assistant", answer)
        st.rerun()
    else:
        st.error(file_text)

# 处理发送消息
if send_btn and user_input.strip():
    add_message("user", user_input)
    st.session_state.user_memory = extract_memory_from_text(user_input, st.session_state.user_memory)
    history = get_current_messages()[:-1]
    api_history = [{"role": m["role"], "content": m["content"]} for m in history]
    with st.spinner("AI助手正在回复..."):
        answer = chat_with_memory(user_input, api_history, st.session_state.user_memory)
    add_message("assistant", answer)
    st.rerun()

# 清空当前对话按钮
if st.button("🗑️ 清空当前对话"):
    set_current_messages([])
    st.rerun()