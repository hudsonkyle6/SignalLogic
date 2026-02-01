# engine/sparkline.py

def sparkline(data, width=28):
    """
    Generate a unicode sparkline from a list of floats.
    Normalizes data 0–1 and maps to block characters.
    """
    if not data:
        return ""

    blocks = "▁▂▃▄▅▆▇█"
    mn = min(data)
    mx = max(data)

    # Avoid zero division
    if mx == mn:
        return blocks[0] * min(len(data), width)

    normalized = [(v - mn) / (mx - mn) for v in data]
    chars = [blocks[int(n * (len(blocks) - 1))] for n in normalized]

    # Limit to dashboard width
    if len(chars) > width:
        chars = chars[-width:]

    return "".join(chars)
