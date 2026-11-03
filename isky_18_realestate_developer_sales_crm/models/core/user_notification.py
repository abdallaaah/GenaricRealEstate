from odoo import models, fields


class UserNotification(models.Model):
    _name = 'user.notification'

    mail_message_id = fields.Many2one('mail.message')
    model = fields.Char(related='mail_message_id.model')
    res_id = fields.Many2oneReference('Related Document ID', model_field='model')
    # ticket_id = fields.Many2one('helpdesk.ticket')
    title = fields.Text()
    read_flag = fields.Boolean()
    # partner_ids = fields.Many2many('res.partner')

    def get_user_messages(self):
        partner_id = self.env.user.partner_id.id
        user_notifications = self.env['partner.notification.rel'].search([('partner_id', '=', partner_id)],
                                                                         limit=20, order='create_date desc')
        notifications = []
        for user_notification in user_notifications:
            notification = self.search([('id', '=', user_notification.notification_id.id)])
            notifications.append({'read_flag': user_notification.read_flag,
                                  'title': notification.title,
                                  'res_id': notification.res_id,
                                  'id': notification.id,
                                  })
        return notifications

    def set_read_flag(self, notification_id):
        partner_id = self.env.user.partner_id.id
        notification = self.env['partner.notification.rel'].search([('notification_id', '=', int(notification_id)),
                                                                    ('partner_id', '=', int(partner_id))])
        notification.write({'read_flag': True})
        return notification


class PartnerNotificationRelation(models.Model):
    _name = 'partner.notification.rel'

    notification_id = fields.Many2one('user.notification')
    partner_id = fields.Many2one('res.partner')
    read_flag = fields.Boolean(default=False)
