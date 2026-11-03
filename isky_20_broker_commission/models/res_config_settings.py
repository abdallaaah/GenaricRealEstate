from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    base_percentage_threshold = fields.Float(
        config_parameter='isky_20_broker_commission.base_percentage_threshold',
        help="Below this project base commission percentage, the computed commission is halved.")
    base_max_commission_percentage_amount = fields.Float(
        config_parameter='isky_20_broker_commission.base_max_commission_percentage_amount',
        help="When the project base commission percentage exactly equals the threshold, "
             "the computed commission is capped at this amount.")
