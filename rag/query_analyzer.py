"""Query analysis and robust task detection.

Priority policy (explicit):
1) MCQ_ANSWERING if structure strongly looks like a question with options.
2) QUIZ_GENERATION if user explicitly asks to generate/train/test with new questions.
3) TEMPLATE_REQUEST only on strong documentary intent.
4) OPEN_QA otherwise.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Iterable

from .models import QueryAnalysis, TaskType
from .utils import normalize_text


MCQ_OPTION_PREFIXES = (
    r"^[A-Da-d][\)\.\-:：]\s+",
    r"^\(?[A-Da-d]\)?\s*[\)\.\-:：]\s+",
    r"^\d+[\)\.\-:：]\s+",
    r"^[-*•]\s+",
    r"^\[[ xX]?\]\s+",
)

MCQ_UI_NOISE_PATTERNS = (
    r"^\d+\s*points?$",
    r"^reponse obligatoire$",
    r"^choisissez.*$",
    r"^selectionnez.*$",
    r"^google forms?$",
    r"^notion$",
    r"^required$",
    r"^obligatoire$",
)

QUIZ_ACTION_MARKERS = [
    "genere", "cree", "fais", "prepare", "produis", "construis", "pose moi", "interroge moi",
    "teste moi", "entraine moi", "s entrainer", "reviser", "faire reviser",
]
QUIZ_TARGET_MARKERS = [
    "qcm", "quiz", "questionnaire", "questions", "entrainement", "revision", "test",
]

TEMPLATE_STRONG_MARKERS = [
    "template", "modele", "exemple de document", "document a remplir", "fichier",
    "telecharger", "telecharge", "formulaire", "trame", "envoie moi le document",
    "donne moi le document", "peux tu me fournir le document", "j ai besoin du template",
    "fournis moi", "partage le document",
]
TEMPLATE_WEAK_DOC_TERMS = [
    "avenant", "convention", "bon de commande", "pv", "proces verbal", "rm",
]

QUIZ_DIRECTIVE_PATTERN = re.compile(
    r"\b(?:genere|cree|fais|prepare|pose|interroge|teste|entraine|reviser?)\b.*\b(?:qcm|quiz|questions?)\b"
)

TEMPLATE_REQUEST_VERB_PATTERN = re.compile(
    r"\b(?:donne|envoie|fournis|partage|telecharge|j ai besoin|peux tu me fournir|peux tu envoyer)\b"
)


def _tokenize(text: str) -> list[str]:
    """Tokenize normalized text to alphanumeric chunks."""

    return [token for token in re.findall(r"[a-z0-9']+", normalize_text(text)) if len(token) >= 2]


def _ngrams(tokens: list[str], size: int) -> list[str]:
    if len(tokens) < size:
        return []
    return [" ".join(tokens[index:index + size]) for index in range(len(tokens) - size + 1)]


def _best_phrase_similarity(text: str, phrase: str) -> float:
    """Best similarity over words + local n-grams.

    Chosen thresholds are conservative to reduce false positives:
    - word threshold: high (single-word typo tolerance only)
    - phrase threshold: moderate (short expression tolerance)
    """

    normalized_text = normalize_text(text)
    normalized_phrase = normalize_text(phrase)
    if not normalized_text or not normalized_phrase:
        return 0.0
    if normalized_phrase in normalized_text:
        return 1.0

    text_tokens = _tokenize(normalized_text)
    phrase_tokens = _tokenize(normalized_phrase)

    candidates: list[str] = list(text_tokens)
    candidates.extend(_ngrams(text_tokens, 2))
    candidates.extend(_ngrams(text_tokens, 3))

    best = 0.0
    for candidate in candidates:
        score = SequenceMatcher(a=candidate, b=normalized_phrase).ratio()
        if score > best:
            best = score

    if phrase_tokens:
        window = len(phrase_tokens)
        for local_phrase in _ngrams(text_tokens, max(1, window)):
            score = SequenceMatcher(a=local_phrase, b=normalized_phrase).ratio()
            if score > best:
                best = score

    return best


def _fuzzy_contains(
    text: str,
    candidates: Iterable[str],
    word_threshold: float = 0.91,
    phrase_threshold: float = 0.85,
) -> bool:
    """Approximate detection using token + expression similarity."""

    normalized_text = normalize_text(text)
    words = _tokenize(normalized_text)

    for candidate in candidates:
        normalized_candidate = normalize_text(candidate)
        if normalized_candidate in normalized_text:
            return True

        for word in words:
            if SequenceMatcher(a=word, b=normalized_candidate).ratio() >= word_threshold:
                return True

        if _best_phrase_similarity(normalized_text, normalized_candidate) >= phrase_threshold:
            return True

    return False


def _clean_option_line(line: str) -> str:
    """Remove common prefixes from option lines (A), 1., bullets, checkboxes)."""

    cleaned = line.strip()
    cleaned = re.sub(r"^(?:[A-Da-d]|\d+)\s*[\)\.\-:：]\s*", "", cleaned)
    cleaned = re.sub(r"^\(?[A-Da-d]\)?\s*[\)\.\-:：]\s*", "", cleaned)
    cleaned = re.sub(r"^[-*•]\s*", "", cleaned)
    cleaned = re.sub(r"^\[[ xX]?\]\s*", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _looks_like_ui_noise(line: str) -> bool:
    normalized = normalize_text(line)
    return any(re.match(pattern, normalized) for pattern in MCQ_UI_NOISE_PATTERNS)


def _is_plausible_option(line: str) -> bool:
    """Filter out unlikely option lines (UI labels, long verbal paragraphs, etc.)."""

    normalized = normalize_text(line)
    if not normalized or len(normalized) < 2:
        return False
    if _looks_like_ui_noise(normalized):
        return False

    words = normalized.split()
    if len(words) > 18:
        return False

    if len(normalized) > 160:
        return False

    # Long, highly verbal lines are often instructions/context rather than options.
    verbal_markers = ["parce que", "veuillez", "merci", "selectionnez", "choisissez", "consigne"]
    if len(words) > 10 and any(marker in normalized for marker in verbal_markers):
        return False

    return True


def _option_homogeneity_score(options: list[str]) -> float:
    """Return a rough consistency score for candidate options (0..1)."""

    if len(options) < 2:
        return 0.0

    lengths = [len(normalize_text(opt).split()) for opt in options]
    max_len = max(lengths)
    min_len = min(lengths)
    if min_len == 0:
        return 0.0

    ratio = max_len / min_len
    if ratio <= 3.0:
        return 1.0
    if ratio <= 5.0:
        return 0.65
    return 0.35


def extract_mcq_options(query: str) -> list[str]:
    """Extract MCQ options from noisy multiline content.

    Strategy:
    1) collect prefixed options first (highest precision);
    2) fallback to structure-based extraction (statement + short option lines);
    3) drop UI/instruction lines and duplicate items;
    4) return [] if reliability is too weak.
    """

    lines = [line.strip() for line in (query or "").splitlines() if line.strip()]
    if len(lines) < 3:
        return []

    prefixed_options: list[str] = []
    for line in lines:
        if any(re.match(pattern, line) for pattern in MCQ_OPTION_PREFIXES):
            candidate = _clean_option_line(line)
            if _is_plausible_option(candidate):
                prefixed_options.append(candidate)

    if len(prefixed_options) >= 2:
        deduped_prefixed: list[str] = []
        for option in prefixed_options:
            if option not in deduped_prefixed:
                deduped_prefixed.append(option)
        return deduped_prefixed[:8]

    statement = normalize_text(lines[0])
    candidates: list[str] = []
    for line in lines[1:]:
        cleaned = _clean_option_line(line)
        normalized = normalize_text(cleaned)
        if not _is_plausible_option(cleaned):
            continue
        if normalized == statement:
            continue
        candidates.append(cleaned)

    deduped_candidates: list[str] = []
    for option in candidates:
        if option not in deduped_candidates:
            deduped_candidates.append(option)

    if not (2 <= len(deduped_candidates) <= 8):
        return []

    # Guardrail on heterogeneity: if options are too inconsistent, be conservative.
    if _option_homogeneity_score(deduped_candidates) < 0.40:
        return []

    return deduped_candidates


def _mcq_structure_signals(query: str, precomputed_options: list[str] | None = None) -> dict[str, float | bool | int]:
    """Compute MCQ structural features once to avoid duplicate work."""

    lines = [line.strip() for line in (query or "").splitlines() if line.strip()]
    options = precomputed_options if precomputed_options is not None else extract_mcq_options(query)

    prefixed_count = sum(
        1 for line in lines if any(re.match(pattern, line) for pattern in MCQ_OPTION_PREFIXES)
    )
    has_points_line = any(re.search(r"\b\d+\s*points?\b", normalize_text(line)) for line in lines)
    has_question_marker = any("?" in line for line in lines[:2])
    short_line_ratio = sum(1 for line in lines if len(line) <= 90) / max(1, len(lines))
    option_like_ratio = len(options) / max(1, len(lines) - 1)
    homogeneity = _option_homogeneity_score(options)

    score = 0.0
    if prefixed_count >= 2:
        score += 0.40
    if len(options) >= 2:
        score += 0.30
    if has_question_marker:
        score += 0.08
    if has_points_line:
        score += 0.08
    if short_line_ratio >= 0.70 and option_like_ratio >= 0.50:
        score += 0.14
    score += max(0.0, min(0.10, 0.10 * homogeneity))

    return {
        "score": min(score, 1.0),
        "prefixed_count": prefixed_count,
        "has_points_line": has_points_line,
        "has_question_marker": has_question_marker,
        "short_line_ratio": short_line_ratio,
        "option_like_ratio": option_like_ratio,
        "homogeneity": homogeneity,
        "option_count": len(options),
    }


def looks_like_mcq(query: str, precomputed_options: list[str] | None = None) -> bool:
    """Detect whether query structurally looks like an MCQ with options."""

    lines = [line.strip() for line in (query or "").splitlines() if line.strip()]
    if len(lines) < 3:
        return False

    signals = _mcq_structure_signals(query, precomputed_options=precomputed_options)
    return bool(signals["score"] >= 0.55)


def _detect_quiz_generation_request(normalized_query: str) -> tuple[bool, float, str]:
    """Detect explicit request to CREATE a quiz (not answer one)."""

    directive_hit = bool(QUIZ_DIRECTIVE_PATTERN.search(normalized_query))
    action_hit = _fuzzy_contains(normalized_query, QUIZ_ACTION_MARKERS, word_threshold=0.90, phrase_threshold=0.85)
    target_hit = _fuzzy_contains(normalized_query, QUIZ_TARGET_MARKERS, word_threshold=0.90, phrase_threshold=0.85)

    if directive_hit or (action_hit and target_hit):
        return True, 0.90, "Demande explicite de génération de quiz/QCM."

    if target_hit and re.search(r"\b\d+\b\s*questions?", normalized_query):
        return True, 0.84, "Demande d'entraînement avec nombre de questions explicite."

    if _fuzzy_contains(normalized_query, ["teste moi", "interroge moi", "entraine moi", "pose moi des questions"]):
        return True, 0.80, "Demande explicite d'entraînement (quiz à générer)."

    return False, 0.0, ""


def _detect_template_request(normalized_query: str) -> tuple[bool, float, str]:
    """Strict template detection to avoid legal-topic false positives."""

    strong_hit = _fuzzy_contains(normalized_query, TEMPLATE_STRONG_MARKERS, word_threshold=0.91, phrase_threshold=0.86)
    weak_doc_hit = _fuzzy_contains(normalized_query, TEMPLATE_WEAK_DOC_TERMS, word_threshold=0.92, phrase_threshold=0.87)
    explicit_request_verb = bool(TEMPLATE_REQUEST_VERB_PATTERN.search(normalized_query))

    if strong_hit:
        return True, 0.88, "Demande explicite de document via marqueurs forts."

    if explicit_request_verb and weak_doc_hit:
        return True, 0.76, "Demande explicite d'envoi/fourniture d'un document."

    return False, 0.0, ""


def _route_with_heuristics(query: str) -> QueryAnalysis:
    """Heuristic-first routing with explicit hierarchy.

    Priority order:
    1) MCQ structure
    2) quiz generation intent
    3) template request intent
    4) open QA
    """

    normalized = normalize_text(query)
    options = extract_mcq_options(query)
    mcq_signals = _mcq_structure_signals(query, precomputed_options=options)
    structure_is_mcq = bool(mcq_signals["score"] >= 0.55)

    if structure_is_mcq and len(options) >= 2:
        return QueryAnalysis(
            task_type=TaskType.MCQ_ANSWERING,
            normalized_query=normalized,
            confidence_score=max(0.70, min(0.97, float(mcq_signals["score"]))),
            mcq_options=options,
            rationale=(
                f"QCM détecté via structure multiligne, {len(options)} options plausibles, "
                f"score_structure={float(mcq_signals['score']):.2f}."
            ),
        )

    is_quiz, quiz_confidence, quiz_rationale = _detect_quiz_generation_request(normalized)
    if is_quiz:
        return QueryAnalysis(
            task_type=TaskType.QUIZ_GENERATION,
            normalized_query=normalized,
            confidence_score=quiz_confidence,
            rationale=quiz_rationale,
        )

    is_template, template_confidence, template_rationale = _detect_template_request(normalized)
    if is_template:
        return QueryAnalysis(
            task_type=TaskType.TEMPLATE_REQUEST,
            normalized_query=normalized,
            confidence_score=template_confidence,
            rationale=template_rationale,
        )

    return QueryAnalysis(
        task_type=TaskType.OPEN_QA,
        normalized_query=normalized,
        confidence_score=0.62,
        rationale="Aucune structure spécifique fiable détectée.",
    )


def _route_with_llm(query: str, llm, heuristic: QueryAnalysis) -> QueryAnalysis:
    """LLM fallback classification with robust JSON parsing and structural override."""

    if llm is None:
        return heuristic

    prompt = f"""
Tu es un classifieur d'intention pour assistant juridique.

Classes possibles:
- open_qa
- mcq_answering
- quiz_generation
- template_request

Règles de priorité:
1) Si la requête contient déjà un énoncé + options de réponse => mcq_answering.
2) Sinon si l'utilisateur demande de créer/générer/préparer un quiz => quiz_generation.
3) Sinon si l'utilisateur demande explicitement un document/template/fichier => template_request.
4) Sinon => open_qa.

Réponds STRICTEMENT en JSON valide:
{{
  "task_type": "open_qa|mcq_answering|quiz_generation|template_request",
  "confidence": 0.0,
  "rationale": "explication courte"
}}

Requête:
{query}
"""

    try:
        raw = llm.invoke(prompt)
        content = raw.content if hasattr(raw, "content") else str(raw)

        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            raise ValueError("No JSON found")

        payload = json.loads(match.group(0))
        task_raw = str(payload.get("task_type", "open_qa")).strip().lower()
        confidence = float(payload.get("confidence", 0.60))
        rationale = str(payload.get("rationale", "Fallback LLM classification")).strip()

        mapping = {
            "open_qa": TaskType.OPEN_QA,
            "mcq_answering": TaskType.MCQ_ANSWERING,
            "quiz_generation": TaskType.QUIZ_GENERATION,
            "template_request": TaskType.TEMPLATE_REQUEST,
        }
        llm_task = mapping.get(task_raw, TaskType.OPEN_QA)

        options = extract_mcq_options(query)
        if looks_like_mcq(query, precomputed_options=options) and len(options) >= 2 and llm_task != TaskType.MCQ_ANSWERING:
            return QueryAnalysis(
                task_type=TaskType.MCQ_ANSWERING,
                normalized_query=normalize_text(query),
                confidence_score=max(0.90, min(1.0, confidence)),
                mcq_options=options,
                rationale="Structure MCQ prioritaire: override du classement LLM incohérent.",
            )

        return QueryAnalysis(
            task_type=llm_task,
            normalized_query=normalize_text(query),
            confidence_score=max(0.0, min(confidence, 1.0)),
            mcq_options=options,
            rationale=rationale or "Fallback LLM classification",
        )
    except Exception:
        return heuristic


def analyze_query(query: str, llm=None) -> QueryAnalysis:
    """Analyze query with heuristics first, then LLM fallback when needed.

    MCQ structural evidence always has priority over conflicting LLM output.
    """

    heuristic = _route_with_heuristics(query)

    if heuristic.task_type == TaskType.MCQ_ANSWERING and heuristic.confidence_score >= 0.75:
        return heuristic
    if heuristic.confidence_score >= 0.88:
        return heuristic

    llm_result = _route_with_llm(query, llm=llm, heuristic=heuristic)

    if heuristic.task_type == TaskType.MCQ_ANSWERING and len(heuristic.mcq_options) >= 2:
        return heuristic

    if llm_result.confidence_score < 0.55:
        return heuristic

    return llm_result


if __name__ == "__main__":
    samples = [
        "à quoi sert un avenant ?",
        "A quelle fréquence une Junior-Entreprise est-elle auditée ?\n10 points\n3 mois\n6 mois\n1 an\n2 ans\nRéponse obligatoire",
        "Une Convention d’Etude\nest obligatoire\nn’est pas obligatoire",
        "génère un QCM sur les avenants",
        "fais-moi 10 questions pour m’entraîner",
        "pose-moi 5 questions sur la convention d'étude",
        "interroge-moi sur les avenants",
        "teste-moi sur le cadre légal CNJE",
        "donne-moi un modèle d’avenant",
        "j’ai besoin du template de convention",
        "convention cadre ou convention d'étude, quelle différence ?",
        "réponds à ce QCM :\nA) Oui\nB) Non",
    ]

    for sample in samples:
        analysis = analyze_query(sample, llm=None)
        print("=" * 80)
        print(sample)
        print("->", analysis.task_type.value, "| conf=", round(analysis.confidence_score, 3))
        print("rationale:", analysis.rationale)
        if analysis.mcq_options:
            print("options:", analysis.mcq_options)
