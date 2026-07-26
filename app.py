import os
import json
import sqlite3
from datetime import datetime
import streamlit as st
from groq import Groq
from pypdf import PdfReader

# ------------------------------------------------------------------
# 1. DATABASE SETUP
# ------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect("hirecompass_tracker.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            role TEXT,
            match_score INTEGER,
            decision TEXT,
            fresher_eligibility TEXT,
            status TEXT DEFAULT 'Applied',
            date_applied TEXT
        )
    """)
    
    # Auto-migrate missing columns
    cursor.execute("PRAGMA table_info(applications)")
    columns = [column[1] for column in cursor.fetchall()]
    if "fresher_eligibility" not in columns:
        cursor.execute("ALTER TABLE applications ADD COLUMN fresher_eligibility TEXT DEFAULT 'ELIGIBLE'")
        
    conn.commit()
    conn.close()

def log_application(company, role, score, decision, eligibility):
    conn = sqlite3.connect("hirecompass_tracker.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO applications (company, role, match_score, decision, fresher_eligibility, date_applied) VALUES (?, ?, ?, ?, ?, ?)",
        (company, role, score, decision, eligibility, datetime.now().strftime("%Y-%m-%d"))
    )
    conn.commit()
    conn.close()

def get_applications():
    conn = sqlite3.connect("hirecompass_tracker.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, company, role, match_score, decision, fresher_eligibility, status, date_applied FROM applications ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_status(app_id, new_status):
    conn = sqlite3.connect("hirecompass_tracker.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE applications SET status = ? WHERE id = ?", (new_status, app_id))
    conn.commit()
    conn.close()

# ------------------------------------------------------------------
# 2. STREAMLIT UI CONFIG & CUSTOM STYLING
# ------------------------------------------------------------------
st.set_page_config(page_title="HireCompass AI", page_icon="🧭", layout="wide")
init_db()

# Custom CSS Injector for Sleeker Styling
st.markdown("""
    <style>
    /* Metric & Highlight Cards */
    .stMetric {
        background-color: #f8f9fa;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }
    
    /* Clean Tab Bar */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 16px;
    }
    
    /* Subtle Divider Margins */
    hr {
        margin-top: 1.5rem !important;
        margin-bottom: 1.5rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# Hero Header
st.title("🧭 HireCompass AI")
st.markdown("""
**AI-powered job application copilot for rapid evaluation, fresher eligibility checks, and interview preparation.**

`✓ Fresher Eligibility` • `✓ Resume vs JD Match` • `✓ ATS Gap Analysis` • `✓ Skill Breakdown` • `✓ Application Tracker`
""")

st.caption("Built with Python • Streamlit • Groq LPU (Llama 3.3) • SQLite")

# Handle API Key Safely
# Handle API Key Safely
try:
    groq_secret = st.secrets["GROQ_API_KEY"]
except:
    groq_secret = ""

with st.sidebar:
    st.header("⚙️ Configuration")

    if groq_secret:
        st.success("✅ Groq API Connected")
        active_api_key = groq_secret
    else:
        active_api_key = st.text_input(
            "Groq API Key",
            type="password"
        )

    st.divider()
    st.header("📊 Application Stats")
    apps = get_applications()
    st.metric("Total Roles Evaluated", len(apps))

   

# ------------------------------------------------------------------
# 3. CORE APPLICATION TABS
# ------------------------------------------------------------------
main_tab, tracker_tab = st.tabs(["⚡ Evaluate & Prepare", "📂 Application Tracker"])

with main_tab:
    col_a, col_b = st.columns(2)
    
    with col_a:
        uploaded_file = st.file_uploader("Upload Your Resume (PDF)", type=["pdf"])
        job_title = st.text_input("Job Title / Role", placeholder="e.g. Data Analyst / Java Full Stack Developer")
        company_name = st.text_input("Company Name", placeholder="e.g. Accenture, TCS, Infosys")
        
    with col_b:
        job_description = st.text_area("Paste Job Description (JD)", height=260)
        
    evaluate_btn = st.button("🚀 Analyze Role with HireCompass", type="primary", use_container_width=True)

    if evaluate_btn:
        if not active_api_key:
            st.error("Missing Groq API Key. Please enter your API key in the sidebar.")
        elif not uploaded_file or not job_description:
            st.error("Please upload a Resume PDF and paste a Job Description.")
        else:
            client = Groq(api_key=active_api_key)
            
            reader = PdfReader(uploaded_file)
            resume_text = "".join([page.extract_text() for page in reader.pages if page.extract_text()])

            prompt = f"""
            You are HireCompass AI, an elite technical career coach and hiring assistant specializing in entry-level & fresher roles for Computer Science graduates.

            Target Role: {job_title if job_title else "Unspecified Role"}
            Company: {company_name if company_name else "Unspecified Company"}

            Job Description:
            {job_description}

            Candidate Resume:
            {resume_text}

            STRICT EVALUATION RULES:
            1. FRESHER ELIGIBILITY ASSESSMENT:
               - Scan the Job Description for required years of experience, seniority tags (e.g. Senior, Lead, Principal, Staff), and role level.
               - Categorize eligibility strictly into one of: "ELIGIBLE", "STRETCH", or "NOT_RECOMMENDED".
               - ELIGIBLE: JD specifies 0-2 years, entry-level, associate, or explicitly mentions freshers/campus hiring.
               - STRETCH: JD specifies 2-4 years, but core technical skills match strongly (startups/SMEs often hire skilled freshers here).
               - NOT_RECOMMENDED: JD specifies 5+ years, Lead, Manager, Principal, or Staff roles.

            2. NO FAKE METRICS IN BULLET REWRITES:
               - NEVER invent fake metrics, statistics, or numbers. Focus purely on action verbs and technical clarity based on facts provided.

            Perform a complete analysis and return JSON STRICTLY matching this structure:
            {{
                "should_apply": "YES" or "NO",
                "apply_reason": "Short 2-sentence rationale on why to apply or skip.",
                "fresher_eligibility": {{
                    "status": "ELIGIBLE" | "STRETCH" | "NOT_RECOMMENDED",
                    "label": "🟢 Eligible for Freshers" | "🟡 Stretch Role (2-3 Yrs JD)" | "🔴 Not Recommended for Freshers",
                    "jd_exp_found": "Extracted experience text from JD",
                    "reasons": [
                        "Reason point 1",
                        "Reason point 2"
                    ]
                }},
                "match_score": 85,
                "skill_match_breakdown": [
                    {{"skill": "SQL", "match_percentage": 100}},
                    {{"skill": "Python", "match_percentage": 90}}
                ],
                "strong_skills": ["Skill 1", "Skill 2"],
                "missing_skills": ["Skill 1", "Skill 2"],
                "bullet_improvements": [
                    {{"current": "Original bullet from resume", "suggested": "Factually accurate, action-oriented rewrite"}}
                ],
                "ats_analysis": {{
                    "missing_keywords": ["Keyword1", "Keyword2"],
                    "generic_phrases": ["Vague phrases to remove"]
                }},
                "learning_roadmap": {{
                    "target_skill": "Primary missing skill",
                    "estimated_days": "4 Days",
                    "action_plan": ["Step 1", "Step 2"]
                }},
                "interview_questions": {{
                    "technical": ["Q1", "Q2"],
                    "hr_behavioral": ["Q1", "Q2"]
                }}
            }}
            """

            with st.spinner("Analyzing JD & Resume on Groq LPU..."):
                try:
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"}
                    )
                    data = json.loads(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
                    st.stop()

            # Auto-log to SQLite
            log_company_name = company_name if company_name else "Unknown Company"
            log_role = job_title if job_title else "General Role"
            fresher_data = data.get("fresher_eligibility", {})
            eligibility_status = fresher_data.get("status", "ELIGIBLE")

            log_application(log_company_name, log_role, data.get("match_score", 0), data.get("should_apply", "N/A"), eligibility_status)

            # --- 1. DECISION BANNER ---
            decision = data.get("should_apply", "YES")
            with st.container(border=True):
                if decision == "YES":
                    st.success("### 🟢 RECOMMENDATION: YES — APPLY FOR THIS ROLE")
                else:
                    st.error("### 🔴 RECOMMENDATION: NO — SKIP / LOW PROBABILITY")
                st.write(f"**Rationale:** {data.get('apply_reason')}")

            # --- 2. FRESHER ELIGIBILITY CHECK ---
            with st.container(border=True):
                st.subheader("🎓 Fresher Eligibility Assessment")
                f_status = fresher_data.get("status", "ELIGIBLE")
                f_label = fresher_data.get("label", "🟢 Eligible for Freshers")
                f_exp = fresher_data.get("jd_exp_found", "Not specified in JD")
                f_reasons = fresher_data.get("reasons", [])

                col_status, col_details = st.columns([1, 2])

                with col_status:
                    if f_status == "ELIGIBLE":
                        st.success(f"### {f_label}")
                    elif f_status == "STRETCH":
                        st.warning(f"### {f_label}")
                    else:
                        st.error(f"### {f_label}")
                    st.caption(f"**JD Experience Mentioned:** `{f_exp}`")

                with col_details:
                    st.write("**Eligibility Rationale:**")
                    for r in f_reasons:
                        st.markdown(f"• {r}")

            # --- 3. SKILL BREAKDOWN ---
            with st.container(border=True):
                st.subheader("📊 Skill-by-Skill Match Breakdown")
                c_score, c_breakdown = st.columns([1, 2])
                
                with c_score:
                    st.metric("Overall Match Score", f"{data.get('match_score')}%")
                    st.caption("Based on key technical skills, experience alignment, and keyword density.")
                    
                with c_breakdown:
                    skills_list = data.get("skill_match_breakdown", [])
                    for item in skills_list:
                        s_name = item.get("skill", "Skill")
                        s_pct = item.get("match_percentage", 50)
                        st.write(f"**{s_name}** ({s_pct}%)")
                        st.progress(s_pct / 100)

            # --- 4. BULLET REWRITES ---
            with st.container(border=True):
                st.subheader("📝 Targeted Bullet Rewrites")
                for item in data.get("bullet_improvements", []):
                    col_curr, col_sug = st.columns(2)
                    with col_curr:
                        st.info(f"**Current:** {item['current']}")
                    with col_sug:
                        st.success(f"**Suggested:** {item['suggested']}")

            # --- 5. ATS & LEARNING ROADMAP ---
            col_ats, col_road = st.columns(2)
            
            with col_ats:
                with st.container(border=True):
                    st.subheader("🔍 ATS Keywords & Warnings")
                    ats = data.get("ats_analysis", {})
                    st.write("**Missing Keywords:**", ", ".join(ats.get("missing_keywords", [])))
                    st.write("**Phrases to Avoid:**", ", ".join(ats.get("generic_phrases", [])))

            with col_road:
                with st.container(border=True):
                    st.subheader("🎓 Micro-Learning Roadmap")
                    road = data.get("learning_roadmap", {})
                    st.write(f"**Skill to Bridge:** `{road.get('target_skill')}`")
                    st.write(f"**Estimated Effort:** `{road.get('estimated_days')}`")
                    for step in road.get("action_plan", []):
                        st.markdown(f"- {step}")

            # --- 6. INTERVIEW PREP ---
            with st.container(border=True):
                st.subheader("🎯 Role-Specific Interview Questions")
                q_tech, q_hr = st.tabs(["💻 Technical Questions", "🗣️ HR & Behavioral"])
                
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
        # Table Headers for clean alignment
        h1, h2, h3, h4, h5, h6 = st.columns([2, 2, 1, 1, 1, 2])
        h1.caption("**Company**")
        h2.caption("**Role**")
        h3.caption("**Score**")
        h4.caption("**Decision**")
        h5.caption("**Eligibility**")
        h6.caption("**Status**")
        st.divider()

        for app_id, comp, role, score, dec, elig, status, date_str in records:
            with st.container():
                c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 1, 1, 1, 2])
                c1.write(f"**{comp}**")
                c2.write(role)
                c3.write(f"{score}%")
                c4.write(f"**{dec}**")
                
                if elig == "ELIGIBLE":
                    c5.caption("🟢 Fresher")
                elif elig == "STRETCH":
                    c5.caption("🟡 Stretch")
                else:
                    c5.caption("🔴 Senior")

                new_st = c6.selectbox(
                    "Status", 
                    ["Evaluated", "Applied", "Interviewing", "Offer", "Rejected"], 
                    index=["Evaluated", "Applied", "Interviewing", "Offer", "Rejected"].index(status) if status in ["Evaluated", "Applied", "Interviewing", "Offer", "Rejected"] else 0,
                    key=f"status_{app_id}",
                    label_visibility="collapsed"
                )
                if new_st != status:
                    update_status(app_id, new_st)
                    st.rerun()
