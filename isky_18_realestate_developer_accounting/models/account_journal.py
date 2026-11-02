from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_security_deposit = fields.Boolean()
    is_reconcile_journal = fields.Boolean()

    @api.constrains('is_reconcile_journal')
    def _check_single_reconcile_journal(self):
        for journal in self:
            if not journal.is_reconcile_journal:
                continue
            existing = self.search([
                ('is_reconcile_journal', '=', True),
                ('company_id', '=', journal.company_id.id),
                ('id', '!=', journal.id),
            ], limit=1)
            if existing:
                raise ValidationError(_(
                    "Only one journal can be flagged as the Reconcile Journal per company. "
                    "'%s' is already flagged for company '%s'.",
                    existing.display_name, journal.company_id.display_name))

    @api.model
    def _get_reconcile_journal(self, company):
        return self.search([
            ('is_reconcile_journal', '=', True),
            *self._check_company_domain(company),
        ], limit=1)
