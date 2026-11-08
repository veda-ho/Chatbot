import re

from services.data_loader import (
    UNIVERSITIES, ELIGIBILITY, MODULES,
    resolve, place_name, unknown_place_reply, matches, norm,
)


# =========================================================
# NTU SCHOOL -> COLLEGE (the eligibility file uses colleges)
# =========================================================

COLLEGES = {
    "nbs": ["nbs", "business", "nanyangbusiness", "accountancy", "accounting", "finance"],
    "ccds": ["ccds", "computing", "computer", "scse", "datascience", "cs"],
    "coe": ["coe", "engineering", "eee", "mae", "cceb", "cee", "mse", "bioengineering"],
    "cos": ["cos", "science", "spms", "sbs", "ase", "physics", "chemistry", "maths", "mathematics", "biology"],
    "cohass": ["cohass", "hass", "humanities", "adm", "art", "design", "wkwsci", "communication",
               "economics", "psychology", "sociology", "history", "english", "linguistics"],
}
COLLEGE_NAMES = {"nbs": "NBS", "ccds": "CCDS", "coe": "College of Engineering",
                 "cos": "College of Science", "cohass": "CoHASS"}

# module file "school" column -> college
MODULE_SCHOOLS = {"CCDS": "ccds", "NBS": "nbs", "SPMS": "cos", "SBS": "cos", "ASE": "cos",
                  "CoHass": "cohass", "ADM": "cohass", "CCEB": "coe", "EEE": "coe",
                  "MAE": "coe", "CEE": "coe", "MSE": "coe"}


def to_college(school):
    s = norm(school)
    if not s:
        return None
    for college, words in COLLEGES.items():
        if any(s == w or (len(w) > 3 and w in s) for w in words):
            return college
    return None


def _cgpa(result):
    value = result.get("cgpa")
    if value is None:
        return None
    try:
        return float(re.findall(r"\d+(?:\.\d+)?", str(value))[0])
    except (IndexError, ValueError):
        return None


def _universities(result):
    """The university the user named, or every university in the country."""
    place = resolve(result.get("university"), result.get("destination"),
                    result.get("city"), result.get("country"))
    if place is None:
        return None, None
    if place["uni"] is not None:
        return place, UNIVERSITIES[UNIVERSITIES["uni_id"] == place["uni"]["uni_id"]]
    return place, UNIVERSITIES[UNIVERSITIES["country"] == place["country"]]


# =========================================================
# ELIGIBILITY
# =========================================================

def answer_eligibility(result, user_type="student"):
    place, unis = _universities(result)
    if place is None:
        return unknown_place_reply()
    if user_type == "staff":
        return "Exchange eligibility applies to students. Switch to Student if you're asking for a student."

    cgpa = _cgpa(result)
    college = to_college(result.get("school"))

    lines = [f"🎓 Exchange eligibility: {place_name(place)}", ""]
    for _, uni in unis.iterrows():
        rows = ELIGIBILITY[matches(ELIGIBILITY["university_name"], uni["match_key"])]
        spots = f"{uni['ntu_spots_sem1']} spots in Sem 1, {uni['ntu_spots_sem2']} in Sem 2"
        if rows.empty:
            lines.append(f"{uni['name']}: no eligibility data yet ({spots}).")
            continue
        if college:
            row = rows[rows["student_type"] == college]
            if row.empty:
                lines.append(f"❌ {uni['name']}: not open to {COLLEGE_NAMES[college]} students.")
                continue
            # some universities have more than one listing (e.g. Aalto's two business campuses)
            for r in row.itertuples():
                name = uni["name"] if len(row) == 1 else r.university_name
                need = r.min_cgpa
                if cgpa is None:
                    lines.append(f"{name}: minimum cGPA {need:.2f} for {COLLEGE_NAMES[college]}.")
                elif cgpa >= need:
                    lines.append(f"✅ {name}: eligible. You need {need:.2f}, you have {cgpa:.2f}.")
                else:
                    lines.append(f"❌ {name}: you need {need:.2f}, you have {cgpa:.2f}.")
            lines.append(f"   {uni['name']} has {spots}.")
        else:
            need = rows["min_cgpa"]
            open_to = ", ".join(COLLEGE_NAMES[c] for c in rows["student_type"].unique())
            range_text = f"{need.min():.2f}" if need.min() == need.max() else f"{need.min():.2f}–{need.max():.2f}"
            verdict = ""
            if cgpa is not None:
                verdict = "✅ " if cgpa >= need.min() else "❌ "
            lines.append(f"{verdict}{uni['name']}: minimum cGPA {range_text}, open to {open_to} ({spots}).")

    if not college:
        lines += ["", "Tell me your school (e.g. NBS, CCDS, EEE) for an exact answer."]
    lines += ["", "Spots are from the GEM Explorer AY25/26 vacancy list."]
    return "\n".join(lines)


# =========================================================
# MODULE MAPPINGS
# =========================================================

def answer_modules(result, user_type="student"):
    place, unis = _universities(result)
    if place is None:
        return unknown_place_reply()
    if len(unis) > 1:
        return (f"Which university in {place['country']}? "
                + ", ".join(unis["name"]) + ".")
    uni = unis.iloc[0]

    mods = MODULES[matches(MODULES["university"], uni["match_key"]) & (MODULES["status"] == "Approved")]
    if mods.empty:
        return f"📚 We don't have any approved module mappings for {uni['name']} yet."

    college = to_college(result.get("school"))
    if college:
        schools = [s for s, c in MODULE_SCHOOLS.items() if c == college]
        mods = mods[mods["school"].isin(schools + ["all"])]

    semester = result.get("semester")
    if semester in (1, 2, "1", "2"):
        by_sem = mods[mods["sem"] == int(semester)]
        if not by_sem.empty:
            mods = by_sem

    # school-specific mappings first, newest first, one example per NTU module
    mods = mods.assign(general=mods["school"] == "all").sort_values(["general", "year"], ascending=[True, False])
    total = mods["ntu_course_code"].nunique()
    examples = mods.drop_duplicates("ntu_course_code").head(8)

    who = f" for {COLLEGE_NAMES[college]}" if college else ""
    lines = [f"📚 Approved module mappings at {uni['name']}{who}",
             f"{total} NTU modules can be mapped. Some examples:", ""]
    for m in examples.itertuples():
        ntu = (f"{m.ntu_course_code} (broadening elective)" if m.ntu_course_code == m.ntu_course_name
               else f"{m.ntu_course_code} {m.ntu_course_name}")
        lines.append(f"• {ntu} ← {m.foreign_course_name} ({m.au:g} AU, approved {m.year} Sem {m.sem})")
    if not college:
        lines += ["", "Tell me your school (e.g. NBS, CCDS) to see only modules for you."]
    lines += ["", "Always check the latest mappings in NTU's Course Finder before you apply."]
    return "\n".join(lines)
