from odoo import fields, models, api


class CustomerOwnership(models.Model):
    _name = 'customer.ownership'
    _rec_name = 'customer_id'

    customer_id = fields.Many2one('res.partner')
    percentage = fields.Float(string='Percentage(%)')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)

    reservation_id = fields.Many2one('real.estate.sale.reservation', compute='_compute_reservation_id', store=True, readonly=False)
    contract_id = fields.Many2one('sale.proposal')
    from_action = fields.Boolean()

    @api.depends('contract_id', 'contract_id.sale_contract_reservation_id')
    def _compute_reservation_id(self):
        for rec in self:
            if rec.from_action:
                return
            if rec.contract_id and rec.contract_id.sale_contract_reservation_id:
                rec.reservation_id = rec.contract_id.sale_contract_reservation_id.id
            else:
                rec.reservation_id = False




