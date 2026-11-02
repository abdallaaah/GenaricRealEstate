from odoo import api, fields, models
from odoo.exceptions import ValidationError


class JobLevel(models.Model):
    _name = 'job.level'

    name = fields.Char()
    
    is_sales_person = fields.Boolean(string='Is Sales Person')
    is_team_leader = fields.Boolean(string='Is Team Leader')
    is_directory = fields.Boolean(string='Is Directory')
    is_sales_manager = fields.Boolean(string='Is Sales Manager')
    is_operations = fields.Boolean(string='Is Operations')

    @api.constrains('is_sales_person', 'is_team_leader', 'is_directory', 'is_sales_manager', 'is_operations')
    def _flag_constrains(self):
        """Ensure at least one role flag is selected"""
        for rec in self:
            flags = [
                rec.is_sales_person,
                rec.is_team_leader,
                rec.is_directory,
                rec.is_sales_manager,
                rec.is_operations,
            ]
            if not any(flags):
                raise ValidationError("At least one role must be selected.")
            """Ensure no more than one record has the same flag set to True"""
            flags_to_check = [
                ('is_sales_person', rec.is_sales_person, 'Sales Person'),
                ('is_team_leader', rec.is_team_leader, 'Team Leader'),
                ('is_directory', rec.is_directory, 'Directory'),
                ('is_sales_manager', rec.is_sales_manager, 'Sales Manager'),
                ('is_operations', rec.is_operations, 'Operations'),
            ]

            for job_level, is_set, label in flags_to_check:
                if is_set:
                    # Check if another record already has this flag set
                    existing = self.search([
                        (job_level, '=', True),
                        ('id', '!=', rec.id)
                    ])
                    if existing:
                        raise ValidationError(f"Only one record can be marked as {label}.")