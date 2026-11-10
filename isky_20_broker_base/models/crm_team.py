from odoo import Command, fields, models


class CrmTeam(models.Model):
    """Organizational hierarchy roles on a sales team.

    Shared by both the real estate module (resale-seller hierarchy on a unit)
    and the CRM module (commission hierarchy on a lead), so it lives here
    rather than in either of them.
    """
    _inherit = 'crm.team'

    director_id = fields.Many2one(
        'res.users', string="Director", check_company=True,
        domain=[('job_level_id.is_directory', '=', True)])
    operation_id = fields.Many2one(
        'res.users', string="Operation Manager", check_company=True,
        domain=[('job_level_id.is_operations', '=', True)])
    sales_manager_id = fields.Many2one(
        'res.users', string="Sales Manager", check_company=True,
        domain=[('job_level_id.is_sales_manager', '=', True)])
    operation_executive_id = fields.Many2one(
        'res.users', string="Operation Executive", check_company=True)

    def write(self, vals):
        member_commands = vals.get('member_ids')
        result = super().write(vals)
        if result and member_commands:
            command, user_ids = member_commands[0][0], [cmd[1] for cmd in member_commands]
            if command == Command.UNLINK:
                self.env['res.users'].browse(user_ids).write({'sale_team_id': False})
            elif command == Command.LINK:
                self.env['res.users'].browse(user_ids).write({'sale_team_id': self.id})
        return result
