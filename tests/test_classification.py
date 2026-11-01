from app.services.classification import classify
from ssc_core.models.website import WebsiteType


def test_wordpress_is_classified_with_high_confidence():
    result = classify(
        {
            "has_wp_config": True,
            "has_wp_content_dir": True,
            "has_wp_includes_dir": True,
            "has_wp_admin_dir": True,
        }
    )
    assert result.website_type == WebsiteType.wordpress
    assert result.confidence > 0.7


def test_static_site_is_not_classified_as_wordpress():
    result = classify({"is_static_site_config": True, "has_index_html_only": True})
    assert result.website_type == WebsiteType.static


def test_wordpress_wins_even_if_static_heuristic_also_fires():
    # A WordPress site with a caching plugin can produce static-looking HTML
    # output, but wp-config.php existing must always win.
    result = classify(
        {
            "has_wp_config": True,
            "has_wp_content_dir": True,
            "is_static_site_config": True,
            "has_index_html_only": True,
        }
    )
    assert result.website_type == WebsiteType.wordpress


def test_laravel_app_is_classified_as_other():
    result = classify({"has_artisan_file": True, "has_composer_json": True})
    assert result.website_type == WebsiteType.other


def test_no_signal_is_unknown_not_guessed():
    result = classify({})
    assert result.website_type == WebsiteType.unknown
    assert result.confidence == 0.0


def test_weak_signal_below_threshold_is_unknown():
    # wp-admin existing alone (without wp-config/wp-content/wp-includes) is too
    # weak a signal on its own to commit to a classification.
    result = classify({"has_wp_admin_dir": True})
    assert result.website_type == WebsiteType.unknown
