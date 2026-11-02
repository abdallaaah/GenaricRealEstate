from odoo import fields, models, api


class Cluster(models.Model):
    _name = 'cluster'
    _description = "Real Estate Cluster"

    name = fields.Char()
    abbreviation = fields.Char()
    system_code = fields.Char(compute="compute_unit_system_code")
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

    @api.depends('parent_source_id')
    def _compute_project_id(self):
        for rec in self:
            source_id = rec.parent_source_id
            if source_id and source_id._name == 'realestate.project':
                rec.project_id = source_id.id
            if source_id and source_id._name == 'zone':
                rec.project_id = source_id.parent_id.id
            elif source_id:
                rec.project_id = False
                while source_id:
                    if source_id._name == 'realestate.project':
                        rec.project_id = source_id.id
                        break
                    project_id = source_id.project_id
                    if project_id:
                        rec.project_id = project_id.id
                        break
                    source_id = source_id.parent_source_id
            else:
                rec.project_id = False

    def compute_cluster_location(self):
        for rec in self:
            name = ''
            if rec.name:
                name += rec.name
            if rec.parent_source_id and rec.parent_source_id.location:
                name += ',' + rec.parent_source_id.location
            rec.location = name

    @api.depends('abbreviation', 'parent_source_id')
    def compute_unit_system_code(self):
        for rec in self:
            parts = []
            if rec.parent_source_id and rec.parent_source_id._name != 'realestate.project' and rec.parent_source_id.system_code:
                parts.append(rec.parent_source_id.system_code)
            if rec.abbreviation:
                parts.append(rec.abbreviation)
            rec.system_code = "-".join(parts)
