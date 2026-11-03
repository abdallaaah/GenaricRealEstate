from odoo import fields,models



class ProjectTask(models.Model):
    _inherit = 'project.task'


    assignees_ids = fields.Many2many(related='project_id.assignees_ids')