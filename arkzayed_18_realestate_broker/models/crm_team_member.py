from odoo import fields, models

class UserInherit(models.Model):

    _inherit = 'crm.team.member'

    user_meeting_count = fields.Integer(compute='_compute_user_meeting_count', string='Meeting Count', store=True)

    def _compute_user_meeting_count(self):
        for rec in self:
            rec.user_meeting_count = self.env['mail.activity'].with_context(active_test=False).search_count([('activity_type_id', '=', self.env.ref('mail.mail_activity_data_meeting').id),
                                                  ('user_id', '=', rec.user_id.id)])