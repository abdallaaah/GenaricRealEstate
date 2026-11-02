from odoo import fields, models

class ProjectSalePhase(models.Model):

    _name = 'project.sale.phase'
    project_id = fields.Many2one('developer.project', string='Project')
    name = fields.Char()