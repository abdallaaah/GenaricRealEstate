from odoo import api, fields, models



class ActivityScheduleInherit(models.TransientModel):
    _inherit = 'mail.activity.schedule'

    @api.model
    def default_get(self, fields):
        res = super(ActivityScheduleInherit, self).default_get(fields)
        if self.env.context.get('active_model') == 'crm.lead':
            # Find the meeting activity type id
            meeting_type = self.env['mail.activity.type'].search([('category', '=', 'meeting')], limit=1)
            if meeting_type:
                res['activity_type_id'] = meeting_type.id
        return res
