from odoo import api, fields, models, _
from odoo.exceptions import UserError


class UnderCollectionWizard(models.Model):
    _name = 'under.collection.wizard'
    _description = 'under.collection.wizard'

    journal_id = fields.Many2one('account.journal', domain=[('type', '=', 'bank')])
    date = fields.Date(default=lambda self: fields.Date.today())

    def _target_cheques(self):
        ids = self.env.context.get('active_ids') or (
            [self.env.context['active_id']] if self.env.context.get('active_id') else [])
        if not ids:
            raise UserError(_("No active id, Please contact the administrator."))
        return self.env['cheque.manage'].browse(ids)

    def under_collection_entry(self):
        if self.env.context.get('active_id'):
            active_id = self.env.context.get('active_id')
            cheque_id = self.env['cheque.manage'].browse(active_id)
            cheque_id.under_collection(self.journal_id, self.date)
        else:
            raise UserError(_("No active id, Please contact the administrator."))

    def collect_entry(self):
        if self.env.context.get('active_id'):
            active_id = self.env.context.get('active_id')
            cheque_id = self.env['cheque.manage'].browse(active_id)
            cheque_id.action_bounce(self.journal_id, self.date)
        else:
            raise UserError(_("No active id, Please contact the administrator."))

    def submit_under_collection_entry(self):
        if self.env.context.get('active_id'):
            cheque = self.env['cheque.manage'].browse(self.env.context['active_id'])
            cheque.action_submit(date=self.date)
        else:
            raise UserError(_("No active id, Please contact the administrator."))

    def return_entry(self):
        if self.env.context.get('active_id'):
            cheque = self.env['cheque.manage'].browse(self.env.context['active_id'])
            cheque.action_return(date=self.date)
        else:
            raise UserError(_("No active id, Please contact the administrator."))

    def to_hermes_entry(self):
        if self.env.context.get('active_id'):
            cheque = self.env['cheque.manage'].browse(self.env.context['active_id'])
            cheque.to_hermes(date=self.date)
        else:
            raise UserError(_("No active id, Please contact the administrator."))

    def to_adib_entry(self):
        for cheque in self._target_cheques():
            cheque.to_adib(date=self.date)

    def return_adib_entry(self):
        for cheque in self._target_cheques():
            cheque.action_return_to_adib(date=self.date)