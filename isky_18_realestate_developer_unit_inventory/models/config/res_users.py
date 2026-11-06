from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    realestate_project_ids = fields.Many2many('realestate.project', string='Projects')
