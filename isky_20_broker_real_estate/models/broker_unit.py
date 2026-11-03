from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BrokerUnit(models.Model):
    _name = 'broker.unit'
    _description = "Real Estate Unit"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(copy=False)
    sequence_number = fields.Char(readonly=True, copy=False)
    unit_number = fields.Char()
    unit_code = fields.Char()
    tcr = fields.Char(string="TCR", copy=False)
    active = fields.Boolean(default=True)
    unit_sale_type = fields.Selection([('primary', "Primary"), ('resale', "Resale")])

    customer_id = fields.Many2one('res.partner')
    phone = fields.Char(related='customer_id.phone')

    unit_purpose = fields.Selection([
        ('to_sale', "To Sale"),
        ('to_rent', "To Rent"),
        ('sale_or_rent', "Sale Or Rent"),
    ], required=True)
    unit_status = fields.Selection([
        ('available', "Available"),
        ('sold', "Sold"),
        ('rented', "Rented"),
    ], default='available')
    unit_type = fields.Selection([
        ('land', "Land"),
        ('retail', "Retail"),
        ('office', "Office"),
        ('clinic', "Clinic"),
        ('residential', "Residential"),
        ('entertainment', "Entertainment"),
        ('industrial', "Industrial"),
        ('parking', "Parking"),
        ('storage', "Storage"),
        ('public_area', "Public Area"),
    ])
    retail_type = fields.Selection([
        ('bank', "Bank"), ('f_and_b', "F&B"), ('fashion_retail', "Fashion Retail"),
        ('beauty_cosmetics', "Beauty and Cosmetics"), ('supermarket', "Supermarket"),
        ('hypermarket', "Hypermarket"), ('kiosk', "Kiosk"), ('other', "Other"),
    ])
    office_type = fields.Selection([('co_working', "Co-working"), ('private_office', "Private Office")])
    residential_type = fields.Selection([
        ('apartment', "Apartment"), ('standalone_villa', "Stand-alone Villa"),
        ('twin_villa', "Twin Villa"), ('town_house', "Town House"), ('duplex', "Duplex"),
        ('chalet', "Chalet"), ('cabin', "Cabin"), ('studio', "Studio"), ('loft', "Loft"),
    ])
    entertainment_type = fields.Selection([
        ('arcade_zone', "Arcade Zone"), ('gym', "Gym"), ('bowling_center', "Bowling Center"), ('other', "Other"),
    ])
    industrial_type = fields.Selection([('factory', "Factory"), ('warehouse', "Warehouse")])
    parking_type = fields.Selection([('indoor_parking', "Indoor Parking"), ('outdoor_parking', "Outdoor Parking")])
    public_area_type = fields.Selection([
        ('landscape', "Landscape"), ('bathroom', "Bathroom"), ('corridors', "Corridors"),
        ('meeting_room', "Meeting Room"), ('admin_office', "Admin Office"),
    ])

    finishing_type = fields.Selection([
        ('finished', "Finished"), ('semi_finished', "Semi-Finished"), ('core_shell', "Core and Shell"),
    ])
    furnished = fields.Boolean()
    heating_source = fields.Selection([
        ('electricity', "Electricity"), ('wood', "Wood"), ('pellets', "Pellets"),
        ('oil', "Oil"), ('gas', "Gas"), ('district_heating', "District Heating"),
    ])
    number_of_rooms = fields.Integer()
    number_of_bathrooms = fields.Integer()
    garden_view = fields.Boolean()
    pool_view = fields.Boolean()
    city_view = fields.Boolean()
    sea_view = fields.Boolean()
    has_garden = fields.Boolean()
    garden_area = fields.Float()
    has_roof = fields.Boolean()
    roof_area = fields.Float()
    has_parking = fields.Boolean()
    number_of_parking_slots = fields.Integer()
    has_balcony = fields.Boolean()
    number_of_balconies = fields.Integer()
    has_pool = fields.Boolean()
    pool_area = fields.Float()
    is_floors = fields.Boolean(string="Multiple Floors")
    floors_count = fields.Integer()
    is_yard = fields.Boolean()
    yard_area = fields.Float()
    built_up_area = fields.Float(string="BUA")

    indoor_gross_area = fields.Float()
    indoor_net_area = fields.Float()
    outdoor_gross_area = fields.Float()
    outdoor_net_area = fields.Float()
    unit_area = fields.Float(string="Gross Total Area", compute='_compute_total_area', store=True)
    net_area = fields.Float(string="Net Total Area", compute='_compute_total_area', store=True)

    sale_price = fields.Monetary()
    sale_maintenance_price = fields.Monetary()
    down_payment_percentage = fields.Float()
    rent_price = fields.Monetary()
    rent_maintenance_price = fields.Monetary()
    rent_period = fields.Selection([('monthly', "Monthly"), ('quarterly', "Quarterly"), ('yearly', "Yearly")])
    maintenance_period = fields.Selection([('monthly', "Monthly"), ('quarterly', "Quarterly"), ('yearly', "Yearly")])
    sale_price_per_meter = fields.Monetary()
    rent_price_per_meter = fields.Monetary()
    maintenance_price_per_meter = fields.Monetary()
    maintenance_percentage = fields.Float()
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    project_id = fields.Many2one('developer.project', string="Project")
    developer_id = fields.Many2one(related='project_id.developer_id')
    sale_phase_id = fields.Many2one(
        'project.sale.phase', string="Sale Phase",
        domain="[('project_id', '=', project_id)]")
    country_id = fields.Many2one(related='project_id.country_id', readonly=False)
    governorate_id = fields.Many2one(related='project_id.governorate_id', readonly=False)
    city_id = fields.Many2one(related='project_id.city_id', readonly=False)
    neighborhood_id = fields.Many2one(related='project_id.neighborhood_id', readonly=False)
    location_url = fields.Char()
    latitude = fields.Float()
    longitude = fields.Float()

    seller_sales_person = fields.Many2one('res.users', default=lambda self: self.env.user, index=True)
    seller_team_leader = fields.Many2one('res.users')
    seller_sales_manager = fields.Many2one('res.users')
    seller_sales_director = fields.Many2one('res.users')
    seller_purpose_sale_price = fields.Monetary()
    seller_purpose_rent_price = fields.Monetary()
    seller_client_id = fields.Many2one('res.partner', domain="[('is_resale_seller', '=', True)]")
    seller_client_phone = fields.Char(string="Seller Phone", related='seller_client_id.phone')
    seller_client_extra_phone = fields.Char(string="Seller Extra Phone", related='seller_client_id.phone1')

    counter_ids = fields.One2many('broker.unit.counter', 'unit_id')
    unit_image = fields.Binary()
    unit_attachment_image_ids = fields.Many2many('ir.attachment')

    @api.depends('indoor_gross_area', 'outdoor_gross_area', 'indoor_net_area', 'outdoor_net_area')
    def _compute_total_area(self):
        for unit in self:
            unit.unit_area = unit.indoor_gross_area + unit.outdoor_gross_area
            unit.net_area = unit.indoor_net_area + unit.outdoor_net_area

    @api.onchange('seller_sales_person')
    def _onchange_seller_sales_person(self):
        for unit in self:
            team = self.env['crm.team'].search([('member_ids', 'in', unit.seller_sales_person.id)], limit=1)
            unit.seller_team_leader = team.user_id
            unit.seller_sales_manager = team.sales_manager_id
            unit.seller_sales_director = team.director_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sequence_number'):
                sequence_code = 'isky_20_broker_real_estate.unit.resale' if vals.get('unit_sale_type') == 'resale' \
                    else 'isky_20_broker_real_estate.unit.primary'
                vals['sequence_number'] = self.env['ir.sequence'].next_by_code(sequence_code)
                if vals.get('sequence_number') and not vals.get('name'):
                    vals['name'] = vals['sequence_number']
        return super().create(vals_list)

    @api.constrains('unit_purpose', 'sale_price', 'rent_price')
    def _check_price_required(self):
        for unit in self:
            if unit.unit_purpose in ('to_sale', 'sale_or_rent') and unit.sale_price <= 0:
                raise ValidationError(self.env._("Sale price is required for this unit."))
            if unit.unit_purpose in ('to_rent', 'sale_or_rent') and unit.rent_price <= 0:
                raise ValidationError(self.env._("Rent price is required for this unit."))

    @api.constrains('project_id', 'country_id', 'governorate_id', 'city_id', 'neighborhood_id')
    def _check_location_required(self):
        for unit in self:
            if unit.project_id:
                continue
            if not (unit.country_id and unit.governorate_id and unit.city_id and unit.neighborhood_id):
                raise ValidationError(self.env._(
                    "Country, governorate, city, and neighborhood are required when the unit is not linked to a project."
                ))

    def action_rollback_to_available(self):
        self.unit_status = 'available'
