from src.utils.address_matcher import AddressMatcher


def test_normalize():
    assert AddressMatcher.normalize(" 4 a ") == "4A"
    assert AddressMatcher.normalize("B.B.") == "BB"
    assert AddressMatcher.normalize(" bb ") == "BB"
    assert AddressMatcher.normalize("") == ""


def test_expand_outage_numbers_ranges():
    # Rule 1: Standard Range
    assert AddressMatcher.expand_outage_numbers("13-15") == {"13", "14", "15"}
    # Rule 1 reversed: Should auto-fix backward ranges
    assert AddressMatcher.expand_outage_numbers("15-13") == {"13", "14", "15"}


def test_expand_outage_numbers_do_od():
    # Rule 2: DO X (Up to X)
    assert AddressMatcher.expand_outage_numbers("DO3") == {"1", "2", "3"}
    # Rule 3: OD X DO Y (From X to Y)
    assert AddressMatcher.expand_outage_numbers("OD10DO12") == {"10", "11", "12"}


def test_expand_outage_numbers_mixed_list():
    # EPBiH often uses comma-separated messes
    raw = "1, 3-4, DO2, BB"
    expected = {"1", "3", "4", "2", "BB"}  # "DO2" expands to 1, 2
    assert AddressMatcher.expand_outage_numbers(raw) == expected


def test_is_match():
    # High confidence match
    assert (
        AddressMatcher.is_match(user_house_number="14", raw_outage_numbers="13-15")
        is True
    )
    # Outside the range
    assert (
        AddressMatcher.is_match(user_house_number="16", raw_outage_numbers="13-15")
        is False
    )

    # WILDCARD SRE LOGIC: If user provides no number, they get the whole street
    assert (
        AddressMatcher.is_match(user_house_number="", raw_outage_numbers="1, 2, 3")
        is True
    )
    # WILDCARD SRE LOGIC: If EPBiH provides no number, the whole street is down
    assert (
        AddressMatcher.is_match(user_house_number="42", raw_outage_numbers="") is True
    )
