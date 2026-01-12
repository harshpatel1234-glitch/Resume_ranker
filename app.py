import os
import re
import json
import math
import datetime
from collections import Counter

from flask import (
    Flask, render_template, request, redirect,
    url_for, send_from_directory, flash, session
)
from werkzeug.utils import secure_filename

# Optional extraction libs
try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import docx
except Exception:
    docx = None

# ----------------------
# Config
# ----------------------
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXT = {".pdf", ".docx", ".doc"}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------
# Domain data (defaults)
# ----------------------
ACTION_VERBS = {
    "led", "designed", "developed", "implemented", "managed", "built", "created",
    "optimised", "optimized", "improved", "launched", "deployed", "engineered",
    "analyzed", "analysed", "research", "trained", "evaluated", "orchestrated",
    "automated", "integrated", "reduced", "increased", "scaled", "mentored"
}

# normalize skills to lowercase for reliable matching
COMMON_SKILLS = {
    "python","java","c++","c#","javascript","react","nodejs","node","express",
    "django","flask","sql","mongodb","postgres","aws","azure","gcp","docker",
    "kubernetes","git","html","css","pandas","numpy","scikit-learn","tensorflow",
    "pytorch","spacy","nlp","machine learning","deep learning","xgboost",
    "excel","tableau","powerbi","linux","bash","rest","api","graphql"
}

SECTION_KEYWORDS = {
    "summary": ["summary", "professional summary", "about me", "profile"],
    "experience": ["experience", "professional experience", "work experience", "employment"],
    "education": ["education", "academic", "qualifications"],
    "skills": ["skills", "technical skills", "skillset"],
    "projects": ["projects", "personal projects", "selected projects"],
    "certifications": ["certifications", "certification", "licenses", "awards"]
}

# ----------------------
# Helpers: extraction
# ----------------------
def allowed_filename(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXT

def extract_text_from_pdf(path: str) -> str:
    if pdfplumber is None:
        return ""
    text_parts = []
    try:
        with pdfplumber.open(path) as pdf:
            for pg in pdf.pages:
                txt = pg.extract_text()
                if txt:
                    text_parts.append(txt)
    except Exception:
        return ""
    return "\n".join(text_parts)

def extract_text_from_docx(path: str) -> str:
    if docx is None:
        return ""
    try:
        d = docx.Document(path)
        paragraphs = [p.text for p in d.paragraphs if p.text]
        return "\n".join(paragraphs)
    except Exception:
        return ""

# ----------------------
# Text utilities / regex
# ----------------------
_WORD_RE = re.compile(r"\b[A-Za-z0-9\+\#\.\-]+\b")
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+\s+")
_YEAR_RANGE_RE = re.compile(
    r"(?P<start>\b(19|20)\d{2})\s*(?:–|-|to|—)\s*(?P<end>\b(19|20)\d{2}|present|Present|Present\b)",
    re.IGNORECASE
)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\-\s\(\)]{7,}\d)")
LINKEDIN_RE = re.compile(r"(linkedin\.com\/[A-Za-z0-9_\-\/]+)", re.IGNORECASE)

def tokenize_words(text: str):
    return _WORD_RE.findall(text or "")

def count_sentences(text: str):
    parts = [s for s in _SENTENCE_SPLIT_RE.split(text or "") if s.strip()]
    return max(1, len(parts))

def estimate_syllables(word: str):
    w = word.lower()
    if len(w) <= 3:
        return 1
    w = re.sub(r'[^a-z]', '', w)
    w = re.sub(r'e$', '', w)
    groups = re.findall(r'[aeiouy]+', w)
    count = max(1, len(groups))
    return count

def count_syllables_in_text(text: str):
    words = tokenize_words(text)
    return sum(estimate_syllables(w) for w in words)

# ----------------------
# Analysis functions
# ----------------------
def detect_sections(text: str):
    text_lower = (text or "").lower()
    missing = []
    found = {}
    for sec, keywords in SECTION_KEYWORDS.items():
        found_any = any(k in text_lower for k in keywords)
        found[sec] = found_any
        if not found_any:
            missing.append(sec)
    return found, missing

def detect_action_verbs(text: str):
    words = [w.lower() for w in tokenize_words(text)]
    cnt = Counter(words)
    found = {v: cnt[v] for v in ACTION_VERBS if cnt[v] > 0}
    return found, sum(found.values())

def detect_skills(text: str):
    text_lower = (text or "").lower()
    found = []
    for s in COMMON_SKILLS:
        # match whole word or simple substring check for multi-word skills
        if re.search(r'\b' + re.escape(s) + r'\b', text_lower):
            found.append(s)
    return sorted(found)

def detect_contacts(text: str):
    email = EMAIL_RE.search(text or "")
    phone = PHONE_RE.search(text or "")
    linkedin = LINKEDIN_RE.search(text or "")
    return {
        "email_found": bool(email),
        "email": email.group(0) if email else None,
        "phone_found": bool(phone),
        "phone": phone.group(0) if phone else None,
        "linkedin_found": bool(linkedin),
        "linkedin": (linkedin.group(0) if linkedin else None)
    }

def detect_year_ranges(text: str):
    ranges = []
    for m in _YEAR_RANGE_RE.finditer(text or ""):
        start = m.group("start")
        end = m.group("end")
        try:
            s = int(start)
        except:
            continue

        if isinstance(end, str) and re.search(r'present', end, re.I):
            e = datetime.datetime.utcnow().year
        else:
            try:
                e = int(end)
            except:
                e = None

        if e:
            ranges.append((s, e))
    return sorted(ranges)

def detect_gaps(text: str):
    ranges = detect_year_ranges(text or "")
    gaps = []
    if not ranges:
        years = sorted({int(y) for y in _YEAR_RE.findall(text or "")})
        if len(years) >= 2:
            for a, b in zip(years, years[1:]):
                if b - a > 3:
                    gaps.append({"from": a, "to": b, "gap_years": b - a})
        return gaps
    prev_start = None
    prev_end = None
    for s, e in ranges:
        if prev_end is None:
            prev_start, prev_end = s, e
            continue
        if s - prev_end > 1:
            gaps.append({"from": prev_end, "to": s, "gap_years": s - prev_end})
        prev_start, prev_end = s, e
    return gaps

def detect_quantified(text: str):
    pct = re.findall(r'\d+(\.\d+)?\s*%', text or "")
    nums = re.findall(r'(?<!\w)(?:[$₹€]?\d{2,}(?:,\d{3})*(?:\.\d+)?)(?!\w)', text or "")
    return len(pct) + len(nums)

def bullet_analysis(text: str):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    bullet_markers = Counter()
    long_bullets = 0
    total_bullets = 0
    for l in lines:
        m = re.match(r'^([\-\u2022\*\–\•]|\d+\.)\s+', l)
        if m:
            total_bullets += 1
            marker = m.group(1)
            bullet_markers[marker] += 1
            after = re.sub(r'^([\-\u2022\*\–\•]|\d+\.)\s+', '', l)
            if len(tokenize_words(after)) > 30:
                long_bullets += 1
    issues = []
    if len(bullet_markers) > 1:
        issues.append("Inconsistent bullet markers detected")
    if long_bullets > 0:
        issues.append(f"{long_bullets} very long bullet points (consider shortening)")
    if total_bullets == 0:
        issues.append("No bullet points detected (use bullets for clarity)")
    return {
        "bullets_total": total_bullets,
        "bullets_markers": dict(bullet_markers),
        "long_bullets": long_bullets,
        "issues": issues
    }

def flesch_reading_ease(text: str):
    words = tokenize_words(text or "")
    num_words = max(1, len(words))
    sentences = max(1, count_sentences(text or ""))
    syllables = max(1, count_syllables_in_text(text or ""))
    score = 206.835 - 1.015 * (num_words / sentences) - 84.6 * (syllables / num_words)
    return round(score, 2)

# ----------------------
# Core analyzer
# ----------------------
def analyze_text(text: str):
    text = (text or "").strip()
    words = tokenize_words(text)
    word_count = len(words)
    page_estimate = max(1, math.ceil(word_count / 500))  # rough estimate (500 words/page)

    sections_found, missing_sections = detect_sections(text)
    verbs_found_map, action_verb_count = detect_action_verbs(text)
    detected_skills = detect_skills(text)
    skills_count = len(detected_skills)
    skills_density = round((skills_count / word_count) * 1000, 2) if word_count > 0 else 0.0
    gaps = detect_gaps(text)
    quant_count = detect_quantified(text)
    bullet_info = bullet_analysis(text)
    contacts = detect_contacts(text)
    readability = flesch_reading_ease(text)

    completeness_score = 100 - (len(missing_sections) * 10)
    verb_score = min(100, action_verb_count * 4)
    quant_score = min(100, quant_count * 6)
    skills_score = min(100, skills_count * 8)
    readability_score = max(0, min(100, int((readability + 20) / 1.2)))

    resume_flow = int((completeness_score * 0.25) + (verb_score * 0.15) + (quant_score * 0.15) + (skills_score * 0.2) + (readability_score * 0.25))

    num_spelling = max(0, word_count // 1200)
    num_grammar = max(0, word_count // 3500)

    total_issues = num_spelling + num_grammar + bullet_info.get("long_bullets", 0)

    sec_comp = max(0.0, 1.0 - (len(missing_sections) * 0.12))
    contact_comp = 1.0 if (contacts["email_found"] and contacts["phone_found"]) else 0.6 if (contacts["email_found"] or contacts["phone_found"]) else 0.2
    skills_comp = min(1.0, skills_count / 8.0)
    quant_comp = min(1.0, quant_count / 3.0)
    bullets_comp = 1.0 if bullet_info["bullets_total"] > 0 and not bullet_info["issues"] else 0.6
    readability_comp = max(0.0, min(1.0, (readability + 100.0) / 200.0))

    ats_score = int(round(100 * (
        sec_comp * 0.24 +
        contact_comp * 0.12 +
        skills_comp * 0.20 +
        quant_comp * 0.12 +
        bullets_comp * 0.10 +
        readability_comp * 0.12
    )))

    recommendations = []
    if len(missing_sections) > 0:
        recommendations.append("Add missing standard sections: " + ", ".join(missing_sections))
    if not contacts["email_found"]:
        recommendations.append("Add a professional email address in contact section.")
    if not contacts["phone_found"]:
        recommendations.append("Add a contact phone number.")
    if skills_count == 0:
        recommendations.append("List your technical skills clearly under a Skills section.")
    if quant_count == 0:
        recommendations.append("Add quantified achievements (numbers, percentages, metrics).")
    if bullet_info["bullets_total"] == 0:
        recommendations.append("Use bullet points under each role to improve scannability.")
    if bullet_info["long_bullets"] > 0:
        recommendations.append("Shorten long bullet points to one concise achievement per line.")
    if readability < 30:
        recommendations.append("Simplify sentence structure; aim for clearer, shorter sentences.")
    if ats_score < 50:
        recommendations.append("ATS score is low — prioritize skills, keywords, clear headings, and contact info.")

    analysis = {
        "ats_percentage": ats_score,
        "word_count": word_count,
        "page_estimate": page_estimate,
        "sections_found": sections_found,
        "missing_sections": missing_sections,
        "action_verbs_map": verbs_found_map,
        "action_verbs": action_verb_count,
        "detected_skills": detected_skills,
        "skills_count": skills_count,
        "skills_density": skills_density,
        "gaps": gaps,
        "quant_count": quant_count,
        "bullet_info": bullet_info,
        "num_spelling": num_spelling,
        "num_grammar": num_grammar,
        "repetition_count": 0,
        "total_issues": total_issues,
        "email_found": contacts["email_found"],
        "phone_found": contacts["phone_found"],
        "linkedin_found": contacts["linkedin_found"],
        "readability": readability,
        "resume_flow": resume_flow,
        "recommendations": recommendations,
        "generated_at": datetime.datetime.utcnow().isoformat()
    }

    return analysis

# ----------------------
# Routes
# ----------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "resumes" not in request.files:
            flash("No files part in request", "error")
            return redirect(request.url)
        files = request.files.getlist("resumes")
        if not files:
            flash("No files selected", "error")
            return redirect(request.url)

        saved_meta = []
        for f in files:
            if f.filename == "":
                continue
            filename = secure_filename(f.filename)
            if not allowed_filename(filename):
                flash(f"Skipping unsupported file type: {filename}", "warning")
                continue
            ts = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
            stored = f"{ts}__{filename}"
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], stored)
            f.save(save_path)

            # try text extraction
            _, ext = os.path.splitext(filename.lower())
            extracted = ""
            if ext == ".pdf":
                extracted = extract_text_from_pdf(save_path)
            elif ext in {".docx", ".doc"}:
                extracted = extract_text_from_docx(save_path)

            # run analysis (best-effort)
            analysis = analyze_text(extracted or "")

            # write analysis json next to file
            analysis_path = save_path + ".analysis.json"
            try:
                with open(analysis_path, "w", encoding="utf-8") as af:
                    json.dump(analysis, af, ensure_ascii=False, indent=2)
            except Exception:
                pass

            saved_meta.append({
                "orig_name": filename,
                "stored_name": stored,
                "path": save_path,
                "size": os.path.getsize(save_path)
            })

        if not saved_meta:
            flash("No valid files were uploaded.", "error")
            return redirect(request.url)

        session["upload_meta"] = saved_meta
        return redirect(url_for("results"))

    return render_template("index.html")

@app.route("/results")
def results():
    uploads = session.get("upload_meta", [])
    rows = []
    for u in uploads:
        stored = u["stored_name"]
        stored_path = os.path.join(app.config["UPLOAD_FOLDER"], stored)
        analysis = {}
        if os.path.exists(stored_path):
            analysis_path = stored_path + ".analysis.json"
            if os.path.exists(analysis_path):
                try:
                    with open(analysis_path, "r", encoding="utf-8") as af:
                        analysis = json.load(af)
                except Exception:
                    analysis = {}
            else:
                extracted = ""
                _, ext = os.path.splitext(stored.lower())
                if ext == ".pdf" and pdfplumber:
                    extracted = extract_text_from_pdf(stored_path)
                elif ext in {".docx", ".doc"} and docx:
                    extracted = extract_text_from_docx(stored_path)
                analysis = analyze_text(extracted or "")
        rows.append({
            "orig_name": u.get("orig_name"),
            "stored_name": stored,
            "size": u.get("size"),
            "analysis": analysis
        })
    return render_template("results.html", rows=rows)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

@app.route("/health")
def health():
    return "ok", 200

if __name__ == "__main__":
    app.run(debug=True)
