from odoo import fields,models



class ProjectProject(models.Model):
    _inherit = 'project.project'


    assignees_ids = fields.Many2many('res.users')