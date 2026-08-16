from collections import Counter

from PIL import Image

NEUTRAL_SATURATION = 24
SAMPLE_SIZE = 160


def _to_hex(colour):
    return "#{:02x}{:02x}{:02x}".format(*colour[:3])


def _saturation(colour):
    red, green, blue = colour[:3]
    return max(red, green, blue) - min(red, green, blue)


def dominant_colours(path, count=5, skip_neutrals=True):
    with Image.open(path) as image:
        sample = image.convert("RGB").copy()
        sample.thumbnail((SAMPLE_SIZE, SAMPLE_SIZE))
        quantised = sample.quantize(colors=32, method=Image.MEDIANCUT).convert("RGB")
        tally = Counter(quantised.getdata())

    ordered = [colour for colour, _ in tally.most_common()]
    if skip_neutrals:
        vivid = [colour for colour in ordered if _saturation(colour) >= NEUTRAL_SATURATION]
        ordered = vivid + [colour for colour in ordered if colour not in vivid]

    return [_to_hex(colour) for colour in ordered[:count]]


def dimensions(path):
    with Image.open(path) as image:
        return image.width, image.height


def is_landscape(width, height):
    return width >= height
