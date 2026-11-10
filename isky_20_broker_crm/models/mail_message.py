from odoo import api, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        for message in messages:
            if message.model != 'crm.lead' or not message.res_id:
                continue
            lead = self.env['crm.lead'].browse(message.res_id)
            follower_partner_ids = set(lead.sudo().message_follower_ids.partner_id.ids) | set(message.partner_ids.ids)
            follower_partner_ids.discard(message.create_uid.partner_id.id)
            if not follower_partner_ids:
                continue
            # Notifications are infrastructure created on behalf of the lead's followers,
            # not an action of the posting user -- sudo() regardless of who posted.
            notification = self.env['user.notification'].sudo().create({
                'title': self.env._("New update on %s", lead.display_name),
                'mail_message_id': message.id,
                'res_id': lead.id,
            })
            self.env['partner.notification.rel'].sudo().create([
                {'notification_id': notification.id, 'partner_id': partner_id}
                for partner_id in follower_partner_ids
            ])
        return messages
