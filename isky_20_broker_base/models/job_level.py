from odoo import api, fields, models
from odoo.exceptions import ValidationError

FLAG_FIELDS = [
    ('is_sales_person', "Sales Person"),
    ('is_team_leader', "Team Leader"),
    ('is_sales_manager', "Sales Manager"),
    ('is_directory', "Director"),
    ('is_operations', "Operations"),
]

TEAM_ROLE_FIELDS = [
    ('member_ids', "Team Members"),
    ('user_id', "Team Leader"),
    ('sales_manager_id', "Sales Manager"),
    ('director_id', "Director"),
]


class JobLevel(models.Model):
    _name = 'job.level'
    _description = "Broker Job Level"
    _order = 'hierarchy_sequence, id'

    name = fields.Char(required=True)
    is_sales_person = fields.Boolean(string="Is Sales Person")
    is_team_leader = fields.Boolean(string="Is Team Leader")
    is_sales_manager = fields.Boolean(string="Is Sales Manager")
    is_directory = fields.Boolean(string="Is Director")
    is_operations = fields.Boolean(string="Is Operations")

    # The reporting chain used to be expressed twice -- as a four-branch if/elif in the
    # commission engine and as six hand-written UNION branches in the achievement report,
    # which disagreed with each other. Both describe the same thing: a team's roles form
    # an ordered chain and a vacant tier is skipped. Encoding the chain here as data means
    # broker.sales.hierarchy can derive every relationship from it, and a client with a
    # different org shape (no sales-manager tier, or an extra one) reconfigures these rows
    # instead of needing a code change -- the same approach as broker.approval.rule.
    hierarchy_sequence = fields.Integer(
        string="Hierarchy Rank", default=0,
        help="Rank in the sales reporting chain: a higher rank manages every lower rank on "
             "the same sales team. Leave at 0 for a level that is outside the chain "
             "(e.g. Operations), which excludes it from commission target rollup.")
    team_role_field = fields.Selection(
        TEAM_ROLE_FIELDS, string="Sales Team Slot",
        help="Which field on the sales team holds the people at this level. Required for a "
             "level that takes part in the reporting chain.")

    @api.constrains('is_sales_person', 'is_team_leader', 'is_sales_manager', 'is_directory', 'is_operations')
    def _check_one_flag_set(self):
        for level in self:
            flags = [level[field_name] for field_name, _label in FLAG_FIELDS]
            if not any(flags):
                raise ValidationError(self.env._("A job level must have exactly one role flag selected."))
            if sum(flags) > 1:
                raise ValidationError(self.env._("A job level must have exactly one role flag selected."))

    @api.constrains('is_sales_person', 'is_team_leader', 'is_sales_manager', 'is_directory', 'is_operations')
    def _check_flag_unique_system_wide(self):
        for level in self:
            for field_name, label in FLAG_FIELDS:
                if not level[field_name]:
                    continue
                other = self.search([(field_name, '=', True), ('id', '!=', level.id)], limit=1)
                if other:
                    raise ValidationError(self.env._("Only one job level can be marked as %s.", label))

    @api.constrains('hierarchy_sequence', 'team_role_field')
    def _check_hierarchy_chain(self):
        for level in self:
            if level.hierarchy_sequence and not level.team_role_field:
                raise ValidationError(self.env._(
                    "%s takes part in the reporting chain (rank %s), so it needs a sales team slot.",
                    level.name, level.hierarchy_sequence,
                ))
            if not level.hierarchy_sequence:
                continue
            clash = self.search([
                ('hierarchy_sequence', '=', level.hierarchy_sequence),
                ('id', '!=', level.id),
            ], limit=1)
            if clash:
                raise ValidationError(self.env._(
                    "%s and %s cannot share hierarchy rank %s -- the chain must be unambiguous.",
                    level.name, clash.name, level.hierarchy_sequence,
                ))

    @api.model
    def _get_hierarchy_chain(self):
        """The reporting chain, lowest rank first. One row per participating level."""
        return self.sudo().search([
            ('hierarchy_sequence', '>', 0),
            ('team_role_field', '!=', False),
        ], order='hierarchy_sequence')

    # The hierarchy view's SQL is generated from the chain above, so it has to be
    # regenerated whenever the chain changes.
    @api.model_create_multi
    def create(self, vals_list):
        levels = super().create(vals_list)
        self.env['broker.sales.hierarchy']._rebuild()
        return levels

    def write(self, vals):
        result = super().write(vals)
        if {'hierarchy_sequence', 'team_role_field'} & set(vals):
            self.env['broker.sales.hierarchy']._rebuild()
        return result

    def unlink(self):
        result = super().unlink()
        self.env['broker.sales.hierarchy']._rebuild()
        return result
