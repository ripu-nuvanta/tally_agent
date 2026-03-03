def format_inr(amount: float) -> str:
    """Format amount with Indian comma system (₹12,34,567.00)."""
    negative = amount < 0
    amount = abs(amount)

    integer_part = int(amount)
    decimal_part = f"{amount:.2f}".split(".")[1]

    s = str(integer_part)
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        pairs = []
        while len(rest) > 2:
            pairs.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            pairs.append(rest)
        pairs.reverse()
        formatted = ",".join(pairs) + "," + last3

    result = f"₹{formatted}.{decimal_part}"
    if negative:
        result = f"-{result}"
    return result
