from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountAccount(models.Model):
    _inherit = "account.account"

    for_withholding_tax = fields.Boolean(default=False)

    change_ownership_type = fields.Selection([
        ('deferred_revenue', 'Deferred Revenue'),
        ('maintenance_fund', 'Maintenance Fund'),
        ('account_receivables', 'Account Receivables'),
    ])

    _sql_constraints = [
        ('unique_change_ownership_type', 'UNIQUE(change_ownership_type) WHERE change_ownership_type IS NOT NULL',
         'Each change ownership type can only be selected once across all accounts.')
    ]

    @api.constrains('change_ownership_type')
    def _check_unique_change_ownership_type(self):
        for record in self:
            if record.change_ownership_type:
                existing = self.search([
                    ('change_ownership_type', '=', record.change_ownership_type),
                    ('id', '!=', record.id)
                ], limit=1)
                if existing:
                    type_label = dict(record._fields['change_ownership_type'].selection).get(record.change_ownership_type)
                    raise ValidationError(
                        _('The change ownership type "%s" is already assigned to another account. '
                          'Each change ownership type can only be selected once.') % type_label
                    )
