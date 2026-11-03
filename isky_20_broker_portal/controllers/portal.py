from odoo.http import request
from odoo.addons.website_crm_partner_assign.controllers.main import WebsiteAccount

from ..models.portal_feature_codes import (
    PORTAL_FEATURE_CRM, PORTAL_FEATURE_PERMISSION_REQUESTS, PORTAL_FEATURE_UNITS,
)


class BrokerPortalAccount(WebsiteAccount):
    """Broadens the stock website_crm_partner_assign reseller-portal domains
    (which only show leads where the portal user is the assigned reseller
    partner) to iSky's actual portal usage: portal users are brokerage
    salespeople/team leads/split-deal participants, matched by crm.lead.
    user_id / team hierarchy / sales_ids, same hierarchy used internally.
    """

    def portal_my_leads(self, *args, **kwargs):
        request.env['broker.feature.flag']._check_portal_feature(PORTAL_FEATURE_CRM)
        return super().portal_my_leads(*args, **kwargs)

    def portal_my_opportunities(self, *args, **kwargs):
        request.env['broker.feature.flag']._check_portal_feature(PORTAL_FEATURE_CRM)
        return super().portal_my_opportunities(*args, **kwargs)

    def portal_my_lead(self, *args, **kwargs):
        request.env['broker.feature.flag']._check_portal_feature(PORTAL_FEATURE_CRM)
        return super().portal_my_lead(*args, **kwargs)

    def portal_my_opportunity(self, *args, **kwargs):
        request.env['broker.feature.flag']._check_portal_feature(PORTAL_FEATURE_CRM)
        return super().portal_my_opportunity(*args, **kwargs)

    def get_domain_my_lead(self, user):
        return [
            ('type', '=', 'lead'),
            '|', ('user_id', '=', user.id), ('user_id.sale_team_id.user_id', '=', user.id),
        ]

    def get_domain_my_opp(self, user):
        return [
            ('type', '=', 'opportunity'),
            '|', '|', '|',
            ('user_id', '=', user.id),
            ('user_id.sale_team_id.user_id', '=', user.id),
            ('sales_ids', 'in', user.id),
            ('commission_ids.employee_id', 'in', user.id),
        ]

    def _prepare_portal_counter_values(self, counter):
        FeatureFlag = request.env['broker.feature.flag']
        if counter == 'permission_request_count' and FeatureFlag.is_portal_feature_enabled(
                PORTAL_FEATURE_PERMISSION_REQUESTS):
            return 'permission.request', [('requester_id', '=', request.env.user.id)], 'read'
        if counter == 'broker_unit_count' and FeatureFlag.is_portal_feature_enabled(PORTAL_FEATURE_UNITS):
            return 'broker.unit', [('seller_sales_person', '=', request.env.user.id)], 'read'
        if counter in ('lead_count', 'opp_count') and not FeatureFlag.is_portal_feature_enabled(PORTAL_FEATURE_CRM):
            return False, False, False
        return super()._prepare_portal_counter_values(counter)
