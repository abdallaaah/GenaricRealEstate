# -*- coding: utf-8 -*-
"""Serialise rendered contract HTML into a Word (.docx) file.

Spire.Doc handles the way in (Word -> HTML) but cannot be used on the way
out: the bundled build is an evaluation one, so it refuses documents longer
than 500 paragraphs and stamps an evaluation banner on every file it writes.
The contracts are ~280 paragraphs today, which leaves no room to grow, hence
this small WordprocessingML writer.

Arabic is the whole point of the module, so every paragraph carries
``w:bidi``, every run its ``w:rtl`` flag and the complex-script twin of each
format (``w:szCs``, ``w:bCs``, ``w:iCs``, ``w:rFonts w:cs``).  Without those
Word applies its own complex-script defaults and the contract opens with
mis-ordered lines or missing glyphs.
"""

import base64
import logging
import re
import zipfile
from io import BytesIO
from xml.sax.saxutils import escape

from bs4 import BeautifulSoup, NavigableString, Tag

_logger = logging.getLogger(__name__)

DEFAULT_FONT = 'Times New Roman'
DEFAULT_FONT_SIZE_PT = 12.0
TWIPS_PER_PT = 20
EMU_PER_PT = 12700
PX_PER_PT = 96.0 / 72.0

# Tags that open a Word paragraph of their own.
PARAGRAPH_TAGS = ['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre']
HEADING_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
# Tags that only group other blocks: they never become a paragraph themselves.
CONTAINER_TAGS = ['html', 'body', 'div', 'section', 'article', 'header', 'footer',
                  'main', 'blockquote', 'center', 'form', 'td', 'th']
# Dropped together with their content.
SKIPPED_TAGS = ['style', 'script', 'head', 'meta', 'link', 'title', 'col', 'colgroup']
CELL_TAGS = ['td', 'th']
LIST_TAGS = ['ol', 'ul']
# Dynamic placeholders (e.g. "{{object.signatures_section}}") get substituted
# with block-level markup (divs, tables...) by mail.render.mixin, but authors
# commonly wrap the placeholder itself in <span> for inline editing. That
# nests block content inside what looks like inline content; checked against
# this list to tell the two apart.
BLOCK_TAGS = PARAGRAPH_TAGS + LIST_TAGS + CONTAINER_TAGS + ['table']

# Characters XML 1.0 cannot carry: Word refuses to open the file if one slips in.
_ILLEGAL_XML_CHARS = re.compile(
    u'[^\u0009\u000A\u000D\u0020-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]')
_LENGTH_RE = re.compile(r'^(-?[\d.]+)\s*(pt|px|in|cm|mm|em|rem|%)?$')
# Arabic, Hebrew and their presentation forms.
_RTL_CHARS_RE = re.compile(u'[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]')
_HEX_COLOR_RE = re.compile(r'^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
_RGB_COLOR_RE = re.compile(r'^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)')
_DATA_URI_RE = re.compile(r'^data:image/(?P<ext>[a-zA-Z0-9.+-]+);base64,(?P<data>.+)$', re.S)

CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Default Extension="jpg" ContentType="image/jpeg"/>
<Default Extension="gif" ContentType="image/gif"/>
<Default Extension="bmp" ContentType="image/bmp"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>"""

ROOT_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

SETTINGS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:zoom w:percent="100"/>
<w:defaultTabStop w:val="720"/>
<w:characterSpacingControl w:val="doNotCompress"/>
<w:themeFontLang w:val="en-US" w:bidi="ar-EG"/>
<w:compat/>
</w:settings>"""

DOCUMENT_NAMESPACES = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
)
# Relationship ids 1 to 3 are taken by styles, numbering and settings.
FIRST_IMAGE_RELATIONSHIP = 4


def _css(tag):
    """Return the inline ``style`` of ``tag`` as a {property: value} dict."""
    declarations = {}
    for declaration in (tag.get('style') or '').split(';'):
        prop, separator, value = declaration.partition(':')
        if separator:
            declarations[prop.strip().lower()] = value.strip()
    return declarations


def _length_pt(value, em_pt=DEFAULT_FONT_SIZE_PT):
    """Convert a CSS length to points, or None when it cannot be read."""
    if not value:
        return None
    match = _LENGTH_RE.match(str(value).strip())
    if not match:
        return None
    amount, unit = float(match.group(1)), match.group(2) or 'px'
    if unit == 'pt':
        return amount
    if unit == 'px':
        return amount / PX_PER_PT
    if unit == 'in':
        return amount * 72
    if unit == 'cm':
        return amount * 72 / 2.54
    if unit == 'mm':
        return amount * 72 / 25.4
    if unit in ('em', 'rem'):
        return amount * em_pt
    return None  # percentages have no absolute equivalent


def _twips(value_pt):
    return str(int(round(value_pt * TWIPS_PER_PT)))


def _color(value):
    """Convert a CSS colour to the RRGGBB form Word expects, or None."""
    if not value:
        return None
    match = _HEX_COLOR_RE.match(value.strip())
    if match:
        digits = match.group(1)
        if len(digits) == 3:
            digits = ''.join(digit * 2 for digit in digits)
        return digits.upper()
    match = _RGB_COLOR_RE.match(value.strip())
    if match:
        return '%02X%02X%02X' % tuple(min(255, int(channel)) for channel in match.groups())
    return None


def _font_name(value):
    """First family of a CSS font stack, unquoted."""
    return value.split(',')[0].strip().strip('\'"') or None


def _text(value):
    return escape(_ILLEGAL_XML_CHARS.sub('', value))


def _looks_rtl(text):
    """True when the text is mostly written in a right-to-left script."""
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return False
    right_to_left = sum(1 for character in letters if _RTL_CHARS_RE.match(character))
    return right_to_left * 5 >= len(letters)  # a fifth of the letters is plenty


def _is_trailing(tag):
    """True when nothing but blank text follows ``tag`` among its siblings."""
    sibling = tag.next_sibling
    while sibling is not None:
        if not (isinstance(sibling, NavigableString) and not sibling.strip()):
            return False
        sibling = sibling.next_sibling
    return True


def _is_inline_block(tag):
    """True when ``tag``'s own CSS sets display:inline-block."""
    return _css(tag).get('display') == 'inline-block'


def _inline_block_group(children, start_index):
    """Consecutive siblings from ``start_index`` that are all
    "display:inline-block", skipping blank text between them.
    Returns ``(group, next_index)``."""
    group = []
    index = start_index
    while index < len(children):
        sibling = children[index]
        if isinstance(sibling, NavigableString):
            if sibling.strip():
                break
            index += 1
            continue
        if not isinstance(sibling, Tag) or not _is_inline_block(sibling):
            break
        group.append(sibling)
        index += 1
    return group, index


# A safe column width budget: this converter's own page is A4 (11906 twips)
# with 1134-twip (56.7pt) margins on each side (see _section_xml), so about
# 482pt is usable; this leaves some room to spare.
_COLUMNS_WIDTH_PT = 460.0


def _columns_as_table(group, rtl):
    """Wrap sibling "inline-block" elements in a synthetic <table> (one row,
    one cell per element) so the existing table renderer - which already
    gets RTL column order and widths right - can lay them out side by side.
    Word has no inline-block: left alone, these would just stack."""
    soup = BeautifulSoup('', 'html.parser')
    table = soup.new_tag('table')
    if rtl:
        table['dir'] = 'rtl'
    row = soup.new_tag('tr')
    table.append(row)
    fallback_width_pt = _COLUMNS_WIDTH_PT / len(group)
    for column in group:
        css = _css(column)
        cell = soup.new_tag('td')
        if column.get('dir'):
            cell['dir'] = column['dir']
        width_pt = _length_pt(css.get('width')) or fallback_width_pt
        style_parts = ['vertical-align:top', 'width:%spt' % width_pt]
        if css.get('text-align'):
            style_parts.append('text-align:%s' % css['text-align'])
        cell['style'] = '; '.join(style_parts)
        for grandchild in list(column.children):
            cell.append(grandchild.extract())
        row.append(cell)
    return table


class _Format(object):
    """Run formatting, inherited down the HTML tree."""

    __slots__ = ('font', 'size_pt', 'bold', 'italic', 'underline', 'strike',
                 'color', 'rtl', 'vert_align')

    def __init__(self, font=DEFAULT_FONT, size_pt=DEFAULT_FONT_SIZE_PT, rtl=True):
        self.font = font
        self.size_pt = size_pt
        self.bold = False
        self.italic = False
        self.underline = False
        self.strike = False
        self.color = None
        self.rtl = rtl
        self.vert_align = None

    def copy(self):
        clone = _Format()
        for attribute in self.__slots__:
            setattr(clone, attribute, getattr(self, attribute))
        return clone

    def derive(self, tag):
        """Return a copy of self updated with the formatting ``tag`` carries."""
        fmt = self.copy()
        if tag.name in ('b', 'strong') or tag.name in HEADING_TAGS:
            fmt.bold = True
        elif tag.name in ('i', 'em'):
            fmt.italic = True
        elif tag.name in ('u', 'ins'):
            fmt.underline = True
        elif tag.name in ('s', 'strike', 'del'):
            fmt.strike = True
        elif tag.name == 'sub':
            fmt.vert_align = 'subscript'
        elif tag.name == 'sup':
            fmt.vert_align = 'superscript'

        direction = (tag.get('dir') or '').lower()
        if direction in ('rtl', 'ltr'):
            fmt.rtl = direction == 'rtl'

        css = _css(tag)
        if css.get('direction') in ('rtl', 'ltr'):
            fmt.rtl = css['direction'] == 'rtl'
        if css.get('font-family'):
            fmt.font = _font_name(css['font-family']) or fmt.font
        size_pt = _length_pt(css.get('font-size'), fmt.size_pt)
        if size_pt:
            fmt.size_pt = size_pt
        weight = css.get('font-weight')
        if weight:
            fmt.bold = weight in ('bold', 'bolder') or (weight.isdigit() and int(weight) >= 600)
        if css.get('font-style'):
            fmt.italic = css['font-style'] in ('italic', 'oblique')
        decoration = css.get('text-decoration') or css.get('text-decoration-line')
        if decoration:
            fmt.underline = 'underline' in decoration
            fmt.strike = 'line-through' in decoration
        fmt.color = _color(css.get('color')) or fmt.color
        return fmt

    def to_xml(self):
        """Run properties, in the order the schema mandates."""
        font = _text(self.font or DEFAULT_FONT)
        parts = ['<w:rFonts w:ascii="%s" w:hAnsi="%s" w:cs="%s"/>' % (font, font, font)]
        if self.bold:
            parts.append('<w:b/><w:bCs/>')
        if self.italic:
            parts.append('<w:i/><w:iCs/>')
        if self.strike:
            parts.append('<w:strike/>')
        if self.color:
            parts.append('<w:color w:val="%s"/>' % self.color)
        half_points = int(round((self.size_pt or DEFAULT_FONT_SIZE_PT) * 2))
        parts.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (half_points, half_points))
        if self.underline:
            parts.append('<w:u w:val="single"/>')
        if self.vert_align:
            parts.append('<w:vertAlign w:val="%s"/>' % self.vert_align)
        if self.rtl:
            parts.append('<w:rtl/>')
        return '<w:rPr>%s</w:rPr>' % ''.join(parts)


class _Paragraph(object):
    """Paragraph formatting, inherited down the HTML tree."""

    __slots__ = ('align', 'rtl', 'space_before_pt', 'space_after_pt', 'indent_start_pt',
                 'indent_end_pt', 'first_line_pt', 'page_break_before', 'num_id', 'level')

    def __init__(self, rtl=True):
        self.align = None
        self.rtl = rtl
        self.space_before_pt = None
        self.space_after_pt = None
        self.indent_start_pt = None
        self.indent_end_pt = None
        self.first_line_pt = None
        self.page_break_before = False
        self.num_id = None
        self.level = 0

    def copy(self):
        clone = _Paragraph()
        for attribute in self.__slots__:
            setattr(clone, attribute, getattr(self, attribute))
        return clone

    def derive(self, tag):
        """Return a copy of self updated with the layout ``tag`` carries."""
        para = self.copy()
        direction = (tag.get('dir') or '').lower()
        if direction in ('rtl', 'ltr'):
            para.rtl = direction == 'rtl'

        css = _css(tag)
        if css.get('direction') in ('rtl', 'ltr'):
            para.rtl = css['direction'] == 'rtl'
        align = (css.get('text-align') or tag.get('align') or '').lower()
        if align in ('left', 'right', 'center', 'justify', 'start', 'end'):
            para.align = align
        if css.get('margin') is not None:
            shorthand_pt = _length_pt(css['margin'].split()[0]) or 0.0
            para.space_before_pt = para.space_after_pt = shorthand_pt
        for prop, attribute in (('margin-top', 'space_before_pt'),
                                ('margin-bottom', 'space_after_pt')):
            value_pt = _length_pt(css.get(prop))
            if value_pt is not None:
                setattr(para, attribute, value_pt)
        # The "start" side of a RTL paragraph is the right one.
        sides = ('right', 'left') if para.rtl else ('left', 'right')
        for side, attribute in zip(sides, ('indent_start_pt', 'indent_end_pt')):
            margin_pt = _length_pt(css.get('margin-' + side))
            padding_pt = _length_pt(css.get('padding-' + side))
            if margin_pt is not None or padding_pt is not None:
                setattr(para, attribute, (margin_pt or 0.0) + (padding_pt or 0.0))
        first_line_pt = _length_pt(css.get('text-indent'))
        if first_line_pt is not None:
            para.first_line_pt = first_line_pt
        if 'always' in (css.get('page-break-before') or css.get('break-before') or ''):
            para.page_break_before = True
        return para

    def to_xml(self):
        """Paragraph properties, in the order the schema mandates."""
        parts = []
        if self.page_break_before:
            parts.append('<w:pageBreakBefore/>')
        if self.num_id:
            parts.append('<w:numPr><w:ilvl w:val="%d"/><w:numId w:val="%d"/></w:numPr>'
                         % (self.level, self.num_id))
        if self.rtl:
            parts.append('<w:bidi/>')
        if self.space_before_pt is not None or self.space_after_pt is not None:
            parts.append('<w:spacing w:before="%s" w:after="%s"/>'
                         % (_twips(self.space_before_pt or 0.0),
                            _twips(self.space_after_pt or 0.0)))
        indent = self._indent_xml()
        if indent:
            parts.append(indent)
        if self.align:
            parts.append('<w:jc w:val="%s"/>' % self._alignment())
        return '<w:pPr>%s</w:pPr>' % ''.join(parts) if parts else ''

    def _indent_xml(self):
        # w:left/w:right are start/end relative: Word mirrors them in a bidi paragraph.
        attributes = []
        if self.indent_start_pt:
            attributes.append('w:left="%s"' % _twips(self.indent_start_pt))
        if self.indent_end_pt:
            attributes.append('w:right="%s"' % _twips(self.indent_end_pt))
        if self.first_line_pt and self.first_line_pt < 0:
            attributes.append('w:hanging="%s"' % _twips(-self.first_line_pt))
        elif self.first_line_pt:
            attributes.append('w:firstLine="%s"' % _twips(self.first_line_pt))
        return '<w:ind %s/>' % ' '.join(attributes) if attributes else ''

    def _alignment(self):
        """CSS alignment as a ``w:jc`` value.

        Word reads ``left``/``right`` as the start/end of the text flow, so
        they swap over in a RTL paragraph (same mapping Spire.Doc writes for
        this markup).
        """
        if self.align == 'justify':
            return 'both'
        if self.align == 'center':
            return 'center'
        if self.align in ('start', 'end'):
            return 'left' if self.align == 'start' else 'right'
        if self.rtl:
            return 'left' if self.align == 'right' else 'right'
        return self.align


class HtmlToDocx(object):
    """Convert an HTML fragment into the bytes of a .docx file.

    Supported: paragraphs and headings, bold/italic/underline/strike, font
    family, size and colour, alignment and indentation, ordered and bulleted
    lists, tables (including colspan), line and page breaks, and images
    embedded as data URIs.
    """

    def __init__(self, html, rtl=None, default_font=DEFAULT_FONT,
                 default_size_pt=DEFAULT_FONT_SIZE_PT):
        self.html = html or ''
        self.rtl = rtl  # None: decide from the script the text is written in
        self.default_font = default_font
        self.default_size_pt = default_size_pt
        self._numbering = []  # one definition per list, in document order
        self._images = []  # (part name, bytes) in relationship order

    # -- public API ------------------------------------------------------

    def convert(self):
        """Return the bytes of the .docx file."""
        soup = BeautifulSoup(self.html, 'html.parser')
        for tag in soup.find_all(SKIPPED_TAGS):
            tag.decompose()
        root = soup.find('body') or soup
        if self.rtl is None:
            self.rtl = _looks_rtl(root.get_text(' '))
        blocks = self._render_blocks(
            root,
            _Format(self.default_font, self.default_size_pt, self.rtl),
            _Paragraph(self.rtl),
        )
        if not blocks or blocks[-1].startswith('<w:tbl>'):
            blocks.append('<w:p/>')  # Word expects a paragraph after a table
        return self._package(''.join(blocks))

    # -- block level -----------------------------------------------------

    def _render_blocks(self, node, fmt, para):
        """Return the block-level XML produced by the children of ``node``."""
        blocks, runs = [], []

        def flush():
            if runs:
                blocks.append(self._paragraph(para, runs))
                del runs[:]

        children = list(node.children)
        index = 0
        while index < len(children):
            child = children[index]
            if isinstance(child, NavigableString):
                text = str(child)
                # Whitespace between blocks is indentation of the HTML source.
                if node.name in CONTAINER_TAGS and not text.strip():
                    index += 1
                    continue
                runs.extend(self._text_runs(text, fmt))
                index += 1
            elif not isinstance(child, Tag):
                index += 1
                continue
            elif isinstance(child, Tag) and _is_inline_block(child):
                # Sibling "display:inline-block" elements are how templates
                # fake side-by-side columns for a browser. Word has no such
                # concept - divs always stack - so without this they would
                # just land one under another instead of side by side.
                flush()
                group, index = _inline_block_group(children, index)
                if len(group) >= 2:
                    blocks.append(self._table(_columns_as_table(group, para.rtl), fmt, para))
                else:
                    blocks.extend(self._render_blocks(group[0], fmt.derive(group[0]), para.derive(group[0])))
            elif child.name in LIST_TAGS:
                flush()
                blocks.extend(self._list_blocks(child, fmt, self._nested_para(para)))
                index += 1
            elif child.name == 'table':
                flush()
                blocks.append(self._table(child, fmt, para))
                index += 1
            elif child.name in PARAGRAPH_TAGS:
                flush()
                blocks.extend(self._paragraph_blocks(child, fmt, para))
                index += 1
            elif child.name in CONTAINER_TAGS:
                flush()
                blocks.extend(self._render_blocks(child, fmt.derive(child), para.derive(child)))
                index += 1
            elif child.find(BLOCK_TAGS):
                # An inline tag (e.g. a placeholder-carrying <span>) that
                # itself contains block content: a browser would implicitly
                # close it at the first block child, so treat it the same
                # way rather than flattening the block content into one run.
                flush()
                blocks.extend(self._render_blocks(child, fmt.derive(child), para.derive(child)))
                index += 1
            elif child.name == 'br' and _is_trailing(child):
                # A <br> with nothing after it adds no visible line, but
                # Word's w:jc="both" only skips stretching a paragraph's
                # true last line: a trailing break would make it think the
                # short line before it isn't the last one and justify-stretch
                # it edge to edge, spacing out every word.
                index += 1
            else:
                runs.extend(self._inline_runs(child, fmt))
                index += 1
        flush()
        return blocks

    def _paragraph_blocks(self, tag, fmt, para):
        """Render a <p>/<li>/<h*>: it always yields at least one paragraph."""
        child_para = para.derive(tag)
        blocks = self._render_blocks(tag, fmt.derive(tag), child_para)
        return blocks or [self._paragraph(child_para, [])]  # keep empty lines

    def _list_blocks(self, tag, fmt, para):
        """Render an <ol>/<ul>: each list gets its own numbering instance so
        that the ``start`` Word left in the HTML is honoured."""
        self._numbering.append({
            'bullet': tag.name == 'ul',
            'start': max(1, int(tag.get('start') or 1)) if tag.name == 'ol' else 1,
        })
        num_id = len(self._numbering)
        list_fmt, list_para = fmt.derive(tag), para.derive(tag)
        blocks = []
        for item in tag.find_all('li', recursive=False):
            item_para = list_para.derive(item)
            item_para.num_id = num_id
            item_para.level = min(8, para.level)
            item_blocks = self._render_blocks(item, list_fmt.derive(item), item_para)
            blocks.extend(item_blocks or [self._paragraph(item_para, [])])
        return blocks

    def _nested_para(self, para):
        """Context for a list: one level deeper when inside a list item."""
        nested = para.copy()
        if para.num_id:
            nested.level = min(8, para.level + 1)
        nested.num_id = None
        return nested

    def _paragraph(self, para, runs):
        return '<w:p>%s%s</w:p>' % (para.to_xml(), ''.join(runs))

    # -- tables ----------------------------------------------------------

    def _table(self, tag, fmt, para):
        rows = [row for row in tag.find_all('tr') if row.find(CELL_TAGS)]
        if not rows:
            return '<w:p/>'
        table_fmt, table_para = fmt.derive(tag), para.derive(tag)
        widths = self._column_widths(rows[0])
        borders = self._borders(tag, rows[0])

        properties = ['<w:tblPr>']
        if table_para.rtl:
            properties.append('<w:bidiVisual/>')
        properties.append('<w:tblW w:w="%d" w:type="%s"/>'
                          % (sum(widths), 'dxa' if widths else 'auto'))
        properties.append(borders['table'])
        if widths:
            properties.append('<w:tblLayout w:type="fixed"/>')
        properties.append('<w:tblCellMar><w:top w:w="0" w:type="dxa"/>'
                          '<w:left w:w="100" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/>'
                          '<w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr>')
        grid = '<w:tblGrid>%s</w:tblGrid>' % ''.join(
            '<w:gridCol w:w="%d"/>' % width for width in (widths or [1000]))

        rows_xml = []
        for row in rows:
            cells = [self._table_cell(cell, index, widths, borders, table_fmt, table_para)
                     for index, cell in enumerate(row.find_all(CELL_TAGS))]
            rows_xml.append('<w:tr>%s</w:tr>' % ''.join(cells))
        return '<w:tbl>%s%s%s</w:tbl>' % (''.join(properties), grid, ''.join(rows_xml))

    def _table_cell(self, cell, index, widths, borders, fmt, para):
        properties = []
        if index < len(widths):
            properties.append('<w:tcW w:w="%d" w:type="dxa"/>' % widths[index])
        colspan = int(cell.get('colspan') or 1)
        if colspan > 1:
            properties.append('<w:gridSpan w:val="%d"/>' % colspan)
        properties.append(borders['cell'])
        vertical_align = _css(cell).get('vertical-align') or cell.get('valign')
        if vertical_align in ('top', 'middle', 'bottom'):
            properties.append('<w:vAlign w:val="%s"/>'
                              % ('center' if vertical_align == 'middle' else vertical_align))
        cell_para = para.derive(cell)
        # Cell padding is already handled by the table margins.
        cell_para.indent_start_pt = cell_para.indent_end_pt = None
        blocks = self._render_blocks(cell, fmt.derive(cell), cell_para)
        if not blocks or blocks[-1].startswith('<w:tbl>'):
            blocks.append('<w:p/>')  # a cell has to end on a paragraph
        return '<w:tc><w:tcPr>%s</w:tcPr>%s</w:tc>' % (''.join(properties), ''.join(blocks))

    def _column_widths(self, row):
        """Column widths in twips, empty when the HTML does not give them all."""
        widths = []
        for cell in row.find_all(CELL_TAGS):
            width_pt = _length_pt(_css(cell).get('width')) or _length_pt(cell.get('width'))
            widths.append(int(round(width_pt * TWIPS_PER_PT)) if width_pt else 0)
        return widths if all(widths) else []

    def _borders(self, table, first_row):
        """Draw single borders as soon as the HTML asks for any."""
        bordered = table.get('border') not in (None, '0')
        for css in [_css(table)] + [_css(cell) for cell in first_row.find_all(CELL_TAGS)]:
            for prop, value in css.items():
                if prop.startswith('border') and 'none' not in value and 'hidden' not in value:
                    bordered = True
        if not bordered:
            return {'table': '', 'cell': ''}
        edges = ''.join('<w:%s w:val="single" w:sz="6" w:space="0" w:color="000000"/>' % edge
                        for edge in ('top', 'left', 'bottom', 'right'))
        inside = ''.join('<w:%s w:val="single" w:sz="6" w:space="0" w:color="000000"/>' % edge
                         for edge in ('insideH', 'insideV'))
        return {
            'table': '<w:tblBorders>%s%s</w:tblBorders>' % (edges, inside),
            'cell': '<w:tcBorders>%s</w:tcBorders>' % edges,
        }

    # -- inline level ----------------------------------------------------

    def _inline_runs(self, tag, fmt):
        if tag.name == 'br':
            return ['<w:r>%s<w:br/></w:r>' % fmt.to_xml()]
        if tag.name == 'img':
            return self._image_runs(tag)
        child_fmt = fmt.derive(tag)
        runs = []
        for child in tag.children:
            if isinstance(child, NavigableString):
                runs.extend(self._text_runs(str(child), child_fmt))
            elif isinstance(child, Tag):
                runs.extend(self._inline_runs(child, child_fmt))
        return runs

    def _text_runs(self, text, fmt):
        # HTML collapses whitespace; non-breaking spaces are content and stay.
        text = re.sub(r'[ \t\r\n]+', ' ', text)
        if not text:
            return []
        return ['<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (fmt.to_xml(), _text(text))]

    def _image_runs(self, tag):
        match = _DATA_URI_RE.match((tag.get('src') or '').strip())
        if not match:
            return []  # an external image would need a fetch: skip it, do not break
        extension = match.group('ext').lower()
        extension = {'jpeg': 'jpg', 'x-png': 'png'}.get(extension, extension)
        if extension not in ('png', 'jpg', 'gif', 'bmp'):
            return []
        try:
            data = base64.b64decode(match.group('data'))
        except Exception:
            _logger.warning("Skipping an image whose data URI is not valid base64")
            return []

        self._images.append(('image%d.%s' % (len(self._images) + 1, extension), data))
        index = len(self._images)
        width_pt, height_pt = self._image_size(tag, data)
        return ['<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
                '<wp:extent cx="%(cx)d" cy="%(cy)d"/><wp:docPr id="%(id)d" name="Picture %(id)d"/>'
                '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                '<pic:pic><pic:nvPicPr><pic:cNvPr id="%(id)d" name="Picture %(id)d"/>'
                '<pic:cNvPicPr/></pic:nvPicPr>'
                '<pic:blipFill><a:blip r:embed="rId%(rel)d"/>'
                '<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%(cx)d" cy="%(cy)d"/></a:xfrm>'
                '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
                '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>'
                % {'id': index, 'rel': FIRST_IMAGE_RELATIONSHIP + index - 1,
                   'cx': int(width_pt * EMU_PER_PT), 'cy': int(height_pt * EMU_PER_PT)}]

    def _image_size(self, tag, data):
        """Size in points: what the HTML asks for, else the image's own size."""
        css = _css(tag)
        width_pt = _length_pt(css.get('width')) or _length_pt(tag.get('width'))
        height_pt = _length_pt(css.get('height')) or _length_pt(tag.get('height'))
        natural_width_pt = natural_height_pt = 0.0
        try:
            from PIL import Image
            pixel_width, pixel_height = Image.open(BytesIO(data)).size
            natural_width_pt = pixel_width / PX_PER_PT
            natural_height_pt = pixel_height / PX_PER_PT
        except Exception:
            _logger.debug("Could not read the size of an embedded image", exc_info=True)
        ratio = (natural_height_pt / natural_width_pt) if natural_width_pt else 0.75
        if width_pt and not height_pt:
            height_pt = width_pt * ratio
        elif height_pt and not width_pt:
            width_pt = height_pt / ratio
        elif not width_pt:
            width_pt, height_pt = natural_width_pt or 300, natural_height_pt or 225
        return width_pt, height_pt

    # -- packaging -------------------------------------------------------

    def _package(self, body_xml):
        document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                    '<w:document %s><w:body>%s%s</w:body></w:document>'
                    % (DOCUMENT_NAMESPACES, body_xml, self._section_xml()))
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml', CONTENT_TYPES_XML)
            archive.writestr('_rels/.rels', ROOT_RELS_XML)
            archive.writestr('word/document.xml', document)
            archive.writestr('word/_rels/document.xml.rels', self._document_rels_xml())
            archive.writestr('word/styles.xml', self._styles_xml())
            archive.writestr('word/numbering.xml', self._numbering_xml())
            archive.writestr('word/settings.xml', SETTINGS_XML)
            for name, data in self._images:
                archive.writestr('word/media/%s' % name, data)
        return buffer.getvalue()

    def _section_xml(self):
        # A4 with 2cm margins, right-to-left section when the body is Arabic.
        return ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
                'w:header="709" w:footer="709" w:gutter="0"/>%s</w:sectPr>'
                % ('<w:bidi/>' if self.rtl else ''))

    def _document_rels_xml(self):
        base = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        relationships = [
            '<Relationship Id="rId1" Type="%sstyles" Target="styles.xml"/>' % base,
            '<Relationship Id="rId2" Type="%snumbering" Target="numbering.xml"/>' % base,
            '<Relationship Id="rId3" Type="%ssettings" Target="settings.xml"/>' % base,
        ]
        for index, (name, _data) in enumerate(self._images):
            relationships.append('<Relationship Id="rId%d" Type="%simage" Target="media/%s"/>'
                                 % (FIRST_IMAGE_RELATIONSHIP + index, base, name))
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '%s</Relationships>' % ''.join(relationships))

    def _styles_xml(self):
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:docDefaults><w:rPrDefault><w:rPr>'
                '<w:rFonts w:ascii="%(font)s" w:hAnsi="%(font)s" w:cs="%(font)s"/>'
                '<w:sz w:val="%(size)d"/><w:szCs w:val="%(size)d"/>%(rtl)s</w:rPr></w:rPrDefault>'
                '<w:pPrDefault><w:pPr>%(bidi)s'
                '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
                '</w:pPr></w:pPrDefault></w:docDefaults>'
                '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
                '<w:name w:val="Normal"/><w:qFormat/></w:style></w:styles>'
                % {'font': _text(self.default_font),
                   'size': int(round(self.default_size_pt * 2)),
                   'rtl': '<w:rtl/>' if self.rtl else '',
                   'bidi': '<w:bidi/>' if self.rtl else ''})

    def _numbering_xml(self):
        abstract, instances = [], []
        for index, definition in enumerate(self._numbering):
            abstract.append('<w:abstractNum w:abstractNumId="%d"><w:nsid w:val="%08X"/>'
                            '<w:multiLevelType w:val="hybridMultilevel"/>%s</w:abstractNum>'
                            % (index, index + 1, self._levels_xml(definition)))
            instances.append('<w:num w:numId="%d"><w:abstractNumId w:val="%d"/></w:num>'
                             % (index + 1, index))
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '%s%s</w:numbering>' % (''.join(abstract), ''.join(instances)))

    def _levels_xml(self, definition):
        bullets = [(u'', 'Symbol'), (u'o', 'Courier New'), (u'', 'Wingdings')]
        formats = ['decimal', 'lowerLetter', 'lowerRoman']
        levels = []
        for level in range(9):
            if definition['bullet']:
                marker, font = bullets[level % 3]
                number_xml = '<w:numFmt w:val="bullet"/><w:lvlText w:val="%s"/>' % _text(marker)
                run_properties = ('<w:rPr><w:rFonts w:ascii="%(font)s" w:hAnsi="%(font)s" '
                                  'w:cs="%(font)s" w:hint="default"/></w:rPr>' % {'font': font})
            else:
                number_xml = ('<w:numFmt w:val="%s"/><w:lvlText w:val="%%%d."/>'
                              % (formats[level % 3], level + 1))
                run_properties = ''
            levels.append('<w:lvl w:ilvl="%d"><w:start w:val="%d"/>%s<w:lvlJc w:val="left"/>'
                          '<w:pPr><w:ind w:left="%d" w:hanging="360"/></w:pPr>%s</w:lvl>'
                          % (level, definition['start'] if level == 0 else 1,
                             number_xml, 720 * (level + 1), run_properties))
        return ''.join(levels)


def html_to_docx(html, rtl=None, default_font=DEFAULT_FONT, default_size_pt=DEFAULT_FONT_SIZE_PT):
    """Return the bytes of a .docx file rendering ``html``."""
    return HtmlToDocx(html, rtl=rtl, default_font=default_font,
                      default_size_pt=default_size_pt).convert()
