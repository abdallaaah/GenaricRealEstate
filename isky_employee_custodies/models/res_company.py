from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    custody_account_id = fields.Many2one('account.account', string='Custody Account')
    custody_journal_id = fields.Many2one('account.journal', string='Journal')
    custody_payment_method_id = fields.Many2one('account.journal', string='Payment Method')
