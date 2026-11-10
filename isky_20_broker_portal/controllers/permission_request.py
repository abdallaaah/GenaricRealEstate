from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

from .portal import check_portal_feature_http, PORTAL_FEATURE_PERMISSION_REQUESTS


class PermissionRequestPortal(CustomerPortal):

    @http.route(['/my/permission-requests', '/my/permission-requests/page/<int:page>'],
                type='http', auth="user", website=True)
    def portal_my_permission_requests(self, page=1, sortby=None, filterby=None, **kw):
        check_portal_feature_http(PORTAL_FEATURE_PERMISSION_REQUESTS)
        values = self._prepare_portal_layout_values()
        PermissionRequest = request.env['permission.request']
        domain = [('requester_id', '=', request.env.user.id)]

        searchbar_sortings = {
            'date': {'label': "Date", 'order': 'create_date desc'},
            'name': {'label': "Reference", 'order': 'name'},
            'status': {'label': "Status", 'order': 'approval_status'},
        }
        searchbar_filters = {
            'all': {'label': "All", 'domain': []},
            'pending': {'label': "Pending", 'domain': [('approval_status', '=', 'pending')]},
            'approved': {'label': "Approved", 'domain': [('approval_status', '=', 'approved')]},
            'rejected': {'label': "Rejected", 'domain': [('approval_status', '=', 'rejected')]},
        }
        sortby = sortby or 'date'
        filterby = filterby or 'all'
        domain += searchbar_filters[filterby]['domain']

        count = PermissionRequest.search_count(domain)
        pager = portal_pager(
            url="/my/permission-requests",
            url_args={'sortby': sortby, 'filterby': filterby},
            total=count, page=page, step=self._items_per_page,
        )
        permission_requests = PermissionRequest.search(
            domain, order=searchbar_sortings[sortby]['order'], limit=self._items_per_page, offset=pager['offset'])

        values.update({
            'permission_requests': permission_requests,
            'page_name': 'permission_request',
            'pager': pager,
            'default_url': '/my/permission-requests',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
        })
        return request.render('isky_20_broker_portal.portal_my_permission_requests', values)

    @http.route(['/my/permission-request/<int:permission_request_id>'], type='http', auth="user", website=True)
    def portal_my_permission_request(self, permission_request_id, **kw):
        check_portal_feature_http(PORTAL_FEATURE_PERMISSION_REQUESTS)
        try:
            permission_request_sudo = self._document_check_access('permission.request', permission_request_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
        values = self._get_page_view_values(
            permission_request_sudo, access_token=None,
            values={'page_name': 'permission_request', 'permission_request': permission_request_sudo},
            session_history=None, no_breadcrumbs=False, **kw)
        return request.render('isky_20_broker_portal.portal_my_permission_request', values)

    @http.route(['/my/permission-request/create'], type='http', methods=['GET', 'POST'], auth="user", website=True)
    def portal_create_permission_request(self, **post):
        check_portal_feature_http(PORTAL_FEATURE_PERMISSION_REQUESTS)
        if post and request.httprequest.method == 'POST':
            request.env['permission.request'].create({
                'request_type': post.get('request_type'),
                'client_name': post.get('client_name'),
                'client_number': post.get('client_number'),
                'request_details': post.get('request_details'),
            })
            return request.redirect('/my/permission-requests')
        return request.render('isky_20_broker_portal.portal_create_permission_request', {})
