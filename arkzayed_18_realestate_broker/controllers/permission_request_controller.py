from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class PermissionRequestPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'permission_request_count' in counters:
            values['permission_request_count'] = request.env['permission.request'].search_count([
                ('requester_id', '=', request.env.user.id)
            ])
        return values

    @http.route(['/my/permission_requests', '/my/permission_requests/page/<int:page>'], type='http', auth="user",
                website=True)
    def portal_my_permission_requests(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        PermissionRequest = request.env['permission.request']

        domain = [('requester_id', '=', request.env.user.id)]

        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'create_date desc'},
            'name': {'label': _('Reference'), 'order': 'name'},
            'status': {'label': _('Status'), 'order': 'approval_status'},
        }

        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'pending': {'label': _('Pending'), 'domain': [('approval_status', '=', 'pending')]},
            'approved': {'label': _('Approved'), 'domain': [('approval_status', '=', 'approved')]},
            'rejected': {'label': _('Rejected'), 'domain': [('approval_status', '=', 'rejected')]},
        }

        # default sort by value
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # default filter by value
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # count for pager
        permission_request_count = PermissionRequest.search_count(domain)

        # pager
        pager = portal_pager(
            url="/my/permission_requests",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=permission_request_count,
            page=page,
            step=self._items_per_page
        )

        # content according to pager and archive selected
        permission_requests = PermissionRequest.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )

        values.update({
            'date': date_begin,
            'permission_requests': permission_requests,
            'page_name': 'permission_request',
            'pager': pager,
            'default_url': '/my/permission_requests',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
        })
        return request.render("arkzayed_18_realestate_broker.portal_my_permission_requests", values)

    @http.route(['/my/permission_request/<int:permission_request_id>'], type='http', auth="user", website=True)
    def portal_my_permission_request(self, permission_request_id=None, **kw):
        try:
            permission_request_sudo = self._document_check_access('permission.request', permission_request_id)
        except (AccessError, MissingError):
            return request.redirect('/my')

        values = self._permission_request_get_page_view_values(permission_request_sudo, **kw)
        return request.render("arkzayed_18_realestate_broker.portal_my_permission_request", values)

    def _permission_request_get_page_view_values(self, permission_request, **kwargs):
        values = {
            'page_name': 'permission_request',
            'permission_request': permission_request,
        }
        return self._get_page_view_values(permission_request, access_token=None, values=values,
                                          session_history=None, no_breadcrumbs=False, **kwargs)

    @http.route(['/my/permission_request/create'], type='http', auth="user", website=True)
    def create_permission_request(self, **post):
        if post and request.httprequest.method == 'POST':
            values = {
                'requester_id': request.env.user.id,
                'request_type': post.get('request_type'),
                'client_name': post.get('client_name'),
                'client_number': post.get('client_number'),
                'request_details': post.get('request_details'),
                'approval_status': 'pending',
            }
            permission_request = request.env['permission.request'].sudo().create(values)
            return request.redirect('/my/permission_requests')

        return request.render("arkzayed_18_realestate_broker.portal_create_permission_request", {})
