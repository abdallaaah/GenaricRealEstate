from odoo import api, fields, models
from odoo.exceptions import ValidationError

# job.level was defined twice (arkzayed_18_realestate_development and
# arkzayed_18_realestate_developer_crm) with slightly different flag sets and two
# same-named, non-super()-calling _flag_constrains methods - only the later-loaded one
# actually ran. Merged into one definition with every flag from both copies.


class JobLevel(models.Model):
    _name = 'job.level'

    name = fields.Char()

    is_sales_person = fields.Boolean(string='Is Sales Person')
    is_team_leader = fields.Boolean(string='Is Team Leader')
    is_directory = fields.Boolean(string='Is Directory')
    is_sales_manager = fields.Boolean(string='Is Sales Manager')
    is_operations = fields.Boolean(string='Is Operations')
    is_sales_sector_manager = fields.Boolean(string='Is Sales Sector Manager')

    @api.constrains('is_sales_person', 'is_team_leader', 'is_directory', 'is_sales_manager',
                     'is_operations', 'is_sales_sector_manager')
    def _flag_constrains(self):
        """Ensure at least one role flag is selected, and no flag is reused across records"""
        for rec in self:
            flags_to_check = [
                ('is_sales_person', rec.is_sales_person, 'Sales Person'),
                ('is_team_leader', rec.is_team_leader, 'Team Leader'),
                ('is_directory', rec.is_directory, 'Directory'),
                ('is_sales_manager', rec.is_sales_manager, 'Sales Manager'),
                ('is_operations', rec.is_operations, 'Operations'),
                ('is_sales_sector_manager', rec.is_sales_sector_manager, 'Sales Sector Manager'),
            ]
            if not any(is_set for _, is_set, _ in flags_to_check):
                raise ValidationError("At least one role must be selected.")

            for job_level, is_set, label in flags_to_check:
                if is_set:
                    existing = self.search([
                        (job_level, '=', True),
                        ('id', '!=', rec.id)
                    ])
                    if existing:
                        raise ValidationError(f"Only one record can be marked as {label}.")
