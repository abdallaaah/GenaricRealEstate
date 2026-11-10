from odoo import fields, models


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    counted = fields.Boolean(
        help="Already counted in the related lead's meeting_counter; prevents double-counting "
             "on repeated recomputes.")
