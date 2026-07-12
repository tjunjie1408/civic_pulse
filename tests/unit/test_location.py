from civicpulse.domain import LocationCompatibility, LocationEntityKind
from civicpulse.location import compare_location_entities, extract_location_entities


def test_block_abbreviation_is_compatible():
    first = extract_location_entities("Pothole at Block A, Jalan Ampang")
    second = extract_location_entities("Pothole at Blok A, Jln Ampang")

    comparison = compare_location_entities(first, second)

    assert comparison.compatibility is LocationCompatibility.COMPATIBLE
    assert any(entity.kind is LocationEntityKind.BLOCK for entity in first)
    assert any(entity.kind is LocationEntityKind.STREET for entity in first)


def test_different_blocks_are_conflicting():
    first = extract_location_entities("Flood at Block A Jalan Ampang")
    second = extract_location_entities("Flood at Block B Jalan Ampang")

    comparison = compare_location_entities(first, second)

    assert comparison.compatibility is LocationCompatibility.CONFLICTING
    assert "block" in comparison.reasons[0]


def test_same_category_near_different_named_schools_conflicts():
    first = extract_location_entities("Pothole near SK Taman Maju")
    second = extract_location_entities("Pothole near SK Taman Jaya")

    comparison = compare_location_entities(first, second)

    assert comparison.compatibility is LocationCompatibility.CONFLICTING


def test_generic_near_school_has_unknown_location():
    first = extract_location_entities("Drain blocked near school")
    second = extract_location_entities("Drain blocked near school")

    comparison = compare_location_entities(first, second)

    assert first == ()
    assert second == ()
    assert comparison.compatibility is LocationCompatibility.UNKNOWN


def test_missing_location_entity_is_not_treated_as_compatible():
    first = extract_location_entities("Pothole at Block A")
    second = extract_location_entities("Pothole reported on Jalan Ampang")

    comparison = compare_location_entities(first, second)

    assert comparison.compatibility is LocationCompatibility.UNKNOWN
