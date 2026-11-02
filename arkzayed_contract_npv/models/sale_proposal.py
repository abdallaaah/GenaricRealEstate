from odoo import _, api, fields, models

ACTIVE_STATES = [
    'approved', 'signed_client', 'operation_review', 'finance_review', 'top_management',
    'signed_ceo', 'ready_to_deliver_contract', 'sent_to_client', 'delivered_contract',
    'ready_to_deliver', 'delivered',
]


def present_value(cash_flows, valuation_date, annual_rate):
    """cash_flows: list of (date, amount). Flows on/before valuation_date count at face value
    (they are due, not future); only genuinely future flows are discounted, by the number of days
    between valuation_date and the flow's date, using an annual compounding rate."""
    total = 0.0
    rate = annual_rate / 100.0
    for d, amount in cash_flows:
        if not d or d <= valuation_date:
            total += amount
            continue
        years = (d - valuation_date).days / 365.0
        total += amount / ((1 + rate) ** years)
    return total


class SaleProposal(models.Model):
    _inherit = 'sale.proposal'

    npv_discount_rate = fields.Float(
        related='company_id.npv_discount_rate', string='Current Company Discount Rate %', readonly=True)

    npv_at_signing = fields.Float(
        string='NPV at Signing', compute='_compute_npv_at_signing', store=True, digits=(16, 2),
        help="Present value of the full installment schedule, discounted back to the contract issue "
             "date at the discount rate in effect when this was first calculated. Locked once set: it "
             "does not change later even if the company's discount rate changes or installments are "
             "edited. Use \"Recalculate\" to force a fresh value.")
    npv_signing_date = fields.Date(
        string='Valuation Date (Signing)', compute='_compute_npv_at_signing', store=True)
    npv_signing_rate = fields.Float(
        string='Discount Rate Used (Locked)', compute='_compute_npv_at_signing', store=True)
    npv_nominal_total = fields.Float(
        string='Nominal Total (Signing)', compute='_compute_npv_at_signing', store=True,
        help="Sum of the installment schedule at face value, with no discounting.")
    npv_signing_discount = fields.Float(
        string='Value Lost to Time (Signing)', compute='_compute_npv_at_signing', store=True,
        help="Nominal Total minus NPV at Signing: how much value the payment plan's timing costs "
             "compared to being paid in full on day one.")

    npv_remaining_nominal = fields.Float(
        string='Remaining Installments (Nominal)', compute='_compute_npv_remaining_today')
    npv_remaining_today = fields.Float(
        string='NPV of Remaining Installments (Today)', compute='_compute_npv_remaining_today',
        help="Present value, as of today, of whatever is still uncollected on this contract's "
             "installment schedule, using today's company discount rate. Recomputed live.")
    npv_remaining_discount = fields.Float(
        string='Value Lost to Time (Remaining)', compute='_compute_npv_remaining_today')

    @api.depends('installment_ids.amount', 'installment_ids.date', 'contract_issue_date')
    def _compute_npv_at_signing(self):
        for rec in self:
            if rec.npv_at_signing:
                continue  # locked: never silently recompute once a value has been set
            lines = rec.installment_ids
            if not lines or not rec.contract_issue_date:
                rec.npv_at_signing = 0.0
                rec.npv_signing_date = rec.npv_signing_date or False
                rec.npv_signing_rate = rec.npv_signing_rate or 0.0
                rec.npv_nominal_total = 0.0
                rec.npv_signing_discount = 0.0
                continue
            rate = rec.company_id.npv_discount_rate
            flows = [(line.date, line.amount) for line in lines]
            nominal = sum(amount for _d, amount in flows)
            npv = present_value(flows, rec.contract_issue_date, rate)
            rec.npv_at_signing = npv
            rec.npv_signing_date = rec.contract_issue_date
            rec.npv_signing_rate = rate
            rec.npv_nominal_total = nominal
            rec.npv_signing_discount = nominal - npv

    def action_recalculate_npv_at_signing(self):
        for rec in self:
            rec.npv_at_signing = 0.0
        self._compute_npv_at_signing()

    @api.depends('installment_ids.remaining_amount', 'installment_ids.date', 'installment_ids.paid',
                 'company_id.npv_discount_rate')
    def _compute_npv_remaining_today(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rate = rec.company_id.npv_discount_rate
            open_lines = rec.installment_ids.filtered(lambda l: not l.paid and (l.remaining_amount or 0) > 0)
            flows = [(line.date, line.remaining_amount) for line in open_lines]
            nominal = sum(amount for _d, amount in flows)
            npv = present_value(flows, today, rate)
            rec.npv_remaining_nominal = nominal
            rec.npv_remaining_today = npv
            rec.npv_remaining_discount = nominal - npv
