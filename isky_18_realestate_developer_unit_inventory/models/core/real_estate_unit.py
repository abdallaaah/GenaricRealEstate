from odoo import fields, models, api, _
from odoo.api import ondelete
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import calendar
from datetime import date
import math
import base64
from PyPDF2 import PdfWriter
from PIL import Image
import io
from ..selections import unit_type_selection, residential_type_selection, public_area_selection, retail_type_selection, \
    entertainment_type_selection, industrial_type_selection, finishing_type_selection

retail_type_selection = retail_type_selection.copy()
retail_type_selection.append(('retail','Retail'))

def add_months(source_date, months):
    month = source_date.month - 1 + months
    year = int(source_date.year + month / 12)
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class RealEstateUnit(models.Model):
    _name = 'real.estate.unit'
    _description = 'Real Estate Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'installment.mixin', 'realestate.hierarchy.node.mixin']
    _rec_name = 'system_code'

    @api.model
    def _selection_parent_model(self):
        model_names = ['realestate.project',
                       'zone',
                       'real.estate.building',
                       'floor',
                       ]
        domain = ['|'] * (len(model_names) - 1)  # Create the appropriate number of OR conditions
        domain += [('name', 'ilike', name) for name in model_names]
        return [(model.model, model.display_name) for model in self.env['ir.model'].sudo().search(domain)]

    name = fields.Char()
    abbreviation = fields.Char(string="Code")
    system_code = fields.Char(compute="compute_unit_system_code", store=True)
    unit_number = fields.Char()
    unit_area = fields.Float(string='Gross Total Area', compute='_compute_total_gross_area', store=True)
    unit_plan = fields.Binary(string='Unit Plan')
    unit_plan_filename = fields.Char(string='Unit Plan Filename')
    unit_plan1 = fields.Binary(string='Unit Plan 1')
    unit_plan1_filename = fields.Char(string='Unit Plan Filename 1')
    unit_plan2 = fields.Binary(string='Unit Plan 2')
    unit_plan2_filename = fields.Char(string='Unit Plan Filename 2')
    floor_plan = fields.Binary(string='Floor Plan')
    floor_plan1 = fields.Binary(string='Floor Plan 1')
    floor_plan2 = fields.Binary(string='Floor Plan 2')
    payment_plan = fields.Binary(string='Payment Plan')
    analytic_account_id = fields.Many2one(comodel_name="account.analytic.account")
    specially_booked = fields.Boolean(string='Specially Booked')
    customer_id = fields.Many2one('res.partner', domain="[('is_customer','=',True)]")
    unit_phase = fields.Char(string='Unit Phase')
    project_phase = fields.Many2one('real.estate.project.phase', string='Project Phase')
    unit_purpose = fields.Selection([
        ('to_lease', 'To Lease'),
        ('to_sale', 'To Sale'),
        ('services', 'Services'),
        ('other', 'Other')
    ], string='Unit Purposes')
    unit_status = fields.Selection([
        ('specially_booked', 'Specially Booked'),
        ('available', 'Available'),
        ('available_for_sale', 'Available For Sale'),
        ('reserved', 'Reserved'),
        ('on_hold_ma', 'Hold M.A '),
        ('blocked', 'Blocked'),
        ('expired_reservation', 'Expired Reservation'),
        ('onhold_expired_reservation', 'On-hold Expired Reservation'),
        ('sold', 'Sold'),
        ('in_lease', 'In Lease'),
        ('delivered', 'Delivered'),
        ('in_merge', 'In Merge'),
        ('cancelled_reservation', 'Cancelled Reservation'),
    ], string='Unit Status', default='available', tracking=True)
    unit_type = fields.Selection(selection=unit_type_selection, string='Unit Type',default='residential')
    unit_sale_type = fields.Selection([('primary', 'Primary'), ('resale', 'Resale')])
    is_compound = fields.Boolean('Compound')
    finishing_type = fields.Selection(selection=finishing_type_selection, string='Finishing Type')
    unit_categorization = fields.Char()
    ready_to_move = fields.Boolean('Ready To Move')
    delivery_date = fields.Date(string='Delivery Date', tracking=True)
    public_area = fields.Selection(selection=public_area_selection, string='Public Area')
    storge_capacity = fields.Float()
    retail_type = fields.Selection(selection=retail_type_selection, string='Retail Type')
    office_type_id = fields.Many2one('office.type', string='Office Type')
    residential_type = fields.Selection(selection=residential_type_selection, string='Residential Type',index=True)
    entertainment_type = fields.Selection(selection=entertainment_type_selection, string='Entertainment Type')
    industrial_type = fields.Selection(selection=industrial_type_selection, string='Industrial Type')
    parking_type = fields.Selection([
        ('indoor_parking', 'Indoor Parking'),
        ('outdoor_parking', 'Outdoor Parking')
    ], string='Parking Type')
    medical_type_id = fields.Many2one('medical.type', string='Medical Type')
    active = fields.Boolean(default=True)
    estimate_delivery_years = fields.Integer(string='Estimated Delivery Years')

    @api.onchange('unit_type')
    def _onchange_unit_type_estimate_delivery_years(self):
        for rec in self:
            config = self.env['unit.estimate.delivery'].search([('unit_type', '=', rec.unit_type)], limit=1)
            rec.estimate_delivery_years = config.estimate_delivery_years if config else 0

    # Resedintial

    finished = fields.Selection(selection=finishing_type_selection, string='Finished')
    furnished = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string='Furnished')
    heating_source = fields.Selection([
        ('unknown', 'Unknown'),
        ('electricity', 'Electricity'),
        ('wood', 'Wood'),
        ('pellets', 'Pellets'),
        ('oil', 'Oil'),
        ('gas', 'Gas'),
        ('district_heating', 'District Heating')
    ], string='Heating Source')
    number_of_rooms = fields.Char(string='Number of Rooms')
    number_of_bathrooms = fields.Char(string='Number of Bathrooms')
    garden_view = fields.Boolean(string='Garden View')
    pool_view = fields.Boolean(string='Pool View')
    city_view = fields.Boolean(string='City View')
    sea_view = fields.Boolean(string='Sea View')
    lagoon_view = fields.Boolean(string='Lagoon View')
    internal_view = fields.Boolean(string='Internal View')
    has_garden = fields.Boolean(string='Has Garden')
    has_outdoor = fields.Boolean(string='Has Outdoor')
    has_roof = fields.Boolean(string='Has Roof')
    roof_area = fields.Float(string='Roof Area')
    has_parking = fields.Boolean(string='Has Parking')
    number_of_slots = fields.Integer(compute='_compute_number_of_slots', store=True)
    has_club_membership = fields.Boolean(string='Has Club Membership')
    design_id = fields.Many2one('unit.design')
    gross_area = fields.Char(string='Gross Area')
    net_area = fields.Char(string='Net Total Area', compute='_compute_total_net_area')
    has_balcony = fields.Boolean(string='Has Balcony')
    number_of_balcony = fields.Integer()
    roof_access = fields.Boolean(string='Roof Access')
    has_pool = fields.Boolean(string='Has Pool')
    solar_system = fields.Boolean(string='Solar System')
    electricity_meter = fields.Boolean(string='Electricity Meter')
    gas_meter = fields.Boolean(string='Gas Meter')
    water_meter = fields.Boolean(string='Water Meter')
    landline = fields.Boolean(string='Landline')
    internet = fields.Boolean(string='Internet')
    air_condition = fields.Boolean(string='Air Condition')
    cooling_water = fields.Boolean(string='Cooling Water')

    sale_price_per_meter = fields.Float(string='Sale Price / Meter')
    rent_price_per_meter = fields.Float(string='Rent Price / Meter')
    maintenance_price_per_meter = fields.Float(string='Maintenance Price / Meter')
    maintenance_percentage = fields.Float(string='Maintenance Percentage', compute='_compute_maintenance_percentage')
    # payment_terms = fields.Text(string='Payment Terms')

    # Merged Units

    merged_unit = fields.Boolean()
    unit_id = fields.Many2one('real.estate.unit')
    units = fields.One2many('real.estate.unit', 'unit_id', domain=[('unit_status', 'in', ['available', 'in_merge'])])
    merge_button = fields.Boolean()

    # Area
    indoor_gross_area = fields.Float(compute='_compute_gross_areas', store=True)
    indoor_net_area = fields.Float()
    terrace_gross_area = fields.Float(compute='_compute_gross_areas', store=True)
    terrace_net_area = fields.Float()
    outdoor_gross_area = fields.Float(compute='_compute_gross_areas', store=True)
    outdoor_net_area = fields.Float()
    new_total_gross_area = fields.Float(string='New Total Gross Area(Indoor + Terrace)', compute='_compute_new_total_gross_area',
                                        store=True)
    landed_area = fields.Float(string='Landed Area')

    # Financial
    indoor_price_per_month_sqm = fields.Float(string="Indoor Price/Month/SQM")
    outdoor_price_per_month_sqm = fields.Float(string="Outdoor Price/Month/SQM")
    indoor_outdoor_price_per_month_sqm = fields.Float(string="Indoor+Outdoor Price/Month/SQM")
    service_charge_per_sqm = fields.Float(string="Service Charge / SQM")
    marketing_fees_annually_percent = fields.Float(string="Marketing Fees Annually Percent")
    payment_terms = fields.Selection([
        ('months', 'Months'),
        ('years', 'Years')
    ], string="Payment Terms")
    payment_terms_duration = fields.Integer()

    # to sale
    indoor_price_sqm = fields.Float(string="Indoor Price/SQM")
    outdoor_price_sqm = fields.Float(string="Outdoor Price/SQM")
    terrace_price_sqm = fields.Float(string="Terrace Price/SQM")
    basic_unit = fields.Float(string="Basic Unit Price",)
    terrace_total_price = fields.Float(string="Terrace Total Price", compute="_compute_terrace_price", store=True)
    project_id = fields.Many2one('realestate.project', compute="_compute_project_id", store=True)
    building_id = fields.Many2one('real.estate.building', compute="_compute_building_id", store=True, string="Building")
    building_system_code = fields.Char(compute="_compute_building_id", string="Building System Code", store=True)
    building_code = fields.Char(compute="_compute_building_id", string="Building Code", store=True)

    warning_msg = fields.Text('Warning Message')
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    # block_reason = fields.Char()
    reason_id = fields.Many2one('block.reason', string='Block Reason', tracking=True)

    apartment_type_id = fields.Many2one('residential.sub.type', domain=[('type', '=', 'apartment')], string='Apartment Type')
    villa_type_id = fields.Many2one('residential.sub.type', domain=[('type', '=', 'villa')], string='Villa Type')
    villa_row = fields.Char(string='Villa Row')
    loft_type_id = fields.Many2one('residential.sub.type', domain=[('type', '=', 'loft')], string='Loft Type')
    parking_area_config_id = fields.Many2one(
        'parking.area.configuration',
        string='Parking Configuration',
        domain="[('unit_type', '=', unit_type)]",
    )

    premiums_ids = fields.Many2many('premiums.premiums')
    total_premium_percentage = fields.Float(compute="_compute_total_premium_percentage", store=True)
    total_premium_price = fields.Float(compute="_compute_total_premium", store=True)

    # total_price_unit = fields.Float(compute="_compute_total_price_unit", store=True)
    total_price_unit_after_discount = fields.Float(string="Total Price After Discount", readonly=True, tracking=True)
    installment_years_after_discount = fields.Integer(string="Installment Years After Discount", readonly=True, tracking=True)
    down_payment_after_discount = fields.Float(string="Down Payment After Discount", readonly=True, tracking=True)
    has_discount = fields.Boolean(string="Has Discount", readonly=True, default=False)
    effective_price = fields.Float(
        compute='_compute_effective_values',
        store=True,
        string="Effective Price",
    )
    effective_down_payment = fields.Float(
        compute='_compute_effective_values',
        store=True,
        string="Effective Down Payment (%)",
    )
    effective_installment_years = fields.Integer(
        compute='_compute_effective_values',
        store=True,
        string="Effective Installment Years",
    )

    # total_price_unit = fields.Float(compute="_compute_total_price_unit", store=True)
    initial_price_unit = fields.Float(compute="_compute_initial_price_unit", store=True)

    #Installment
    installment_plan_id = fields.Many2one('down.payment.increase',string="Installment Plan", compute='_compute_plan_line', domain=[('unit_type', '=', 'unit_type')])
    installemnt_years = fields.Integer(string="Number of Installment Years", tracking=True, default=7)

    down_payment = fields.Float(string="Down Payment (%)", tracking=True)
    down_payment_date = fields.Date(string="Down Payment Date")
    maintenance_fees = fields.Float(string="Maintenance Fees", compute="_compute_maintenance_fees")

    installment_template_id = fields.Many2one('installment.template', string='Installment Template')
    maintenance_template_id = fields.Many2one('maintenance.template', string='Maintenance Template')

    total_price_unit = fields.Float()
    contracted_selling_price = fields.Float(string="Contracted Selling Price", readonly=True)

    discount_percentage = fields.Float(string="Discount Percentage", tracking=True)
    price_after_discount = fields.Float(string="Price After Discount", compute='_compute_price_after_discount', inverse='_inverse_price_after_discount', store=True, readonly=False, tracking=True)
    maintenance_start_date = fields.Date(string='Maintenance Start Date')

    @api.depends('total_price_unit', 'discount_percentage')
    def _compute_price_after_discount(self):
        for rec in self:
            if rec.total_price_unit:
                rec.price_after_discount = rec.total_price_unit * (1 - rec.discount_percentage / 100.0)
            else:
                rec.price_after_discount = 0.0

    def _inverse_price_after_discount(self):
        for rec in self:
            if rec.total_price_unit:
                rec.discount_percentage = (1 - rec.price_after_discount / rec.total_price_unit) * 100.0
            else:
                rec.discount_percentage = 0.0

    def action_available_for_sale(self):
        for rec in self:
            rec.unit_status = 'available_for_sale'

    @api.depends('indoor_gross_area', 'terrace_gross_area')
    def _compute_new_total_gross_area(self):
        for rec in self:
            rec.new_total_gross_area = rec.indoor_gross_area + rec.terrace_gross_area

    @api.depends('premiums_ids.percentage')
    def _compute_total_premium_percentage(self):
        for rec in self:
            rec.total_premium_percentage = sum(rec.premiums_ids.mapped('percentage'))

    @api.depends('residential_type', 'apartment_type_id', 'apartment_type_id.number_of_slots',
                 'unit_type', 'new_total_gross_area', 'parking_area_config_id', 'parking_area_config_id.area_per_slot')
    def _compute_number_of_slots(self):
        for rec in self:
            if rec.unit_type == 'residential' and rec.residential_type == 'apartment' and rec.apartment_type_id:
                apartment = rec.apartment_type_id
                if apartment.number_of_slots > 0:
                    rec.has_parking = True
                    rec.number_of_slots = apartment.number_of_slots
                else:
                    rec.has_parking = False
                    rec.number_of_slots = 0
            elif rec.unit_type in ['retail', 'office', 'medical', 'entertainment', 'industrial'] and rec.parking_area_config_id:
                area_per_slot = rec.parking_area_config_id.area_per_slot
                if area_per_slot > 0 and rec.new_total_gross_area > 0:
                    rec.number_of_slots = math.floor(rec.new_total_gross_area / area_per_slot)
                    rec.has_parking = True if rec.number_of_slots > 0 else False
                else:
                    rec.has_parking = False
                    rec.number_of_slots = 0
            else:
                rec.has_parking = False
                rec.number_of_slots = 0

    @api.depends('total_premium_percentage', 'basic_unit')
    def _compute_total_premium(self):
        for rec in self:
            rec.total_premium_price = rec.total_premium_percentage * rec.basic_unit

    @api.onchange('total_premium_percentage', 'basic_unit')
    def _compute_total_price_unit(self):
        for rec in self:
            rec.total_price_unit = math.ceil(rec.basic_unit / 100) * 100

    @api.depends('unit_type')
    def _compute_plan_line(self):
        for rec in self:
            if rec.unit_type:
                plan = self.env['down.payment.increase'].search([
                    ('unit_type', '=', rec.unit_type)
                ], limit=1)
                if plan:
                    rec.installment_plan_id = plan
                else:
                    rec.installment_plan_id = False
            else:
                rec.installment_plan_id = False

    @api.depends('has_discount', 'total_price_unit', 'total_price_unit_after_discount',
                 'down_payment', 'down_payment_after_discount',
                 'installemnt_years', 'installment_years_after_discount')
    def _compute_effective_values(self):
        for rec in self:
            if rec.has_discount:
                rec.effective_price = rec.total_price_unit_after_discount
                rec.effective_down_payment = rec.down_payment_after_discount
                rec.effective_installment_years = rec.installment_years_after_discount
            else:
                rec.effective_price = rec.total_price_unit
                rec.effective_down_payment = rec.down_payment
                rec.effective_installment_years = rec.installemnt_years

    @api.depends('terrace_gross_area', 'terrace_price_sqm')
    def _compute_terrace_price(self):
        for rec in self:
            rec.terrace_total_price = rec.terrace_gross_area * rec.terrace_price_sqm

    @api.depends('parent_source_id')
    def _compute_building_id(self):
        for rec in self:
            source = rec.parent_source_id
            rec.building_id = False

            while source:
                if source._name == 'real.estate.building':
                    rec.building_id = source.id
                    rec.building_code = source.abbreviation
                    rec.building_system_code = source.system_code
                    break
                if hasattr(source, 'parent_source_id'):
                    source = source.parent_source_id
                else:
                    break

    @api.depends('maintenance_template_id')
    def _compute_maintenance_percentage(self):
        for rec in self:
            template = rec.maintenance_template_id
            if template:
                rec.maintenance_percentage = template.percentage
            else:
                rec.maintenance_percentage = 0.0


    @api.depends('maintenance_percentage','price_after_discount')
    def _compute_maintenance_fees(self):
        for unit in self:
            unit.maintenance_fees = unit.price_after_discount * unit.maintenance_percentage

    def _get_installments_grouped_by_date(self):
        """Build payment plan schedule on the fly with maintenance placed at the end."""
        self.ensure_one()

        # 1. Base Price: Use price_after_discount if available, otherwise total_price_unit
        total = self.price_after_discount if self.price_after_discount > 0 else (self.total_price_unit or 0.0)
        today = fields.Date.context_today(self)
        installments_start = (today + relativedelta(months=3))
        maint_start = self.maintenance_start_date or self.delivery_date or installments_start

        unit_lines = []
        maintenance_lines = []

        if self.env.context.get('override_unit_templates'):
            inst_id = self.env.context.get('force_installment_template_id')
            maint_id = self.env.context.get('force_maintenance_template_id')
            template = self.env['installment.template'].browse(inst_id) if inst_id else False
            maintenance_template = self.env['maintenance.template'].browse(maint_id) if maint_id else False
            total = self.env.context.get('force_total_price', total)
        else:
            template = self.installment_template_id
            maintenance_template = self.maintenance_template_id

        # 2. PROCESS UNIT INSTALLMENT TEMPLATE
        if template:
            # Down Payment 1 (Reservation Percentage)
            if template.reservation_percentage:
                pct = template.reservation_percentage / 100.0 if template.reservation_percentage > 1.0 else template.reservation_percentage
                unit_lines.append({
                    'name': 'Down Payment 1',
                    'date':  today,
                    'amount': total * pct,
                })

            # Down Payment 2 (Contracting Percentage)
            if template.contracting_percentage:
                pct = template.contracting_percentage / 100.0 if template.contracting_percentage > 1.0 else template.contracting_percentage
                dp2_date = (today + relativedelta(months=3))
                installments_start = (dp2_date + relativedelta(months=3))
                unit_lines.append({
                    'name': 'Down Payment 2',
                    'date': dp2_date,
                    'amount': total * pct,
                })

            # Regular Unit Installments
            for amount, duration, step in (
                    (template.monthly_installment_amount, template.monthly_installment_duration, 1),
                    (template.quarterly_installment_amount, template.quarterly_installment_duration, 3),
                    (template.semi_annual_installment_amount, template.semi_annual_installment_duration, 6),
                    (template.annual_installment_amount, template.annual_installment_duration, 12),
            ):
                if amount and duration:
                    pct = amount / 100.0 if amount > 1.0 else amount
                    line_amount = (pct * total) / float(duration)
                    date_payment = installments_start
                    for _seq in range(duration):
                        unit_lines.append({
                            'name': 'Installment',
                            'date': date_payment,
                            'amount': line_amount,
                        })
                        date_payment = date_payment + relativedelta(months=step)


        # 3. PROCESS MAINTENANCE TEMPLATE
        if maintenance_template:
            pct_val = maintenance_template.percentage or self.maintenance_percentage or 0.0
            maint_pct = pct_val / 100.0 if pct_val > 1.0 else pct_val
            total_maintenance_amount = total * maint_pct

            has_breakdown = False
            for amount, duration, step in (
                    (maintenance_template.monthly_installment_amount, maintenance_template.monthly_installment_duration,
                     1),
                    (maintenance_template.quarterly_installment_amount,
                     maintenance_template.quarterly_installment_duration, 3),
                    (maintenance_template.semi_annual_installment_amount,
                     maintenance_template.semi_annual_installment_duration, 6),
                    (maintenance_template.annual_installment_amount, maintenance_template.annual_installment_duration,
                     12),
            ):
                if amount and duration:
                    has_breakdown = True
                    multiplier = (amount / 100.0) if amount > 1.0 else amount
                    line_maint_amount = (total_maintenance_amount * multiplier) / float(duration)

                    date_maint = maint_start
                    for _seq in range(duration):
                        maintenance_lines.append({
                            'date': date_maint,
                            'amount': line_maint_amount,
                        })
                        date_maint = date_maint + relativedelta(months=step)

            if not has_breakdown and total_maintenance_amount:
                maintenance_lines.append({
                    'date': maint_start,
                    'amount': total_maintenance_amount,
                })

        # 4. GROUP UNIT LINES BY DATE
        by_date_unit = defaultdict(list)
        for line in unit_lines:
            by_date_unit[line['date']].append(line)

        sorted_unit_dates = sorted(by_date_unit.keys(), key=lambda d: d or date.min)

        result = []
        dp_count = 1
        inst_count = 1

        for date_val in sorted_unit_dates:
            u_lines = by_date_unit[date_val]
            unit_amount = sum(l['amount'] for l in u_lines)
            names = [l['name'] for l in u_lines]
            if 'Down Payment 2' in names and len(names) == 1:
                label = 'Down Payment 2'
            elif 'Down Payment 1' in names or 'Down Payment' in names:
                label = f'Down Payment {dp_count}'
                dp_count += 1
            else:
                label = f'Installment {inst_count}'
                inst_count += 1

            percentage = round((unit_amount / total) * 100, 2) if total > 0 else 0.0

            result.append({
                'label': label,
                'date': date_val,
                'percentage': percentage,
                'unit_amount': unit_amount,
                'maintenance_amount': 0.0,
            })

        # 5. APPLY ROUNDING & RECOMPUTE PERCENTAGES
        if hasattr(self, 'apply_installment_rounding_dicts'):
            result = self.apply_installment_rounding_dicts(result, amount_field='unit_amount')

            for row in result:
                if total > 0:
                    row['percentage'] = round((row['unit_amount'] / total) * 100, 2)

        # 6. APPEND MAINTENANCE LINES AT THE VERY END
        maint_count = 1
        maintenance_lines.sort(key=lambda x: x['date'] or date.min)
        for m_line in maintenance_lines:
            label = 'Maintenance Installment' if len(
                maintenance_lines) == 1 else f'Maintenance Installment {maint_count}'
            maint_count += 1

            result.append({
                'label': label,
                'date': m_line['date'],
                'percentage': 0.0,
                'unit_amount': 0.0,
                'maintenance_amount': m_line['amount'],
            })

        return result

    def action_print_payment_plan(self):
        self.ensure_one()
        if not self.installment_template_id and not self.maintenance_template_id:
            raise ValidationError(_("Please select an installment or maintenance template first."))

        return self.env.ref('arkzayed_18_realestate_development.unit_payment_plan_report').with_context(
            active_model=self._name,
            active_id=self.id
        ).report_action(self)

    @api.onchange('installment_plan_id', 'installemnt_years')
    def _down_payment(self):
        for rec in self:
            if rec.installment_plan_id and rec.installemnt_years:
                installment_price_line = rec.installment_plan_id.price_plan_ids.filtered(lambda l: l.year_no == rec.installemnt_years)
                if installment_price_line.year_no:
                    rec.down_payment = installment_price_line.down_payment / 100
                else:
                    rec.down_payment = False
            else:
                rec.down_payment = False

    @api.onchange('specially_booked')
    def specially_booked_onchange(self):
        if self.specially_booked:
            self.unit_status = 'specially_booked'

    @api.onchange('indoor_price_sqm', 'building_id', 'unit_type')
    def _onchange_outdoor_price_sqm(self):
        if self.indoor_price_sqm and self.building_id and self.unit_type:
            config = self.env['real.estate.unit.type.configuration'].search([
                ('building_id', '=', self.building_id.id),
                ('unit_type', '=', self.unit_type)
            ], limit=1)

            if config:
                self.outdoor_price_sqm = self.indoor_price_sqm * config.outdoor_price_percentage

    def merge(self):
        for rec in self:
            rec.merge_button = True
            if len(rec.units) <= 1:
                raise ValidationError("You must select more than one unit to merge.")

            if any(unit.unit_status == 'in_merge' for unit in rec.units):
                merged_units = rec.units.filtered(lambda u: u.unit_status == 'in_merge')
                merged_unit_names = ', '.join(merged_units.mapped('name'))
                raise ValidationError(
                    "The following unit(s) are already merged: %s. Please select units that are available." % merged_unit_names)

            for unit in rec.units:
                unit.unit_status = 'in_merge'

    def unmerge(self):
        for rec in self:
            for unit in rec.units:
                unit.unit_status = 'available'
                rec.active = False
                rec.merge_button = False

    outdoor_area = fields.Char(string='Outdoor Area')

    # Parking
    parking_number = fields.Integer(string='Parking Number')
    parking_code = fields.Char(string='Parking Code')
    parking_name = fields.Char(string='Parking Name')
    parent_source_id = fields.Reference([
                                         ('floor', 'Floor'),
                                         ('zone', 'Zone'),
                                         ('real.estate.building', 'Building'),
                                         ('realestate.project', 'Project')], string='Parent reference')
    unit_location = fields.Char(compute='compute_unit_location')

    counter_ids = fields.One2many(comodel_name="realestate.counter", inverse_name="unit_id")
    gas_counter_ids = fields.One2many(comodel_name="realestate.gas.counter", inverse_name="unit_id")
    water_counter_ids = fields.One2many(comodel_name="realestate.water.counter", inverse_name="unit_id")
    landline_counter_ids = fields.One2many(comodel_name="realestate.landline.counter", inverse_name="unit_id")
    internet_counter_ids = fields.One2many(comodel_name="realestate.internet", inverse_name="unit_id")

    is_floors = fields.Boolean('Floors')
    floors_count = fields.Integer()
    is_yard = fields.Boolean('Yard')
    yard_area = fields.Float('Yard Area')
    floor_id = fields.Many2one('floor', compute="_compute_floor_id", store=True, readonly=True)
    @api.depends('parent_source_id')
    def _compute_floor_id(self):
        for rec in self:
            parent = rec.parent_source_id
            rec.floor_id = False
            if parent and parent._name == 'floor':
                rec.floor_id = parent.id
            else:
                rec.floor_id = False

    @api.model
    def get_unit_stats(self):
        Unit = self.env['real.estate.unit']
        avail_unit = Unit.sudo().search_count([('unit_status', '=', 'available')])
        reserved_unit = Unit.sudo().search_count([('unit_status', '=', 'reserved')])
        lease_unit = Unit.sudo().search_count([('unit_status', '=', 'in_lease')])
        sold_unit = Unit.sudo().search_count([('unit_status', '=', 'sold')])
        blocked_unit = Unit.sudo().search_count([('unit_status', '=', 'blocked')])
        total_unit = Unit.sudo().search_count([])

        currency_symbol = self.env['res.currency'].search([]).mapped('symbol')


        # Property Type
        residential_unit = Unit.sudo().search_count([('unit_type', '=', 'residential')])
        parking_unit = Unit.sudo().search_count([('unit_type', '=', 'parking')])
        industrial_unit = Unit.sudo().search_count([('unit_type', '=', 'industrial')])
        medical_unit = Unit.sudo().search_count([('unit_type', '=', 'medical')])
        office_unit = Unit.sudo().search_count([('unit_type', '=', 'office')])
        entertainment_unit = Unit.sudo().search_count([('unit_type', '=', 'entertainment')])
        retail_unit = Unit.sudo().search_count([('unit_type', '=', 'retail')])

        unit_type = [
            ['Residential', 'Parking', 'Industrial', 'Medical', 'Office', 'Entertainment', 'Retail'],
            [residential_unit, parking_unit, industrial_unit, medical_unit, office_unit, entertainment_unit, retail_unit]
        ]
        unit_stage = [
            ['Available Units', 'Sold Properties', 'Reserved Properties', 'On Lease', 'Blocked'],
            [avail_unit, sold_unit, reserved_unit, lease_unit, blocked_unit]
        ]

        data = {
            'avail_unit': avail_unit,
            'reserved_unit': reserved_unit,
            'lease_unit': lease_unit,
            'sold_unit': sold_unit,
            'blocked_unit': blocked_unit,
            'total_unit': total_unit,
            'unit_type': unit_type,
            'unit_stage': unit_stage,
            # 'due_paid_amount': self.due_paid_amount(),
        }
        return data

    def compute_unit_location(self):
        for rec in self:
            name = ''
            if rec.name:
                name += rec.name
            if rec.parent_source_id and rec.parent_source_id.location:
                name += ',' + rec.parent_source_id.location
            rec.unit_location = name

    @api.onchange('name')
    def _change_unit_abbreviation(self):
        for rec in self:
            if rec.name:
                rec.abbreviation = rec.name

    def action_unit_blocked(self):

        #check if the user has the permission to block the unit
        if not self.env.user.has_group('isky_18_realestate_developer_unit_inventory.group_block_unit'):
            raise ValidationError(_("You do not have the permission to block this unit."))

        return {'type': 'ir.actions.act_window',
                'name': _('Block Unit'),
                'res_model': 'blocked.unit.reason',
                'target': 'new',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'default_unit_id': self.id}, }

    def action_unit_onhold(self):
        self.ensure_one()
        if self.unit_status in ['available', 'available_for_sale']:
            self.unit_status = 'on_hold_ma'

    def action_get_installment_report(self):
        for rec in self:
            if not rec.down_payment_date:
                raise ValidationError(_("Please set Down Payment Date before generating the payment plan report."))

        return {
            'type': 'ir.actions.act_url',
            'url': f"/unit/excel/report/{self.id}",
            'target': 'new'
        }

    def action_unit_sold(self):
        for rec in self:
            rec.unit_status = 'sold'

    def action_unit_lease(self):
        for rec in self:
            rec.unit_status = 'in_lease'

    @api.depends('indoor_gross_area', 'outdoor_gross_area','terrace_gross_area')
    def _compute_total_gross_area(self):
        for rec in self:
            rec.unit_area = rec.indoor_gross_area + rec.outdoor_gross_area + rec.terrace_gross_area

    @api.depends('indoor_net_area', 'outdoor_net_area','terrace_net_area')
    def _compute_total_net_area(self):
        for rec in self:
            rec.net_area = rec.indoor_net_area + rec.outdoor_net_area + rec.terrace_net_area

    @api.depends('indoor_net_area', 'terrace_net_area', 'outdoor_net_area', 'building_id', 'unit_type', 'has_garden')
    def _compute_gross_areas(self):
        building_ids = self.mapped('building_id').ids
        unit_types = list(set(self.mapped('unit_type')))

        configs = self.env['real.estate.unit.type.configuration'].search([
            ('building_id', 'in', building_ids),
            ('unit_type', 'in', unit_types)
        ])

        config_dict = {
            (config.building_id.id, config.unit_type): config
            for config in configs
        }

        for rec in self:
            #default values if not provided
            indoor_r = terrace_r = outdoor_r = 1.0
            if rec.building_id and rec.unit_type:
                config = config_dict.get((rec.building_id.id, rec.unit_type))
                if config:
                    indoor_r = config.indoor_gross_ratio
                    terrace_r = config.terrace_gross_ratio
                    outdoor_r = (
                        config.garden_gross_ratio
                        if rec.unit_type == 'residential' and rec.has_garden
                        else config.outdoor_gross_ratio
                    )
                    if not rec.has_outdoor and not rec.has_garden:
                        outdoor_r = 0

            rec.indoor_gross_area = rec.indoor_net_area * indoor_r
            rec.terrace_gross_area = rec.terrace_net_area * terrace_r
            rec.outdoor_gross_area = rec.outdoor_net_area * outdoor_r

    @api.onchange('indoor_gross_area', 'indoor_price_sqm', 'outdoor_gross_area', 'outdoor_price_sqm','terrace_total_price')
    def _compute_basic_unit(self):
        for rec in self:
            indoor_total = rec.indoor_gross_area * rec.indoor_price_sqm
            outdoor_total = rec.outdoor_gross_area * rec.outdoor_price_sqm
            rec.basic_unit = indoor_total + outdoor_total + rec.terrace_total_price

    def action_rollback(self):
        for rec in self:
            rec.unit_status = 'available'

    @api.model_create_multi
    def create(self, vals_list):
        records = super(RealEstateUnit, self).create(vals_list)

        for rec in records:
            if rec.building_id and rec.unit_type:
                config = self.env['real.estate.unit.type.configuration'].search([
                    ('building_id', '=', rec.building_id.id),
                    ('unit_type', '=', rec.unit_type),
                ], limit=1)
                if config:
                    price_vals = {}
                    if config.indoor_price_sqm and not rec.indoor_price_sqm:
                        price_vals['indoor_price_sqm'] = config.indoor_price_sqm
                    if config.terrace_price_sqm and not rec.terrace_price_sqm:
                        price_vals['terrace_price_sqm'] = config.terrace_price_sqm
                    if price_vals:
                        rec.write(price_vals)

        # Trigger parent area recomputation for new units
        self._trigger_parent_area_recomputation(records)

        return records

    def write(self, vals):
        result = super(RealEstateUnit, self).write(vals)

        # Trigger parent area recomputation if area fields or parent changed
        if any(field in vals for field in ['unit_area', 'new_total_gross_area', 'parent_source_id',
                                           'indoor_gross_area', 'terrace_gross_area']):
            self._trigger_parent_area_recomputation(self)

        return result

    def _trigger_parent_area_recomputation(self, records):
        """Helper method to trigger area recomputation on parent models (Floor and FloorArea)"""
        floors_to_update = set()
        floor_areas_to_update = set()

        for rec in records:
            if rec.parent_source_id:
                if rec.parent_source_id._name == 'floor':
                    floors_to_update.add(rec.parent_source_id.id)
                elif rec.parent_source_id._name == 'floor.area':
                    floor_areas_to_update.add(rec.parent_source_id.id)

        if floors_to_update:
            floors = self.env['floor'].browse(list(floors_to_update))
            floors._compute_aggregate_areas()

        if floor_areas_to_update:
            floor_areas = self.env['floor.area'].browse(list(floor_areas_to_update))
            floor_areas._compute_aggregate_areas()

    def request_discount_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Request Discount',
            'res_model': 'discount.request.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_unit_id': self.id,
                'default_down_payment': self.down_payment,
                'default_total_price_unit': self.total_price_unit,
                'default_installment_years': self.installemnt_years,
            },
        }

    def _add_document_to_merger(self, merger, document_data, document_name):
        if not document_data:
            return

        try:
            raw_data = base64.b64decode(document_data)
            stream = io.BytesIO(raw_data)

            if raw_data.startswith(b'%PDF-'):
                try:
                    pdf_stream = io.BytesIO(raw_data)
                    merger.append(pdf_stream)
                    return
                except Exception:
                    pass

            try:
                stream.seek(0)
                image = Image.open(stream)
                
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')
                
                img_pdf_stream = io.BytesIO()
                image.save(img_pdf_stream, 'PDF', resolution=100.0)
                img_pdf_stream.seek(0)
                merger.append(img_pdf_stream)
            except Exception as img_e:
                raise ValidationError(_("Could not process '%s' as PDF or Image. Error: %s") % (document_name, str(img_e)))

        except Exception as e:
            if isinstance(e, ValidationError):
                raise e
            raise ValidationError(_("Error processing '%s': %s") % (document_name, str(e)))

    def action_print_combined_documents(self):
        """Combine building plan (PDF), unit plan (PNG), and payment plan (PNG) into one PDF"""
        self.ensure_one()

        # Check if all required documents exist
        if not self.building_id.building_plan:
            raise ValidationError(_("Building plan is missing for building: %s") % self.building_id.name)
        if not self.unit_plan:
            raise ValidationError(_("Unit plan is missing"))
        if not self.payment_plan:
            raise ValidationError(_("Payment plan is missing"))

        try:
            # Initialize PDF merger
            merger = PdfWriter()

            self._add_document_to_merger(merger, self.building_id.building_plan, _("Building Plan"))

            self._add_document_to_merger(merger, self.unit_plan, _("Unit Plan"))

            self._add_document_to_merger(merger, self.payment_plan, _("Payment Plan"))

            # 4. Write merged PDF to output stream
            output_stream = io.BytesIO()
            merger.write(output_stream)
            merger.close()
            output_stream.seek(0)

            # 5. Create attachment
            combined_pdf = base64.b64encode(output_stream.read())
            filename = f"{self.system_code}_combined_documents.pdf"

            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': combined_pdf,
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })

            # 6. Return action to download/view the PDF
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }

        except Exception as e:
            raise ValidationError(_("Error combining documents: %s") % str(e))

    def action_print_unit_report(self):
        """Print unit plan with architectural specifications table"""
        self.ensure_one()

        if not self.unit_plan:
            raise ValidationError(_("Unit plan is missing. Please upload a unit plan before printing the report."))

        return self.env.ref('arkzayed_18_realestate_development.action_report_unit_plan').report_action(self)

    def _get_unit_documents_images(self):
        self.ensure_one()
        documents = []

        if self.residential_type == 'villa':
            for field_name in ('unit_plan', 'unit_plan1', 'unit_plan2',
                               'floor_plan', 'floor_plan1', 'floor_plan2',
                               'payment_plan'):
                value = self[field_name]
                if value:
                    documents.append(value)

        elif self.residential_type in ('apartment', 'loft'):
            if self.building_id.building_plan:
                documents.append(self.building_id.building_plan)

            for field_name in ('unit_plan', 'unit_plan1', 'unit_plan2',
                               'floor_plan', 'floor_plan1', 'floor_plan2',
                               'payment_plan'):
                value = self[field_name]
                if value:
                    documents.append(value)

        return documents

    def _get_unit_offer_plan_images(self):
        self.ensure_one()
        return [img for img in (self.unit_plan, self.unit_plan1) if img]

    def action_unit_documents(self):
        self.ensure_one()

        if not self._get_unit_documents_images():
            raise ValidationError(_("No documents are available for this unit yet."))

        if self.env.context.get('with_download'):
            return self.env.ref('arkzayed_18_realestate_development.action_report_unit_documents').report_action(self)

        else:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/report/pdf/arkzayed_18_realestate_development.report_unit_documents_document/{self.id}',
                'target': 'new',
            }

    def action_print_unit_offer_plan(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Print Unit Offer Plan'),
                'res_model': 'unit.offer.plan.wizard', 'view_mode': 'form', 'target': 'new',
                'context': {'default_unit_id': self.id}}

    def _get_phase_installment_templates(self):
        self.ensure_one()
        return self.env['installment.template'].search([])

    def _get_offer_plan_templates(self, chosen_ids=None):
        self.ensure_one()
        templates = self._get_phase_installment_templates()
        if chosen_ids:
            chosen = self.env['installment.template'].browse(chosen_ids).exists()
            return chosen.sorted(lambda t: chosen_ids.index(t.id))
        return templates

    def _get_maintenance_templates_for_report(self):
        self.ensure_one()
        return self.env['maintenance.template'].search([
            ('default_for_reservation', '=', True)
        ])


    _SCHEDULE_PERIODS = [
        ('monthly_installment', 1, _("Monthly")),
        ('quarterly_installment', 3, _("Quarterly")),
        ('semi_annual_installment', 6, _("Semi Annual")),
        ('annual_installment', 12, _("Annual")),
    ]

    def _build_payment_schedule_rows(self, template, start_date, qualifier, one_time_charges):

        self.ensure_one()
        if not template or not start_date:
            return []

        base_price = self.price_after_discount or 0
        rows = []

        for field_prefix, month_step, frequency_label in self._SCHEDULE_PERIODS:
            multiplier = getattr(template, f'{field_prefix}_amount')
            if multiplier <= 0:
                continue
            duration = getattr(template, f'{field_prefix}_duration') or 1
            installment_amount = (multiplier * base_price) / float(duration)
            percentage = round((installment_amount / base_price * 100), 2) if base_price > 0 else 0
            label = f"{frequency_label} {qualifier}"
            date_payment = start_date

            for _i in range(duration):
                rows.append({
                    'label': label,
                    'date': date_payment,
                    'amount': installment_amount,
                    'percentage': percentage,
                })
                date_payment = add_months(date_payment, month_step)

        for amount, label in one_time_charges:
            percentage = round((amount / base_price * 100), 2) if base_price > 0 else 0
            rows.append({
                'label': label,
                'date': start_date,
                'amount': amount,
                'percentage': percentage,
            })

        rows.sort(key=lambda r: r['date'] or date.min)
        for idx, row in enumerate(rows, 1):
            row['serial'] = idx

        return rows

    def _get_unit_offer_plan_schedule_for_template(self, template):
        self.ensure_one()
        base_price = self.price_after_discount or 0
        today = fields.Date.context_today(self)

        dp_pct = (template.reservation_percentage or 0) if template else 0
        dp2_pct = (template.contracting_percentage or 0) if template else 0   # field label: "Down Payment 2 Percentage"
        dp2_date = add_months(today, 3)
        installments_start = add_months(dp2_date if dp2_pct > 0 else today, 3)

        rows = self._build_payment_schedule_rows(template, installments_start, _("Installment"), [])

        if dp_pct > 0:
            rows.append({'label': _("Down Payment"), 'date': today,
                         'amount': (dp_pct / 100.0) * base_price, 'percentage': dp_pct})
        if dp2_pct > 0:
            rows.append({'label': _("Down Payment 2"), 'date': dp2_date,
                         'amount': (dp2_pct / 100.0) * base_price, 'percentage': dp2_pct})

        # the unit's own maintenance template, or the one flagged "Default For Reservation" when the unit has none
        maintenance_template = self.maintenance_template_id or self.env['maintenance.template'].search(
            [('default_for_reservation', '=', True)], limit=1)
        maintenance_rate = maintenance_template.percentage if maintenance_template else 0.0
        if maintenance_template and maintenance_rate > 0:
            maintenance_amount = self.total_price_unit * maintenance_rate
            maintenance_pct = round((maintenance_amount / base_price * 100), 2) if base_price > 0 else 0
            rows.append({
                'label': _("Maintenance Installment"),
                # the unit's own Maintenance Start Date when it is filled, otherwise 3 years after Down Payment 1 (print day)
                'date': self.maintenance_start_date or add_months(today, 36),
                'amount': maintenance_amount,
                'percentage': maintenance_pct,
            })

        rows.sort(key=lambda r: r['date'] or date.min)
        rows = self.apply_installment_rounding_dicts(rows, amount_field='amount')
        for idx, row in enumerate(rows, 1):
            row['serial'] = idx
            if base_price > 0:
                row['percentage'] = round((row['amount'] / base_price * 100), 2)

        return rows

    def _get_maintenance_schedule_for_template(self, template):
        self.ensure_one()
        base_price = self.price_after_discount or 0
        one_time_charges = [(template.percentage / 100.0 * base_price, _("Maintenance Fee"))] if template else []

        return self._build_payment_schedule_rows(
            template, self.delivery_date, _("Maintenance"), one_time_charges
        )

