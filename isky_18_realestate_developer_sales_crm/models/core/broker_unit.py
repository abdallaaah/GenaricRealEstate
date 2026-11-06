from email.policy import default

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import requests
import urllib.parse
from bs4 import BeautifulSoup
import re


class BrokerUnit(models.Model):
    _name = 'broker.unit'
    _description = 'Real Estate Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'website.published.mixin']

    @api.model
    def _selection_parent_model(self):
        model_names = ['realestate.project', 'zone', 'cluster', 'real.estate.building', 'floor', 'floor.area']
        domain = ['|'] * (len(model_names) - 1)  # Create the appropriate number of OR conditions
        domain += [('name', 'ilike', name) for name in model_names]
        return [(model.model, model.display_name) for model in self.env['ir.model'].sudo().search(domain)]

    name = fields.Char(copy=False)
    # abbreviation = fields.Char()
    unit_number = fields.Char()
    unit_code = fields.Char()
    unit_area = fields.Float(string='Gross Total Area', compute='_compute_total_gross_area')
    unit_plan = fields.Binary()
    # analytic_account_id = fields.Many2one(comodel_name="account.analytic.account")
    customer_id = fields.Many2one('res.partner')
    phone = fields.Char(related="customer_id.phone")
    mobile = fields.Char(related="customer_id.mobile")
    unit_phase = fields.Char(string='Unit Phase')
    sale_phase = fields.Many2one('project.sale.phase', string='Sale Phase', domain="[('id', 'in', all_sale_phases_ids)]")
    all_sale_phases_ids = fields.Many2many('project.sale.phase', compute='_compute_sale_phases')
    unit_purpose = fields.Selection([
        ('to_sale', 'To Sale'),
        ('to_rent', 'To Rent'),
        ('sale_or_rent', 'Sale Or Rent'),
    ], string='Unit Purposes', required=True)
    unit_status = fields.Selection([
        ('available', 'Available'),
        ('sold', 'Sold'),
        ('rented', 'Rented'),
    ], string='Unit Status', default='available')
    unit_type = fields.Selection([
        ('land', 'Land'),
        ('retail', 'Retail'),
        ('office', 'Office'),
        ('clinic', 'Clinic'),
        ('residential', 'Residential'),
        ('entertainment', 'Entertainment'),
        ('industrial', 'Industrial'),
        ('parking', 'Parking'),
        ('storage', 'Storage'),
        ('public_area', 'Public Area')
    ], string='Unit Type')
    public_area = fields.Selection([
        ('landscape', 'Landscape'),
        ('bathroom', 'Bathroom'),
        ('corridors', 'Corridors'),
        ('meeting_room', 'Meeting Room'),
        ('admin_office', 'Admin Office'),
        ('pray_room', 'Pray Room'),
        ('services_room', 'services Room')
    ], string='Public Area')
    storge_capacity = fields.Float()
    retail_type = fields.Selection([
        ('bank', 'Bank'),
        ('f&b', 'F&B'),
        ('fashion_retail', 'Fashion Retail'),
        ('beauty_cosmetics', 'Beauty and Cosmetics'),
        ('supermarket', 'Supermarket'),
        ('hypermarket', 'Hypermarket'),
        ('kiosk', 'Kiosk'),
        ('laundry', 'Laundry'),
        ('competitive_socializing', 'Competitive Socializing'),
        ('gym', 'Gym'),
        ('health_wellness', 'Health and Wellness'),
        ('home_goods', 'Home Goods'),
        ('pharmacies', 'Pharmacies'),
        ('bookstores', 'Bookstores'),
        ('car_wash', 'Car wash'),
        ('light_F&B', ' light F&B'),
        ('concept_store', 'Concept Store'),
        ('sporting_goods', 'Sporting Goods'),
        ('electronics', 'Electronics'),
        ('jewelry', 'Jewelry'),
        ('furniture', 'Furniture'),
        ('car_dealerships', 'Car Dealerships'),
        ('other', 'Other'),
    ], string='Retail Type')
    office_type = fields.Selection([
        ('co_working', 'Co-working'),
        ('private_office', 'Private office')
    ], string='Office Type')
    residential_type = fields.Selection([
        ('apartment', 'Apartment'),
        ('standalone_villa', 'Stand-alone Villa'),
        ('twin_villa', 'Twin Villa'),
        ('town_house', 'Town House'),
        ('duplex', 'Duplex'),
        ('chalet', 'Chalet'),
        ('cabin', 'Cabin'),
        ('studio', 'Studio'),
        ('loft', 'Loft')
    ], string='Residential Type')
    entertainment_type = fields.Selection([
        ('arcade_zone', 'Arcade Zone'),
        ('gym', 'Gym'),
        ('bowling_center', 'Bowling Center'),
        ('other', 'Other'),
    ], string='Entertainment Type')
    industrial_type = fields.Selection([
        ('factory', 'Factory'),
        ('warehouse', 'Warehouse')
    ], string='Industrial Type')
    parking_type = fields.Selection([
        ('indoor_parking', 'Indoor Parking'),
        ('outdoor_parking', 'Outdoor Parking')
    ], string='Parking Type')
    active = fields.Boolean(default=True)

    # Resedintial

    finishing_type = fields.Selection([
        ('finished', 'Finished'),
        ('semi_finished', 'Semi-Finished'),
        ('core_shell', 'Core and Shell')
    ], string='Finished')
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
    garden_area = fields.Float(string='Garden Area')
    has_roof = fields.Boolean(string='Has Roof')
    roof_area = fields.Float(string='Roof Area')
    has_parking = fields.Boolean(string='Has Parking')
    number_of_slots = fields.Integer()
    has_club_membership = fields.Boolean(string='Has Club Membership')
    gross_area = fields.Float(string='Gross Area')
    net_area = fields.Char(string='Net Total Area', compute='_compute_total_net_area')
    has_balcony = fields.Boolean(string='Has Balcony')
    number_of_balcony = fields.Integer()
    roof_access = fields.Boolean(string='Roof Access')
    has_pool = fields.Boolean(string='Has Pool')
    pool_area = fields.Float(string='Pool Area')
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
    maintenance_percentage = fields.Float(string='Maintenance Percentage')


    unit_id = fields.Many2one('broker.unit')

    # Area
    indoor_gross_area = fields.Float()
    indoor_net_area = fields.Float()
    outdoor_gross_area = fields.Float()
    outdoor_net_area = fields.Float()

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
    indoor_outdoor_price_sqm = fields.Float(string="Indoor+Outdoor Price/SQM")
    project_id = fields.Many2one('developer.project', store=True, string='Project')
    developer_id = fields.Many2one(related='project_id.developer_id')

    warning_msg = fields.Text('Warning Message')
    # plan_id = fields.Many2one('account.analytic.plan', string='Plan',copy=False)

    # new fields
    unit_sale_type = fields.Selection([('primary', 'Primary'), ('resale', 'Resale')])
    is_compound = fields.Boolean('Compound', default=True)
    furniture_type = fields.Selection([('furnished', 'Furnished'), ('not_furnished', 'Not Furnished')])
    ready_to_move = fields.Boolean('Ready To Move')
    location_url = fields.Char(string='Location')
    latitude = fields.Float()
    longitude = fields.Float()

    sale_price = fields.Integer()
    sale_maintenance_price = fields.Float()
    down_payment_percentage = fields.Float()

    rent_price = fields.Float()
    rent_maintenance_price = fields.Float()
    rent_period = fields.Selection([('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('yearly', 'Yearly')])
    maintenance_period = fields.Selection([('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('yearly', 'Yearly')])
    country_id = fields.Many2one('res.country', related='project_id.country_id' ,string="Country", readonly=False)
    governorate_id = fields.Many2one('res.country.state', related='project_id.governorate_id' ,string="Governorate",
                                     domain="[('country_id', '=', country_id)]", readonly=False)
    city_id = fields.Many2one(related='project_id.city_id', readonly=False)
    neighborhood_id = fields.Many2one('neighborhood.neighborhood', related='project_id.neighborhood_id', string='Neighborhood', readonly=False)

    seller_sales_person = fields.Many2one('res.users', default=lambda self: self.env.user, index=True)
    seller_sales_person_phone = fields.Char(related='seller_sales_person.mobile')
    seller_team_leader = fields.Many2one('res.users')
    seller_sales_manager = fields.Many2one('res.users')
    seller_sales_director = fields.Many2one('res.users')
    seller_purpose_sale_price = fields.Float()
    seller_purpose_rent_price = fields.Float()
    seller_client_name = fields.Char(domain="[('is_seller','=', True)]")
    seller_client_id = fields.Many2one('res.partner', domain="[('is_resale_seller','=', True)]", string='seller client name', index=True, required=True)
    seller_client_phone = fields.Char(related='seller_client_id.phone', string='seller client phone', required=True)
    seller_client_extra_phone = fields.Char(related='seller_client_id.mobile', string='seller client extra phone')
    is_client_tap_viewer = fields.Boolean(compute='_compute_is_client_tap', readonly=False)
    is_seller_details_tap_viewer = fields.Boolean(compute='_compute_is_seller_details_tap', readonly=False)
    sequence_number = fields.Char('Sequence Number', readonly=True, copy=False)
    tcr = fields.Char()

    @api.onchange('seller_sales_person')
    def _onchange_seller_sales_person(self):
        """
        When the seller sales person is selected, automatically set the team leader,
        sales manager, and sales director from the salesperson's team.
        """
        print('from portaaaaal')
        if self.seller_sales_person:
            # We need to search for teams and then filter by members in Python
            # instead of using a direct domain search to avoid potential errors
            sales_teams = self.env['crm.team'].sudo().search([])
            user_teams = sales_teams.filtered(lambda team: self.seller_sales_person.id in team.member_ids.ids)

            if user_teams:
                sales_team = user_teams[0]  # Take the first team the user belongs to
                # Set the hierarchy values from the sales team
                self.seller_team_leader = sales_team.user_id  # Team leader is the team's responsible
                self.seller_sales_manager = sales_team.sales_manager_id
                self.seller_sales_director = sales_team.director_id
            else:
                # Clear the fields if no team is found
                self.seller_team_leader = False
                self.seller_sales_manager = False
                self.seller_sales_director = False

    @api.model
    def create(self, vals):
        is_portal = self.env.context.get('from_portal', False)
        # Generate sequence if not already set
        if not vals.get('sequence_number'):
            if is_portal:
                sale_type = vals.get('unit_sale_type', 'primary')
            else:
                sale_type = self.env.context.get('default_unit_sale_type', 'primary')

            print(f"Using sale_type: {sale_type}")

            if sale_type == 'primary':
                vals['sequence_number'] = self.env['ir.sequence'].next_by_code('unit.primary.sequence')
            elif sale_type == 'resale':
                vals['sequence_number'] = self.env['ir.sequence'].next_by_code('unit.resale.sequence')

            # Set the name based on the generated sequence if sequence was generated
            if vals.get('sequence_number'):
                vals['name'] = vals['sequence_number']
        if vals.get('unit_type') == 'residential' and vals.get('built_up_area') <= 0:
            raise ValidationError("Please Set BUA")

        return super(BrokerUnit, self).create(vals)

    @api.depends('parent_source_id')
    def _compute_project_id(self):
        for rec in self:
            source_id = rec.parent_source_id
            if source_id and source_id._name == 'realestate.project':
                rec.project_id = source_id.id
            if source_id and source_id._name == 'zone':
                rec.project_id = source_id.parent_id.id
            elif source_id:
                rec.project_id = False
                while source_id:
                    if source_id._name == 'realestate.project':
                        rec.project_id = source_id.id
                        break
                    project_id = source_id.project_id
                    if project_id:
                        rec.project_id = project_id.id
                        break
                    source_id = source_id.parent_source_id
            else:
                rec.project_id = False

    outdoor_area = fields.Char(string='Outdoor Area')

    # Parking
    parking_number = fields.Integer(string='Parking Number')
    parking_code = fields.Char(string='Parking Code')
    parking_name = fields.Char(string='Parking Name')
    parent_source_id = fields.Reference([('floor.area', 'Floor Area'),
                                         ('floor', 'Floor'),
                                         ('cluster', 'Cluster'),
                                         ('zone', 'Zone'),
                                         ('real.estate.building', 'Building'),
                                         ('realestate.project', 'Project')], string='Parent reference')
    unit_location = fields.Char()  # compute='compute_unit_location')

    counter_ids = fields.One2many(comodel_name="counter.counter", inverse_name="unit_id")
    gas_counter_ids = fields.One2many(comodel_name="gas.counter", inverse_name="unit_id")
    water_counter_ids = fields.One2many(comodel_name="water.counter", inverse_name="unit_id")
    landline_counter_ids = fields.One2many(comodel_name="landline.counter", inverse_name="unit_id")
    internet_counter_ids = fields.One2many(comodel_name="internet", inverse_name="unit_id")
    is_floors = fields.Boolean('Multiple Floors')
    floors_count = fields.Integer()
    is_yard = fields.Boolean('Yard')
    yard_area = fields.Float('Yard Area')
    built_up_area = fields.Float('BUA', requied=True)
    unit_document_ids = fields.Many2many('documents.document')
    # website
    unit_image = fields.Binary()
    unit_attachment_image_ids = fields.Many2many('ir.attachment', string='Unit Attachment Images')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    @api.depends('indoor_gross_area', 'outdoor_gross_area')
    def _compute_total_gross_area(self):
        for rec in self:
            rec.unit_area = rec.indoor_gross_area + rec.outdoor_gross_area

    @api.depends('indoor_net_area', 'outdoor_net_area')
    def _compute_total_net_area(self):
        for rec in self:
            rec.net_area = rec.indoor_net_area + rec.outdoor_net_area

    def action_rollback(self):
        for rec in self:
            rec.unit_status = 'available'

    @api.onchange('location_url')
    def get_amp_let_location(self):
        if self.location_url:
            url = self.location_url
            data = self.fetch_google_maps_data(url)
            self.latitude = data.get("latitude") if data.get("latitude") else 0
            self.longitude = data.get("longitude") if data.get("longitude") else 0

    def fetch_google_maps_data(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"error": f"Failed to fetch data, status code: {response.status_code}"}

        soup = BeautifulSoup(response.text, "html.parser")

        # Example: Extract latitude and longitude from meta tags or script content
        scripts = soup.find_all("script")
        lat_lng_pattern = re.compile(r"@([-\d.]+),([-\d.]+),")

        for script in scripts:
            if script.string and lat_lng_pattern.search(script.string):
                match = lat_lng_pattern.search(script.string)
                latitude = match.group(1)
                longitude = match.group(2)
                return {
                    "latitude": latitude,
                    "longitude": longitude,
                    "url": url
                }

        return {"error": "No latitude/longitude found"}

    def action_open_documents(self):
        return {
            'name': 'Documents',
            'type': 'ir.actions.act_window',
            'view_mode': 'kanban,tree,form',
            'views': [(False, 'kanban'), (False, 'list'), (False, 'form')],
            'res_model': 'documents.document',
            'domain': [('id', 'in', self.unit_document_ids.ids)],
        }

    @api.depends('project_id')
    def _compute_sale_phases(self):
        if self.project_id:
            phases = self.env['project.sale.phase'].search([('project_id', '=', self.project_id.id)])
            if phases:
                phases_list = [phase.id for phase in phases]
                if phases_list:
                    self.all_sale_phases_ids = phases_list
                else:
                    self.all_sale_phases_ids = []
            else:
                self.all_sale_phases_ids = []
        else:
            self.all_sale_phases_ids = []

    @api.constrains('sale_price', 'rent_price')
    def _check_required_fields(self):
        if self.unit_purpose == 'to_sale' and self.sale_price <= 0:
            raise ValidationError("Sale Price Is Required")
        if self.unit_purpose == 'to_rent' and self.rent_price <= 0:
            raise ValidationError("Rent Price Is Required")
        if self.unit_purpose == 'sale_or_rent' and (self.rent_price <= 0 or self.sale_price <= 0):
            raise ValidationError("Sale Price And Rent Price Is Required")

    @api.constrains('country_id', 'governorate_id', 'city_id', 'neighborhood_id')
    def _check_location_required_fields(self):
        if not self.project_id:
            if not self.country_id:
                raise ValidationError("Country is required if you don't select project")
            if not self.governorate_id:
                raise ValidationError("Governorate required if you don't select project")
            if not self.city_id:
                raise ValidationError("City required if you don't select project")
            if not self.neighborhood_id:
                raise ValidationError("Neighborhood required if you don't select project")

    @api.depends('seller_sales_person', 'seller_team_leader', 'seller_sales_manager')
    def _compute_is_client_tap(self):
        for rec in self:
            if (self.env.user in [rec.seller_sales_person, rec.seller_team_leader, rec.seller_sales_manager]
                    or self.env.user.has_group('isky_18_realestate_developer_sales_crm.lead_admin_group')):
                rec.is_client_tap_viewer = True
            else:
                rec.is_client_tap_viewer = False

    @api.depends('seller_sales_person', 'seller_team_leader', 'seller_sales_manager')
    def _compute_is_seller_details_tap(self):
        for rec in self:
            if (self.env.user in [rec.seller_sales_person, rec.seller_team_leader, rec.seller_sales_manager]
                    or self.env.user.has_group('isky_18_realestate_developer_sales_crm.lead_admin_group')):
                rec.is_seller_details_tap_viewer = True
            else:
                rec.is_seller_details_tap_viewer = False


    def compute_seller_tap_details(self, user):
        """
        When the seller sales person is selected, automatically set the team leader,
        sales manager, and sales director from the salesperson's team.
        """
        if user:
            # We need to search for teams and then filter by members in Python
            # instead of using a direct domain search to avoid potential errors
            sales_teams = self.env['crm.team'].sudo().search([])
            user_teams = sales_teams.filtered(lambda team: user in team.member_ids.ids)

            if user_teams:
                sales_team = user_teams[0]  # Take the first team the user belongs to
                # Set the hierarchy values from the sales team
                seller_team_leader = sales_team.user_id.id  # Team leader is the team's responsible
                seller_sales_manager = sales_team.sales_manager_id.id
                seller_sales_director = sales_team.director_id.id
                user_phone = self.env['res.users'].browse(user).mapped('mobile')[0]

            else:
                # Clear the fields if no team is found
                seller_team_leader = False
                seller_sales_manager = False
                seller_sales_director = False
                user_phone = 0
            return (seller_team_leader, seller_sales_manager, seller_sales_director, user_phone)

