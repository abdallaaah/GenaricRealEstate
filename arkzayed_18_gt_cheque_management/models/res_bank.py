from odoo import api, fields, models

class ResBank(models.Model):
    _inherit = 'res.bank'
    journal_id = fields.Many2one('account.journal',string='Journal',domain=[('type', '=', 'bank')])
