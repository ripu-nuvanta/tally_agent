from backend.utils.currency_format import format_inr

def test_indian_format_lakhs():
    assert format_inr(123456.78) == "₹1,23,456.78"

def test_indian_format_crores():
    assert format_inr(12345678.90) == "₹1,23,45,678.90"

def test_negative_amount():
    assert format_inr(-50000) == "-₹50,000.00"

def test_zero():
    assert format_inr(0) == "₹0.00"

def test_small_number():
    assert format_inr(999.99) == "₹999.99"

def test_thousands():
    assert format_inr(50000) == "₹50,000.00"

def test_large_crores():
    assert format_inr(100000000) == "₹10,00,00,000.00"
