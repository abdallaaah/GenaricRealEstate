from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    broker_sequence_prefix = fields.Char(related='company_id.broker_sequence_prefix', readonly=False)
