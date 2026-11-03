from odoo import api, fields, models

# This file holds the real.estate.unit fields/methods that reference sale.proposal and
# real.estate.sale.reservation. They were extracted out of real_estate_unit.py so that model's
# core definition could move into isky_18_realestate_developer_unit_inventory (Level 0) without
# pulling sale.proposal along with it. This file stays in the old monolith for now and will move,
# unchanged, into the future Sales & CRM module (Level 2) in that phase.


class RealEstateUnit(models.Model):
    _inherit = 'real.estate.unit'

    sale_proposal_parking_id = fields.Many2one('sale.proposal', string='Sale Proposal Parking')
    sale_proposal_parking_charging_id = fields.Many2one('sale.proposal', string="Sale Proposal Parking Charging")

    # Sales Contract Information for Tree View
    sale_contract_id = fields.Many2one(
        'sale.proposal',
        string='Sale Contract',
        compute='_compute_sale_contract',
        store=True,
        help="Most recent sale contract for this unit"
    )

    contract_installment_template_id = fields.Many2one(
        'installment.template',
        string='Contract Installment Template',
        related='sale_contract_id.installment_template_id',
        store=True,
        readonly=True
    )

    contract_total_area = fields.Float(
        string='Contract Total Area',
        related='sale_contract_id.contracted_total_area',
        store=True,
        readonly=True,
        digits=(16, 2)
    )

    contract_selling_price_from_contract = fields.Float(
        string='Contract Selling Price',
        related='sale_contract_id.contracted_selling_price',
        store=True,
        readonly=True,
        help="Selling price from the sale contract"
    )

    contract_count = fields.Integer(compute="_compute_contract_count")
    reservation_count = fields.Integer(compute="_compute_reservation_count")

    def _compute_contract_count(self):
        for rec in self:
            rec.contract_count = self.env['sale.proposal'].search_count([('unit_id', '=', rec.id)])

    def _compute_reservation_count(self):
        for rec in self:
            rec.reservation_count = self.env['real.estate.sale.reservation'].search_count([('unit_id', '=', rec.id)])

    @api.depends('unit_status')
    def _compute_sale_contract(self):
        """
        Find the active sale contract for this unit.
        Prioritizes signed/delivered contracts, then falls back to any contract.
        """
        for rec in self:
            # First, try to find signed/active contracts
            contract = self.env['sale.proposal'].search([
                ('unit_id', '=', rec.id),
                ('state', 'in', ['signed_client', 'signed_ceo', 'ready_to_deliver', 'delivered'])
            ], limit=1, order='create_date desc')

            # If no signed contract, get any contract (including draft)
            if not contract:
                contract = self.env['sale.proposal'].search([
                    ('unit_id', '=', rec.id),
                ], limit=1, order='create_date desc')

            rec.sale_contract_id = contract.id if contract else False

    def action_view_contracts(self):
        self.ensure_one()
        tree_view = self.env.ref('arkzayed_18_realestate_development.view_sale_proposal_tree')
        form_view = self.env.ref('arkzayed_18_realestate_development.view_sale_proposal_form')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contracts',
            'res_model': 'sale.proposal',
            'view_mode': 'list,form',
            'views': [(tree_view.id, 'list'), (form_view.id, 'form')],
            'domain': [('unit_id', '=', self.id)],
        }

    def action_view_reservations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reservations',
            'res_model': 'real.estate.sale.reservation',
            'view_mode': 'list,form',
            'domain': [('unit_id', '=', self.id)],
        }
