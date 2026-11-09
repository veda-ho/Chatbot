"""
Pass a question to a real person at NTU.

When the bot can't help (the user asks for a person, it's an emergency, a
special case like an appeal, or we have no data), the reply gets a button
that opens an email to the right NTU office. The email already contains the
user's question, the details they gave the bot and the recent chat, so
they don't have to explain everything again.
"""
from urllib.parse import quote


# Who to contact. Students: NTU's GEM Explorer team (from ntu.edu.sg).
# Staff: NTU has no public travel-desk email, so the email opens with an
# empty "To" for the staff member to fill in. Put an address in "email"
# if your school has one.
CONTACTS = {
    "student": {
        "name": "NTU's GEM Explorer team (Office of Global Education and Mobility)",
        "short": "the GEM Explorer team",
        "email": "GEM-Explorer@ntu.edu.sg",
        "phone": "+65 6790 5878",
        "hours": "Mon–Thu 8:30am–5:30pm, Fri 8:30am–5pm",
    },
    "staff": {
        "name": "your school's finance or admin office (they handle travel approvals and claims)",
        "short": "your school office",
        "email": "",
        "phone": "",
        "hours": "",
    },
}

EMERGENCY = (
    "🚨 If you're in danger or hurt, call the local emergency number first:\n"
    "• 112 in Finland, Hungary, Luxembourg, Croatia and Indonesia\n"
    "• 113 (police) or 115 (ambulance) in Vietnam\n"
    "• 993 (police) or 991 (ambulance) in Brunei\n"
    "Singapore's Ministry of Foreign Affairs 24-hour hotline: +65 6379 8800 / 8855"
)
STUDENT_SOS = "NTU's 24/7 travel assistance (International SOS): +65 6338 7800"

# Phrases our answers use when we have no data for a place
NO_DATA = [
    "don't have any", "no eligibility data", "I can help with our 7 exchange destinations",
]

DETAIL_NAMES = [
    ("university", "University"), ("city", "City"), ("country", "Country"),
    ("destination", "Destination"), ("semester", "Semester"), ("month", "Month"),
    ("departure_date", "Flight date"), ("nights", "Nights"),
    ("school", "School"), ("cgpa", "cGPA"),
]


# =========================================================
# WHEN TO OFFER A PERSON
# =========================================================

def has_no_data(reply):
    return any(phrase in reply for phrase in NO_DATA)


# =========================================================
# THE REPLY TEXT
# =========================================================

def reply(result, user_type="student"):
    """The answer to 'I want to talk to a person' (intent: human_help)."""
    who = CONTACTS["staff" if user_type == "staff" else "student"]
    lines = []

    if result.get("urgent"):
        lines += [EMERGENCY]
        if user_type != "staff":
            lines.append(STUDENT_SOS)
        lines.append("")

    lines += ["🙋 Let me pass this to a person.", "",
              f"This needs {who['name']}."]
    if who["email"]:
        lines.append(f"✉️ {who['email']}")
    if who["phone"]:
        lines.append(f"📞 {who['phone']} ({who['hours']})")
    lines += ["", "Press the button below. It opens an email with your question and the "
                  "details you've told me, so you don't have to explain again."]
    return "\n".join(lines)


def offer_line(user_type="student"):
    """Added under answers where we have no data, or after the bot is stuck twice."""
    who = CONTACTS["staff" if user_type == "staff" else "student"]
    return f"🙋 Not what you needed? Press the button to ask {who['short']}."


def error_line(user_type="student"):
    """Added when Gemini is down, so an urgent question still reaches someone."""
    who = CONTACTS["staff" if user_type == "staff" else "student"]
    return f"🙋 If it's urgent, press the button to email {who['short']} instead."


# =========================================================
# THE BUTTON (a ready-to-send email)
# =========================================================

def button(user_type, message, history, context):
    """The 'email a person' button: its label and a mailto link with everything filled in."""
    staff = user_type == "staff"
    who = CONTACTS["staff" if staff else "student"]

    details = [f"- {label}: {context[key]}" for key, label in DETAIL_NAMES
               if context.get(key) not in (None, "", [])]

    recent = []
    for turn in (history or [])[-4:]:
        text = " ".join(str(turn.get("text", "")).split())
        if len(text) > 120:
            text = text[:120] + "..."
        recent.append(f"{'Me' if turn.get('role') == 'user' else 'Bot'}: {text}")

    question = " ".join(str(message).split())
    body = "\n".join(
        ["Hi,", "",
         f"I'm an NTU {'staff member' if staff else 'student'} using ExchangeBot and need help with this:",
         "", f"\"{question}\"", ""]
        + (["Details I gave the bot:"] + details + [""] if details else [])
        + (["Recent chat with the bot:"] + recent + [""] if recent else [])
        + ["Name:", "School:" if staff else "Matriculation number:", "", "Thank you!"]
    )
    subject = "ExchangeBot question: " + (question[:60] + ("..." if len(question) > 60 else ""))

    href = f"mailto:{who['email']}?subject={quote(subject)}&body={quote(body)}"
    label = "✉️ Email the GEM Explorer team" if not staff and who["email"] else "✉️ Write an email for help"

    # shows up in the Render logs, so we can count how often people need a person
    print(f"HANDOFF ({user_type}): {question[:80]}")

    return {"label": label, "href": href}
