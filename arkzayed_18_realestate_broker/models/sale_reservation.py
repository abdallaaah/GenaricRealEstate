from odoo import models,Command, api

class SaleContract(models.Model):
    _inherit = 'real.estate.sale.reservation'

    def _build_commission_hierarchy(self):
        self.ensure_one()
        DEFAULT_COMMISSION = 100.0

        job_positions = ['Sales Person', 'Sales Manager', 'Sales Sector Manager', 'Director']
        job_position_order = {pos: index for index, pos in enumerate(job_positions)}
        def _get_team_users_with_roles(user):
            team_member = self.env['crm.team.member'].search(
                [('user_id', '=', user.id)], limit=1
            )

            if team_member and team_member.crm_team_id:
                team_id = team_member.crm_team_id
                return [
                    (user, 'Sales Person'),
                    (team_id.sales_manager_id, 'Sales Manager'),
                    (team_id.operation_id, 'Sales Sector Manager'),
                    (team_id.director_id, 'Director'),
                ]
            # If the user has no team, they are just added as a Sales Person
            return [(user, 'Sales Person')]

        unique_lines = {}

        self.commission_ids = [Command.clear()]

        def _add_users(users_with_roles):
            for user, role in users_with_roles:
                if not user:
                    continue
                uid = user.id

                if (
                        uid not in unique_lines
                        or job_position_order[role] < job_position_order.get(unique_lines[uid], 99)
                ):
                    unique_lines[uid] = role

        _add_users(_get_team_users_with_roles(self.user_id))

        if self.split_deal and self.sales_ids:
            for person in self.sales_ids:
                _add_users(_get_team_users_with_roles(person))

        role_counts = {}
        for role in unique_lines.values():
            if role not in role_counts:
                role_counts[role] = 0
            role_counts[role] += 1

        sorted_lines = sorted(
            unique_lines.items(),
            key=lambda x: job_position_order[x[1]]
        )

        self.commission_ids = [
            Command.create({
                'employee_id': user_id,
                'jop_position': role,
                'commission': DEFAULT_COMMISSION / role_counts[role],
            })
            for user_id, role in sorted_lines
        ]

