from odoo import models, fields, api


class MailMessageInherit(models.Model):
    _inherit = 'mail.message'

    @api.model
    def create(self, vals):
        res = super(MailMessageInherit, self).create(vals)
        lead = self.env['crm.lead'].search([('id', '=', res.res_id)])
        followers = lead.sudo().message_follower_ids.mapped('partner_id').ids
        followers = set(followers + res.partner_ids.ids)
        if res.create_uid.partner_id.id in followers:
            followers.remove(res.create_uid.partner_id.id)

        notification = self.env['user.notification'].create({
            'title': f'New Update In {lead.display_name}',
            'mail_message_id': res.id,
            'res_id': lead.id,
            # 'partner_ids':  [(6, 0, followers)],
        })
        for follower in followers:
            self.env['partner.notification.rel'].create({
                'notification_id': notification.id,
                'partner_id': follower,
            })
        return res
