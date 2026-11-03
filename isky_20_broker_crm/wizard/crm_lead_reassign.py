from odoo import api, fields, models


class CrmLeadReassign(models.TransientModel):
    _name = 'crm.lead.reassign'
    _description = "Reassign Leads"

    user_id = fields.Many2one('res.users', string="Assign To", domain=lambda self: self._domain_user_id())

    @api.model
    def _domain_user_id(self):
        user = self.env.user
        if user.has_group('isky_20_broker_crm.group_lead_admin') \
                or user.has_group('isky_20_broker_crm.group_operation_manager'):
            return []
        teams = self.env['crm.team'].search([
            '|', '|', '|',
            ('user_id', '=', user.id), ('sales_manager_id', '=', user.id),
            ('director_id', '=', user.id), ('operation_id', '=', user.id),
        ])
        return [('id', 'in', (teams.member_ids | teams.user_id).ids)]

    def action_reassign(self):
        self.ensure_one()
        leads = self.env['crm.lead'].browse(self.env.context.get('active_ids', []))
        new_team = self.env['crm.team'].search([
            '|', ('member_ids', 'in', self.user_id.id), ('user_id', '=', self.user_id.id),
        ], limit=1)
        first_stage = self.env.ref('isky_20_broker_crm.lead_stage_new')
        for lead in leads:
            values = {
                'previous_user_id': lead.user_id.id,
                'user_id': self.user_id.id,
                'reassigned': True,
                'assigned_by_id': self.env.user.id,
            }
            if new_team:
                values['team_id'] = new_team.id
            if lead.lead_stage_id and not lead.lead_stage_id.first and not lead.is_qualified and not lead.locked:
                values['lead_stage_id'] = first_stage.id
            lead.write(values)
        return {'type': 'ir.actions.act_window_close'}
