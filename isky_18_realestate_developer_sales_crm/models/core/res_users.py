from odoo import models, fields,api

class ResUsers(models.Model):

    _inherit = 'res.users'

    job_level_id = fields.Many2one('job.level')
