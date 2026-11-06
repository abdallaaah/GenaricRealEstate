from odoo import fields, models, api


class Cluster(models.Model):
    _name = 'cluster'
    _description = "Real Estate Cluster"
    _inherit = ['realestate.hierarchy.node.mixin']

    name = fields.Char()
    abbreviation = fields.Char()
    system_code = fields.Char(compute="compute_unit_system_code", store=True)
    code = fields.Char()
    parent_source_id = fields.Reference([
        ('zone', 'Zone'),
        ('realestate.project', 'Project')
    ], string='Parent reference', required=1)
    location = fields.Char(compute='compute_cluster_location')
    project_phases_ids = fields.Many2many('real.estate.project.phase')
    project_type_ids = fields.Many2many('realestate.project.type', string='Type', required=True)
    project_id = fields.Many2one('realestate.project', compute="_compute_project_id", store=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    def compute_cluster_location(self):
        for rec in self:
            name = ''
            if rec.name:
                name += rec.name
            if rec.parent_source_id and rec.parent_source_id.location:
                name += ',' + rec.parent_source_id.location
            rec.location = name
