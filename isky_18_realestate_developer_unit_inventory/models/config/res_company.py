from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    hierarchy_template_id = fields.Many2one(
        'realestate.hierarchy.template', string='Default Unit Hierarchy Template',
        help='Default set of middle levels (building/cluster/zone/floor), in order, used '
             'for new real estate projects. A project may override this.')
