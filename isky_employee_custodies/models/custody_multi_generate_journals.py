from odoo import models, api, _
from odoo.exceptions import ValidationError


class CustodyMultiGenerateJournals(models.TransientModel):
    _name = "custody.multi.generate.journals"
    _description = "Generate Journal Entry for Selected Custodies"

    def generate_journals(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        for record in self.env['employee.custody'].browse(active_ids):
            if record.state not in ('draft', 'open'):
                raise ValidationError(
                    _("Selected custody(s) cannot be confirmed as they are not in 'new' or 'open' state."))
            record.with_context({'button_type': 'receive'}).button_journal_entry()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
