import pytest

from civicpulse.categorize import classify_category
from civicpulse.domain import Category


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("longkang tersumbat dekat sekolah", Category.BLOCKED_DRAIN),
        ("drain blocked again", Category.BLOCKED_DRAIN),
        ("jalan berlubang besar", Category.POTHOLE),
        ("air naik sebab banjir", Category.FLOODING),
        ("road under flood", Category.FLOODING),
        ("road is flooding", Category.FLOODING),
        ("road was flooded", Category.FLOODING),
        ("sampah tidak dikutip", Category.RUBBISH),
        ("lampu jalan rosak", Category.STREET_LIGHT),
    ],
)
def test_unique_category_signal_is_explainable(text: str, category: Category) -> None:
    prediction = classify_category(text)

    assert prediction.category is category
    assert prediction.matched_terms
    assert prediction.review_required is False


def test_no_category_signal_requires_review() -> None:
    prediction = classify_category("something happened near the market")

    assert prediction.category is Category.OTHER
    assert prediction.matched_terms == ()
    assert prediction.review_required is True


def test_equal_category_signals_require_review() -> None:
    prediction = classify_category("jalan berlubang and lampu jalan rosak")

    assert prediction.category is Category.OTHER
    assert prediction.review_required is True


def test_floodlight_is_not_a_flooding_category_signal() -> None:
    prediction = classify_category("floodlight is broken")

    assert prediction.category is Category.OTHER
    assert prediction.matched_terms == ()
