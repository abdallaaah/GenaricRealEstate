from werkzeug.exceptions import NotFound

from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError, AccessError, UserError
from odoo.addons.web.controllers import json
from odoo.addons.website_crm_partner_assign.controllers.main import WebsiteAccount
from odoo.osv.expression import OR, AND
from odoo.tools import groupby as groupbyelem
from odoo.tools.translate import _
from operator import itemgetter


class CustomWebsiteAccount(WebsiteAccount):
    def get_domain_my_lead(self, user):
        # Custom domain: remove the `partner_assigned_id` condition
        locked_stage = request.env.ref('arkzayed_18_realestate_broker.stage_locked').id
        return [
            ('type', '=', 'lead'), '|', ('user_id', '=', user.id), ('user_id.sale_team_id.user_id', '=', user.id)
        ]


    def get_domain_my_opp(self, user):
        # Custom domain: remove the `partner_assigned_id` condition
        return [
            ('type', '=', 'opportunity'),
            '|', '|', '|','|','|',
            ('user_id', '=', user.id),
            ('user_id.sale_team_id.user_id', '=', user.id),
            ('sales_ids', 'in', [user.id]),
            ('sales_ids', 'in', user.crm_team_member_ids.ids),
            ('sales_ids.sale_team_id.user_id', '=', user.id),
            ('commission_ids.employee_id', 'in', [user.id])
        ]


    @http.route(['/my/leads', '/my/leads/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_leads(self, page=1, date_begin=None, date_end=None, sortby=None, groupby='none', search=None, search_in='all', **kw):
        values = self._prepare_portal_layout_values()
        CrmLead = request.env['crm.lead']

        domain = self.get_domain_my_lead(request.env.user)
        lead_stages = request.env['lead.stage'].search([], order='sequence desc')

        # Add groupby options
        searchbar_groupby = {
            'none': {'input': 'none', 'label': _('None')},
            'stage': {'input': 'lead_stage_id', 'label': _('Stage')},
            'project': {'input': 'project_id', 'label': _('Project')},
            'user_id': {'input': 'user_id', 'label': _('Salesperson')},
            'is_fresh': {'input': 'is_fresh', 'label': _('Fresh Leads')},
        }

        # Default groupby none
        if not groupby:
            groupby = 'none'

        searchbar_sortings = {
            'date': {'label': 'Newest', 'order': 'create_date desc'},
            'name': {'label': 'Name', 'order': 'name'},
            'stage': {'label': 'Stage', 'order': 'lead_stage_id'},
            'date_open': {'label': 'Last Assignment Date', 'order': 'date_open desc'},
        }
        searchbar_inputs = {
            'All': {'label': _('Search All'), 'input': 'all'},
            'Number': {'label': _('Search Number'), 'input': 'number'},
            'Contract': {'label': _('Search Contact'), 'input': 'contact'},
            'Sequence': {'label': _('Search Sequence'), 'input': 'sequence'},
            'Salesperson': {'label': _('Search Salesperson'), 'input': 'salesperson'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        if search and search_in and (search_domain := self._get_opportunity_search_domain(search_in, search, 'lead')):
            domain = AND([domain, search_domain])

        # count for pager
        lead_count = CrmLead.sudo().search_count(domain)
        # pager
        pager = request.website.pager(
            url="/my/leads",
            url_args={
                'date_begin': date_begin,
                'date_end': date_end,
                'sortby': sortby,
                'groupby': groupby,
                'search_in': search_in,
                'search': search
            },
            total=lead_count,
            page=page,
            step=self._items_per_page
        )

        # content according to pager and archive selected
        leads = CrmLead.sudo().search(domain, order=order, limit=self._items_per_page if groupby == 'none' else 0, offset=pager['offset'])

        # Group leads if groupby is set
        if groupby != 'none':
            input_field = searchbar_groupby[groupby]['input']
            grouped_leads = [{input_field: k, 'leads': request.env['crm.lead'].concat(*g)}
                             for k, g in groupbyelem(leads, itemgetter(input_field))]
        else:
            grouped_leads = [{'leads': leads}]

        values.update({
            'date': date_begin,
            'leads': leads,
            'lead_stages': lead_stages,
            'page_name': 'lead',
            'pager': pager if groupby == 'none' else False,
            'default_url': '/my/leads',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_groupby': searchbar_groupby,
            'groupby': groupby,
            'search_in': search_in,
            'search': search,
            'searchbar_inputs': searchbar_inputs,
            'grouped_leads': grouped_leads,
            'can_create_lead': request.env['crm.lead'].check_access('create'),
        })
        return request.render("website_crm_partner_assign.portal_my_leads", values)

    @http.route(['/my/lead/<int:lead_id>'], type='http', auth="user", website=True)
    def portal_my_lead(self, lead_id, **kw):
        try:
            lead_sudo = self._document_check_access('crm.lead', lead_id)
        except (AccessError, ValidationError):
            return request.redirect('/my/leads')
        lead_sudo = request.env['crm.lead'].sudo().browse(lead_id)
        unit_types = request.env['crm.lead']._fields['unit_type'].selection
        finish_types = request.env['crm.lead']._fields['finish_type'].selection
        priorities = request.env['crm.lead']._fields['priority'].selection
        lost_reasons = request.env['crm.lost.reason'].sudo().search([])
        print('lost_reasons', lost_reasons)

        values = {
            'lead': lead_sudo,
            'lead_stages': request.env['lead.stage'].search([], order='sequence asc'),
            'user_activity': lead_sudo.sudo().activity_ids.filtered(
                lambda activity: activity.user_id == request.env.user)[:1],
            'activity_types': request.env['mail.activity.type'].sudo().search(
                ['|', ('res_model', '=', lead_sudo._name), ('res_model', '=', False)]),
            'states': request.env['res.country.state'].sudo().search([]),
            'countries': request.env['res.country'].sudo().search([]),
            'page_name': 'lead',
            'unit_types': unit_types,
            'finish_types': finish_types,
            'priorities': priorities,
            'user': request.env.user,
            'messages': [],
            'lost_reasons': lost_reasons,
        }
        return request.render("website_crm_partner_assign.portal_my_lead", values)

    def get_mail_messages(self, lead):
        messages = request.env['mail.message'].sudo().search([
            ('model', '=', 'crm.lead'),
            ('res_id', '=', lead.id),
            ('message_type', '!=', 'comment'),
            '|', ('body', '!=', False), ('tracking_value_ids', '!=', False)
        ], order='date DESC')

        messages = messages.filtered(
            lambda message: message.author_id.id == request.env.user.partner_id.id or message.author_id == False)

        message_vals = []
        for message in messages:
            tracking_values = message.sudo().tracking_value_ids._filter_has_field_access(request.env)
            formatted_tracking = tracking_values._tracking_value_format()
            message_vals.append({
                'author_id': message.author_id,
                'date': message.date,
                'body': message.body,
                'formatted_tracking': formatted_tracking,
            })
        return message_vals

    @http.route(['/my/opportunities', '/my/opportunities/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_opportunities(self, page=1, date_begin=None, date_end=None, sortby=None, groupby='none', search=None, search_in='all', **kw):
        values = self._prepare_portal_layout_values()
        CrmLead = request.env['crm.lead']

        domain = self.get_domain_my_opp(request.env.user)
        opp_stages = request.env['crm.stage'].search([], order='sequence desc')

        # Add groupby options
        searchbar_groupby = {
            'none': {'input': 'none', 'label': _('None')},
            'stage': {'input': 'stage_id', 'label': _('Stage')},
            'project': {'input': 'project_id', 'label': _('Project')},
            'user_id': {'input': 'user_id', 'label': _('Salesperson')},
        }

        # Default groupby none
        if not groupby:
            groupby = 'none'

        searchbar_sortings = {
            'date': {'label': 'Newest', 'order': 'create_date desc'},
            'name': {'label': 'Name', 'order': 'name'},
            'stage': {'label': 'Stage', 'order': 'stage_id'},
            'date_open': {'label': 'Last Assignment Date', 'order': 'date_open desc'},
        }

        searchbar_inputs = {
            'All': {'label': _('Search All'), 'input': 'all'},
            'Number': {'label': _('Search Number'), 'input': 'number'},
            'Contract': {'label': _('Search Contact'), 'input': 'contact'},
            'Sequence': {'label': _('Search Sequence'), 'input': 'sequence'},
            'Salesperson': {'label': _('Search Salesperson'), 'input': 'salesperson'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        if search and search_in and (
                search_domain := self._get_opportunity_search_domain(search_in, search, 'opportunity')):
            domain = AND([domain, search_domain])

        # count for pager
        opp_count = CrmLead.sudo().search_count(domain)

        # pager
        pager = request.website.pager(
            url="/my/opportunities",
            url_args={
                'date_begin': date_begin,
                'date_end': date_end,
                'sortby': sortby,
                'groupby': groupby,
                'search_in': search_in,
                'search': search,
            },
            total=opp_count,
            page=page,
            step=self._items_per_page
        )

        # content according to pager and archive selected
        opportunities = CrmLead.sudo().search(domain, order=searchbar_sortings[sortby]['order'], limit=self._items_per_page,
                                       offset=pager['offset'])

        # Group opportunities based on selected grouping
        if groupby == 'project':
            # Group by project_id
            grouped_opps = [{'project_id': k, 'opportunities': request.env['crm.lead'].concat(*g)}
                            for k, g in groupbyelem(opportunities, itemgetter('project_id'))]
        elif groupby == 'stage':
            # Group by stage_id
            grouped_opps = [{'stage_id': k, 'opportunities': request.env['crm.lead'].concat(*g)}
                            for k, g in groupbyelem(opportunities, itemgetter('stage_id'))]
        elif groupby == 'user_id':
            # Group by user_id
            grouped_opps = [{'user_id': k, 'opportunities': request.env['crm.lead'].concat(*g)}
                            for k, g in groupbyelem(opportunities, itemgetter('user_id'))]
        elif groupby == 'is_fresh':
            # Group by user_id
            grouped_opps = [{'is_fresh': k, 'opportunities': request.env['crm.lead'].concat(*g)}
                            for k, g in groupbyelem(opportunities, itemgetter('is_fresh'))]
        else:
            # No grouping
            grouped_opps = [{'opportunities': opportunities}]

        values.update({
            'date': date_begin,
            'opportunities': opportunities,
            'opp_stages': opp_stages,
            'page_name': 'opportunity',
            'pager': pager,
            'default_url': '/my/opportunities',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_groupby': searchbar_groupby,
            'groupby': groupby,
            'grouped_opps': grouped_opps,
            'searchbar_inputs': searchbar_inputs,
            'search_in': search_in,
            'search': search,
        })
        return request.render("website_crm_partner_assign.portal_my_opportunities", values)

    @http.route(['''/my/opportunity/<model('crm.lead', "[('type','=', 'opportunity')]"):opp>'''], type='http',
                auth="user", website=True)
    def portal_my_opportunity(self, opp, **kw):
        if opp.type != 'opportunity':
            raise NotFound()
        unit_types = request.env['crm.lead']._fields['unit_type'].selection
        finish_types = request.env['crm.lead']._fields['finish_type'].selection
        priorities = request.env['crm.lead']._fields['priority'].selection
        lost_reasons = request.env['crm.lost.reason'].sudo().search([])

        return request.render(
            "website_crm_partner_assign.portal_my_opportunity", {
                'opportunity': opp,
                'user_activity': opp.sudo().activity_ids.filtered(
                    lambda activity: activity.user_id == request.env.user)[:1],
                'stages': request.env['crm.stage'].search(['|', ('team_id', '=', False), ('team_id', '=', opp.team_id.id)],
                                                          order='sequence desc, name desc, id desc'),
                'activity_types': request.env['mail.activity.type'].sudo().search(
                    ['|', ('res_model', '=', opp._name), ('res_model', '=', False)]),
                'states': request.env['res.country.state'].sudo().search([]),
                'countries': request.env['res.country'].sudo().search([]),
                'unit_types': unit_types,
                'finish_types': finish_types,
                'priorities': priorities,
                'messages': [],
                'lost_reasons': lost_reasons,
            })


    @http.route(['/my/lead/create'], type='http', methods=["POST", "GET"], auth="user", website=True)
    def portal_create_lead(self, **kwargs):
        if request.httprequest.method == 'POST':
            # if not request.env['crm.lead'].check_access('create'):
            #     return request.redirect('/my/leads')
            try:
                def parse_date(date_str):
                    return date_str if date_str and date_str.strip() else False

                # Prepare lead values
                lead_values = {
                    # Basic Information
                    'name': kwargs.get('name'),
                    'partner_id': int(kwargs.get('partner_id')) if kwargs.get('partner_id') else False,
                    'lead_stage_id': int(kwargs.get('lead_stage_id')) if kwargs.get('lead_stage_id') else False,
                    'contact_name': kwargs.get('contact_name'),
                    'partner_name': kwargs.get('partner_name'),
                    'function': kwargs.get('function'),
                    'phone': kwargs.get('phone'),
                    'mobile': kwargs.get('mobile'),
                    'email_from': kwargs.get('email_from'),
                    'email_cc': kwargs.get('email_cc'),

                    # Lead Classification
                    'type': 'lead',
                    'interested_in': kwargs.get('interested_in'),
                    'buying_type': kwargs.get('buying_type'),
                    'buying_purpose': kwargs.get('buying_purpose'),
                    'priority': kwargs.get('priority'),

                    # Project Related
                    'developer_id': int(kwargs.get('developer_id')) if kwargs.get('developer_id') else False,
                    'project_id': int(kwargs.get('project_id')) if kwargs.get('project_id') else False,
                    'dest_country_id': int(kwargs.get('dest_country_id')) if kwargs.get('dest_country_id') else False,
                    'governorate_id': int(kwargs.get('government_id')) if kwargs.get('government_id') else False,
                    'dest_city_id': int(kwargs.get('governorate_id')) if kwargs.get('governorate_id') else False,
                    'project_city': kwargs.get('project_city'),
                    'neighborhood_id': int(kwargs.get('neighborhood_id')) if kwargs.get('neighborhood_id') else False,

                    # Property Specifications
                    'unit_type': kwargs.get('unit_type'),
                    'unit_number': kwargs.get('unit_number'),
                    'finish_type': kwargs.get('finish_type'),
                    'furniture_type': kwargs.get('furniture_type'),
                    'place_preferences': kwargs.get('place_preferences'),
                    'ready_to_move': kwargs.get('ready_to_move') == 'on',

                    # Measurements
                    'number_of_bedrooms': int(kwargs.get('number_of_bedrooms')) if kwargs.get(
                        'number_of_bedrooms') else 0,
                    'number_of_bathrooms': int(kwargs.get('number_of_bathrooms')) if kwargs.get(
                        'number_of_bathrooms') else 0,
                    'building_area': int(kwargs.get('building_area')) if kwargs.get('building_area') else 0,
                    'garden_area': int(kwargs.get('garden_area')) if kwargs.get('garden_area') else 0,
                    'land_area': int(kwargs.get('land_area')) if kwargs.get('land_area') else 0,
                    'min_area': float(kwargs.get('min_area')) if kwargs.get('min_area') else 0.0,
                    'max_area': float(kwargs.get('max_area')) if kwargs.get('max_area') else 0.0,
                    'min_price': int(kwargs.get('min_price')) if kwargs.get('min_price') else 0,
                    'max_price': int(kwargs.get('max_price')) if kwargs.get('max_price') else 0,

                    # Sales Information
                    'user_id': int(kwargs.get('user_id'), 0),
                    # 'team_id': kwargs.get('team_id'),
                    'company_id': int(kwargs.get('company_id')) if kwargs.get('company_id') else False,
                    'sales_volume': int(kwargs.get('sales_volume')) if kwargs.get('sales_volume') else 0,

                    # Dates
                    'date_open': parse_date(kwargs.get('date_open')),
                    'date_closed': parse_date(kwargs.get('date_closed')),
                    'follow_up_date': parse_date(kwargs.get('follow_up_date')),

                    # UTM Tracking
                    'campaign_id': int(kwargs.get('campaign_id')) if kwargs.get('campaign_id') else False,
                    'medium_id': int(kwargs.get('medium_id')) if kwargs.get('medium_id') else False,
                    'source_id': int(kwargs.get('source_id')) if kwargs.get('source_id') else False,
                    'channel': kwargs.get('channel') if kwargs.get('channel') else False,
                    'campaign_form_name': kwargs.get('campaign_form_name') if kwargs.get('campaign_form_name') else False,
                    'media_buyer': kwargs.get('media_buyer') if kwargs.get('media_buyer') else False,

                    # Extra Contact Information
                    'phone1': kwargs.get('phone1'),
                    'phone2': kwargs.get('phone2'),
                    'phone3': kwargs.get('phone3'),
                    'phone4': kwargs.get('phone4'),

                    # Address Information
                    'street': kwargs.get('street'),
                    'street2': kwargs.get('street2'),
                    'city': kwargs.get('city'),
                    'state_id': int(kwargs.get('state_id')) if kwargs.get('state_id') else False,

                    #Extra Customer Info
                    'gender': kwargs.get('gender') if kwargs.get('gender') else False,
                    'marital_status': kwargs.get('marital_status') if kwargs.get('marital_status') else False,
                    'num_of_childrens': int(kwargs.get('children')) if kwargs.get('children') else False,
                    'hoppies': kwargs.get('hoppy') if kwargs.get('hoppy') else False,

                    # Additional Information
                    'referred': kwargs.get('referred'),
                    'partner_assigned_id': request.env.user.commercial_partner_id.id,
                    'duplicate_portal': kwargs.get('duplicate_portal'),  # Will be passed to model

                    # 'page_name': 'portal_create_lead'
                }

                # Clean up empty values
                lead_values = {k: v for k, v in lead_values.items() if v not in ('', None)}
                lead = request.env['crm.lead'].create(lead_values)
                return request.redirect('/my/leads')

            except (AccessError, ValidationError) as e:
                raise UserError(str(e))
                # return request.render("arkzayed_18_realestate_broker.portal_create_lead", {
                #     'error': f"There is an error {str(e)}",
                #     'values': kwargs,
                # })

            except Exception as e:
                raise UserError(str(e))
                # return request.render("arkzayed_18_realestate_broker.portal_create_lead", {
                #     'error': f"There is an error {str(e)}",
                #     'values': kwargs,
                # })

        # GET request - render empty form
        values = {
            'lead_stages': request.env['lead.stage'].search([], order='sequence asc'),
            'page_name': 'create_lead'
        }
        return request.render("arkzayed_18_realestate_broker.portal_create_lead", values)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        CrmLead = request.env['crm.lead'].sudo()
        if 'lead_count' in counters:
            values['lead_count'] = (
                CrmLead.search_count(self.get_domain_my_lead(request.env.user))
                if CrmLead.has_access('read')
                else 0
            )
        if 'opp_count' in counters:
            values['opp_count'] = (
                CrmLead.search_count(self.get_domain_my_opp(request.env.user))
                if CrmLead.has_access('read')
                else 0
            )
        return values

    @http.route(['/my/lead/update_stage'], type='json', auth="user", website=True)
    def update_lead_stage(self, lead_id, stage_id, **kw):
        try:
            lead = request.env['crm.lead'].browse(int(lead_id))
            if lead.exists() and lead.check_access_rights('write', raise_exception=True):
                lead.sudo().write({'lead_stage_id': int(stage_id)})
                return {'success': True}
        except Exception as e:
            return {'error': str(e)}
        return {'error': 'Unknown error occurred'}

    # @http.route(['/my/lead/state_to_unqualified'], type='json', auth="user", website=True)
    # def state_to_unqualified_state(self, lead_id, reasons, **kw):
    #     try:
    #         lead = request.env['crm.lead'].browse(int(lead_id))
    #
    #         if not lead.exists() or not lead.check_access_rights('write', raise_exception=True):
    #             return {'error': 'Access Denied'}
    #
    #         if not reasons:
    #             return {'error': 'Cancel Reason Is Required'}
    #
    #         lead.sudo().write({
    #             'reasons': reasons,
    #             'lead_stage_id': request.env.ref('arkzayed_18_realestate_broker.stage_new').id
    #         })
    #         return {'success': True}
    #     except Exception as e:
    #         return {'error': str(e)}

    @http.route(['/my/lead/call_later'], type='json', auth="user", website=True)
    def action_call_later(self, lead_id, **kw):
        try:
            lead = request.env['crm.lead'].browse(int(lead_id))
            if not lead.exists() or not lead.check_access_rights('write', raise_exception=True):
                return {'error': 'Access Denied'}

            call_activity_object = request.env['mail.activity.type'].search([('name', '=', 'Call')])
            lead.sudo().write({'lost_reason_id': False})

            activity_vals = {
                'res_id': lead.id,
                'res_model': lead._name,
                'activity_type_id': call_activity_object.id,
            }
            request.env['mail.activity'].sudo().create(activity_vals)

            return {'success': True}
        except Exception as e:
            return {'error': str(e)}

    @http.route(['/my/lead/no_answer'], type='json', auth="user", website=True)
    def action_no_answer(self, lead_id, **kw):
        try:
            lead = request.env['crm.lead'].browse(int(lead_id))
            if not lead.exists() or not lead.check_access_rights('write', raise_exception=True):
                return {'error': 'Access Denied'}

            lead.sudo().write({
                'lost_reason_id': False,
                'lead_stage_id': request.env.ref('arkzayed_18_realestate_broker.stage_no_answer').id
            })
            return {'success': True}
        except Exception as e:
            return {'error': str(e)}

    @http.route(['/my/lead/qualified'], type='json', auth="user", website=True)
    def action_qualified_lead(self, lead_id, **kw):
        try:
            lead = request.env['crm.lead'].browse(int(lead_id))
            if not lead.exists() or not lead.check_access_rights('write', raise_exception=True):
                return {'error': 'Access Denied'}

            if lead.sales_volume <= 0 and lead.type == 'opportunity':
                return {'error': 'Please Update Sales Volume'}

            lead.sudo().write({
                'lost_reason_id': False,
                'lead_stage_id': request.env.ref('arkzayed_18_realestate_broker.stage_qualified').id
            })
            return {'success': True}
        except Exception as e:
            return {'error': str(e)}

    def _get_opportunity_search_domain(self, search_in, search, type):
        search_domains = []
        if search_in in ('all', 'number'):
            search_domains.append([('mobile', 'ilike', search)])
            search_domains.append([('phone', 'ilike', search)])
            search_domains.append([('phone1', 'ilike', search)])
            search_domains.append([('phone2', 'ilike', search)])
            search_domains.append([('phone3', 'ilike', search)])
            search_domains.append([('phone4', 'ilike', search)])

        if search_in in ('all', 'contact'):
            search_domains.append([('partner_id.name', 'ilike', search)])
        if search_in in ('all', 'sequence'):
            if type == 'opportunity':
                search_domains.append([('opportunity_sequence', 'ilike', search)])
            else:
                search_domains.append([('lead_sequence', 'ilike', search)])
        if search_in in ('all', 'salesperson'):
            search_domains.append([('user_id.name', 'ilike', search)])

        return OR(search_domains) if search_domains else []
