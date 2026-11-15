"""The attribute table and the word matching (fpt/attributes.py), on real strings from the team's workbook."""
import pytest

from fpt.attributes import ATTRIBUTES, BY_NAME, SEARCH_FORM, TYPES, match_post, match_text, match_trim, search_terms


def post(category='', fabrics='', colour=''):
    return match_post({'category': category, 'fabrics': fabrics, 'colour': colour})


@pytest.mark.parametrize('cell, expected', [
    ('Creme', {'Cream'}),
    ('Off white', {'Cream'}),
    ('Ivory', {'Cream'}),
    ('Navy Blue', {'Navy'}),                       # navy is not also blue
    ('Light Blue', {'Blue'}),
    ('White, Black', {'White', 'Black'}),
    ('Pearl White', {'White'}),
    ('cheery red', {'Red'}),
    ('Chery Red', {'Red'}),
    ('Blush Pink', {'Pink'}),
    ('Buttermilk Yellow', {'Yellow'}),
    ('Chocolate Brown', {'Brown'}),
    ('Ash Grey', {'Grey'}),
    ('Mixed', set()),
    ('Neutral', set()),
])
def test_colours(cell, expected):
    assert post(colour=cell) == expected


@pytest.mark.parametrize('cell, expected', [
    ('Trench Coat , Trouser', {'Trench coat', 'Trousers'}),
    ('Lace Stalkings', {'Tights', 'Lace'}),       # garment from the word, fabric from the same cell
    ('Maxi coat', {'Coat'}),
    ('Waist coat', set()),                          # a waistcoat is not a coat
    ('Trench coat', {'Trench coat'}),               # not also Coat
    ('T-shirt', {'Top'}),                           # T-shirts count as tops, not shirts
    ('Polo shirt', {'Shirt'}),
    ('Turtle neck shirt', {'Turtleneck', 'Shirt'}),
    ('Little black dress', {'Dress'}),
    ('Frock', {'Dress'}),
    ('Bodycon slit dress', {'Bodycon dress', 'Dress'}),
    ('Jumper', {'Sweater'}),
    ('Knitwear', {'Sweater'}),
    ('Skinny Pants', {'Trousers'}),
    ('Badhana', {'Scarf'}),
    ('Cap', {'Hat'}),
    ('Cashmere scarf', {'Scarf', 'Cashmere'}),
    ('Tweed blazer', {'Blazer', 'Tweed'}),
    ('Outerwear', set()),
])
def test_garments(cell, expected):
    assert post(category=cell) == expected


@pytest.mark.parametrize('cell, expected', [
    ('Casualwear', {'Casual'}),
    ('Casual wear', {'Casual'}),
    ('Evening & Luxury', {'Evening wear'}),
    ('Eveningwear', {'Evening wear'}),
    ('Formals', {'Formal / office'}),
    ('Office wear', {'Formal / office'}),
    ('Corpcore', {'Formal / office'}),
    ('Pyjamas', {'Loungewear'}),
    ('Night wear', set()),                          # ambiguous in the sheet, left out on purpose
    ('Demure Dressing', set()),                     # "dressing" is not "dress"
])
def test_styles(cell, expected):
    assert post(category=cell) == expected


@pytest.mark.parametrize('cell, expected', [
    ('Wool-blend suiting', {'Wool'}),
    ('Silk satin or polyester satin', {'Silk', 'Satin'}),
    ('Bouclé tweed', {'Bouclé', 'Tweed'}),
    ('Sequin Tweed Fabric/Bouclé Tweed, Sequin work', {'Sequins & beads', 'Tweed', 'Bouclé'}),
    ('Fur & Net', {'Fur', 'Tulle'}),
    ('Faux leather', {'Leather'}),
    ('Corton', {'Cotton'}),
    ('Cotton twill (leopard print)', {'Cotton', 'Twill', 'Animal motifs'}),
    ('Fine ribbed knit', {'Knit'}),
    ('Cotton-linen blend', {'Cotton', 'Linen'}),
    ('Embroidered cotton eyelet lace', {'Cotton', 'Lace', 'Embroidery'}),
    ('Polyester', set()),
    ('Viscose (rayon)', set()),
    ('Nylon spandex', set()),
])
def test_fabrics(cell, expected):
    assert post(fabrics=cell) == expected


@pytest.mark.parametrize('row, expected', [
    (dict(type='Floral embroidery', colour='Multicolour', material='Silk thread'), {'Floral details', 'Embroidery'}),
    (dict(type='Small metal rivets', colour='Silver/gunmetal', material='Metal'), {'Studs & rivets'}),
    (dict(type='Stud-like embellishments', colour='Silver/black', material='Metal'), {'Studs & rivets'}),
    (dict(type='Jewelled buttons', colour='Clear, silver, multicolour', material='Metal with glass/crystal stones'),
     {'Pearls & crystals'}),
    (dict(type='Exposed metal zipper', colour='Silver', material='Metal teeth'), {'Exposed zips'}),
    (dict(type='Decorative zipper', colour='Gold', material='Metal'), {'Exposed zips', 'Gold hardware'}),
    (dict(type='Concealed zipper', colour='Black', material='Nylon coil'), set()),
    (dict(type='Butterfly Motif', colour='Multicolour', material='Thread Embroidery'), {'Animal motifs', 'Embroidery'}),
    (dict(type='Camellia flower motif', colour='Multicolour', material='Printed fabric'), {'Floral details'}),
    (dict(type='Chantilly lace', colour='Black', material='Lace textile'), {'Lace'}),
    (dict(type='Tweed-covered buttons', colour='Matching tweed colours', material='Fabric covered base'), {'Tweed'}),
    (dict(type='Beaded embroidery', colour='Silver', material='Beads and thread'), {'Embroidery', 'Sequins & beads'}),
])
def test_runway(row, expected):
    assert match_trim(row) == expected


def test_table_is_complete():
    assert len(BY_NAME) == len(ATTRIBUTES)
    for a in ATTRIBUTES:
        assert a['type'] in TYPES, a['name']
        terms, cat = search_terms(a)
        assert cat == SEARCH_FORM[a['type']][1]
        if a['excluded']:
            assert terms is None, a['name']
            continue
        if terms is None:   # covered only by an item already on the site
            assert a['existing'], f"{a['name']}: no search term and no reason"
        else:
            assert len(terms) == 3 and all(t.strip() for t in terms), a['name']
        assert a['posts'] or a['runway'], f"{a['name']} is matched on nothing"


def test_match_text_is_whole_word():
    assert match_text('redress', 'Colours') == set()
    assert match_text('tops', 'Garments') == {'Top'}
    assert match_text('topshop', 'Garments') == set()
