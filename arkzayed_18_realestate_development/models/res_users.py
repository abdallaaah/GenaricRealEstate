from odoo import models, fields,api

class ResUsers(models.Model):

    _inherit = 'res.users'

    realestate_project_ids = fields.Many2many('realestate.project', string='Projects')
    job_level_id = fields.Many2one('job.level')
