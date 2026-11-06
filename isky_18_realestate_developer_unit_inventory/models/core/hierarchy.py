from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

# Fixed endpoints (project, unit) plus the four configurable middle levels.
# Keys are what a template line / node maps to; values are the actual model name.
LEVEL_MODEL_BY_TYPE = {
    'project': 'realestate.project',
    'building': 'real.estate.building',
    'cluster': 'cluster',
    'zone': 'zone',
    'floor': 'floor',
    'unit': 'real.estate.unit',
}
LEVEL_TYPE_BY_MODEL = {model: level_type for level_type, model in LEVEL_MODEL_BY_TYPE.items()}

MIDDLE_LEVEL_SELECTION = [
    ('building', 'Building'),
    ('cluster', 'Cluster'),
    ('zone', 'Zone'),
    ('floor', 'Floor'),
]


class RealestateHierarchyTemplate(models.Model):
    """A reusable, ordered set of middle levels between project (root) and unit (leaf).

    Company picks a default (res.company.hierarchy_template_id); a project may
    override it (realestate.project.hierarchy_template_id).
    """
    _name = 'realestate.hierarchy.template'
    _description = 'Real Estate Hierarchy Template'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    level_ids = fields.One2many('realestate.hierarchy.level', 'template_id', string='Levels')

    def level_sequence(self):
        """Ordered list of middle level_type codes, root to leaf (project/unit excluded)."""
        self.ensure_one()
        return self.level_ids.sorted('sequence').mapped('level_type')


class RealestateHierarchyLevel(models.Model):
    """One middle level (building/cluster/zone/floor) in a hierarchy template, in order."""
    _name = 'realestate.hierarchy.level'
    _description = 'Real Estate Hierarchy Level'
    _order = 'sequence, id'

    template_id = fields.Many2one('realestate.hierarchy.template', required=True, ondelete='cascade')
    level_type = fields.Selection(MIDDLE_LEVEL_SELECTION, required=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ('template_level_type_unique', 'unique(template_id, level_type)',
         'A level can only appear once in a hierarchy template.'),
    ]

    def _locked_projects(self):
        templates = self.mapped('template_id')
        if not templates:
            return self.env['realestate.project']
        projects = self.env['realestate.project'].search([('hierarchy_template_id', 'in', templates.ids)])
        return projects.filtered(lambda p: p._hierarchy_has_units())

    def _check_not_locked(self):
        locked = self._locked_projects()
        if locked:
            raise ValidationError(_(
                "Cannot change hierarchy levels: %s already has units. "
                "The hierarchy level definition is locked once a project has its first unit."
            ) % ', '.join(locked.mapped('name')))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_not_locked()
        return records

    def write(self, vals):
        templates_before = self.mapped('template_id')
        result = super().write(vals)
        (self | self.search([('template_id', 'in', templates_before.ids)]))._check_not_locked()
        return result

    def unlink(self):
        self._check_not_locked()
        return super().unlink()


class RealestateHierarchyNodeMixin(models.AbstractModel):
    """Shared behavior for the middle/leaf hierarchy node models (building, cluster, zone,
    floor, real.estate.unit): system code concatenation, owning-project lookup, uniqueness
    of code under the same parent, level-sequence enforcement, and the code-immutability lock.

    Relies on each concrete model having an `abbreviation` field and a `parent_source_id`
    Reference field. Project is the tree root and does not use this mixin.
    """
    _name = 'realestate.hierarchy.node.mixin'
    _description = 'Real Estate Hierarchy Node Mixin'

    def _hierarchy_get_parent_record(self):
        """The record this node is directly nested under, or False. Override for models
        that keep a legacy, non-generic parent field (e.g. zone's parent_id)."""
        self.ensure_one()
        return self.parent_source_id

    def _hierarchy_own_level_type(self):
        return LEVEL_TYPE_BY_MODEL.get(self._name)

    def _hierarchy_parent_domain(self):
        """Domain matching siblings under the same effective parent."""
        self.ensure_one()
        parent = self._hierarchy_get_parent_record()
        if not parent:
            return [('parent_source_id', '=', False)]
        return [('parent_source_id', '=', '%s,%d' % (parent._name, parent.id))]

    def _hierarchy_get_project(self):
        """Walk up the parent chain to the owning realestate.project, or False."""
        self.ensure_one()
        node = self._hierarchy_get_parent_record()
        seen = set()
        while node:
            key = (node._name, node.id)
            if key in seen:
                return False
            seen.add(key)
            if node._name == 'realestate.project':
                return node
            node = node._hierarchy_get_parent_record() if hasattr(node, '_hierarchy_get_parent_record') else False
        return False

    def _hierarchy_get_code_chain(self):
        """Codes from the project root down to self, inclusive, root first."""
        self.ensure_one()
        codes = [self.abbreviation] if self.abbreviation else []
        node = self._hierarchy_get_parent_record()
        seen = set()
        while node:
            key = (node._name, node.id)
            if key in seen:
                break
            seen.add(key)
            if getattr(node, 'abbreviation', False):
                codes.append(node.abbreviation)
            if node._name == 'realestate.project':
                break
            node = node._hierarchy_get_parent_record() if hasattr(node, '_hierarchy_get_parent_record') else False
        return list(reversed(codes))

    def _hierarchy_is_locked(self):
        self.ensure_one()
        project = self._hierarchy_get_project()
        return bool(project) and project._hierarchy_has_units()

    @api.depends('abbreviation', 'parent_source_id')
    def compute_unit_system_code(self):
        for rec in self:
            chain = rec._hierarchy_get_code_chain()
            project = rec._hierarchy_get_project()
            separator = project.code_separator if project else '-'
            rec.system_code = separator.join(chain) if chain else False

    @api.depends('parent_source_id')
    def _compute_project_id(self):
        for rec in self:
            rec.project_id = rec._hierarchy_get_project() or False

    def _check_hierarchy_code_unique(self):
        for rec in self:
            if not rec.abbreviation:
                continue
            domain = rec._hierarchy_parent_domain() + [
                ('abbreviation', '=', rec.abbreviation),
                ('id', '!=', rec.id),
            ]
            if self.search_count(domain):
                raise ValidationError(_(
                    "The code '%s' is already used by another record under the same parent."
                ) % rec.abbreviation)

    def _check_hierarchy_sequence(self):
        for rec in self:
            parent = rec._hierarchy_get_parent_record()
            if not parent:
                continue
            project = rec._hierarchy_get_project()
            if not project:
                continue
            sequence = project.hierarchy_level_sequence()
            own_type = rec._hierarchy_own_level_type()
            if own_type not in sequence:
                continue
            idx = sequence.index(own_type)
            if idx == 0:
                continue
            expected_type = sequence[idx - 1]
            expected_model = LEVEL_MODEL_BY_TYPE[expected_type]
            if parent._name != expected_model:
                raise ValidationError(_(
                    "'%s' must be placed directly under a %s for this project's hierarchy "
                    "template, not a %s."
                ) % (rec.display_name or rec.abbreviation or rec.id, expected_type, parent._name))

    @api.constrains('abbreviation', 'parent_source_id')
    def _check_hierarchy_node(self):
        self._check_hierarchy_code_unique()
        self._check_hierarchy_sequence()

    def write(self, vals):
        if 'abbreviation' in vals:
            for rec in self:
                if rec.abbreviation and rec.abbreviation != vals['abbreviation'] and rec._hierarchy_is_locked():
                    raise ValidationError(_(
                        "The code of '%s' cannot be changed: its project's unit hierarchy is "
                        "locked (it already has at least one unit)."
                    ) % (rec.display_name or rec.abbreviation))
        return super().write(vals)
