from email.policy import default

from odoo import models, fields, api
import logging
from datetime import datetime
_logger = logging.getLogger(__name__)

class MailActivityInherit(models.Model):

    _inherit = 'mail.activity'
    # date_deadline = fields.Datetime()
    time_deadline = fields.Float(string='Due Time')
    time_type = fields.Selection([('am', 'Am'), ('pm', 'Pm')])
    counted = fields.Boolean(default=False)



    @api.readonly
    def action_close_dialog(self):
        if self.env.context.get('from_crm_call_later'):
            record = self.env['crm.lead'].browse(self.env.context.get('active_id'))
            if record:
                record.write({'lead_stage_id': self.env.ref('arkzayed_18_realestate_developer_crm.stage_call_later').id, 'follow_up_date': self.date_deadline})
        return {'type': 'ir.actions.act_window_close'}

    @api.model_create_multi
    def create(self, vals_list):
        print('zzzz', vals_list)
        activities = super(MailActivityInherit, self).create(vals_list)

        # find partners related to responsible users, separate readable from unreadable
        if any(user != self.env.user for user in activities.user_id):
            user_partners = activities.user_id.partner_id
            readable_user_partners = user_partners._filtered_access('read')
        else:
            readable_user_partners = self.env.user.partner_id

        # when creating activities for other: send a notification to assigned user;
        if self.env.context.get('mail_activity_quick_update'):
            activities_to_notify = self.env['mail.activity']
        else:
            activities_to_notify = activities.filtered(lambda act: act.user_id != self.env.user)
        if activities_to_notify:
            to_sudo = activities_to_notify.filtered(lambda act: act.user_id.partner_id not in readable_user_partners)
            other = activities_to_notify - to_sudo
            to_sudo.sudo().action_notify()
            other.action_notify()

        # subscribe (batch by model and user to speedup)
        for model, activity_data in activities._classify_by_model().items():
            per_user = dict()
            for activity in activity_data['activities'].filtered(lambda act: act.user_id):
                if activity.user_id not in per_user:
                    per_user[activity.user_id] = [activity.res_id]
                else:
                    per_user[activity.user_id].append(activity.res_id)
            for user, res_ids in per_user.items():
                pids = user.partner_id.ids if user.partner_id in readable_user_partners else user.sudo().partner_id.ids
                self.env[model].browse(res_ids).message_subscribe(partner_ids=pids)

        # send notifications about activity creation
        todo_activities = activities.filtered(lambda act: act.date_deadline <= fields.Date.today())
        if todo_activities:
            activity.user_id._bus_send("mail.activity/updated", {"activity_created": True})
        return activities


    # def _action_done(self, feedback=False, attachment_ids=None):
    #     """ Private implementation of marking activity as done: posting a message, deleting activity
    #         (since done), and eventually create the automatical next activity (depending on config).
    #         :param feedback: optional feedback from user when marking activity as done
    #         :param attachment_ids: list of ir.attachment ids to attach to the posted mail.message
    #         :returns (messages, activities) where
    #             - messages is a recordset of posted mail.message
    #             - activities is a recordset of mail.activity of forced automically created activities
    #     """
    #     # marking as 'done'
    #     messages = self.env['mail.message']
    #     next_activities_values = []
    #
    #     # Search for all attachments linked to the activities we are about to unlink. This way, we
    #     # can link them to the message posted and prevent their deletion.
    #     attachments = self.env['ir.attachment'].search_read([
    #         ('res_model', '=', self._name),
    #         ('res_id', 'in', self.ids),
    #     ], ['id', 'res_id'])
    #
    #     activity_attachments = defaultdict(list)
    #     for attachment in attachments:
    #         activity_id = attachment['res_id']
    #         activity_attachments[activity_id].append(attachment['id'])
    #
    #     for model, activity_data in self._classify_by_model().items():
    #         # Allow user without access to the record to "mark as done" activities assigned to them. At the end of the
    #         # method, the activity is unlinked or archived which ensure the user has enough right on the activities.
    #         records_sudo = self.env[model].sudo().browse(activity_data['record_ids'])
    #         for record_sudo, activity in zip(records_sudo, activity_data['activities']):
    #             # extract value to generate next activities
    #             if activity.chaining_type == 'trigger':
    #                 vals = activity.with_context(activity_previous_deadline=activity.date_deadline)._prepare_next_activity_values()
    #                 next_activities_values.append(vals)
    #
    #             # post message on activity, before deleting it
    #             activity_message = record_sudo.message_post_with_source(
    #                 'mail.message_activity_done',
    #                 attachment_ids=attachment_ids,
    #                 author_id=self.env.user.partner_id.id,
    #                 render_values={
    #                     'activity': activity,
    #                     'feedback': feedback,
    #                     'display_assignee': activity.user_id != self.env.user
    #                 },
    #                 mail_activity_type_id=activity.activity_type_id.id,
    #                 subtype_xmlid='mail.mt_activities',
    #             )
    #             if activity.activity_type_id.keep_done:
    #                 attachment_ids = (attachment_ids or []) + activity_attachments.get(activity.id, [])
    #                 if attachment_ids:
    #                     activity.attachment_ids = attachment_ids
    #
    #             # Moving the attachments in the message
    #             # TODO: Fix void res_id on attachment when you create an activity with an image
    #             # directly, see route /web_editor/attachment/add
    #             if activity_attachments[activity.id]:
    #                 message_attachments = self.env['ir.attachment'].browse(activity_attachments[activity.id])
    #                 if message_attachments:
    #                     message_attachments.write({
    #                         'res_id': activity_message.id,
    #                         'res_model': activity_message._name,
    #                     })
    #                     activity_message.attachment_ids = message_attachments
    #             messages += activity_message
    #
    #     next_activities = self.env['mail.activity']
    #     if next_activities_values:
    #         next_activities = self.env['mail.activity'].create(next_activities_values)
    #
    #     activity_to_keep = self.filtered('activity_type_id.keep_done')
    #     activity_to_keep.action_archive()
    #     # (self - activity_to_keep).unlink()  # will unlink activity, dont access `self` after that
    #
    #     return messages, next_activities


