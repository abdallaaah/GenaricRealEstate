from odoo import fields, models, api


class CustomerOwnership(models.Model):
    """The shared split line for reservations and contracts. Phase 3 step 5 moved the
    percentage, the ordering and the sum-to-100 rule into realestate.split.line.mixin;
    customer_id stays named as it is because legacy reports and views read it by name."""
    _name = 'customer.ownership'
    _inherit = ['realestate.split.line.mixin']
    _rec_name = 'customer_id'
    # _order comes from realestate.split.line.mixin

    _split_party_field = 'customer_id'
    # B2: PRECEDENCE order, not just a list. A contract line also carries reservation_id
    # (see _compute_reservation_id below), so the contract has to win or the line would be
    # counted in both totals.
    _split_parent_fields = ('contract_id', 'reservation_id')

    customer_id = fields.Many2one('res.partner')
    # percentage and sequence come from realestate.split.line.mixin
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    reservation_id = fields.Many2one('real.estate.sale.reservation', compute='_compute_reservation_id', store=True, readonly=False)
    contract_id = fields.Many2one('sale.proposal')
    from_action = fields.Boolean()

    @api.constrains('percentage', 'sequence', 'reservation_id', 'contract_id')
    def _check_split_total_is_100(self):
        """Redeclared with this model's parent fields added, so moving a line between a
        reservation and a contract re-checks both groups. Same guard pattern as S6."""
        return super()._check_split_total_is_100()

    @api.depends('contract_id', 'contract_id.sale_contract_reservation_id')
    def _compute_reservation_id(self):
        for rec in self:
            if rec.from_action:
                # B1: `continue`, not `return`. A `return` here aborted the loop, leaving every
                # later record in the set with no value for a stored compute - which Odoo
                # rejects outright. The copy action creates every line with from_action=True in
                # one batch, so it could never succeed with more than zero template lines.
                continue
            if rec.contract_id and rec.contract_id.sale_contract_reservation_id:
                rec.reservation_id = rec.contract_id.sale_contract_reservation_id.id
            else:
                rec.reservation_id = False




