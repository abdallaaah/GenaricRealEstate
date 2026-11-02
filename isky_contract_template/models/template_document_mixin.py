# -*- coding: utf-8 -*-
import base64
from urllib.parse import urlencode

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.mimetypes import guess_mimetype

from .html_to_docx import html_to_docx


class TemplateDocument(models.AbstractModel):
    _name = 'template.document.mixin'
    _description = 'Template Document Mixin'
    _inherit = ['mail.render.mixin']

    template_id = fields.Many2one('dynamic.template', string='Contract Template')
    body_html = fields.Html(
        'Body', render_engine='qweb', render_options={'post_process': True},
        prefetch=True, translate=True, sanitize=False, compute="_compute_body_html")
    # Filled in on demand, when /web/content streams the file to the browser.
    docx_file = fields.Binary(
        string='Word File', compute='_compute_docx_file', attachment=False)
    docx_filename = fields.Char(compute='_compute_docx_file')

    @api.depends('template_id', 'template_id.body_html')
    def _compute_body_html(self):
        for rec in self:
            if rec.template_id:
                result = rec._render_template_inline_template(rec.template_id.body_html, rec._name, rec.ids)
                rec.body_html = result.get(rec.id)
            else:
                rec.body_html = False

    @api.depends('body_html')
    def _compute_docx_file(self):
        for rec in self:
            rec.docx_filename = '%s.docx' % (rec.display_name or _('Contract')).replace('/', '-')
            rec.docx_file = base64.b64encode(rec._render_docx()) if rec.template_id else False

    def action_download_word(self):
        """Download the rendered contract as an editable Word file."""
        self.ensure_one()
        if not self.template_id:
            raise UserError(_("Select a contract template first: there is nothing "
                              "to write in the Word file."))
        query = urlencode({
            'model': self._name,
            'id': self.id,
            'field': 'docx_file',
            'filename_field': 'docx_filename',
            'download': 'true',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content?%s' % query,
            'target': 'self',
        }

    def _render_docx(self):
        """Return the contract as the bytes of a .docx file."""
        self.ensure_one()
        return html_to_docx(self._docx_header_html() + (self.body_html or ''))

    def _docx_header_html(self):
        """The company logo on top, mirroring what the PDF layout prints."""
        self.ensure_one()
        company = self.company_id if self._fields.get('company_id') and self.company_id \
            else self.env.company
        if not (self.template_id.with_logo and company.logo):
            return ''
        mimetype = guess_mimetype(base64.b64decode(company.logo))
        return ('<p style="text-align:center"><img src="data:%s;base64,%s" '
                'style="width:150pt"/></p>' % (mimetype, company.logo.decode()))
