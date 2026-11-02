from odoo import fields, models, api


class LeadReassign(models.TransientModel):
    _name = 'crm.lead.reassign'
    _description = 'Reassign Leads'

    user_id = fields.Many2one(
        'res.users',
        string='Assign to',
        domain=lambda self: self._compute_user_domain()
    )

    @api.model
    def _compute_user_domain(self):
        user = self.env.user
        team_ids = self.env['crm.team'].sudo().search([])

        is_admin = self.is_admin_user(team_ids, user)
        return [] if is_admin else [('id', 'in', self.get_all_teams_members_for_all_roles(team_ids, user))]

    def is_admin_user(self, team_ids, user):
        operation = self.get_teams_member_as_operation(team_ids, user)
        # operation_executive = self.get_teams_member_as_operation_executive(team_ids, user)
        lead_admin = user.has_group('arkzayed_18_realestate_broker.lead_admin_group')
        return operation  or lead_admin #or operation_executive

    def get_all_teams_members_for_all_roles(self, team_ids, user):
        team_leader_members = self.get_teams_member_as_team_leader(team_ids, user)
        sales_manager_members = self.get_teams_member_as_sales_manager(team_ids, user)
        director_members = self.get_teams_member_as_director(team_ids, user)
        return (team_leader_members + sales_manager_members + director_members).ids

    def get_teams_member_as_team_leader(self, team_ids, user):
        team_leader_ids = team_ids.filtered(lambda x: x.user_id.id == user.id)
        return team_leader_ids.mapped('member_ids') + team_leader_ids.mapped('user_id')

    def get_teams_member_as_sales_manager(self, team_ids, user):
        sales_manager_ids = team_ids.filtered(lambda x: x.sales_manager_id.id == user.id)
        return sales_manager_ids.mapped('member_ids') + sales_manager_ids.mapped('user_id')

    def get_teams_member_as_director(self, team_ids, user):
        director_ids = team_ids.filtered(lambda x: x.director_id.id == user.id)
        return director_ids.mapped('member_ids') + director_ids.mapped('user_id')

    def get_teams_member_as_operation(self, team_ids, user):
        operation_ids = team_ids.filtered(lambda x: x.operation_id.id == user.id)
        return operation_ids.mapped('member_ids') + operation_ids.mapped('user_id')

    # def get_teams_member_as_operation_executive(self, team_ids, user):
    #     operation_executive_ids = team_ids.filtered(lambda x: x.operation_executive_id.id == user.id)
    #     return operation_executive_ids.mapped('member_ids') + operation_executive_ids.mapped('user_id')

    def reassign_leads(self):
        leads = self.env['crm.lead'].browse(self.env.context.get('active_ids'))
        first_stage = self.env.ref('arkzayed_18_realestate_broker.stage_new')

        for lead in leads:
            # Get the current team to find current sales manager and director
            current_team = lead.team_id
            current_sales_manager = current_team.sales_manager_id if current_team else False
            current_director = current_team.director_id if current_team else False

            # Find the new user's team - fixed the search domain
            new_user_team = self.env['crm.team'].search([
                '|',
                ('member_ids', 'in', [self.user_id.id]),
                ('user_id', '=', self.user_id.id)
            ], limit=1)

            # Prepare update values
            update_vals = {
                # Store previous values
                'previous_stage_id': lead.lead_stage_id.id if lead.lead_stage_id else False,
                'previous_user_id': lead.user_id.id if lead.user_id else False,
                'previous_sales_manager_id': current_sales_manager.id if current_sales_manager else False,
                'previous_director_id': current_director.id if current_director else False,

                # New values
                'user_id': self.user_id.id,
                'reassigned': True,
                'assigned_by_id': self.env.user.id  # Track who's doing the reassignment
            }

            # Update team if found
            if new_user_team:
                update_vals['team_id'] = new_user_team.id

            # Check if the lead is not in the first stage
            if not lead.first:
                update_vals['is_fresh'] = False

            # Set lead stage to "first" unless it's qualified, locked, or treated
            if (lead.lead_stage_id and
                    not lead.lead_stage_id.first and
                    not lead.qualified and
                    not lead.locked):
                update_vals['lead_stage_id'] = first_stage.id

            # Update the lead
            lead.write(update_vals)

        return {'type': 'ir.actions.act_window_close'}
