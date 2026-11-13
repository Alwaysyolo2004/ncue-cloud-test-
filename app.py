# ==============================================================================
# Project: NCUE AI Academic Portal
# Author: Michael Octavianus Henlianto Muliaba & Team
# Description: Dual-role RAG Academic Assistant with Professor Analytics
# v2 Optimized + Self-Registration & Force Password Change Workflow
# ==============================================================================

import time

import pandas as pd
import streamlit as st

st.set_page_config(page_title="NCUE AI Academic Portal", page_icon="🎓", layout="wide")

import auth
import config
import db
import rag

db.init_db()
auth.seed_users()

WATERMARK_HTML = """
    <style>
    .hidden-watermark {
        color: transparent; /* Makes text completely invisible by default */
        font-size: 0.40rem;
        text-align: center;
        padding: 4px;
        border-radius: 2px;
        transition: all 0.3s ease;
        user-select: none; /* Prevents accidental highlighting when clicking */
    }
    .hidden-watermark:hover {
        color: #FFD700; /* Text turns gold when the cursor points directly at it */
        background-color: rgba(255, 255, 255, 0.05);
        font-weight: bold;
    }
    </style>

    <div class="hidden-watermark">
        🔑 Unique ID: NCUE-2026-MOHM-8839<br>
        Authd 龍021-112
    </div>
"""

SOURCE_LABELS = {"professor": "⭐ 教授答案", "handout": "📄 講義", "general": "🌐 講義未涵蓋", "error": "⚠️ 錯誤"}
MAX_LOGIN_FAILS, LOCK_SECONDS = 5, 60


# ==================== shared resources ====================
if not config.GOOGLE_API_KEY:
    st.error("GOOGLE_API_KEY 未設定。本機請寫在 `.env`，雲端請填在部署平台的 Secrets / Environment variables。")
    st.stop()


@st.cache_resource(show_spinner="載入講義向量庫…")
def get_vectorstore():
    return rag.get_vectorstore()


@st.cache_resource
def get_llm():
    return rag.get_llm()


def render_sources(docs):
    if docs:
        with st.expander(f"📌 引用的講義片段（{len(docs)}）"):
            for i, d in enumerate(docs, 1):
                st.markdown(f"**[{i}] {d['source']} · p.{d['page']}**")
                st.caption(d["text"])


# ==================== session ====================
for key, default in {"authenticated": False, "user": None, "login_fails": 0, "lock_until": 0.0}.items():
    st.session_state.setdefault(key, default)


# ==================== LOGIN / REGISTRATION SCREEN ====================
if not st.session_state.authenticated:
    st.title("🎓 NCUE AI Academic Portal - Login")
    st.caption("Please sign in to access your course portal or instructor dashboard.")
    if config.DEMO_MODE:
        st.info("Demo 帳號：`student_john`、`student_sarah`、`prof_smith`（密碼請向組員索取）")

    remaining = int(st.session_state.lock_until - time.time())
    
    # 建立登入與註冊的分页 (Tabs)
    tab_login, tab_register = st.tabs(["🔑 Sign In", "📝 Register (Students)"])
    
    with tab_login:
        with st.form("login_form"):
            username_input = st.text_input("Username:")
            password_input = st.text_input("Password:", type="password")
            login_btn = st.form_submit_button("Sign In", disabled=remaining > 0)

        if remaining > 0:
            st.warning(f"登入失敗次數過多，請 {remaining} 秒後再試。")
        elif login_btn:
            user = auth.authenticate(username_input.strip(), password_input)
            if user:
                st.session_state.update(authenticated=True, user=user, login_fails=0)
                st.rerun()
            st.session_state.login_fails += 1
            if st.session_state.login_fails >= MAX_LOGIN_FAILS:
                st.session_state.update(lock_until=time.time() + LOCK_SECONDS, login_fails=0)
            st.error("帳號或密碼錯誤。")
            
    with tab_register:
        st.write("填寫下方表單以註冊新的學生帳號：")
        with st.form("register_form"):
            reg_username = st.text_input("Choose Username:")
            reg_name = st.text_input("Full Name:")
            reg_password = st.text_input("Password:", type="password")
            reg_password_confirm = st.text_input("Confirm Password:", type="password")
            reg_btn = st.form_submit_button("Create Account")
            
            if reg_btn:
                if reg_password != reg_password_confirm:
                    st.error("兩次輸入的密碼不一致。")
                else:
                    try:
                        auth.register_student(reg_username, reg_password, reg_name)
                        st.success("註冊成功！請切換至「Sign In」頁面登入您的帳號。")
                    except Exception as e:
                        st.error(f"註冊失敗：{e}")
                        
    st.stop()


current_user = st.session_state.user

# ==================== FORCE PASSWORD CHANGE WORKFLOW ====================
if current_user.get("must_change_password", 0) == 1:
    st.title("🔐 強制修改密碼 (Security Update)")
    st.warning("這是系統指派的暫時密碼。基於資安考量，您必須先修改密碼才能進入系統。")
    
    with st.form("force_change_pwd_form"):
        new_pwd = st.text_input("新密碼 (至少 6 碼):", type="password")
        confirm_pwd = st.text_input("確認新密碼:", type="password")
        change_btn = st.form_submit_button("確認修改並進入系統")
        
        if change_btn:
            if new_pwd != confirm_pwd:
                st.error("兩次輸入的新密碼不一致。")
            elif len(new_pwd) < 6:
                st.error("新密碼長度至少需要 6 碼。")
            else:
                try:
                    auth.update_password(current_user["username"], new_pwd)
                    # 更新 session 中的 user 狀態，解除強制改密碼鎖
                    updated_user = db.get_user(current_user["username"])
                    st.session_state.user = {k: updated_user[k] for k in ("username", "role", "name", "must_change_password")}
                    st.success("密碼修改成功！正在進入系統...")
                    st.rerun()
                except Exception as e:
                    st.error(f"修改失敗：{e}")
    st.stop()


role = current_user["role"]
is_anonymous = False

# ==================== SIDEBAR CONFIGURATION ====================
with st.sidebar:
    st.header(f"👤 {current_user['name']}")
    st.caption(f"Role: {role}")
    if st.button("Log Out", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    st.divider()

    if role == "Professor":
        st.header("⚙️ Professor Controls")
        course = st.selectbox("Select Analytics Filter:", [config.ALL_COURSES] + config.COURSES)
    else:
        st.header("⚙️ Student Portal")
        course = st.selectbox("Select Course:", config.COURSES)
        st.divider()
        st.subheader("🕶️ Privacy Settings")
        is_anonymous = st.checkbox("Submit queries anonymously", value=False)
        st.caption("Applies to both AI chat logs and direct professor questions.")

    st.divider()
    st.markdown(WATERMARK_HTML, unsafe_allow_html=True)


# ==================== VIEW 1: STUDENT PORTAL ====================
def student_view():
    st.title(f"📚 {course} Study Assistant")
    tab_chat, tab_office_hours = st.tabs(["💬 AI Handout Chat", "📬 Office Hours & Professor Q&A"])

    with tab_chat:
        st.caption("Ask questions about lecture notes, exam prep, or coding handouts.")
        chat_key = f"chat::{current_user['username']}::{course}"  # 每門課各自一段對話
        history = st.session_state.setdefault(chat_key, [])

        for message in history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                render_sources(message.get("docs"))

        user_query = st.chat_input("Ask a question about this course...")
        if user_query and user_query.strip():
            user_query = user_query.strip()[: config.MAX_QUERY_CHARS]
            with st.chat_message("user"):
                st.markdown(user_query)
            with st.chat_message("assistant"):
                with st.spinner("Searching course knowledge base..."):
                    result = rag.answer_question(get_llm(), get_vectorstore(), user_query, course, history)
                st.markdown(result["answer"])
                render_sources(result["docs"])
            db.log_query(course, user_query, current_user["username"], is_anonymous, result["source"])
            history.append({"role": "user", "content": user_query})
            history.append({"role": "assistant", "content": result["answer"], "docs": result["docs"]})

    with tab_office_hours:
        st.subheader("📬 Direct Office Hours Q&A")
        st.write("Send a private question to your professor. Answers the professor pins appear below for everyone.")
        with st.form("direct_q_form", clear_on_submit=True):
            direct_question = st.text_area("Your Direct Question to the Professor:", max_chars=config.MAX_QUERY_CHARS)
            if st.form_submit_button("Submit Direct Question"):
                if direct_question.strip():
                    db.submit_direct_question(course, direct_question, current_user["username"], is_anonymous)
                    st.success("Your question has been sent to the professor!")
                else:
                    st.warning("Please type a question before submitting.")

        mine = db.list_my_questions(current_user["username"], course)
        if mine:
            with st.expander(f"🗂️ 我的提問（{len(mine)}）"):
                for q in mine:
                    badge = "✅" if q["status"] == "Answered" else "⏳"
                    tag = "（匿名）" if q["is_anonymous"] else ""
                    st.markdown(f"{badge} **{q['question']}** {tag}")
                    st.caption(q["ts"])
                    if q["answer"]:
                        st.info(q["answer"])

        st.divider()
        st.subheader("⭐ Highlighted & Answered Q&A Feed")
        pinned = db.list_direct_questions(course, highlighted_only=True)
        if pinned:
            for item in pinned:
                with st.container(border=True):
                    st.markdown(f"**Q: {item['question']}**")
                    st.caption(item["answered_ts"] or item["ts"])  # 公開區不顯示提問者
                    st.info(f"**Professor's Answer:**\n\n{item['answer']}")
        else:
            st.info("No highlighted professor Q&As for this course yet.")


# ==================== VIEW 2: PROFESSOR DASHBOARD ====================
def professor_view():
    st.title("👨‍🏫 Instructor Teaching Analytics & Office Hours Manager")
    tab_analytics, tab_direct, tab_verified, tab_handouts = st.tabs(
        ["📊 Analytics & Top FAQs", "📬 Direct Student Inquiries", "⭐ Verified RAG Overrides", "📄 Handouts"])

    with tab_analytics:
        a = db.query_analytics(course)
        src = a["by_source"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total AI Queries", a["total"])
        c2.metric("Distinct Askers", a["askers"])
        c3.metric("Answered by Your Overrides", src.get("professor", 0))
        c4.metric("Not Covered by Handouts", src.get("general", 0),
                  help="AI 判斷講義資訊不足、改用一般知識回答的次數 → 講義可能需要補充")

        if a["daily"]:
            st.subheader("📈 Daily Questions")
            st.bar_chart(pd.DataFrame(a["daily"]).set_index("day"))

        st.subheader("🔥 Top Frequently Asked Questions (AI)")
        if a["top"]:
            st.dataframe(pd.DataFrame(a["top"]), use_container_width=True, hide_index=True)
        else:
            st.write("No query activity logged yet.")

        st.subheader("🕳️ Questions the Handouts Didn't Cover")
        if a["gaps"]:
            st.dataframe(pd.DataFrame(a["gaps"]), use_container_width=True, hide_index=True)
        else:
            st.caption("目前沒有講義未涵蓋的問題。")

        with st.expander("📜 Recent Activity Audit Log"):
            if a["logs"]:
                df = pd.DataFrame(a["logs"])
                df["answered_from"] = df["answered_from"].map(SOURCE_LABELS).fillna(df["answered_from"])
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button("下載 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="query_log.csv", mime="text/csv")
            else:
                st.write("No recent logs found.")

    with tab_direct:
        st.subheader("📬 Student Direct Questions & Office Hours Inquiries")
        pending_only = st.toggle("只顯示待回覆", value=True)
        qa_list = db.list_direct_questions(course, pending_only=pending_only)
        if not qa_list:
            st.write("No direct student inquiries found.")
        for item in qa_list:
            with st.container(border=True):
                st.markdown(f"**Course:** {item['course']} | **Student:** {item['student']} ({item['ts']}) "
                            f"| **Status:** {item['status']}")
                st.markdown(f"**Question:** {item['question']}")
                with st.form(key=f"answer_form_{item['id']}"):
                    ans = st.text_area("Your Official Reply:", value=item["answer"])
                    pin = st.checkbox("⭐ Highlight/Pin this Q&A for all students", value=bool(item["is_highlighted"]))
                    if st.form_submit_button("Send Reply & Update"):
                        if pin and not ans.strip():
                            st.warning("要先填回覆才能置頂。")
                        else:
                            db.answer_direct_question(item["id"], ans, pin)
                            st.rerun()

    with tab_verified:
        st.subheader("⭐ Publish Professor Verified Answer (RAG Override)")
        st.write("學生提問包含關鍵字時，直接回傳你的答案（多個命中時取最長、最具體的關鍵字）。")
        with st.form("prof_answer_form", clear_on_submit=True):
            target = st.selectbox("適用課程", [config.ALL_COURSES] + config.COURSES,
                                  index=0 if course == config.ALL_COURSES else config.COURSES.index(course) + 1)
            keyword = st.text_input("Target Keyword or Question Phrase (e.g., 'batch system', '位元運算'):")
            answer = st.text_area("Official Definitive Answer:")
            if st.form_submit_button("Publish Verified Answer"):
                if keyword.strip() and answer.strip():
                    db.upsert_verified_answer(target, keyword, answer)
                    st.success(f"已發布「{keyword.strip()}」的教授答案（同課程同關鍵字會覆蓋舊的）。")
                else:
                    st.warning("Please fill in both fields.")

        for v in db.list_verified_answers(course):
            with st.container(border=True):
                left, right = st.columns([6, 1])
                left.markdown(f"**{v['keyword']}** · _{v['course']}_")
                left.caption(v["answer"][:300])
                if right.button("刪除", key=f"del_v_{v['id']}"):
                    db.delete_verified_answer(v["id"])
                    st.rerun()

    with tab_handouts:
        st.subheader("📄 Handout Management")
        target = st.selectbox("要上傳到哪門課", config.COURSES,
                              index=0 if course == config.ALL_COURSES else config.COURSES.index(course))
        files = st.file_uploader("Upload course PDF(s):", type=["pdf"], accept_multiple_files=True)
        if files and st.button("Process & Index", type="primary"):
            vs = get_vectorstore()
            for f in files:
                with st.spinner(f"處理 {f.name}…"):
                    try:
                        n = rag.index_pdf(vs, f.getvalue(), f.name, target)
                        st.success(f"{f.name}：已建立 {n} 個片段 → {target}")
                    except Exception as e:
                        st.error(f"{f.name} 失敗：{e}")

        st.divider()
        handouts = rag.list_handouts(get_vectorstore(), target)
        if not handouts:
            st.caption(f"{target} 目前沒有講義。")
        for h in handouts:
            left, right = st.columns([6, 1])
            left.markdown(f"**{h['source']}** — {h['pages']} 頁，{h['chunks']} 個片段")
            if right.button("移除", key=f"del_h_{h['file_hash']}"):
                rag.delete_handout(get_vectorstore(), target, h["file_hash"])
                st.rerun()


if role == "Student":
    student_view()
else:
    professor_view()
