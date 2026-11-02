import ast
import base64
import logging
import os
import re
from odoo.exceptions import UserError, ValidationError
from bs4 import BeautifulSoup
from spire.doc import *
from spire.doc.common import *
from odoo import models, fields, api, _
from odoo.tools.rendering_tools import INLINE_TEMPLATE_REGEX

_logger = logging.getLogger(__name__)

PLACEHOLDER_BRACE_TOKEN_REGEX = re.compile(r"\{\{|\}\}")


class DynamicTemplate(models.Model):
    _name = 'dynamic.template'
    _description = 'Dynamic Template with Robust Word to HTML Conversion'

    name = fields.Char(string='Template Name', required=True)
    active = fields.Boolean(default=True)
    body_html = fields.Html(
        'Body', prefetch=True, translate=True, sanitize=False)

    word_file = fields.Binary(string='Upload Word File', attachment=True)
    word_filename = fields.Char(string='Filename')
    with_logo = fields.Boolean(string='With Logo')
    contract_count = fields.Integer(
        string='Contracts', compute='_compute_contract_count')

    def _compute_contract_count(self):
        """Count the contracts (sale proposals) rendering this template."""
        proposals = self.env['sale.proposal']
        counts = {}
        if proposals.has_access('read'):
            counts = dict(proposals._read_group(
                [('template_id', 'in', self.ids)], ['template_id'], ['__count']))
        for template in self:
            template.contract_count = counts.get(template, 0)

    def action_view_contracts(self):
        """Open the contracts (sale proposals) using this template."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contracts'),
            'res_model': 'sale.proposal',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id},
            'target': 'current',
        }

    @api.constrains('body_html')
    def _check_body_html_placeholders(self):
        for template in self:
            if template.body_html:
                template._validate_dynamic_placeholders(template.body_html)

    def _validate_dynamic_placeholders(self, html):
        """Reject unbalanced/malformed `{{ expression }}` dynamic placeholders
        before save, instead of letting them fail (or silently not render)
        later when the template is rendered (see
        rendering_tools.INLINE_TEMPLATE_REGEX / mail.render.mixin)."""
        depth = 0
        for token in PLACEHOLDER_BRACE_TOKEN_REGEX.findall(html):
            depth += 1 if token == '{{' else -1
            if depth < 0:
                raise ValidationError(_(
                    "Invalid dynamic placeholder in template \"%(name)s\": found a "
                    "closing \"}}\" without a matching opening \"{{\". Please fix "
                    "the placeholder before saving.",
                    name=self.name,
                ))
        if depth != 0:
            raise ValidationError(_(
                "Invalid dynamic placeholder in template \"%(name)s\": found an "
                "unclosed \"{{\" without a matching \"}}\". Please fix the "
                "placeholder before saving.",
                name=self.name,
            ))

        for match in INLINE_TEMPLATE_REGEX.finditer(html):
            expression = match.group(1).strip()
            try:
                ast.parse(expression, mode='eval')
            except SyntaxError as error:
                raise ValidationError(_(
                    "Invalid dynamic placeholder expression \"%(expr)s\" in "
                    "template \"%(name)s\": %(error)s",
                    expr=expression, name=self.name, error=error,
                ))

    @api.onchange('word_file')
    def _onchange_word_file(self):
        if self.word_file:
            try:
                file_content = base64.b64decode(self.word_file)
                temp_word_path = self._save_temp_file(file_content, 'temp_word_file.docx')
                temp_html_path = '/tmp/converted_document.html'

                self._convert_to_html(temp_word_path, temp_html_path)
                self.body_html = self._cleanup_html(self._read_file(temp_html_path))

                os.unlink(temp_word_path)
                os.unlink(temp_html_path)
            except Exception as e:
                raise UserError(f"Error converting Word file to HTML: {str(e)}")
        else:
            self.body_html = False

    def _save_temp_file(self, content, filename):
        temp_path = f'/tmp/{filename}'
        with open(temp_path, 'wb') as temp_file:
            temp_file.write(content)
        return temp_path

    def _read_file(self, filepath):
        with open(filepath, 'r') as file:
            return file.read()

    def _convert_to_html(self, word_path, html_path):
        document = Document()
        document.LoadFromFile(word_path)
        document.SaveToFile(html_path, FileFormat.Html)
        document.Close()

    def _cleanup_html(self, html_content):
        html_content = html_content.replace('margin-left: -', 'margin-left: 0')
        soup = BeautifulSoup(html_content, 'html.parser')
        self._remove_warning_spans(soup)
        self._update_body_style(soup)
        return str(soup)

    def _remove_warning_spans(self, soup):
        warning_span = soup.find('span', text=lambda t: t and 'warning' in t.lower())
        if warning_span:
            warning_span.decompose()

    def _update_body_style(self, soup):
        body_tag = soup.find('body')
        if body_tag and 'style' in body_tag.attrs:
            body_tag['style'] += 'margin-left: 20%;'
        else:
            body_tag['style'] = 'margin-left: 20%;'
