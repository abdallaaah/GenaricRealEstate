from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class RealestateProject(models.Model):
    """specify Project details with relation of project type"""

    _name = 'realestate.project'
    _description = "Real Estate Project"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char('Name', required=True)
    abbreviation = fields.Char(string="Code", required=True)
    system_code = fields.Char(compute="compute_unit_system_code", store=True)
    code_separator = fields.Char(
        string='Code Separator', default='-', required=True,
        help='Separator used when concatenating this project\'s node codes into a unit system code.')
    hierarchy_template_id = fields.Many2one(
        'realestate.hierarchy.template', string='Hierarchy Template',
        default=lambda self: self.env.company.hierarchy_template_id,
        help='Defines which middle levels (building/cluster/zone/floor) exist between '
             'this project and its units, and in what order. Defaults to the company '
             'template; set a different one here to override it for this project. '
             'Locked once the project has its first unit.')
    hierarchy_locked = fields.Boolean(compute='_compute_hierarchy_locked',
                                       help='True once this project has at least one unit; '
                                            'its hierarchy level definition can no longer change.')
    purchase_date = fields.Date('Date')
    construction_date = fields.Date('Construction Date')
    launching_date = fields.Date('Launching Date')
    total_area = fields.Integer('Plot Area', help='Total Area With m2')
    bua = fields.Integer('BUA')
    main_owner = fields.Char('Owner')
    project_type_ids = fields.Many2many('realestate.project.type', string='Type', required=True)
    project_plan = fields.Binary(string='Plan')
    license = fields.Binary(string='License')
    permits = fields.Binary('permits')
    contracts = fields.Binary('Contracts')
    feature_ids = fields.Many2many('real.estate.feature')
    facility_ids = fields.Many2many('real.estate.facility')
    nearby_connectivity_ids = fields.Many2many('real.estate.nearby.connectivity')
    project_phases_ids = fields.Many2many('real.estate.project.phase')
    location = fields.Char(compute='compute_location')
    guide_line = fields.Binary('Guide Line')
    handbook = fields.Binary('Handbook')
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    analytic_account_id = fields.Many2one(comodel_name="account.analytic.account")

    _sql_constraints = [
        ('abbreviation_company_unique', 'unique(abbreviation, company_id)',
         'A project code must be unique per company.'),
    ]

    def compute_location(self):
        for rec in self:
            rec.location = rec.name

    @api.depends('abbreviation')
    def compute_unit_system_code(self):
        for rec in self:
            rec.system_code = rec.abbreviation

    def _hierarchy_has_units(self):
        self.ensure_one()
        return bool(self.env['real.estate.unit'].search_count([('project_id', '=', self.id)]))

    def _compute_hierarchy_locked(self):
        for rec in self:
            rec.hierarchy_locked = rec.id and rec._hierarchy_has_units()

    def hierarchy_level_sequence(self):
        """Ordered level_type codes from project (root) to unit (leaf), including the
        fixed endpoints, for this project's hierarchy template."""
        self.ensure_one()
        middle = self.hierarchy_template_id.level_sequence() if self.hierarchy_template_id else []
        return ['project'] + middle + ['unit']

    def write(self, vals):
        if 'hierarchy_template_id' in vals:
            for rec in self:
                if rec.hierarchy_template_id.id != vals['hierarchy_template_id'] and rec._hierarchy_has_units():
                    raise ValidationError(_(
                        "The hierarchy template of '%s' cannot be changed: it already has "
                        "units. The level definition is locked once a project has its first unit."
                    ) % rec.name)
        return super().write(vals)

