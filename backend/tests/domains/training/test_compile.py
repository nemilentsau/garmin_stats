"""Semantic classification tests for compiled training entries."""

from app.domains.training.application import compile as compile_module


def test_running_bundle_classification_has_one_training_owned_source():
    classify = getattr(compile_module, "is_running_bundle", None)

    assert classify is not None
    assert classify("running.v3") is True
    assert classify("support.v3") is False
    assert classify("strength.v3") is False
