from odoo import models, fields, _, api
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
from odoo.addons.isky_18_realestate_developer_unit_inventory.models.selections import referred_by_selection, charge_for_selection, charge_area_selection, charge_price_selection

referred_by_selection = referred_by_selection.copy()
referred_by_selection.remove(('management', 'Management'))
referred_by_selection.remove(('direct', 'Direct'))

class RealEstateLeaseContract(models.Model):
    _name = 'real.estate.lease.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Real Estate Lease Contract'

    def _default_income_account(self):
        return self.env["ir.config_parameter"].sudo().get_param("arkzayed_18_realestate_development.income_account")

    name = fields.Char(string='Contract Reference', required=True, copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))
    customer_id = fields.Many2one('res.partner')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id, domain=[('active', '=', True)])
    unit_id = fields.Many2one('real.estate.unit')
    unit_name = fields.Char(related='unit_id.name')
    unit_number = fields.Char(related='unit_id.unit_number')
    # unit_code = fields.Char(related='unit_id.unit_code')
    unit_location = fields.Char(related='unit_id.unit_location')
    unit_area = fields.Float(related='unit_id.unit_area')
    net_area = fields.Char(related='unit_id.net_area')
    indoor_price_per_month_sqm = fields.Float(related='unit_id.indoor_price_per_month_sqm')
    outdoor_price_per_month_sqm = fields.Float(related='unit_id.outdoor_price_per_month_sqm')
    indoor_outdoor_price_per_month_sqm = fields.Float(related='unit_id.indoor_outdoor_price_per_month_sqm')
    lease_contract_type = fields.Selection([
        ('residential', 'Residential'),
        ('commercial', 'Commercial')
    ])
    charge_for = fields.Selection(selection=charge_for_selection)
    charge_area = fields.Selection(selection=charge_area_selection)
    charge_price = fields.Selection(selection=charge_price_selection)
    contract_status = fields.Selection([
        ('draft', 'Draft'),
        ('reserved', 'Reserved'),
        ('approved', 'Approved'),
        ('running', 'Running'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated')
    ], copy=False, default='draft')
    referred_by = fields.Selection(selection=referred_by_selection, string='Referred By')
    referred_by_partner_id = fields.Many2one('res.partner')
    referred_by_employee_id = fields.Many2one('hr.employee')
    other = fields.Char()
    contract_issue_date = fields.Date()
    contract_start_date = fields.Date()
    contract_end_date = fields.Date()
    expected_opening_data = fields.Date()
    preparation_period = fields.Integer()
    contract_assessment_date = fields.Date()
    minimum_lease_term = fields.Integer()
    notice_period = fields.Integer()
    # payment_plan = fields.Selection([
    #     ('monthly', 'Monthly'),
    #     ('quarterly', 'Quarterly'),
    #     ('semi_annually', 'Semi-Annually'),
    #     ('annually', 'Annually')
    # ])
    rent_price_per_m2_per_month = fields.Float()
    outdoor_rent_price_per_m2_per_month = fields.Float()
    maintenance_per_m2_per_month = fields.Float()
    outdoor_maintenance_per_m2_per_month = fields.Float()
    advance_payment = fields.Float()
    security_deposit = fields.Float()
    grace_period_start = fields.Date()
    grace_period_end = fields.Date()
    annual_increase = fields.Float()
    minimum_opening_hours = fields.Integer()
    revenue_share = fields.Float()
    revenue_share_2 = fields.Float()
    expected_sales_per_month = fields.Float()
    marketing_fees = fields.Float()
    capex = fields.Boolean()
    service_charge_per_m2_per_month = fields.Float()
    late_payment_penalty = fields.Text()
    late_payment_limit = fields.Text()
    late_opening_penalty = fields.Text()
    non_evacuation_penalty = fields.Text()
    electricity = fields.Boolean()
    water = fields.Boolean()
    gas = fields.Boolean()
    cooling_water = fields.Boolean()
    cooling_water_price = fields.Float()
    landline = fields.Boolean()
    landline_fees = fields.Float()
    internet = fields.Boolean()
    solar_system = fields.Boolean()
    heating_system = fields.Boolean()
    paid = fields.Float(compute="_check_amounts", string="Paid Amount")
    balance = fields.Float(compute="_check_amounts", string="Balance", )
    amount_total = fields.Float(compute="_check_amounts", string="Total Amount", )
    template_id = fields.Many2one("installment.template", "Installment Template")
    loan_line_ids = fields.One2many("loan.line", "installment_contract_id")
    rental_fee = fields.Float("Rental fee", compute="_compute_rental_fee", digits=(25, 5), store=True)
    rent = fields.Integer("Rent (in month)")
    rental_agreement = fields.Selection(selection=[("per_sft", "Per M2"), ("fixed", "Fixed Amount")],
                                        default="per_sft")
    periodicity = fields.Selection([("days", "Days"), ("weeks", "Weeks"), ("months", "Months"), ("years", "Years")],
                                   string="Recurrence", required=True, default="months", tracking=True,
                                   help="Invoice automatically repeat at specified interval")
    recurring_interval = fields.Integer(string="Invoicing Period", help="Repeat every (Days/Week/Month/Year)",
                                        required=True, default=1, tracking=True)
    date_payment = fields.Date("First Payment Date", default=fields.Date.context_today)
    increment_period = fields.Selection([("months", "Months"), ("years", "Years")],
                                        string="Increment Recurrence", required=True, default="years", tracking=True)
    increment_recurring_interval = fields.Integer("Increment Recurring Interval")
    increment_percentage = fields.Float("Increment Percentage")
    account_income = fields.Many2one("account.account", "Income Account", default=_default_income_account)
    tax_status = fields.Selection([("per_installment", "Per Installment"), ("tax_base_amount", "Tax Base Amount")],
                                  default="per_installment")
    lg_required = fields.Boolean(deafult=False)
    lg_number = fields.Char()
    bank_name = fields.Char()
    lg_amount = fields.Float()
    capex_line_ids = fields.One2many('capex.cost.lines', 'contract_id')
    construction_deposit = fields.Float()
    # maintenance
    maintenance_periodicity = fields.Selection(
        [("days", "Days"), ("weeks", "Weeks"), ("months", "Months"), ("years", "Years")],
        string="Maintenance", default="months", tracking=True,
        help="Invoice automatically repeat at specified interval")
    maintenance_interval = fields.Integer(string="Invoicing Period (Maintenance)",
                                          help="Repeat every (Days/Week/Month/Year)",
                                          default=1, tracking=True)
    maintenance_total_cost = fields.Float(compute="_compute_maintenance_total_cost", store=True)
    maintenance_line_ids = fields.One2many("loan.line", "maintenance_contract_id")
    maintenance_paid = fields.Float(compute="_check_maintenance_amounts", string="Maintenance Paid Amount")
    maintenance_balance = fields.Float(compute="_check_maintenance_amounts", string="Maintenance Balance")
    maintenance_amount_total = fields.Float(compute="_check_maintenance_amounts", string="Maintenance Total Amount")
    maintenance_increment_period = fields.Selection([("months", "Months"), ("years", "Years")],
                                                    string="Maintenance Recurrence", default="years", tracking=True)
    increment_maintenance_interval = fields.Integer("Increment Period (Maintenance)")
    maintenance_percentage = fields.Float("Increment Percentage")
    maintenance_first_date = fields.Date()
    include_free_parking = fields.Boolean('Free Parking')
    slots = fields.Selection([("specific slots", "Specific Slots"), ("number of slots", "Number Of Slots")])
    charging_slots = fields.Selection([("specific slots", "Specific Slots"), ("number of slots", "Number Of Slots")])
    number_of_slots = fields.Integer()
    charging_number_of_slots = fields.Integer()
    parking_lines_ids = fields.One2many('real.estate.unit', 'lease_contract_id')
    charging_parking_lines_ids = fields.One2many('real.estate.unit', 'leasee_contract_id')
    parking_unit_id = fields.Many2one('real.estate.unit', string="Select Parking Unit", domain="[('unit_type','=','parking'),('unit_status', '=', 'available'), ('unit_purpose', '=', 'to_lease')]")
    separate_parking_price = fields.Boolean()
    parking_price = fields.Float()
    # parking_installment_template_id = fields.Many2one('maintenance.template', domain=[('type', '=', 'parking')])
    parking_fees_contract_ids = fields.One2many('loan.line', 'parking_fees_contract_id')
    parking_price_method = fields.Selection(
        [('fixed_amount', 'Fixed Amount'), ('percentage', 'Percentage From Unit Price')])
    monthly_parking_installment_start_date = fields.Date()
    quarterly_parking_installment_start_date = fields.Date()
    semi_annual_parking_installment_start_date = fields.Date()
    annual_parking_installment_start_date = fields.Date()
    # monthly_parking_duration = fields.Integer(related="parking_installment_template_id.monthly_installment_duration")
    # quarter_parking_duration = fields.Integer(related="parking_installment_template_id.quarterly_installment_duration")
    # semi_parking_annual_duration = fields.Integer(related="parking_installment_template_id.semi_annual_installment_duration")
    # annual_parking_duration = fields.Integer(related="parking_installment_template_id.annual_installment_duration")
    parking_increase_percentage = fields.Float()
    parking_interval = fields.Integer(string="Invoicing Period (Parking)",
                                          help="Repeat every (Days/Week/Month/Year)",
                                          default=1, tracking=True)
    parking_installment_period = fields.Selection([("months", "Months"), ("years", "Years")],
                                                    default="years", tracking=True)

    parking_increase_interval = fields.Integer(string="Increment Period (Parking)",
                                      help="Repeat every (Days/Week/Month/Year)",
                                      default=1, tracking=True)
    parking_increment_period = fields.Selection([("months", "Months"), ("years", "Years")],
                                                default="years", tracking=True)
    parking_increment_percentage = fields.Integer()

    handover_conditions = fields.Text()
    handover_terms = fields.Text()
    refund_policy = fields.Text()
    cancellation_policy = fields.Text()

    def write(self, vals):
        res = super().write(vals)
        contract_status = vals.get('contract_status')
        if self.unit_id:
            if contract_status == 'reserved':
                self.unit_id.unit_status = 'reserved'
            elif contract_status == 'approved':
                self.unit_id.unit_status = 'reserved'
            elif contract_status == 'running':
                self.unit_id.unit_status = 'in_lease'
        if contract_status == 'approved':
            if self.customer_id.company_type != 'person' and not self.customer_id.cr:
                raise UserError('Customer Has no CR')
        if not self.customer_id.cr:
            return
        return res

    @api.depends("loan_line_ids.amount", "loan_line_ids.amount_residual")
    def _check_amounts(self):
        total_paid = 0
        total_non_paid = 0
        amount_total = 0
        for rec in self:
            for line in rec.loan_line_ids:
                amount_total += line.amount
                total_non_paid += line.amount_residual
                total_paid += line.amount - line.amount_residual

            rec.paid = sum(rec.loan_line_ids.filtered(lambda x: x.payment_state == 'paid').mapped('amount'))
            rec.balance = total_non_paid
            rec.amount_total = amount_total

    @api.depends("maintenance_line_ids.amount", "maintenance_line_ids.amount_residual")
    def _check_maintenance_amounts(self):
        total_paid = 0
        total_non_paid = 0
        amount_total = 0
        for rec in self:
            for line in rec.maintenance_line_ids:
                amount_total += line.amount
                total_non_paid += line.amount_residual
                total_paid += line.amount - line.amount_residual

            rec.maintenance_paid = sum(
                rec.maintenance_line_ids.filtered(lambda x: x.payment_state == 'paid').mapped('amount'))
            rec.maintenance_balance = total_non_paid
            rec.maintenance_amount_total = amount_total

    @api.depends("rent", 'charge_for', 'charge_area', 'charge_price', 'rent_price_per_m2_per_month')
    def _compute_rental_fee(self):
        for rec in self:
            if rec.rental_agreement == "per_sft":
                indoor_price_per_month_sqm = rec.unit_id.indoor_price_per_month_sqm
                outdoor_price_per_month_sqm = rec.unit_id.outdoor_price_per_month_sqm
                indoor_outdoor_price_per_month_sqm = rec.unit_id.indoor_outdoor_price_per_month_sqm

                # Indoor Charge
                if rec.charge_for == 'indoor':
                    if rec.charge_area == 'net_area':
                        rec.rental_fee = rec.unit_id.indoor_net_area * indoor_price_per_month_sqm
                    elif rec.charge_area == 'gross_area':
                        rec.rental_fee = rec.unit_id.indoor_gross_area * indoor_price_per_month_sqm

                # Outdoor Charge
                elif rec.charge_for == 'outdoor':
                    if rec.charge_area == 'net_area':
                        rec.rental_fee = rec.unit_id.outdoor_net_area * outdoor_price_per_month_sqm
                    elif rec.charge_area == 'gross_area':
                        rec.rental_fee = rec.unit_id.outdoor_gross_area * outdoor_price_per_month_sqm

                # Indoor and Outdoor Charge
                elif rec.charge_for == 'indoor_outdoor':
                    if rec.charge_area == 'net_area':
                        if rec.charge_price == 'single':
                            rec.rental_fee = (rec.unit_id.indoor_net_area + rec.unit_id.outdoor_net_area) * indoor_outdoor_price_per_month_sqm
                        elif rec.charge_price == 'separate':
                            rec.rental_fee = (rec.unit_id.indoor_net_area * indoor_price_per_month_sqm) + (rec.unit_id.outdoor_net_area * rec.outdoor_price_per_month_sqm)
                    elif rec.charge_area == 'gross_area':
                        if rec.charge_price == 'single':
                            rec.rental_fee = (rec.unit_id.indoor_gross_area + rec.unit_id.outdoor_gross_area) * indoor_outdoor_price_per_month_sqm
                        elif rec.charge_price == 'separate':
                            rec.rental_fee = (rec.unit_id.indoor_gross_area * indoor_price_per_month_sqm) + (rec.unit_id.outdoor_gross_area * rec.outdoor_price_per_month_sqm)
            else:
                rec.rental_fee = rec.rent

    @api.depends('charge_for', 'charge_area', 'charge_price', 'maintenance_per_m2_per_month')
    def _compute_maintenance_total_cost(self):
        for rec in self:
            price_per_m2 = rec.maintenance_per_m2_per_month

            # Indoor Charge
            if rec.charge_for == 'indoor':
                if rec.charge_area == 'net_area':
                    rec.maintenance_total_cost = rec.unit_id.indoor_net_area * price_per_m2
                elif rec.charge_area == 'gross_area':
                    rec.maintenance_total_cost = rec.unit_id.indoor_gross_area * price_per_m2

            # Outdoor Charge
            elif rec.charge_for == 'outdoor':
                if rec.charge_area == 'net_area':
                    rec.maintenance_total_cost = rec.unit_id.outdoor_net_area * price_per_m2
                elif rec.charge_area == 'gross_area':
                    rec.maintenance_total_cost = rec.unit_id.outdoor_gross_area * price_per_m2

            # Indoor and Outdoor Charge
            elif rec.charge_for == 'indoor_outdoor':
                if rec.charge_area == 'net_area':
                    if rec.charge_price == 'single':
                        rec.maintenance_total_cost = (rec.unit_id.indoor_net_area + rec.unit_id.outdoor_net_area) * price_per_m2
                    elif rec.charge_price == 'separate':
                        rec.maintenance_total_cost = (rec.unit_id.indoor_net_area * price_per_m2) + (rec.unit_id.outdoor_net_area * rec.outdoor_maintenance_per_m2_per_month)
                elif rec.charge_area == 'gross_area':
                    if rec.charge_price == 'single':
                        rec.maintenance_total_cost = (rec.unit_id.indoor_gross_area + rec.unit_id.outdoor_gross_area) * price_per_m2
                    elif rec.charge_price == 'separate':
                        rec.maintenance_total_cost = (rec.unit_id.indoor_gross_area * price_per_m2) + (rec.unit_id.outdoor_gross_area * rec.outdoor_maintenance_per_m2_per_month)

    def action_calculate_installment(self):
        if self.rent_price_per_m2_per_month > 0.0 or self.rental_fee > 0.00:
            self.prepare_lines()

    def action_calculate_maintenance(self):
        if self.maintenance_per_m2_per_month > 0.0 or self.maintenance_total_cost > 0.00:
            self.maintenance_prepare_lines()

    def prepare_lines(self):
        rental_lines = []
        self.loan_line_ids = None
        for rec in self:
            if rec.periodicity and rec.date_payment and rec.contract_end_date:
                i = 1
                date_to = rec.contract_end_date
                rental_fee = rec.rental_fee * rec.recurring_interval
                new_date = rec.date_payment
                rental_lines.append((0, 0, {
                    "serial": i,
                    "amount": rental_fee,
                    "date": new_date,
                    "name": _("Rental Fee"),
                }))
                i += 1
                incr_new_date = rec.date_payment
                periodicity = self.periodicity
                increment_period = self.increment_period
                incr_new_date = incr_new_date + relativedelta(**{increment_period: self.increment_recurring_interval})

                while new_date < (date_to - relativedelta(**{periodicity: self.recurring_interval})):
                    new_date = new_date + relativedelta(**{periodicity: self.recurring_interval})
                    if incr_new_date <= new_date:
                        incr_new_date = incr_new_date + relativedelta(
                            **{increment_period: self.increment_recurring_interval})

                        rental_fee += (rental_fee * self.increment_percentage) / 100

                    rental_lines.append((0, 0, {
                        "serial": i,
                        "amount": rental_fee,
                        "date": new_date,
                        "name": _("Rental Fee"),
                    }))
                    i += 1
                self.write({"loan_line_ids": rental_lines})

    def maintenance_prepare_lines(self):
        maintenance_lines = []
        self.maintenance_line_ids = None
        for rec in self:
            if rec.maintenance_periodicity and rec.date_payment and rec.contract_end_date:
                i = 1
                date_to = rec.contract_end_date
                maintenance_fee = rec.maintenance_total_cost * rec.maintenance_interval
                if rec.maintenance_periodicity == 'years':
                    maintenance_fee *= 12
                if rec.maintenance_periodicity == 'weeks':
                    maintenance_fee /= 4
                new_date = rec.maintenance_first_date
                maintenance_lines.append((0, 0, {
                    "serial": i,
                    "amount": maintenance_fee,
                    "date": new_date,
                    "name": _("Maintenance Fee"),
                }))
                i += 1
                incr_new_date = rec.date_payment
                periodicity = self.maintenance_periodicity
                increment_period = self.maintenance_increment_period
                incr_new_date = incr_new_date + relativedelta(**{increment_period: self.increment_maintenance_interval})

                while new_date < (date_to - relativedelta(**{periodicity: self.maintenance_interval})):
                    new_date = new_date + relativedelta(**{periodicity: self.maintenance_interval})
                    if incr_new_date <= new_date:
                        incr_new_date = incr_new_date + relativedelta(
                            **{increment_period: self.increment_maintenance_interval})

                        maintenance_fee += (maintenance_fee * self.maintenance_percentage) / 100

                    maintenance_lines.append((0, 0, {
                        "serial": i,
                        "amount": maintenance_fee,
                        "date": new_date,
                        "name": _("Maintenance Fee"),
                    }))
                    i += 1
                self.write({"maintenance_line_ids": maintenance_lines})


    def add_monthly_parking_lines(self, date ,amount, name):
        for rec in self:
            rec.write({
                'parking_fees_contract_ids': [(0, 0, {
                    'date': date,
                    'name': name,
                    'amount': amount
                })]
            })


    def calculate_raise(self):
        for rec in self:
            if rec.parking_increment_period == 'months':
                pass
            if rec.parking_increment_period == 'years':
                pass

    def calc_next_raise_date(self, date, raise_period, interval):
        next_raise_date = None
        if raise_period == "months":
            next_raise_date = date + relativedelta(months=interval)
        if raise_period == "years":
            next_raise_date = date + relativedelta(years=interval)
        return next_raise_date

    def action_calculate_parking_lease(self):
        [line.unlink() for line in self.parking_fees_contract_ids]
        if not self.contract_end_date:
            raise ValidationError("Please Add Contract End Date")
        if not self.parking_interval:
            raise ValidationError("Please Add parking Interval")

        for rec in self:
            amount = rec.parking_price
            date = rec.date_payment
            end_date = rec.contract_end_date
            name = "Parking Fee"
            count = 0
            last_amount = 0
            next_raise_date = self.calc_next_raise_date(rec.date_payment, rec.parking_increment_period, rec.parking_increase_interval)
            while(date < end_date):

                if rec.parking_installment_period == 'months':
                    if count == 0:
                        amount = rec.parking_price * rec.parking_interval
                    self.add_monthly_parking_lines(date, round(amount, 2), name)
                    date = date + relativedelta(months=rec.parking_interval)
                    if date >= next_raise_date:
                        """so i will change the amount to the new one after raise"""

                        amount += amount * (rec.parking_increment_percentage / 100 )
                        next_raise_date = self.calc_next_raise_date(date, rec.parking_increment_period,
                                                                    rec.parking_increase_interval)

                if rec.parking_installment_period == 'years':
                    if count == 0:
                        amount = rec.parking_price * (rec.parking_interval * 12) #- last_amount
                    self.add_monthly_parking_lines(date, round(amount, 2), name)
                    date = date + relativedelta(years=rec.parking_interval)
                    if date >= next_raise_date:
                        """so i will change the amount to the new one after raise"""

                        amount += amount * (rec.parking_increment_percentage / 100 )
                        next_raise_date = self.calc_next_raise_date(date, rec.parking_increment_period,
                                                                    rec.parking_increase_interval)
                count+=1
            print(count)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('lease.contract') or _('New')
        res = super(RealEstateLeaseContract, self).create(vals)
        parking_lines = vals.get('parking_lines_ids')
        if parking_lines:
            for park in parking_lines:
                unit = self.env['real.estate.unit'].browse(int(park[2].get('unit_id')))
                unit.unit_status = 'reserved'
        return res

    @api.onchange('include_free_parking')
    def _onchange_include_free_parking(self):
        if self.include_free_parking == False:
            self.slots = None

    @api.onchange('contract_status')
    def _change_parking_status(self):
        if self.contract_status == 'running':
            for park in self.parking_lines_ids:
                park.unit_id.unit_status = 'in_lease'