from odoo import models, fields


class BlockedUnitWizard(models.TransientModel):
    _name = 'blocked.unit.reason'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    unit_id = fields.Many2one('real.estate.unit')
    # reason = fields.Char(required=True)
    reason_id = fields.Many2one('block.reason')

    def action_block_unit(self):
        self.ensure_one()
        print(self.env.context)
        unit_id = self.env['real.estate.unit'].browse(self.env.context.get('default_unit_id'))
        if unit_id and self.reason_id:
            unit_id.write({'reason_id': self.reason_id, 'unit_status': 'blocked'})
            unit_id.message_post(
                body=f"Blocking Reason: {self.reason_id.name}",
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
