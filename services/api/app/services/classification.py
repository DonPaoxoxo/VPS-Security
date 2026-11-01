"""Website classification engine.

Takes the read-only filesystem/vhost indicators an agent gathers for a single
virtual host and produces a (website_type, confidence, evidence) verdict.
Never reads credentials or database config values — only structural
indicators (file/directory existence, vhost directives).
"""

from dataclasses import dataclass

from ssc_core.models.website import WebsiteType

# Each rule: (candidate_type, indicator_key, weight, required_absence_keys)
# Weights are additive signal strength, not probabilities; final confidence
# is normalized against the strongest competing candidate.
_WORDPRESS_RULES: list[tuple[str, float]] = [
    ("has_wp_config", 0.45),
    ("has_wp_content_dir", 0.25),
    ("has_wp_includes_dir", 0.2),
    ("has_wp_admin_dir", 0.1),
]

_STATIC_RULES: list[tuple[str, float]] = [
    ("is_static_site_config", 0.5),  # agent-detected: vhost serves static files only, no PHP/proxy handler
    ("has_index_html_only", 0.3),
    ("has_spa_build_markers", 0.2),  # e.g. dist/ or build/ with hashed asset filenames
]

_OTHER_RULES: list[tuple[str, float]] = [
    ("has_artisan_file", 0.5),  # Laravel
    ("has_composer_json", 0.25),
    ("has_package_json_server", 0.4),  # Node.js server app (not a static SPA build)
    ("is_reverse_proxy", 0.5),
    ("has_server_side_php_files", 0.3),
]


@dataclass
class ClassificationResult:
    website_type: WebsiteType
    confidence: float
    evidence: list[tuple[WebsiteType, str, float]]


def classify(indicators: dict[str, bool]) -> ClassificationResult:
    scores: dict[WebsiteType, float] = {
        WebsiteType.wordpress: 0.0,
        WebsiteType.static: 0.0,
        WebsiteType.other: 0.0,
    }
    evidence: list[tuple[WebsiteType, str, float]] = []

    for rules, wtype in (
        (_WORDPRESS_RULES, WebsiteType.wordpress),
        (_STATIC_RULES, WebsiteType.static),
        (_OTHER_RULES, WebsiteType.other),
    ):
        for key, weight in rules:
            if indicators.get(key):
                scores[wtype] += weight
                evidence.append((wtype, key, weight))

    # A WordPress install is static-served at the HTTP layer but is never
    # classified as "static" — wp-config.php existing rules that out even if
    # a static-site heuristic also fired on cached HTML.
    if indicators.get("has_wp_config"):
        scores[WebsiteType.static] = 0.0

    best_type = max(scores, key=lambda t: scores[t])
    best_score = scores[best_type]

    if best_score <= 0:
        return ClassificationResult(WebsiteType.unknown, 0.0, [])

    # Confidence = best score normalized by itself plus runner-up, capped at 0.97.
    runner_up = max((v for t, v in scores.items() if t != best_type), default=0.0)
    confidence = best_score / (best_score + runner_up) if (best_score + runner_up) > 0 else best_score
    confidence = min(confidence, 0.97)

    # Require a minimum absolute signal strength before committing to a type —
    # otherwise classify as unknown rather than guessing.
    if best_score < 0.2:
        return ClassificationResult(WebsiteType.unknown, confidence, evidence)

    relevant_evidence = [e for e in evidence if e[0] == best_type]
    return ClassificationResult(best_type, confidence, relevant_evidence)
