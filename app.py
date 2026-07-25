import os
import json
import sqlite3
from datetime import datetime
import streamlit as st
from groq import Groq
from pypdf import PdfReader

# ------------------------------------------------------------------
# 1. DATABASE SETUP (Local Application Tracker)
# ------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect("jobpilot_tracker.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            role TEXT,
            match_score INTEGER,
            decision TEXT,
            status TEXT DEFAULT 'Applied',
            date_applied TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_application(company, role, score, decision):
    conn = sqlite3.connect("jobpilot_tracker.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO applications (company, role, match_score, decision, date_applied) VALUES (?, ?, ?, ?, ?)",
        (company, role, score, decision, datetime.now().strftime("%Y-%m-%d"))
    )
    conn.commit()
    conn.close()

def get_applications():
    conn = sqlite3.connect("jobpilot_tracker.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, company, role, match_score, decision, status, date_applied FROM applications ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_status(app_id, new_status):
    conn = sqlite3.connect("jobpilot_tracker.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE applications SET status = ? WHERE id = ?", (new_status, app_id))
    conn.commit()
    conn.close()

# ------------------------------------------------------------------
# 2. STREAMLIT UI CONFIG
# ------------------------------------------------------------------
st.set_page_config(page_title="JobPilot AI", page_icon="🎯", layout="wide")
init_db()

st.title("🎯 JobPilot AI")
st.caption("Your high-speed job application decision engine & preparation assistant.")

with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Groq API Key", type="password")
    
    st.divider()
    st.header("📊 Quick Tracker Stats")
    apps = get_applications()
    st.metric("Total Jobs Evaluated", len(apps))

# ------------------------------------------------------------------
# 3. CORE APPLICATION TABS
# ------------------------------------------------------------------
main_tab, tracker_tab = st.tabs(["⚡ Evaluate & Prepare", "📂 Application Tracker"])

with main_tab:
    col_a, col_b = st.columns(2)
    
    with col_a:
        uploaded_file = st.file_uploader("Upload Your Resume (PDF)", type=["pdf"])
        job_title = st.text_input("Job Title / Role", placeholder="e.g. Data Analyst / Java Developer")
        company_name = st.text_input("Company Name", placeholder="e.g. Accenture")
        
    with col_b:
        job_description = st.text_area("Paste Job Description (JD)", height=260)
        
    evaluate_btn = st.button("🚀 Analyze Role with JobPilot", type="primary", use_container_width=True)

    if evaluate_btn:
        if not api_key:
            st.error("Please enter your Groq API Key in the sidebar.")
        elif not uploaded_file or not job_description:
            st.error("Please provide both a Resume PDF and a Job Description.")
        else:
            client = Groq(api_key=api_key)
            
            # Read PDF
            reader = PdfReader(uploaded_file)
            resume_text = "".join([page.extract_text() for page in reader.pages if page.extract_text()])

            prompt = f"""
            You are JobPilot AI, an elite technical career coach and hiring assistant.
            
            Target Role: {job_title if job_title else "Unspecified Role"}
            Company: {company_name if company_name else "Unspecified Company"}
            
            Job Description:
            {job_description}
            
            Candidate Resume:
            {resume_text}
            
            Perform a complete analysis and return JSON STRICTLY matching this structure:
            {{
                "should_apply": "YES" or "NO",
                "apply_reason": "Short 2-sentence rationale on why to apply or skip.",
                "match_score": 82,
                "strong_skills": ["Skill 1", "Skill 2"],
                "missing_skills": ["Skill 1", "Skill 2"],
                "bullet_improvements": [
                    {{"current": "Old bullet from resume", "suggested": "Quantified, impact-driven rewrite tailored to JD"}}
                ],
                "ats_analysis": {{
                    "missing_keywords": ["Keyword1", "Keyword2"],
                    "weak_bullets": ["Bullet that needs work"],
                    "generic_phrases": ["Phrase that sounds too vague"]
                }},
                "learning_roadmap": {{
                    "target_skill": "Primary missing skill",
                    "estimated_days": "4 Days",
                    "action_plan": ["Step 1", "Step 2"]
                }},
                "interview_questions": {{
                    "technical": ["Q1", "Q2", "Q3"],
                    "hr_behavioral": ["Q1", "Q2"]
                }}
            }}
            """

            with st.spinner("Analyzing JD & Resume on Groq..."):
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                
                data = json.loads(response.choices[0].message.content)

            # Log to SQLite DB
            log_company_name = company_name if company_name else "Unknown Company"
            log_role = job_title if job_title else "General Role"
            log_application(log_company_name, log_role, data.get("match_score", 0), data.get("should_apply", "N/A"))

            st.divider()

            # --- FEATURE 1: SHOULD I APPLY? ---
            decision = data.get("should_apply", "YES")
            if decision == "YES":
                st.success(f"### 🟢 SHOULD YOU APPLY? **YES**")
            else:
                st.error(f"### 🔴 SHOULD YOU APPLY? **NO / SKIP FOR NOW**")
            st.write(f"**Reason:** {data.get('apply_reason')}")

            st.divider()

            # --- FEATURE 2: MATCH SCORE & SKILLS GAP ---
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                st.metric("Overall Match Score", f"{data.get('match_score')}%")
            with c2:
                st.subheader("✔ Strong Skills")
                for s in data.get("strong_skills", []):
                    st.markdown(f"- **{s}**")
            with c3:
                st.subheader("✖ Missing Skills")
                for s in data.get("missing_skills", []):
                    st.markdown(f"- <span style='color:red;'>{s}</span>", unsafe_allow_html=True)

            st.divider()

            # --- FEATURE 3: RESUME BULLET IMPROVEMENTS ---
            st.subheader("📝 Targeted Bullet Rewrites")
            for item in data.get("bullet_improvements", []):
                col_curr, col_sug = st.columns(2)
                with col_curr:
                    st.info(f"**Current:** {item['current']}")
                with col_sug:
                    st.success(f"**Suggested:** {item['suggested']}")

            st.divider()

            # --- FEATURE 4: ATS OPTIMIZATION & LEARNING ROADMAP ---
            col_ats, col_road = st.columns(2)
            
            with col_ats:
                st.subheader("🔍 ATS Optimization Warnings")
                ats = data.get("ats_analysis", {})
                st.write("**Missing Keywords:**", ", ".join(ats.get("missing_keywords", [])))
                st.write("**Generic Phrases to Cut:**", ", ".join(ats.get("generic_phrases", [])))

            with col_road:
                st.subheader("🎓 Micro-Learning Gap")
                road = data.get("learning_roadmap", {})
                st.write(f"**Skill to Bridge:** `{road.get('target_skill')}`")
                st.write(f"**Estimated Time:** `{road.get('estimated_days')}`")
                for step in road.get("action_plan", []):
                    st.markdown(f"1. {step}")

            st.divider()

            # --- FEATURE 5: CUSTOM INTERVIEW PREP ---
            st.subheader("🎯 Job-Specific Interview Question Bank")
            q_tech, q_hr = st.tabs(["💻 Technical Questions", "🗣️ HR / Behavioral"])
            
            with q_tech:
                for q in data.get("interview_questions", {}).get("technical", []):
                    st.markdown(f"- {q}")
            with q_hr:
                for q in data.get("interview_questions", {}).get("hr_behavioral", []):
                    st.markdown(f"- {q}")

# ------------------------------------------------------------------
# 4. APPLICATION TRACKER TAB
# ------------------------------------------------------------------
with tracker_tab:
    st.subheader("📂 Application History")
    records = get_applications()
    
    if not records:
        st.info("No applications evaluated yet. Run an analysis above to auto-log.")
    else:
        for app_id, comp, role, score, dec, status, date_str in records:
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 2])
                c1.write(f"**{comp}**")
                c2.write(role)
                c3.write(f"{score}%")
                c4.write(f"**{dec}**")
                
                # Dynamic Status Updater
                new_st = c5.selectbox(
                    "Status", 
                    ["Evaluated", "Applied", "Interviewing", "Offer", "Rejected"], 
                    index=["Evaluated", "Applied", "Interviewing", "Offer", "Rejected"].index(status) if status in ["Evaluated", "Applied", "Interviewing", "Offer", "Rejected"] else 0,
                    key=f"status_{app_id}"
                )
                if new_st != status:
                    update_status(app_id, new_st)
                    st.rerun()
            st.divider()