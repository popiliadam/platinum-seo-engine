"""D-06 — one Turkish-aware fold: İ/I mapped before lower-casing."""
from __future__ import annotations

from scripts.discovery import cannibalization_transform as cn
from scripts.discovery import on_page_audit_transform as op
from scripts.planning.new_content_plan_transform import make_url_slug
from scripts.util import text_fold as tf


def test_slug_of_dotted_capital_i() -> None:
    assert make_url_slug("İzmir Diş Kliniği") == "izmir-dis-klinigi"
    assert tf.slugify("İzmir Diş Kliniği") == "izmir-dis-klinigi"


def test_fold_key_matches_turkish_case_pairs() -> None:
    assert tf.fold_key("İzmir") == tf.fold_key("izmir")
    assert tf.fold_key("IŞIK") == tf.fold_key("ışık") == "isik"
    assert tf.fold_key("IKEA") == "ikea"


def test_brand_queries_match_across_turkish_case() -> None:
    assert cn._is_brand_query("izmir diş kliniği fiyat", ["İzmir Diş"])
    assert cn._is_brand_query("ışık mobilya", ["IŞIK"])
    assert op._is_brand_query("ışık mobilya", ["IŞIK"])


def test_hreflang_trailing_slash_is_same_page() -> None:
    from scripts.discovery import hreflang_audit_transform as ha
    assert ha._nurl("https://x.test/en/") == ha._nurl("https://x.test/en")


def test_cluster_map_gsc_urls_are_normalized() -> None:
    from scripts.planning import cluster_map_transform as cm
    assert cm._norm_page("  HTTPS://X.test/kombi/?utm_source=a ") == "https://x.test/kombi"
