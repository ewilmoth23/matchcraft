import re
from collections import Counter
from dataclasses import dataclass

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "JavaScript": ("javascript", "js"),
    "TypeScript": ("typescript",),
    "React": ("react", "react.js", "reactjs"),
    "Node.js": ("node.js", "nodejs", "node"),
    "FastAPI": ("fastapi",),
    "Django": ("django",),
    "Flask": ("flask",),
    "Java": ("java",),
    "C#": ("c#", "c sharp"),
    "C++": ("c++",),
    "Go": ("golang", "go programming"),
    "Rust": ("rust",),
    "Ruby": ("ruby",),
    "PHP": ("php",),
    "HTML": ("html", "html5"),
    "CSS": ("css", "css3"),
    "Tailwind CSS": ("tailwind", "tailwind css"),
    "SQL": ("sql",),
    "PostgreSQL": ("postgresql", "postgres"),
    "MySQL": ("mysql",),
    "SQLite": ("sqlite",),
    "SQLAlchemy": ("sqlalchemy",),
    "MongoDB": ("mongodb", "mongo"),
    "Redis": ("redis",),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure",),
    "Google Cloud": ("gcp", "google cloud"),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Terraform": ("terraform",),
    "Ansible": ("ansible",),
    "Git": ("git",),
    "Linux": ("linux",),
    "CI/CD": ("ci/cd", "continuous integration", "continuous delivery"),
    "REST APIs": ("rest api", "restful", "rest apis"),
    "GraphQL": ("graphql",),
    "Machine Learning": ("machine learning", "ml models"),
    "Large Language Models": ("large language model", "large language models", "llm", "llms"),
    "Natural Language Processing": ("natural language processing", "nlp"),
    "Pandas": ("pandas",),
    "NumPy": ("numpy",),
    "PyTorch": ("pytorch",),
    "TensorFlow": ("tensorflow",),
    "Apache Spark": ("apache spark", "pyspark"),
    "Kafka": ("kafka",),
    "Snowflake": ("snowflake",),
    "Databricks": ("databricks",),
    "Tableau": ("tableau",),
    "Power BI": ("power bi",),
    "Excel": ("excel",),
    "Data Analysis": ("data analysis", "data analytics"),
    "Jira": ("jira",),
    "Agile": ("agile",),
    "Scrum": ("scrum",),
    "Project Management": ("project management", "project manager"),
    "Stakeholder Management": ("stakeholder management", "stakeholder engagement"),
    "Leadership": ("leadership", "led teams", "team lead"),
    "Communication": ("communication", "written communication", "verbal communication"),
    "Collaboration": ("collaboration", "cross-functional collaboration", "collaborative"),
    "Problem Solving": ("problem solving", "problem-solving"),
    "Time Management": ("time management",),
    "Salesforce": ("salesforce",),
    "SAP": ("sap",),
}

SECTION_ALIASES: dict[str, set[str]] = {
    "summary": {"summary", "professional summary", "profile", "objective", "about"},
    "experience": {"experience", "work experience", "professional experience", "employment"},
    "skills": {"skills", "technical skills", "core competencies", "technologies", "expertise"},
    "education": {"education", "academic background", "training"},
    "certifications": {"certifications", "certificates", "licenses"},
    "projects": {"projects", "selected projects", "personal projects"},
}

ACTION_VERBS = {
    "achieved",
    "automated",
    "built",
    "coached",
    "collaborated",
    "coordinated",
    "created",
    "delivered",
    "deployed",
    "designed",
    "developed",
    "directed",
    "engineered",
    "established",
    "executed",
    "improved",
    "implemented",
    "increased",
    "launched",
    "led",
    "managed",
    "migrated",
    "optimized",
    "organized",
    "reduced",
    "resolved",
    "scaled",
    "shipped",
    "streamlined",
    "tested",
}

STOPWORDS = {
    # Scaffolding that appears in almost every requirement sentence. Counting these as
    # meaningful terms inflated the denominator of every overlap ratio, so a genuinely
    # matched requirement was scored as only partially covered.
    "ability",
    "demonstrated",
    "excellent",
    "experience",
    "familiarity",
    "knowledge",
    "proven",
    "strong",
    "understanding",
    "working",
    "and",
    "the",
    "with",
    "for",
    "that",
    "this",
    "from",
    "your",
    "you",
    "our",
    "are",
    "will",
    "have",
    "has",
    "job",
    "role",
    "work",
    "team",
    "years",
    "using",
    "into",
    "their",
    "about",
    "who",
    "but",
    "not",
    "all",
    "any",
    "can",
    "including",
    "preferred",
    "required",
    "skills",
}

# A deliberately small, conservative inflection rule. A job description says
# "scheduling appointments" where a résumé says "scheduled appointments"; without this
# they were different terms, and the evaluation corpus showed genuinely supported
# non-catalog requirements scored as merely transferable because of it. This is not a
# general-purpose stemmer: it only strips the three most common verb/plural endings, and
# only when a substantial stem remains, so unrelated words do not collapse together.
_INFLECTED = re.compile(r"^(?P<stem>[a-z][a-z0-9+#.-]{3,})(?:ing|ed)$")
# The lookbehind guards the stem's final character: never turn `analysis` into `analysi`,
# `process` into `proces`, `status` into `statu`, or `kubernetes` into `kubernete`.
_PLURAL = re.compile(r"^(?P<stem>[a-z][a-z0-9+#.-]{2,}(?<![siue]))s$")


# Explicit overrides for pairs the rule above cannot reach.
TERM_NORMALIZATION = {
    "builds": "build",
    "building": "build",
    "built": "build",
    "delivered": "deliver",
    "delivering": "deliver",
    "delivery": "deliver",
    "improved": "improve",
    "improving": "improve",
    "services": "service",
    "systems": "system",
    "tested": "test",
    "testing": "test",
    "tests": "test",
}


def normalize_inflection(word: str) -> str:
    """Collapse `scheduled`/`scheduling` and `providers`/`provider` onto one term."""
    if word in TERM_NORMALIZATION:
        return TERM_NORMALIZATION[word]
    # A token carrying a technical separator is a product name, not an English word.
    # Without this guard the plural rule turned `node.js` into `node.j`.
    if any(character in word for character in ".+#"):
        return word
    inflected = _INFLECTED.match(word)
    if inflected:
        return inflected.group("stem")
    plural = _PLURAL.match(word)
    if plural:
        return plural.group("stem")
    return word


@dataclass(frozen=True)
class SkillEvidence:
    skill: str
    excerpt: str
    line_number: int
    contextual: bool


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _contains_alias(text: str, alias: str) -> bool:
    return re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", text, re.IGNORECASE) is not None


def extract_skill_evidence(text: str) -> dict[str, SkillEvidence]:
    result: dict[str, SkillEvidence] = {}
    current_section: str | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        # Trim only from the ends so the stored excerpt stays an exact substring of the
        # reviewed résumé text. Interior whitespace is collapsed for matching only.
        excerpt = raw_line.lstrip("•●▪◦‣▸·∙*-–— \t").rstrip()
        line = normalize_space(excerpt)
        if not line:
            continue
        detected_section = section_kind(line.rstrip(":"))
        if detected_section:
            current_section = detected_section
            continue
        lower = line.casefold()
        line_tokens = re.findall(r"[a-z0-9+#.]+", lower)
        list_like = bool(re.match(r"^(skills?|technologies|tools|languages)\s*[:|]", lower))
        list_like = list_like or (len(line.split()) < 14 and line.count(",") >= 2)
        list_like = list_like or current_section == "skills"
        list_like = list_like or bool(re.search(r"https?://|\b\S+@\S+", line, re.IGNORECASE))
        list_like = list_like or (
            len(line_tokens) >= 3 and len(set(line_tokens)) / len(line_tokens) <= 0.5
        )
        for canonical, aliases in SKILL_ALIASES.items():
            if any(_contains_alias(lower, alias.casefold()) for alias in aliases):
                candidate = SkillEvidence(canonical, excerpt, line_number, not list_like)
                existing = result.get(canonical)
                if existing is None or (candidate.contextual and not existing.contextual):
                    result[canonical] = candidate
    return result


def section_kind(heading: str) -> str | None:
    candidate = re.sub(r"[^a-z ]", "", heading.casefold()).strip()
    for kind, aliases in SECTION_ALIASES.items():
        if candidate in aliases:
            return kind
    return None


def looks_like_heading(line: str) -> bool:
    clean = line.strip().rstrip(":")
    return bool(section_kind(clean)) or (
        1 <= len(clean.split()) <= 4
        and len(clean) <= 45
        and clean.upper() == clean
        and clean.isascii()
    )


def bullet_lines(text: str) -> list[str]:
    bullets: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^(?:[•●▪◦‣▸·∙*\-–—]|\d+[.)])\s+", stripped):
            bullet = re.sub(r"^(?:[•●▪◦‣▸·∙*\-–—]|\d+[.)])\s+", "", stripped).strip()
            if bullet:
                bullets.append(bullet)
    return bullets


def measurable_result(text: str) -> bool:
    has_metric = bool(
        re.search(
            r"(?:\$\s?\d|\d+(?:\.\d+)?\s?(?:%|percent|hours?|days?|weeks?|months?|users?|clients?|records?|x\b))",
            text,
            re.IGNORECASE,
        )
    )
    impact_language = bool(
        re.search(
            r"\b(?:increased|reduced|improved|saved|grew|cut|accelerated|decreased|raised|delivered|within|under)\b",
            text,
            re.IGNORECASE,
        )
    )
    return has_metric and impact_language


def starts_with_action_verb(text: str) -> bool:
    first = re.sub(r"[^a-z]", "", text.casefold().split(maxsplit=1)[0]) if text.strip() else ""
    return first in ACTION_VERBS


def significant_terms(text: str, limit: int = 30) -> list[str]:
    # Interior separators are meaningful (node.js, co-ordinate, c++), but a trailing
    # sentence period or dash is punctuation. Leaving it attached made "dashboards"
    # and "dashboards." distinct terms and silently broke requirement overlap.
    words = [
        trimmed
        for word in re.findall(r"[a-z][a-z0-9+#.-]{2,}", text.casefold())
        if len(trimmed := word.strip(".-")) >= 3
    ]
    counts = Counter(
        normalize_inflection(word) for word in words if word not in STOPWORDS and not word.isdigit()
    )
    return [word for word, _ in counts.most_common(limit)]


def date_formats_consistent(text: str) -> bool:
    ranges = re.findall(
        r"\b(?:[A-Z][a-z]{2,8}\s+\d{4}|\d{1,2}/\d{4}|\d{4})\s*(?:-|–|—|to)\s*"
        r"(?:Present|Current|Now|[A-Z][a-z]{2,8}\s+\d{4}|\d{1,2}/\d{4}|\d{4})\b",
        text,
        re.IGNORECASE,
    )
    styles: set[str] = set()
    for value in ranges:
        # "Present"/"Current"/"Now" are open-ended end markers, not month names, and
        # the range regex already accepts them case-insensitively.
        without_open_end = re.sub(r"(?i)\b(?:present|current|now)\b", "", value)
        if "/" in value:
            styles.add("numeric_month")
        elif re.search(r"[A-Za-z]{3,}", without_open_end, re.IGNORECASE):
            styles.add("named_month")
        else:
            styles.add("year_only")
    return len(styles) <= 1


def repeated_phrases(text: str, minimum_count: int = 3) -> list[str]:
    phrases: Counter[str] = Counter()
    for bullet in bullet_lines(text):
        terms = [term for term in significant_terms(bullet, 100) if len(term) >= 4]
        for index in range(len(terms) - 1):
            phrases[" ".join(terms[index : index + 2])] += 1
    return [phrase for phrase, count in phrases.most_common(5) if count >= minimum_count]
