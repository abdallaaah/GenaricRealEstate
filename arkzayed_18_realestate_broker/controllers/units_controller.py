from keyword import kwlist

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.exceptions import AccessError
from odoo.tools.translate import _
from odoo.addons.website_crm_partner_assign.controllers.main import WebsiteAccount
from odoo.addons.portal.controllers.portal import CustomerPortal



class UnitsPortal(CustomerPortal):

    @http.route('/my/units/<int:id>', type='http', auth='user', methods=['GET'], website=True)
    def portal_form_list_units(self, id=None,**kwargs):
        if id:
            unit = request.env['broker.unit'].browse(id)
        return request.render('arkzayed_18_realestate_broker.portal_my_units', {'unit': unit})


    @http.route('/my/unit/create', type='http', auth='user', methods=['GET', 'POST'], website=True)
    def create_unit(self, **kwargs):
        # unit_types = request.env['broker_unit']
        if kwargs and request.httprequest.method == 'POST':
            # print(type(kwargs.get('project_id')), 'pppppppppppp')
            # print(type(int(kwargs.get('project_id'))), 'pppppppppppp')
            print(kwargs.get('unit_sale_type'), 'zzzzzzzzz')
            data = {
                'name': kwargs.get('unit_name') if kwargs.get('unit_name') else '',
                # 'abbreviation': kwargs.get('abbreviation') if kwargs.get('abbreviation') else '',
                'unit_code': kwargs.get('unit_code') if kwargs.get('unit_code') else '',
                'unit_number': kwargs.get('unit_number') if kwargs.get('unit_number') else '',
                'unit_type': kwargs.get('unit_type') if kwargs.get('unit_type') else '',
                'project_id': int(kwargs.get('project_id')) if kwargs.get('project_id') else '',
                'retail_type': kwargs.get('retail_type') if kwargs.get('retail_type') else '',
                'residential_type': kwargs.get('residential_type') if kwargs.get('residential_type') else '',
                'currency_id': int(kwargs.get('currency_id')) if kwargs.get('currency_id') else '',
                'developer_id': int(kwargs.get('developer_id')) if kwargs.get('developer_id') else '',
                'sale_phase': int(kwargs.get('sale_phase_id')) if kwargs.get('sale_phase_id') else '',
                'unit_sale_type': kwargs.get('unit_sale_type') if kwargs.get('unit_sale_type') else '',
                'is_compound': kwargs.get('compound_boolean') if kwargs.get('compound_boolean') else '',
                'customer_id': int(kwargs.get('customer_id')) if kwargs.get('customer_id') else '',
                'number_of_rooms': int(kwargs.get('num_rooms_value')) if kwargs.get('num_rooms_value') else '',
                'number_of_bathrooms': int(kwargs.get('num_bathrooms_value')) if kwargs.get('num_bathrooms_value') else '',
                'indoor_gross_area': int(kwargs.get('in-gross-area')) if kwargs.get('in-gross-area') else '',
                'indoor_net_area': int(kwargs.get('in-gross-area')) if kwargs.get('in-gross-area') else '',
                'outdoor_gross_area': int(kwargs.get('out-gross-area')) if kwargs.get('out-gross-area') else '',
                'outdoor_net_area': int(kwargs.get('out-gross-area')) if kwargs.get('out-gross-area') else '',
                'net_area': int(kwargs.get('net-total-area')) if kwargs.get('net-total-area') else '',
                'gross_area': int(kwargs.get('gross-total-area')) if kwargs.get('gross-total-area') else '',
                'sale_maintenance_price': int(kwargs.get('sale_maintenance_price')) if kwargs.get('sale_maintenance_price') else '',
                'down_payment_percentage': int(kwargs.get('down_payment_percentage')) if kwargs.get('down_payment_percentage') else '',
                'rent_maintenance_price': int(kwargs.get('rent_maintenance_price')) if kwargs.get('rent_maintenance_price') else '',
                'rent_period': kwargs.get('rent_period') if kwargs.get('rent_period') else '',
                'maintenance_period': int(kwargs.get('maintenance_period')) if kwargs.get('maintenance_period') else '',
                'built_up_area' : int(kwargs.get('built_up_area')) if kwargs.get('built_up_area') else '',
                'indoor_price_sqm': int(kwargs.get('indoor_price_sqm')) if kwargs.get('indoor_price_sqm') else '',
                'outdoor_price_sqm': int(kwargs.get('outdoor_price_sqm')) if kwargs.get('outdoor_price_sqm') else '',
                'indoor_outdoor_price_sqm': int(kwargs.get('in_out_price_sqm')) if kwargs.get('in_out_price_sqm') else '',
                'indoor_price_per_month_sqm': int(kwargs.get('indoor_price_month_sqm')) if kwargs.get('indoor_price_month_sqm') else '',
                'outdoor_price_per_month_sqm': int(kwargs.get('outdoor_price_sqm_month')) if kwargs.get('outdoor_price_sqm_month') else '',
                'indoor_outdoor_price_per_month_sqm': int(kwargs.get('in_out_price_sqm_month')) if kwargs.get('in_out_price_sqm_month') else '',
                'service_charge_per_sqm': int(kwargs.get('service_charge_sqm')) if kwargs.get('service_charge_sqm') else '',
                'marketing_fees_annually_percent': int(kwargs.get('marketing_fees')) if kwargs.get('marketing_fees') else '',
                'payment_terms_duration': int(kwargs.get('payment_terms_duration')) if kwargs.get('payment_terms_duration') else '',
                'warning_msg': kwargs.get('warning') if kwargs.get('warning') else '',
                'location_url': kwargs.get('location_url') if kwargs.get('location_url') else '',
                'latitude': int(kwargs.get('latitude_value')) if kwargs.get('latitude_value') else '',
                'longitude': int(kwargs.get('longitude_value')) if kwargs.get('longitude_value') else '',
                'country_id': int(kwargs.get('country_id')) if kwargs.get('country_id') else '',
                'governorate_id': int(kwargs.get('governorate_id')) if kwargs.get('governorate_id') else '',
                'city_id': int(kwargs.get('city_id')) if kwargs.get('city_id') else '',
                'neighborhood_id': int(kwargs.get('neighborhood_id')) if kwargs.get('neighborhood_id') else '',
                'is_floors': int(kwargs.get('multi_floors_boolean')) if kwargs.get('multi_floors_boolean') else '',
                'floors_count': int(kwargs.get('floors_number')) if kwargs.get('floors_number') else '',
                'unit_purpose': kwargs.get('unit_purpose') if kwargs.get('unit_purpose') else '',
                'sale_price': int(kwargs.get('sale_price_value')) if kwargs.get('sale_price_value') else '',
                'rent_price': int(kwargs.get('rent_price_value')) if kwargs.get('rent_price_value') else '',
                'unit_status': kwargs.get('unit_status') if kwargs.get('unit_status') else '',
                'is_yard': kwargs.get('yard_boolean') if kwargs.get('yard_boolean') else '',
                'finishing_type': kwargs.get('unit_finished_sale_type') if kwargs.get('unit_finished_sale_type') else '',
                'ready_to_move': kwargs.get('ready_to_move') if kwargs.get('ready_to_move') else '',
                'garden_view': kwargs.get('garden_view') if kwargs.get('garden_view') else '',
                'pool_view': kwargs.get('garden_view') if kwargs.get('garden_view') else '',
                'city_view': kwargs.get('city_view') if kwargs.get('city_view') else '',
                'sea_view': kwargs.get('sea_view') if kwargs.get('sea_view') else '',
                'lagoon_view': kwargs.get('lagoon_view') if kwargs.get('lagoon_view') else '',
                'internal_view': kwargs.get('internal_view') if kwargs.get('internal_view') else '',
                'has_garden': kwargs.get('has_garden') if kwargs.get('has_garden') else '',
                'has_roof': kwargs.get('has_roof') if kwargs.get('has_roof') else '',
                'solar_system': kwargs.get('solar_system') if kwargs.get('solar_system') else '',
                'electricity_meter': kwargs.get('electricity_meter') if kwargs.get('electricity_meter') else '',
                'gas_meter': kwargs.get('gas_meter') if kwargs.get('gas_meter') else '',
                'water_meter': kwargs.get('water_meter') if kwargs.get('water_meter') else '',
                'landline': kwargs.get('landline') if kwargs.get('landline') else '',
                'internet': kwargs.get('internet') if kwargs.get('internet') else '',
                'air_condition': kwargs.get('air_condition') if kwargs.get('air_condition') else '',
                'cooling_water': kwargs.get('cooling_water') if kwargs.get('cooling_water') else '',
                'has_club_membership': kwargs.get('has_club') if kwargs.get('has_club') else '',
                'seller_sales_person': request.env.user.id,
            }
            if data:
                object = request.env['broker.unit'].with_context(from_portal=True).create(data)
                object._onchange_seller_sales_person()
        unit_types = request.env['broker.unit'].sudo().fields_get(['unit_type'])['unit_type']['selection']
        retail_type = request.env['broker.unit'].sudo().fields_get(['retail_type'])['retail_type']['selection']
        office_type = request.env['broker.unit'].sudo().fields_get(['office_type'])['office_type']['selection']
        residential_type = request.env['broker.unit'].sudo().fields_get(['residential_type'])['residential_type']['selection']
        projects = request.env['developer.project'].sudo().search([])
        developers = request.env['res.partner'].sudo().search([])
        users = request.env['res.users'].sudo().search([])
        currencies = request.env['res.currency'].sudo().search([])
        phases = request.env['project.sale.phase'].sudo().search([])
        countries = request.env['res.country'].sudo().search([])
        governorate = request.env['res.country.state'].sudo().search([])
        cities = request.env['res.country.city'].sudo().search([])
        neighborhoods = request.env['neighborhood.neighborhood'].sudo().search([])

        if request.httprequest.method == 'POST':
            print('the kwww', kwargs)

        project_developer_data = {}
        for project in projects:
            if project.developer_id:
                project_developer_data['id'] = project.id
                project_developer_data['developer_id'] = project.developer_id
                project_developer_data['developer_name'] = project.developer_id.name
        return request.render('arkzayed_18_realestate_broker.portal_create_unit', {'unit_types': unit_types,
                                                                               'retail_type': retail_type,
                                                                               'office_type': office_type,
                                                                               'residential_type': residential_type,
                                                                               'projects': projects,
                                                                               'project_developer_data': project_developer_data,
                                                                               'developers': developers,
                                                                               'currencies': currencies,
                                                                               'phases': phases,
                                                                               'countries': countries,
                                                                               'governorate': governorate,
                                                                               'cities': cities,
                                                                               'users': request.env.user,
                                                                               'neighborhoods': neighborhoods})

    @http.route('/my/units', type='http', website=True)
    def portal_list_units(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        units = request.env['broker.unit'].search([])
        searchbar_sortings = {
            'create_date': {'label': _('Newest'), 'order': 'create_date desc'},
            'name': {'label': _('Name'), 'order': 'name'},
        }
        if not sortby:
            sortby = 'create_date'
        order = searchbar_sortings[sortby]['order']
        unit_count = units.search_count([])
        pager = request.website.pager(
            url="/my/units",
            url_args={'sortby': sortby},
            total=unit_count,
            page=page,
            step=self._items_per_page
        )
        # content according to pager and archive selected
        units = units.search([],order=order, limit=self._items_per_page, offset=pager['offset'])

        values.update({
            'units': units,
            'page_name': 'unit_list_view',
            'error': {},
            'error_message': []
        })
        return request.render('arkzayed_18_realestate_broker.unit_list_view', values)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        # Add create access check
        if 'units_count' in counters:
            values['units_count'] = request.env['broker.unit'].search_count([])
        return values
