from odoo import api, fields, models
from odoo.exceptions import ValidationError

FLAG_FIELDS = [
    ('is_sales_person', "Sales Person"),
    ('is_team_leader', "Team Leader"),
    ('is_sales_manager', "Sales Manager"),
    ('is_directory', "Director"),
    ('is_operations', "Operations"),
]


class JobLevel(models.Model):
    _name = 'job.level'
    _description = "Broker Job Level"

    name = fields.Char(required=True)
    is_sales_person = fields.Boolean(string="Is Sales Person")
    is_team_leader = fields.Boolean(string="Is Team Leader")
    is_sales_manager = fields.Boolean(string="Is Sales Manager")
    is_directory = fields.Boolean(string="Is Director")
    is_operations = fields.Boolean(string="Is Operations")

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
