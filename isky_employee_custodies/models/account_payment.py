from odoo import models, fields, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    custody_id = fields.Many2one('employee.custody', string='Employee Custody', copy=False)

    def _create_payment_entry(self, amount):
        res = super(AccountPayment, self)._create_payment_entry(amount)
        if self.custody_id:
            res['custody_id'] = self.custody_id.id
        return res
