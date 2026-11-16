
import streamlit as st
import requests
import sqlite3
import re
import html
from pathlib import Path

# ======================================
# 1. CONFIGURATION
# ======================================

st.set_page_config(
    page_title="SkillMatch",
    page_icon="🎯",
    layout="wide"
)

DB_PATH = Path(__file__).with_name("skillmatch.db")

# ======================================
# 2. DESIGN
# ======================================

st.markdown("""
<style>
.stApp {
    background: #F4F7FB;
    color: #172033;
}
.block-container {
    max-width: 1200px;
    padding-top: 2rem;
}
[data-testid="stSidebar"] {
    background: #172554;
}
[data-testid="stSidebar"] * {
    color: white !important;
}
[data-testid="stMetric"] {
    background: white;
    border: 1px solid #E1E7F0;
    padding: 15px;
    border-radius: 12px;
}
.stTextInput input {
    background: white !important;
    color: #172033 !important;
}
.job-card {
    background: white;
    border: 1px solid #E1E7F0;
    border-radius: 12px;
    padding: 15px;
}
</style>
""", unsafe_allow_html=True)

# ======================================
# 3. DATABASE
# ======================================

def init_database():

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_jobs (
                url TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                score INTEGER,
                skills TEXT,
                job_type TEXT,
                salary TEXT
            )
        """)


def save_job(job):

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute("""
            INSERT OR REPLACE INTO saved_jobs
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job["url"],
            job["title"],
            job["company"],
            job["location"],
            job["score"],
            ", ".join(job["matched"]),
            job["job_type"],
            job["salary"]
        ))


def get_saved_jobs():

    with sqlite3.connect(DB_PATH) as conn:

        cursor = conn.execute("""
            SELECT url, title, company, location,
                   score, skills, job_type, salary
            FROM saved_jobs
            ORDER BY rowid DESC
        """)

        return cursor.fetchall()


def delete_saved_job(url):

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            "DELETE FROM saved_jobs WHERE url = ?",
            (url,)
        )


init_database()

# ======================================
# 4. FETCH REAL JOBS
# ======================================

@st.cache_data(ttl=900, show_spinner=False)
def fetch_jobs(skills):

    url = "https://jobicy.com/api/jobs"
    all_jobs = {}

    queries = [{"count": 100}]

    for skill in skills[:8]:

        if 3 <= len(skill) <= 50:

            queries.append({
                "count": 100,
                "tag": skill
            })

    for params in queries:

        response = requests.get(
            url,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if data.get("success") is False:
            continue

        for job in data.get("jobs", []):

            job_id = job.get("id") or job.get("url")

            if job_id:
                all_jobs[str(job_id)] = job

    return list(all_jobs.values())


# ======================================
# 5. TEXT CLEANING
# ======================================

def clean_text(value):

    value = re.sub(
        r"<(script|style).*?>.*?</\1>",
        " ",
        value or "",
        flags=re.I | re.S
    )

    value = re.sub(r"<[^>]+>", " ", value)

    return re.sub(
        r"\s+",
        " ",
        html.unescape(value)
    ).strip()


# ======================================
# 6. SKILL MATCHING
# ======================================

def calculate_match(job, user_skills):

    title = job.get("jobTitle", "").lower()

    excerpt = clean_text(
        job.get("jobExcerpt", "")
    ).lower()

    description = clean_text(
        job.get("jobDescription", "")
    ).lower()

    industry = job.get("jobIndustry") or []

    if not isinstance(industry, list):
        industry = [str(industry)]

    industry_text = " ".join(industry).lower()

    matched = []
    total_points = 0

    for skill in user_skills:

        pattern = (
            r"(?<!\w)"
            + re.escape(skill.lower())
            + r"(?!\w)"
        )

        points = 0

        if re.search(pattern, title):
            points = 5

        elif re.search(pattern, excerpt):
            points = 3

        elif re.search(pattern, industry_text):
            points = 2

        elif re.search(pattern, description):
            points = 1

        if points > 0:

            matched.append(skill)
            total_points += points

    # Highest possible score = 5 points per skill
    score = round(
        total_points / (5 * len(user_skills)) * 100
    )

    return score, matched


# ======================================
# 7. MANDATORY INSERTION SORT
# ======================================

def insertion_sort(items):

    for i in range(1, len(items)):

        key = items[i]
        j = i - 1

        while j >= 0 and items[j]["score"] < key["score"]:

            items[j + 1] = items[j]
            j -= 1

        items[j + 1] = key

    return items


# ======================================
# 8. SIDEBAR NAVIGATION
# ======================================

with st.sidebar:

    st.title("🎯 SkillMatch")
    st.caption("Your skills. Your opportunities.")

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Find Opportunities",
            "Saved Jobs",
            "About Project"
        ]
    )

    st.divider()

    st.caption("Python + Streamlit")
    st.caption("Algorithm: Insertion Sort")


# ======================================
# 9. FIND OPPORTUNITIES PAGE
# ======================================

if page == "Find Opportunities":

    st.title("Welcome to SkillMatch")
    st.write(
        "Discover real job opportunities that match your skills."
    )

    with st.form("search_form"):

        st.subheader("Search Your Opportunities")

        skills_input = st.text_input(
            "Your Skills",
            placeholder="Python, Excel, SQL"
        )

        col1, col2 = st.columns(2)

        with col1:

            location = st.text_input(
                "Country / Location",
                placeholder="Pakistan, USA, UK (optional)"
            )

        with col2:

            job_title = st.text_input(
                "Job Title",
                placeholder="Developer, Designer (optional)"
            )

        job_type_filter = st.selectbox(
            "Job Type",
            [
                "All",
                "Full-Time",
                "Part-Time",
                "Contract",
                "Internship",
                "Freelance"
            ]
        )

        search = st.form_submit_button(
            "Search Opportunities",
            use_container_width=True
        )

    if search:

        if not skills_input.strip():

            st.warning("Please enter your skills.")

        else:

            skills = list(dict.fromkeys(
                s.strip()
                for s in skills_input.split(",")
                if s.strip()
            ))

            try:

                with st.spinner(
                    "Finding real opportunities..."
                ):

                    jobs = fetch_jobs(tuple(skills))

                results = []

                for job in jobs:

                    title = job.get("jobTitle", "Unknown")
                    company = job.get("companyName", "Unknown")
                    job_location = job.get(
                        "jobGeo",
                        "Not specified"
                    )

                    types = job.get("jobType") or []

                    if isinstance(types, str):
                        types = [types]

                    types_text = ", ".join(types)

                    if (
                        job_type_filter != "All"
                        and job_type_filter.lower()
                        not in types_text.lower()
                    ):
                        continue

                    if (
                        location.strip()
                        and location.lower()
                        not in job_location.lower()
                    ):
                        continue

                    if (
                        job_title.strip()
                        and job_title.lower()
                        not in title.lower()
                    ):
                        continue

                    score, matched = calculate_match(
                        job,
                        skills
                    )

                    if score == 0:
                        continue

                    salary = ""

                    if (
                        job.get("salaryMin") is not None
                        or job.get("salaryMax") is not None
                    ):

                        salary = (
                            f'{job.get("salaryMin", "N/A")} - '
                            f'{job.get("salaryMax", "N/A")} '
                            f'{job.get("salaryCurrency", "")}'
                        )

                        if job.get("salaryPeriod"):
                            salary += (
                                " / " + job["salaryPeriod"]
                            )

                    job_url = job.get("url", "")

                    if not job_url.startswith(
                        ("https://", "http://")
                    ):
                        continue

                    results.append({

                        "title": title,
                        "company": company,
                        "location": job_location,
                        "score": score,
                        "matched": matched,
                        "job_type": types_text,
                        "salary": salary,
                        "description": clean_text(
                            job.get("jobExcerpt", "")
                        ),
                        "date": job.get("pubDate", ""),
                        "url": job_url

                    })

                sorted_results = insertion_sort(results)

                # Store search results
                st.session_state["results"] = sorted_results
                st.session_state["job_count"] = len(jobs)

            except requests.RequestException as error:

                st.error("Job service connection failed.")
                st.caption(str(error))

            except (ValueError, TypeError) as error:

                st.error("Unable to process job data.")
                st.caption(str(error))

    # DISPLAY SEARCH RESULTS
    if "results" in st.session_state:

        results = st.session_state["results"]

        st.divider()
        st.subheader("Search Overview")

        a, b, c = st.columns(3)

        a.metric(
            "Jobs Retrieved",
            st.session_state.get("job_count", 0)
        )

        b.metric("Matching Jobs", len(results))

        c.metric(
            "Status",
            "Completed"
        )

        st.divider()
        st.subheader("Recommended Opportunities")

        if results:

            for i, job in enumerate(results):

                with st.container(border=True):

                    left, right = st.columns([4, 1])

                    with left:

                        st.subheader(job["title"])
                        st.write("🏢", job["company"])
                        st.caption("📍 " + job["location"])

                    with right:

                        st.metric(
                            "Match Score",
                            f'{job["score"]}%'
                        )

                    st.progress(job["score"] / 100)

                    st.write(
                        "**Matched Skills:**",
                        ", ".join(job["matched"])
                    )

                    if job["job_type"]:
                        st.caption(
                            "Job Type: " + job["job_type"]
                        )

                    if job["salary"]:
                        st.write("**Salary:**", job["salary"])

                    with st.expander("Job Description"):

                        st.write(job["description"])
                        st.write("Published:", job["date"])

                    col_apply, col_save = st.columns(2)

                    with col_apply:

                        st.link_button(
                            "View / Apply Now ↗",
                            job["url"],
                            use_container_width=True
                        )

                    with col_save:

                        if st.button(
                            "⭐ Save Job",
                            key=f"save_{i}",
                            use_container_width=True
                        ):

                            save_job(job)
                            st.success("Job saved successfully!")

        else:

            st.warning(
                "No matches found. Try different skills or filters."
            )


# ======================================
# 10. SAVED JOBS PAGE
# ======================================

elif page == "Saved Jobs":

    st.title("⭐ Saved Opportunities")

    saved_jobs = get_saved_jobs()

    if saved_jobs:

        st.write(
            f"You have saved {len(saved_jobs)} opportunities."
        )

        for i, job in enumerate(saved_jobs):

            url, title, company, location, score, skills, job_type, salary = job

            with st.container(border=True):

                st.subheader(title)

                st.write("🏢", company)
                st.write("📍", location)
                st.write("Match Score:", str(score) + "%")
                st.write("Skills:", skills)

                if salary:
                    st.write("Salary:", salary)

                col1, col2 = st.columns(2)

                with col1:

                    st.link_button(
                        "View Opportunity",
                        url,
                        use_container_width=True
                    )

                with col2:

                    if st.button(
                        "Remove Saved Job",
                        key=f"remove_{i}",
                        use_container_width=True
                    ):

                        delete_saved_job(url)
                        st.rerun()

    else:

        st.info("You have not saved any jobs yet.")


# ======================================
# 11. PROJECT INFORMATION
# ======================================

elif page == "About Project":

    st.title("About SkillMatch")

    st.write(
        "SkillMatch is a Python-based skill matching "
        "and opportunity discovery application."
    )

    st.subheader("Technology Used")

    st.write("• Programming Language: Python")
    st.write("• User Interface: Streamlit")
    st.write("• Database: SQLite")
    st.write("• Real Job Data: Jobicy API")
    st.write("• Sorting Algorithm: Insertion Sort")

    st.subheader("Insertion Sort")

    st.write(
        "Insertion Sort arranges job opportunities "
        "in descending order according to their "
        "calculated matching scores."
    )

    st.write(
        "Time Complexity: O(n²) in the worst case."
    )

    st.subheader("Data Source")

    st.write(
        "Job listings are retrieved from Jobicy. "
        "The original listing links are provided for applications."
    )

    st.markdown(
        "[Visit Jobicy](https://jobicy.com/jobs)"
    )

# ======================================
# 12. FOOTER
# ======================================

st.divider()

st.caption(
    "SkillMatch | Python | Streamlit | SQLite | Insertion Sort"
)
