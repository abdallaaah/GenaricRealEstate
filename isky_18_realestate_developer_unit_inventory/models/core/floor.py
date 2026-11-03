from odoo import fields, models, api


class Floor(models.Model):
    _name = 'floor'
    _description = "Floor"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'system_code'

    name = fields.Char()
    abbreviation = fields.Char(string="Code")
    system_code = fields.Char(compute="compute_unit_system_code", store=True)
    parent_source_id = fields.Reference([
        ('real.estate.building', 'Building'),
        ('zone', 'Zone'),
        ('realestate.project', 'Project')
    ], string='Parent reference')
    location = fields.Char(compute='compute_floor_location')
    project_phases_ids = fields.Many2many('real.estate.project.phase')
    project_type_ids = fields.Many2many('realestate.project.type', string='Type', required=True)
    project_id = fields.Many2one('realestate.project', compute="_compute_project_id", store=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    floor_area = fields.Float(string="Floor Area")

    # Aggregate area fields from units
    total_gross_area = fields.Float(
        string='Total Gross Area',
        compute='_compute_aggregate_areas',
        store=True,
        digits=(16, 2),
        help='Sum of Gross Total Area (unit_area) from all units in this floor'
    )

    total_new_gross_area = fields.Float(
        string='Total New Gross Area (Indoor + Terrace)',
        compute='_compute_aggregate_areas',
        store=True,
        digits=(16, 2),
        help='Sum of New Total Gross Area (indoor_gross_area + terrace_gross_area) from all units in this floor'
    )

    unit_count = fields.Integer(
        string='Number of Units',
        compute='_compute_aggregate_areas',
        store=True
    )

    @api.depends('name', 'abbreviation')  # Depend on floor changes
    def _compute_aggregate_areas(self):
        """
        Compute aggregate areas from all units in this floor.
        This will update whenever units are added/removed or their areas change.
        """
        for rec in self:
            if not rec.id:
                rec.unit_count = 0
                rec.total_gross_area = 0.0
                rec.total_new_gross_area = 0.0
                continue

            # Search for units where parent_source_id references this floor
            units = self.env['real.estate.unit'].search([
                ('parent_source_id', '=', f'floor,{rec.id}')
            ])

            rec.unit_count = len(units)
            rec.total_gross_area = sum(units.mapped('unit_area') or [0.0])
            rec.total_new_gross_area = sum(units.mapped('new_total_gross_area') or [0.0])

    @api.depends('parent_source_id')
    def _compute_project_id(self):
        for rec in self:
            source_id = rec.parent_source_id
            if source_id and source_id._name == 'realestate.project':
                rec.project_id = source_id.id
            elif source_id and source_id._name == 'zone':
                rec.project_id = source_id.parent_id.id if hasattr(source_id, 'parent_id') else False
            elif source_id:
                rec.project_id = False
                while source_id:
                    if source_id._name == 'realestate.project':
                        rec.project_id = source_id.id
                        break
                    if hasattr(source_id, 'project_id'):
                        project_id = source_id.project_id
                        if project_id:
                            rec.project_id = project_id.id
                            break
                    if hasattr(source_id, 'parent_source_id'):
                        source_id = source_id.parent_source_id
                    else:
                        break
            else:
                rec.project_id = False

    def compute_floor_location(self):
        for rec in self:
            name = ''
            if rec.name:
                name += rec.name
            if rec.parent_source_id and hasattr(rec.parent_source_id, 'location') and rec.parent_source_id.location:
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
