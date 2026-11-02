from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'
    received_checks = fields.Many2one('account.account', string='Received Checks')
    outgoing_checks = fields.Many2one('account.account', string='Outgoing Checks')
    hermes_account = fields.Many2one('account.account', string='Hermes Account')
    adib_account = fields.Many2one('account.account', string='ADIB Account')
    return_account = fields.Many2one('account.account', string='Return Account')

