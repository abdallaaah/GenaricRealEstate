from odoo import models, fields, api, _
from odoo.exceptions import ValidationError,UserError


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    director_id = fields.Many2one('res.users', string='Director', check_company=True, domain=[('job_level_id.is_directory', '=', True)])
    operation_id = fields.Many2one('res.users', string='Sales Sector Manager', check_company=True, domain=[('job_level_id.is_sales_sector_manager', '=', True)])
    sales_manager_id = fields.Many2one('res.users', string='Sales Manager', check_company=True, domain=[('job_level_id.is_sales_manager', '=', True)])
    member_ids = fields.Many2many(
        'res.users', string='Salespersons',
        domain="[('company_ids', 'in', member_company_ids)]",
        compute='_compute_member_ids', inverse='_inverse_member_ids', search='_search_member_ids',
        help="Users assigned to this team.")
    # operation_executive_id = fields.Many2one('res.users', string='Operation Executive', check_company=True)
    # current selected sales person in lead
    current_sales_person_id = fields.Many2one('res.users', string='Current Sales Person', check_company=True)
    is_current_team = fields.Boolean(string='Is Current Team',
                                     help='Make this team the default team the the auto assignment process start from')

    @api.constrains('is_current_team')
    def _check_single_current_team(self):
        for rec in self:
            if rec.is_current_team:
                count = self.search_count([
                    ('is_current_team', '=', True),
                    ('id', '!=', rec.id),
                    ('company_id', '=', rec.company_id.id)
                ])
                if count:
                    raise ValidationError(
                        f"Only one team for the current company {rec.company_id.name if rec.company_id else ''} can be marked as the current team."
                    )

    def write(self, vals):
        member_ids = vals.get('member_ids')
        res = super().write(vals)
        if res and member_ids and member_ids[0][0] == 3:
            user_ids = [user[1] for user in member_ids]
            self.env['res.users'].browse(user_ids).write({'sale_team_id': False})
        if res and member_ids and member_ids[0][0] == 4:
            user_ids = [user[1] for user in member_ids]
            self.env['res.users'].browse(user_ids).write({'sale_team_id': self.id})
        return res

    def _get_next_sales_person(self):
        """
        This method will do two things:
        1. Get the next sales person in the team based on the sorted order of crm_team_member_ids(based on user_id)
        2. Update the current_sales_person_id to the next sales person
        """
        self.ensure_one()
        team_members = self.crm_team_member_ids.filtered(lambda m : m.assignment_optout == False).sorted(key=lambda member: member.user_id.id)
        if not team_members:
            raise UserError(f"{self.name} team doesn't have any team members ,please assign some team members to it. ")

        if not self.current_sales_person_id:
            next_member = team_members[0]
        else:
            current_index = next((index for (index, d) in enumerate(team_members) if d.user_id == self.current_sales_person_id), -1)
            next_index = (current_index + 1) % len(team_members)
            next_member = team_members[next_index]

        self.current_sales_person_id = next_member.user_id
        return next_member.user_id