from odoo import api, fields, models


class UserNotification(models.Model):
    _name = 'user.notification'
    _description = "In-App Notification"

    mail_message_id = fields.Many2one('mail.message', required=True, ondelete='cascade')
    model = fields.Char(related='mail_message_id.model')
    res_id = fields.Many2oneReference(string="Related Document ID", model_field='model')
    title = fields.Char(required=True)

    @api.model
    def get_user_messages(self):
        partner_id = self.env.user.partner_id.id
        relations = self.env['partner.notification.rel'].search(
            [('partner_id', '=', partner_id)], limit=20, order='create_date desc')
        return [{
            'id': rel.notification_id.id,
            'title': rel.notification_id.title,
            'res_id': rel.notification_id.res_id,
            'read_flag': rel.read_flag,
        } for rel in relations]

    @api.model
    def set_read_flag(self, notification_id):
        partner_id = self.env.user.partner_id.id
        relation = self.env['partner.notification.rel'].search([
            ('notification_id', '=', int(notification_id)),
            ('partner_id', '=', partner_id),
        ])
        relation.write({'read_flag': True})
        return bool(relation)


class PartnerNotificationRel(models.Model):
    _name = 'partner.notification.rel'
    _description = "Per-Partner Notification Read State"

    notification_id = fields.Many2one('user.notification', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade')
    read_flag = fields.Boolean(default=False)
