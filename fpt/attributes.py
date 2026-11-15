"""The attribute list: what the team recorded in their workbook, how each word is matched, and what is searched.

One table holds everything, so it can be read and checked in one place:
- `posts`: a regular expression matched (whole words, any case) against the post fields the team filled in.
  Garments and styles are matched on the "category" field, fabrics on "category" + "fabrics", colours on "colour".
- `runway`: a regular expression matched against the runway trim fields ("type", "colour", "material").
- `plain` / `garment`: the Google search terms for (England, France, Denmark). `plain` is the bare word,
  searched inside Google's Apparel category; `garment` is the word with a typical garment, in all categories.
  The pilot (data/google_trends/pilot/decision.md) picked one form per type: SEARCH_FORM.
  For Denmark the England term is also tried (Danes often search in English); the one with more searches wins.
- `existing`: the item already on the site that covers this attribute. Where that item exists for a country,
  its series is reused for that country instead of a new search.
- `excluded`: why an attribute is shown from the team's data only, without a forecast.
"""
from __future__ import annotations

import re

TYPES = ["Garments", "Fabrics", "Colours", "Styles", "Runway details"]

# Field each type is matched on in posts.csv.
POST_FIELDS = {
    "Garments": ["category"],
    "Styles": ["category"],
    "Fabrics": ["category", "fabrics"],
    "Colours": ["colour"],
    "Runway details": ["category", "fabrics"],
}

# Inclusion rule.
MIN_POSTS = 2
MIN_RUNWAY = 5

# Search form per type, decided by the pilot (data/google_trends/pilot/decision.md):
# (form, Google category). Category 68 is "Apparel"; 0 is all categories.
SEARCH_FORM = {
    "Garments": ("plain", 68),
    "Fabrics": ("garment", 0),
    "Colours": ("garment", 0),
    "Styles": ("garment", 0),
    "Runway details": ("garment", 0),
}


def A(name, type_, posts=None, runway=None, plain=None, garment=None, existing=None, note="", excluded=""):
    return dict(name=name, type=type_, posts=posts, runway=runway, plain=plain, garment=garment,
                existing=existing, note=note, excluded=excluded)


# (GB, FR, DK) tuples for terms.
ATTRIBUTES = [
    # ---------------- Garments ----------------
    A("Dress", "Garments", r"dress(es)?|frocks?",
      plain=("dress", "robe", "kjole"),
      note="counts every kind of dress, including bodycon and lace dresses; 'frock' merged"),
    A("Trench coat", "Garments", r"trench( ?coats?)?", existing="Trench coat"),
    A("Blazer", "Garments", r"blazers?", existing="Blazer"),
    A("Coat", "Garments", r"(?<!trench )(?<!waist )coats?",
      plain=("coat", "manteau", "frakke"), note="'maxi coat' merged; trench coats counted separately"),
    A("Shirt", "Garments", r"(?<!t-)shirts?",
      plain=("shirt", "chemise", "skjorte"), note="T-shirts are counted under Top"),
    A("Sweater", "Garments", r"sweaters?|jumpers?|knitwear",
      plain=("jumper", "pull", "sweater"), note="'jumper' and 'knitwear' merged"),
    A("Trousers", "Garments", r"trousers?|pants",
      plain=("trousers", "pantalon", "bukser"), note="'trouser' and 'pants' merged"),
    A("Jeans", "Garments", r"jeans",
      plain=("jeans", "jean", "jeans"), note="wide-leg jeans also has its own item"),
    A("Skirt", "Garments", r"skirts?",
      plain=("skirt", "jupe", "nederdel")),
    A("Shorts", "Garments", r"shorts",
      plain=("shorts", "short", "shorts")),
    A("Top", "Garments", r"tops?|t-shirts?",
      plain=("top", "top", "top"), note="tank, off-shoulder and T-shirt tops merged"),
    A("Turtleneck", "Garments", r"turtle ?necks?",
      plain=("turtleneck", "col roulé", "rullekrave")),
    A("Scarf", "Garments", r"scarf|scarves|bandanas?|bandhana|badhana",
      plain=("scarf", "écharpe", "tørklæde"), note="bandanas merged (spelt 'bandhana'/'badhana' in the sheet)"),
    A("Hat", "Garments", r"hats?|caps?",
      plain=("hat", "chapeau", "hat"), note="caps merged"),
    A("Tights", "Garments", r"tights|stockings?|stalkings?",
      plain=("tights", "collants", "strømpebukser"), note="'stockings' (spelt 'stalkings') merged"),
    A("Bodycon dress", "Garments", r"bodycon", existing="Bodycon dress"),
    A("Bomber jacket", "Garments", r"bombers?( jackets?)?", existing="Bomber jacket"),
    A("Cardigan", "Garments", r"cardigans?", existing="Cardigan"),
    A("Slip dress", "Garments", r"slip dress(es)?", existing="Slip dress"),
    A("Wide-leg jeans", "Garments", r"wide[- ]leg", existing="Wide-leg jeans"),

    # ---------------- Fabrics ----------------
    A("Cotton", "Fabrics", r"cotton|corton",
      plain=("cotton", "coton", "bomuld"), garment=("cotton dress", "robe en coton", "bomuldskjole"), note="'corton' typo merged"),
    A("Wool", "Fabrics", r"wool",
      plain=("wool", "laine", "uld"), garment=("wool coat", "manteau en laine", "uldfrakke"), existing="Wool coat"),
    A("Satin", "Fabrics", r"satin",
      plain=("satin", "satin", "satin"), garment=("satin dress", "robe en satin", "satin kjole"),
      existing="Satin dress"),
    A("Knit", "Fabrics", r"knit(ted|s)?",
      plain=("knit", "maille", "strik"), garment=("knit dress", "robe en maille", "strikkjole"), note="ribbed and cable knits merged"),
    A("Denim", "Fabrics", r"denim",
      plain=("denim", "denim", "denim"), garment=("denim jacket", "veste en jean", "cowboyjakke")),
    A("Tweed", "Fabrics", r"tweed", runway=r"tweed",
      plain=("tweed", "tweed", "tweed"), garment=("tweed jacket", "veste en tweed", "tweed jakke"),
      existing="Tweed jacket", note="bouclé tweed also counted under Bouclé"),
    A("Leather", "Fabrics", r"leather",
      plain=("leather", "cuir", "læder"), garment=("leather jacket", "veste en cuir", "læderjakke"), existing="Leather jacket", note="faux leather included"),
    A("Lace", "Fabrics", r"lace", runway=r"lace|broderie anglaise",
      plain=("lace", "dentelle", "blonder"), garment=("lace dress", "robe en dentelle", "blondekjole"), existing="Lace dress"),
    A("Cashmere", "Fabrics", r"cashmere",
      plain=("cashmere", "cachemire", "kashmir"), garment=("cashmere jumper", "pull en cachemire", "kashmir sweater"), existing="Cashmere jumper"),
    A("Fur", "Fabrics", r"fur",
      plain=("fur", "fourrure", "pels"), garment=("faux fur coat", "manteau fausse fourrure", "pelsjakke"), note="faux fur included"),
    A("Jersey", "Fabrics", r"jersey",
      plain=("jersey", "jersey", "jersey"), garment=("jersey dress", "robe en jersey", "jerseykjole")),
    A("Chiffon", "Fabrics", r"chiffon",
      plain=("chiffon", "mousseline", "chiffon"), garment=("chiffon dress", "robe en mousseline", "chiffonkjole")),
    A("Velvet", "Fabrics", r"velvet",
      plain=("velvet", "velours", "fløjl"), garment=("velvet dress", "robe en velours", "fløjlskjole")),
    A("Suede", "Fabrics", r"suede",
      plain=("suede", "daim", "ruskind"), garment=("suede jacket", "veste en daim", "ruskindsjakke"), existing="Suede jacket"),
    A("Tulle", "Fabrics", r"tulle|net",
      plain=("tulle", "tulle", "tyl"), garment=("tulle skirt", "jupe en tulle", "tylskørt"), note="'net' merged"),
    A("Silk", "Fabrics", r"silk",
      plain=("silk", "soie", "silke"), garment=("silk dress", "robe en soie", "silkekjole")),
    A("Linen", "Fabrics", r"linen",
      plain=("linen", "lin", "hør"), garment=("linen trousers", "pantalon en lin", "hørbukser")),
    A("Crepe", "Fabrics", r"crepe",
      plain=("crepe", "crêpe", "crepe"), garment=("crepe dress", "robe en crêpe", "crepe kjole"),
      note="plain word also means the pancake, so the garment form is the safer test"),
    A("Mesh", "Fabrics", r"mesh",
      plain=("mesh", "résille", "mesh"), garment=("mesh top", "top en résille", "mesh top")),
    A("Bouclé", "Fabrics", r"boucl[eé]",
      plain=("boucle", "bouclette", "bouclé"), garment=("boucle jacket", "veste bouclette", "bouclé jakke")),
    A("Poplin", "Fabrics", r"poplin",
      plain=("poplin", "popeline", "poplin"), garment=("poplin shirt", "chemise en popeline", "poplin skjorte")),
    A("Twill", "Fabrics", r"twill|gabardine",
      excluded="a weave name that shoppers rarely search; shown from the posts only"),

    # ---------------- Colours ----------------
    A("White", "Colours", r"(?<!off )(?<!off-)white",
      plain=("white", "blanc", "hvid"), garment=("white dress", "robe blanche", "hvid kjole"), note="'off white' counted under Cream"),
    A("Black", "Colours", r"black",
      plain=("black", "noir", "sort"), garment=("black dress", "robe noire", "sort kjole")),
    A("Beige", "Colours", r"beige",
      plain=("beige", "beige", "beige"), garment=("beige dress", "robe beige", "beige kjole")),
    A("Brown", "Colours", r"brown",
      plain=("brown", "marron", "brun"), garment=("brown dress", "robe marron", "brun kjole"), existing="Brown dress", note="light, dark and chocolate brown merged"),
    A("Blue", "Colours", r"(?<!navy )blue",
      plain=("blue", "bleu", "blå"), garment=("blue dress", "robe bleue", "blå kjole"), note="light, dark and pastel blue merged; navy counted separately"),
    A("Burgundy", "Colours", r"burgundy",
      plain=("burgundy", "bordeaux", "bordeaux"), garment=("burgundy dress", "robe bordeaux", "bordeaux kjole"), existing="Burgundy dress"),
    A("Grey", "Colours", r"gr[ae]y",
      plain=("grey", "gris", "grå"), garment=("grey dress", "robe grise", "grå kjole")),
    A("Cream", "Colours", r"cream|creme|crème|off[ -]white|ivory",
      plain=("cream", "crème", "creme"), garment=("cream dress", "robe crème", "creme kjole"), note="'creme', 'off white' and 'ivory' merged"),
    A("Camel", "Colours", r"camel",
      plain=("camel", "camel", "camel"), garment=("camel coat", "manteau camel", "camel frakke"), note="searched with 'coat': a camel dress is rare and 'camel' alone is the animal"),
    A("Red", "Colours", r"red|cheery|chery",
      plain=("red", "rouge", "rød"), garment=("red dress", "robe rouge", "rød kjole"), note="'cherry red' (spelt 'cheery'/'chery') merged"),
    A("Navy", "Colours", r"navy",
      plain=("navy", "bleu marine", "marineblå"), garment=("navy dress", "robe bleu marine", "marineblå kjole")),
    A("Pink", "Colours", r"pink|rose",
      plain=("pink", "rose", "lyserød"), garment=("pink dress", "robe rose", "lyserød kjole"), note="blush, pastel and rose merged"),
    A("Green", "Colours", r"green|lime",
      plain=("green", "vert", "grøn"), garment=("green dress", "robe verte", "grøn kjole")),
    A("Yellow", "Colours", r"yellow|butter",
      plain=("yellow", "jaune", "gul"), garment=("yellow dress", "robe jaune", "gul kjole"), existing="Yellow dress", note="'butter' and 'buttermilk yellow' merged"),
    A("Silver", "Colours", r"silver",
      plain=("silver", "argenté", "sølv"), garment=("silver dress", "robe argentée", "sølv kjole")),
    A("Polka dots", "Colours", r"polka|dots?", existing="Polka dot dress",
      note="a print, grouped with colours"),

    # ---------------- Styles ----------------
    A("Casual", "Styles", r"casual ?wear|casual",
      plain=("casual", "casual", "casual"), garment=("casual outfit", "tenue décontractée", "casual outfit")),
    A("Evening wear", "Styles", r"evening ?wear|evening",
      plain=("evening", "soirée", "fest"), garment=("evening dress", "robe de soirée", "festkjole")),
    A("Formal / office", "Styles", r"formal(s|wear)?|office ?wear|corpcore",
      plain=("formal", "habillé", "pæn"), garment=("office outfit", "tenue de bureau", "kontortøj"), note="'corpcore' merged"),
    A("Loungewear", "Styles", r"lounge ?wear|pyjamas?",
      plain=("loungewear", "homewear", "loungewear"), garment=("loungewear", "homewear", "loungewear"),
      note="'night wear' left out: in the sheet it is used both for evening and for at-home looks"),
    A("Boho", "Styles", r"boho", existing="Boho dress"),

    # ---------------- Runway details ----------------
    A("Floral details", "Runway details", r"floral", runway=r"floral|flower|camellia|botanical",
      garment=("floral dress", "robe fleurie", "blomstret kjole")),
    A("Embroidery", "Runway details", r"embroider(y|ed)?", runway=r"embroider",
      garment=("embroidered dress", "robe brodée", "broderet kjole")),
    A("Sequins & beads", "Runway details", r"sequin(s|ed)?|beaded", runway=r"sequin|bead",
      garment=("sequin dress", "robe à sequins", "pailletkjole")),
    A("Pearls & crystals", "Runway details", r"pearls?|crystals?|rhinestones?", runway=r"pearl|crystal|jewel|rhinestone|glass",
      garment=("pearl embellished", "perles brodées", "perler kjole")),
    A("Gold hardware", "Runway details", None, runway=r"gold",
      garment=("gold buttons", "boutons dorés", "guldknapper"),
      note="trim entries whose colour includes gold (buttons, zips, rivets, embroidery)"),
    A("Studs & rivets", "Runway details", r"stud(s|ded)?|rivets?", runway=r"stud|rivet",
      garment=("studded jacket", "veste cloutée", "nitter jakke")),
    A("Exposed zips", "Runway details", None, runway=r"exposed|decorative zipper",
      excluded="shoppers rarely search for zip styles; shown from the runway data only"),
    A("Feathers", "Runway details", r"feathers?", runway=r"feather",
      garment=("feather dress", "robe à plumes", "fjerkjole"),
      excluded="below the inclusion rule (4 runway entries, no posts)"),
    A("Geometric motifs", "Runway details", r"geometric", runway=r"geometric",
      garment=("geometric print", "imprimé géométrique", "geometrisk print")),
    A("Animal motifs", "Runway details", r"leopard|animal|zebra", runway=r"animal|leopard|butterfly|bird|insect",
      garment=("leopard print dress", "robe léopard", "leopard kjole"),
      existing="Leopard print dress", note="leopard print in posts; animal, bird, insect and butterfly motifs on the runway"),
]

# Words recorded in the sheet but left out on purpose, with the reason.
DROPPED_WORDS = {
    "mixed": "not a colour: used for multi-coloured outfits",
    "neutral": "not one colour",
    "multicolour": "not one colour",
    "polyester": "generic fibre content, not a style choice",
    "viscose": "generic fibre content, not a style choice",
    "nylon": "generic fibre content, not a style choice",
    "elastane / spandex / lycra": "stretch fibre in the blend, not a style choice",
    "acrylic": "generic fibre content, not a style choice",
    "suiting": "generic word for tailoring cloth",
    "luxury": "a price level, not something the outfit is made of or looks like",
    "outerwear": "an umbrella group; the coats and jackets in it are counted one by one",
    "night wear": "used both for evening and for at-home looks in the sheet",
}


def _rx(pattern: str, stem: bool = False) -> re.Pattern:
    """Whole words: not preceded or followed by a letter. Post patterns list their endings explicitly;
    runway patterns are word stems ("embroider" matches "embroidery", "rivet" matches "rivets")."""
    tail = r"[a-zà-ÿ]*" if stem else ""
    return re.compile(r"(?<![a-zà-ÿ])(?:" + pattern + r")" + tail + r"(?![a-zà-ÿ])", re.IGNORECASE)


COMPILED = {a["name"]: (_rx(a["posts"]) if a["posts"] else None,
                        _rx(a["runway"], stem=True) if a["runway"] else None)
            for a in ATTRIBUTES}
BY_NAME = {a["name"]: a for a in ATTRIBUTES}
assert len(BY_NAME) == len(ATTRIBUTES), "duplicate attribute names"


def search_terms(a: dict) -> tuple[tuple[str, str, str] | None, int]:
    """The (GB, FR, DK) search terms and Google category for an attribute, following SEARCH_FORM.
    None when the attribute is not searched (or is covered only by an item already on the site)."""
    form, cat = SEARCH_FORM[a["type"]]
    return (None if a["excluded"] else a[form]), cat


def country_terms(a: dict, existing: dict[tuple[str, str], str]) -> dict[str, list[str]]:
    """Per country, the terms to use for an attribute: the existing site term when there is one
    (`existing` maps (country, English item name) -> term), otherwise the searched form; for Denmark the
    England term is added as an English alternative when it differs."""
    t, _ = search_terms(a)
    out = {}
    for i, cc in enumerate(["GB", "FR", "DK"]):
        if a["existing"] and (cc, a["existing"]) in existing:
            out[cc] = [existing[(cc, a["existing"])]]
        elif t is not None:
            out[cc] = [t[i]] + ([t[0]] if cc == "DK" and t[0] != t[i] else [])
    return out


def match_text(text: str, type_: str | None = None) -> set[str]:
    """Attributes of a type (or all types) whose post pattern occurs in `text`."""
    text = "" if text is None else str(text)
    out = set()
    for a in ATTRIBUTES:
        if type_ and a["type"] != type_:
            continue
        rx = COMPILED[a["name"]][0]
        if rx is not None and rx.search(text):
            out.add(a["name"])
    return out


def match_post(post: dict) -> set[str]:
    """All attributes a post mentions, each type matched on its own fields."""
    out = set()
    for type_ in TYPES:
        text = " | ".join(str(post.get(f) or "") for f in POST_FIELDS[type_])
        out |= match_text(text, type_)
    return out


def match_trim(trim: dict) -> set[str]:
    """Runway attributes one trim entry mentions (matched on type, colour and material)."""
    text = " | ".join(str(trim.get(f) or "") for f in ("type", "colour", "material"))
    out = set()
    for a in ATTRIBUTES:
        rx = COMPILED[a["name"]][1]
        if rx is not None and rx.search(text):
            out.add(a["name"])
    return out
