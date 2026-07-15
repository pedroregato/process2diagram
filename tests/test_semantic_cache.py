from services.semantic_cache import SemanticCache, _normalize_for_hash


def test_normalize_for_hash_collapses_whitespace():
    assert _normalize_for_hash("Texto  com   espacos\n\nextras") == "Texto com espacos extras"
    assert _normalize_for_hash("  \t leading and trailing \n") == "leading and trailing"


def test_compute_hash_whitespace_only_difference_matches():
    a = SemanticCache.compute_hash("deepseek", "model", "sys", "Texto  com   espacos\n\nextras")
    b = SemanticCache.compute_hash("deepseek", "model", "sys", "Texto com espacos extras")
    assert a == b


def test_compute_hash_content_change_still_differs():
    a = SemanticCache.compute_hash("deepseek", "model", "sys", "Texto com espacos extras")
    b = SemanticCache.compute_hash("deepseek", "model", "sys", "Texto com espacos diferentes")
    assert a != b


def test_compute_hash_differs_by_provider_model_system():
    base = SemanticCache.compute_hash("deepseek", "model", "sys", "user")
    assert base != SemanticCache.compute_hash("openai", "model", "sys", "user")
    assert base != SemanticCache.compute_hash("deepseek", "other-model", "sys", "user")
    assert base != SemanticCache.compute_hash("deepseek", "model", "other-sys", "user")
