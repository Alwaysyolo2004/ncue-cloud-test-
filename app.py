# ==============================================================================
# Project: NCUE AI Academic Portal
# Author: Michael Octavianus Henlianto Muliaba
# Date: October 2026
# Description: Dual-role RAG Academic Assistant with Professor Analytics
# ==============================================================================

import streamlit as st
from backend import load_rag_pipeline, ask_rag, process_uploaded_pdf, save_professor_answer
from analytics import log_query, get_query_analytics
from qa_manager import submit_direct_question, get_qa_list, update_qa_answer
from auth import authenticate_user, register_user, update_user_password  # import update_user_password 

st.set_page_config(page_title="NCUE AI Academic Portal", page_icon="🎓", layout="wide")

# Initialize Session State for Authentication
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None

# ==================== LOGIN & REGISTER SCREEN ====================
if not st.session_state.authenticated:
    st.title("🎓 NCUE AI Academic Portal")
    st.caption("portal akademik for student and proffesor")
    
    # pendaftran akun/ new account
    tab_login, tab_register = st.tabs(["🔑 Log In ", " 📝 Register "])
    
    with tab_login:
        with st.form("login_form"):
            st.subheader("Enter your acccount")
            username_input = st.text_input("Username:")
            password_input = st.text_input("Password:", type="password")
            login_btn = st.form_submit_button("Sign In")
            
            if login_btn:
                user = authenticate_user(username_input, password_input)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success(f"welcome back, {user['name']}!")
                    st.rerun()
                else:
                    st.error("Wrong Username or Password (capslock have affect)")
                    
    with tab_register:
        with st.form("register_form"):
            st.subheader("Make New Account (Student)")
            reg_name = st.text_input("Nama :")
            reg_username = st.text_input("Username:")
            reg_password = st.text_input("Password:", type="password")
            reg_Cpassword = st.text_input("Confirm Password:", type="password")
            
            reg_btn = st.form_submit_button("Register")
            
            if reg_btn:
                # 1. Cek apakah ada kolom yang kosong
                if not reg_name or not reg_username or not reg_password or not reg_Cpassword:
                    st.warning("please fill the form")
                
                elif reg_password != reg_Cpassword:
                    st.error("password not confirmed, please check the password again")
                
                else:
                    success, message = register_user(reg_username, reg_password, reg_name, role="Student")
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                        
    st.stop()  

# ==================== FORCE PASSWORD CHANGE (SECURITY CHECK) ====================
# Jika user sudah login, tapi statusnya wajib ganti password (akun dibuat admin)
if st.session_state.authenticated and st.session_state.user.get("must_change_password", False):
    st.title("🔒 Security Check: Change Temporary Password")
    st.warning("Welcome Professor, please change your account password into your personal preference")
    
    with st.form("change_temp_password_form"):
        new_pass = st.text_input("New Password:", type="password")
        confirm_new_pass = st.text_input("Confirm New Password:", type="password")
        change_btn = st.form_submit_button("Update Password")
        
        if change_btn:
            if not new_pass or not confirm_new_pass:
                st.warning("Please fill in all fields.")
            elif new_pass != confirm_new_pass:
                st.error("New passwords do not match!")
            else:
                success, msg = update_user_password(st.session_state.user["username"], new_pass)
                if success:
                    st.success("Password updated successfully! Please log in again with your new password.")
                    st.session_state.authenticated = False
                    st.session_state.user = None
                    st.rerun()
                else:
                    st.error(msg)
    st.stop()

# Load Backend RAG Engine
@st.cache_resource
def init_backend():
    return load_rag_pipeline()

retriever, llm = init_backend()
current_user = st.session_state.user
role = current_user["role"]

# ==================== SIDEBAR CONFIGURATION ====================
with st.sidebar:
    st.header(f"👤 {current_user['name']}")
    st.caption(f"Role: {role}")
    
    if st.button("Log Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.rerun()
        
    st.divider()
    st.markdown("""
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
    """, unsafe_allow_html=True)

    course_list = ["General Handouts", "Operating Systems", "Computer Architecture", "Data Structures"]
    
    if role == "Professor":
        st.header("⚙️ Professor Controls")
        course = st.selectbox("Select Analytics Filter:", ["All Courses"] + course_list)
    else:
        st.header("⚙️ Student Portal")
        course = st.selectbox("Select Course:", course_list)
        
        st.divider()
        st.subheader("🕶️ Privacy Settings")
        is_anonymous = st.checkbox("Submit queries anonymously", value=False)
        st.caption("Applies to both AI chat logs and direct professor questions.")
        
        st.divider()
        st.subheader("📄 Handout Management")
        uploaded_file = st.file_uploader("Upload course PDF:", type=["pdf"])
        if uploaded_file is not None:
            if st.button("Process & Index Handout", use_container_width=True):
                with st.spinner("Analyzing and embedding PDF..."):
                    chunk_count = process_uploaded_pdf(uploaded_file)
                    st.success(f"Indexed {chunk_count} chunks into {course}!")
                    st.cache_resource.clear()

        st.markdown("""
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
    """, unsafe_allow_html=True)

# ==================== VIEW 1: STUDENT PORTAL ====================
if role == "Student":
    st.title(f"📚 {course} Study Assistant")
    
    # Sub-tabs for AI Chat vs Office Hours Q&A
    tab_chat, tab_office_hours = st.tabs(["💬 AI Handout Chat", "📬 Office Hours & Professor Q&A"])
    
    with tab_chat:
        st.caption("Ask questions about lecture notes, exam prep, or coding handouts.")
        chat_key = f"messages_{current_user['username']}"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for message in st.session_state[chat_key]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if "docs" in message and message["docs"]:
                    with st.expander("📌 View Retrieved Handout Context"):
                        for idx, doc in enumerate(message["docs"], 1):
                            st.markdown(f"**Chunk {idx}:**")
                            st.caption(doc.page_content)

        if user_query := st.chat_input("Ask a question about this course..."):
            log_query(course, user_query, current_user["username"], is_anonymous)
            st.session_state[chat_key].append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            with st.chat_message("assistant"):
                with st.spinner("Searching course knowledge base..."):
                    answer, docs = ask_rag(retriever, llm, user_query)
                    st.markdown(answer)
                    if docs:
                        with st.expander("📌 View Retrieved Handout Context"):
                            for idx, doc in enumerate(docs, 1):
                                st.markdown(f"**Chunk {idx}:**")
                                st.caption(doc.page_content)
                    st.session_state[chat_key].append({"role": "assistant", "content": answer, "docs": docs})

    with tab_office_hours:
        st.subheader("📬 Direct Office Hours Q&A")
        st.write("Send a private or direct question to your professor regarding course material. You can also view highlighted professor answers below.")
        
        with st.form("direct_q_form"):
            direct_question = st.text_area("Your Direct Question to the Professor:")
            submit_direct = st.form_submit_button("Submit Direct Question")
            if submit_direct:
                if direct_question:
                    submit_direct_question(course, direct_question, current_user["username"], is_anonymous)
                    st.success("Your question has been sent directly to the professor!")
                else:
                    st.warning("Please type a question before submitting.")
        
        st.divider()
        st.subheader("⭐ Highlighted & Answered Q&A Feed")
        qa_items = get_qa_list(course)
        highlighted_items = [q for q in qa_items if q["is_highlighted"]]
        
        if highlighted_items:
            for item in highlighted_items:
                with st.container(border=True):
                    st.markdown(f"**Q: {item['question']}**")
                    st.caption(f"Asked by: {item['student']} | {item['timestamp']}")
                    st.info(f"**Professor's Answer:**\n\n{item['answer']}")
        else:
            st.info("No highlighted professor Q&As for this course yet.")

# ==================== VIEW 2: PROFESSOR DASHBOARD ====================
else:
    st.title("👨‍🏫 Instructor Teaching Analytics & Office Hours Manager")
    
    tab_analytics, tab_direct_qa, tab_verified = st.tabs(["📊 Analytics & Top FAQs", "📬 Direct Student Inquiries", "⭐ Verified RAG Overrides"])
    
    analytics = get_query_analytics(course)
    
    with tab_analytics:
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Total AI Queries Logged", value=analytics["total_queries"])
        with col2:
            st.metric(label="Active Course Filter", value=course)
            
        st.divider()
        st.subheader("🔥 Top Frequently Asked Questions (AI)")
        if analytics["top_queries"]:
            for query_text, count in analytics["top_queries"]:
                st.info(f"**Question:** \"{query_text}\" — **Asked {count} time(s)**")
        else:
            st.write("No query activity logged yet.")

        st.divider()
        st.subheader("📜 Recent Activity Audit Log")
        if analytics["logs"]:
            st.dataframe(analytics["logs"], use_container_width=True)
        else:
            st.write("No recent logs found.")

    with tab_direct_qa:
        st.subheader("📬 Student Direct Questions & Office Hours Inquiries")
        st.write("Review personal questions sent by students. You can reply and check **'Highlight for Students'** to pin the answer to the course feed.")
        
        qa_list = get_qa_list(course)
        if qa_list:
            for item in qa_list:
                with st.container(border=True):
                    st.markdown(f"**Course:** {item['course']} | **Student:** {item['student']} ({item['timestamp']})")
                    st.markdown(f"**Question:** {item['question']}")
                    
                    with st.form(key=f"answer_form_{item['id']}"):
                        ans_input = st.text_area("Your Official Reply:", value=item["answer"])
                        highlight_toggle = st.checkbox("⭐ Highlight/Pin this Q&A for all students", value=item["is_highlighted"])
                        reply_btn = st.form_submit_button("Send Reply & Update")
                        
                        if reply_btn:
                            update_qa_answer(item["id"], ans_input, highlight_toggle)
                            st.success("Reply saved!")
                            st.rerun()
        else:
            st.write("No direct student inquiries found.")

    with tab_verified:
        st.subheader("⭐ Publish Professor Verified Answer (RAG Override)")
        st.write("Add an official answer that takes absolute priority when students ask matching questions in the AI chat.")
        
        with st.form("prof_answer_form"):
            keyword_input = st.text_input("Target Keyword or Question Phrase (e.g., 'batch system'):")
            answer_input = st.text_area("Official Definitive Answer:")
            submit_btn = st.form_submit_button("Publish Verified Answer")
            
            if submit_btn:
                if keyword_input and answer_input:
                    save_professor_answer(keyword_input, answer_input)
                    st.success(f"Successfully published verified answer for '{keyword_input}'!")
                else:
                    st.warning("Please fill in both fields.")
