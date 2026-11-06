from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class Zone(models.Model):
    _name = 'zone'
    _description = "Real Estate Zone"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'realestate.hierarchy.node.mixin']
    _rec_name = 'system_code'

    name = fields.Char()
    abbreviation = fields.Char(string="Code")
    system_code = fields.Char(compute="compute_unit_system_code", store=True)
    # Legacy direct-to-project link, kept for backward compatibility with existing data/views.
    # Still works unchanged for zones that sit directly under a project. A zone nested deeper
    # (e.g. under a building or cluster) uses parent_source_id instead - see
    # _hierarchy_get_parent_record() below, which prefers it when set.
    parent_id = fields.Many2one('realestate.project', string="Project")
    parent_source_id = fields.Reference([
        ('realestate.project', 'Project'),
        ('real.estate.building', 'Building'),
        ('cluster', 'Cluster'),
    ], string='Parent reference')
    project_id = fields.Many2one('realestate.project', compute="_compute_project_id", store=True)
    location = fields.Char(compute='compute_zone_location')
    project_phases_ids = fields.Many2many('real.estate.project.phase')
    project_type_ids = fields.Many2many('realestate.project.type', string='Type', required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    def _hierarchy_get_parent_record(self):
        self.ensure_one()
        return self.parent_source_id or self.parent_id

    def _hierarchy_parent_domain(self):
        self.ensure_one()
        parent = self._hierarchy_get_parent_record()
        if not parent:
            return [('parent_source_id', '=', False), ('parent_id', '=', False)]
        if self.parent_source_id:
            return [('parent_source_id', '=', '%s,%d' % (parent._name, parent.id))]
        return [('parent_source_id', '=', False), ('parent_id', '=', parent.id)]

    @api.constrains('parent_id')
    def _check_hierarchy_node_parent_id(self):
        self._check_hierarchy_code_unique()
        self._check_hierarchy_sequence()

    @api.constrains('parent_id', 'parent_source_id')
    def _check_zone_has_parent(self):
        for rec in self:
            if not rec.parent_id and not rec.parent_source_id:
                raise ValidationError(_("A zone must have a parent: a project, building, or cluster."))

    def compute_zone_location(self):
        for rec in self:
            parent = rec._hierarchy_get_parent_record()
            name = ''
            if rec.name:
                name += rec.name
            if parent and parent.location:
                name += ',' + parent.location
            rec.location = name
