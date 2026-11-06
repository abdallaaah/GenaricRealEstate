from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """S8: surfaces the two company-level cheque settings. related + readonly=False is the
    standard way to edit a company field from the settings form."""
    _inherit = 'res.config.settings'

    cheque_incoming_credit_account_id = fields.Many2one(
        'account.account',
        related='company_id.cheque_incoming_credit_account_id',
        readonly=False,
        domain=[('deprecated', '=', False)],
        string='Incoming Cheque Credit Account')

    cheques_enabled = fields.Boolean(
        related='company_id.cheques_enabled',
        readonly=False,
        string='Generate Cheques from Deals')
