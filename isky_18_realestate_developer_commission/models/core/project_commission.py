from odoo import fields, models


class ProjectCommission(models.Model):
    _name = 'realestate.project.commission'
    _description = 'Realestate Project Commission'

    project_ids = fields.Many2many('realestate.project')
    broker_ids = fields.Many2many('res.partner',domain="[('is_broker','=',True)]")
    percentage = fields.Float()
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
