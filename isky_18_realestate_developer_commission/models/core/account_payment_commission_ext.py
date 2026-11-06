from odoo import models, fields


class AccountPayment(models.Model):
    """broker.claim sync, moved here from the accounting bridge: broker.claim is this
    module's own model, which the bridge (L1) must not reach into. Chains via super() on
    top of isky_18_realestate_developer_sales_crm's own account.payment override."""
    _inherit = 'account.payment'

    def action_post(self):
        result = super(AccountPayment, self).action_post()
        for payment in self:
            if payment.state == 'paid':
                self.update_broker_claim(payment.id)
        return result

    def action_draft(self):
        super(AccountPayment, self).action_draft()
        for payment in self:
            broker_claim = self.env['broker.claim'].search([
                ('payment_id', '=', payment.id)
            ], limit=1)
            if broker_claim and broker_claim.state != 'draft':
                broker_claim.write({
                    'state': 'confirmed',
                    'payment_date': False
                })

    def update_broker_claim(self, payment):
        broker_claim = self.env['broker.claim'].search([
            ('payment_id', '=', payment)
        ], limit=1)
        if broker_claim and broker_claim.state != 'paid':
            broker_claim.write({
                'state': 'paid',
                'payment_date': fields.Date.today()
            })
