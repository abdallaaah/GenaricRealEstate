from odoo import fields, models, api


class FloorArea(models.Model):
    _name = 'floor.area'
    _description = "Floor's Area"

    name = fields.Char()
    abbreviation = fields.Char()
    system_code = fields.Char(compute="compute_unit_system_code", store=True)
    code = fields.Char()
    parent_source_id = fields.Reference([
        ('floor', 'Floor'),
        ('cluster', 'Cluster'),
        ('zone', 'Zone'),
        ('real.estate.building', 'Building'),
        ('realestate.project', 'Project')
    ], string='Parent reference', required="1")

    location = fields.Char(compute='compute_floor_area_location')
    project_phases_ids = fields.Many2many('real.estate.project.phase')
    project_id = fields.Many2one('realestate.project', compute="_compute_project_id", store=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    # Aggregate area fields from units
    total_gross_area = fields.Float(
        string='Total Gross Area',
        compute='_compute_aggregate_areas',
        store=True,
        digits=(16, 2),
        help='Sum of Gross Total Area (unit_area) from all units in this floor area'
    )

    total_new_gross_area = fields.Float(
        string='Total New Gross Area (Indoor + Terrace)',
        compute='_compute_aggregate_areas',
        store=True,
        digits=(16, 2),
        help='Sum of New Total Gross Area (indoor_gross_area + terrace_gross_area) from all units in this floor area'
    )

    unit_count = fields.Integer(
        string='Number of Units',
        compute='_compute_aggregate_areas',
        store=True
    )

    @api.depends('name', 'abbreviation')
    def _compute_aggregate_areas(self):
        """
        Compute aggregate areas from all units in this floor area.
        This will update whenever units are added/removed or their areas change.
        """
        for rec in self:
            if not rec.id:
                rec.unit_count = 0
                rec.total_gross_area = 0.0
                rec.total_new_gross_area = 0.0
                continue

            # Find all units that belong to this floor area
            units = self.env['real.estate.unit'].search([
                ('parent_source_id', '=', f'floor.area,{rec.id}')
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

    def compute_floor_area_location(self):
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
