from odoo import fields, models


class ProjectSalePhase(models.Model):
    _name = 'project.sale.phase'
    _description = "Project Sale Phase"

    name = fields.Char(required=True)
    project_id = fields.Many2one('developer.project', string="Project")
