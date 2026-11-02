from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from ..models.sale_proposal import present_value

PERIODS_PER_YEAR = {
    'monthly': 12,
    'quarterly': 4,
    'semi_annual': 2,
    'annual': 1,
}


class NpvCalculatorWizard(models.TransientModel):
    _name = 'arkzayed.npv.calculator.wizard'
    _description = 'NPV Calculator (standalone, no contract needed)'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    discount_rate = fields.Float(
        compute='_compute_discount_rate', string='Discount Rate % (company setting)', readonly=True)
    price_source = fields.Selection([
        ('manual', 'Type a Price'),
        ('unit', 'Pick a Unit'),
    ], string='Price Source', default='manual', required=True,
        help="\"Pick a Unit\" only reads the unit's list price to fill the field below - it does not "
             "reserve, block, or change anything about the unit. You can still edit the price "
             "afterwards to try a different number.")
    unit_id = fields.Many2one(
        'real.estate.unit', string='Unit',
        help="Selecting a unit only fills the Total Price field for convenience; it has no other "
             "effect on the unit (no reservation, no status change).")
    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.context_today)
    total_price = fields.Float(string='Total Price', required=True)
    down_payment_pct = fields.Float(string='Down Payment %', default=10.0)
    years = fields.Float(
        string='Duration (Years)', default=5.0, required=True,
        help="Fractions are fine, e.g. 7.5 for seven and a half years. With Annual frequency, a "
             "fractional year rounds to the nearest whole installment.")
    frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
    ], string='Installment Frequency', default='quarterly', required=True)

    down_payment_amount = fields.Float(compute='_compute_schedule', string='Down Payment Amount')
    installment_count = fields.Integer(compute='_compute_schedule', string='Number of Installments')
    actual_duration_years = fields.Float(
        compute='_compute_schedule', string='Actual Duration (Years)', digits=(16, 2),
        help="Installment Count ÷ payments per year. If this doesn't match \"Duration (Years)\" "
             "exactly, your number didn't divide evenly into whole installments and was rounded - "
             "this is the real duration that was actually used.")
    end_date = fields.Date(compute='_compute_schedule', string='Last Installment Date')
    installment_amount = fields.Float(compute='_compute_schedule', string='Amount per Installment')
    nominal_total = fields.Float(compute='_compute_schedule', string='Nominal Total (= Total Price)')
    npv_total = fields.Float(compute='_compute_schedule', string='NPV (Present Value)')
    value_lost_to_time = fields.Float(compute='_compute_schedule', string='Value Lost to Time')
    npv_pct_of_nominal = fields.Float(compute='_compute_schedule', string='NPV as % of Price')

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        # Read-only convenience: only fills the price field on this transient wizard record.
        # Never writes anything back to the unit (no reservation, no status change).
        if self.unit_id:
            self.total_price = self.unit_id.price_after_discount or self.unit_id.total_price_unit or 0.0

    @api.onchange('price_source')
    def _onchange_price_source(self):
        if self.price_source == 'manual':
            self.unit_id = False

    @api.depends('company_id')
    def _compute_discount_rate(self):
        # Independent of company_id ever being set on the record: falls back to the current user's
        # company, so this can never silently read as 0 just because a hidden default didn't apply.
        for wiz in self:
            wiz.discount_rate = (wiz.company_id or self.env.company).npv_discount_rate

    @api.depends('start_date', 'total_price', 'down_payment_pct', 'years', 'frequency', 'discount_rate')
    def _compute_schedule(self):
        for wiz in self:
            price = wiz.total_price or 0.0
            down = price * (wiz.down_payment_pct or 0.0) / 100.0
            remaining = price - down
            periods_per_year = PERIODS_PER_YEAR[wiz.frequency]
            n = max(round((wiz.years or 0) * periods_per_year), 0)
            interval_months = 12 // periods_per_year

            flows = []
            if wiz.start_date:
                flows.append((wiz.start_date, down))
            installment_amount = (remaining / n) if n else 0.0
            last_date = wiz.start_date
            if wiz.start_date:
                for k in range(1, n + 1):
                    last_date = wiz.start_date + relativedelta(months=interval_months * k)
                    flows.append((last_date, installment_amount))

            nominal = sum(a for _d, a in flows)
            npv = present_value(flows, wiz.start_date, wiz.discount_rate) if wiz.start_date else 0.0

            wiz.down_payment_amount = down
            wiz.installment_count = n
            wiz.actual_duration_years = (n / periods_per_year) if periods_per_year else 0.0
            wiz.end_date = last_date if n else wiz.start_date
            wiz.installment_amount = installment_amount
            wiz.nominal_total = nominal
            wiz.npv_total = npv
            wiz.value_lost_to_time = nominal - npv
            wiz.npv_pct_of_nominal = (npv / nominal * 100.0) if nominal else 0.0
