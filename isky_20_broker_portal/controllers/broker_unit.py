from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

from .portal import check_portal_feature_http, PORTAL_FEATURE_UNITS


class BrokerUnitPortal(CustomerPortal):

    @http.route(['/my/units', '/my/units/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_units(self, page=1, sortby=None, **kw):
        check_portal_feature_http(PORTAL_FEATURE_UNITS)
        BrokerUnit = request.env['broker.unit']
        domain = [('seller_sales_person', '=', request.env.user.id)]
        searchbar_sortings = {
            'date': {'label': "Newest", 'order': 'id desc'},
            'name': {'label': "Reference", 'order': 'name'},
        }
        sortby = sortby or 'date'

        count = BrokerUnit.search_count(domain)
        pager = portal_pager(
            url="/my/units", total=count, page=page, step=self._items_per_page)
        units = BrokerUnit.search(
            domain, order=searchbar_sortings[sortby]['order'], limit=self._items_per_page, offset=pager['offset'])

        values = self._prepare_portal_layout_values()
        values.update({
            'units': units,
            'page_name': 'broker_unit',
            'pager': pager,
            'default_url': '/my/units',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render('isky_20_broker_portal.portal_my_units', values)

    @http.route(['/my/unit/<int:unit_id>'], type='http', auth='user', website=True)
    def portal_my_unit(self, unit_id, **kw):
        check_portal_feature_http(PORTAL_FEATURE_UNITS)
        try:
            unit_sudo = self._document_check_access('broker.unit', unit_id)
        except (AccessError, MissingError):
            return request.redirect('/my/units')
        values = self._get_page_view_values(
            unit_sudo, access_token=None, values={'page_name': 'broker_unit', 'unit': unit_sudo},
            session_history=None, no_breadcrumbs=False, **kw)
        return request.render('isky_20_broker_portal.portal_my_unit', values)

    @http.route(['/my/unit/create'], type='http', methods=['GET', 'POST'], auth='user', website=True)
    def portal_create_unit(self, **post):
        check_portal_feature_http(PORTAL_FEATURE_UNITS)
        if post and request.httprequest.method == 'POST':
            vals = {
                'unit_sale_type': 'resale',
                'unit_purpose': post.get('unit_purpose'),
                'unit_type': post.get('unit_type'),
                'unit_number': post.get('unit_number'),
                'seller_sales_person': request.env.user.id,
                'seller_client_id': int(post['seller_client_id']) if post.get('seller_client_id') else False,
                'project_id': int(post['project_id']) if post.get('project_id') else False,
                'sale_price': float(post['sale_price']) if post.get('sale_price') else 0.0,
                'rent_price': float(post['rent_price']) if post.get('rent_price') else 0.0,
            }
            unit = request.env['broker.unit'].create(vals)
            return request.redirect(f'/my/unit/{unit.id}')
        values = {
            'projects': request.env['developer.project'].sudo().search([]),
            'sellers': request.env['res.partner'].search([('is_resale_seller', '=', True)]),
        }
        return request.render('isky_20_broker_portal.portal_create_unit', values)
