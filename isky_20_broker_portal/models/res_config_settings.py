from odoo import api, fields, models

from .portal_feature_codes import PORTAL_FEATURE_CRM, PORTAL_FEATURE_PERMISSION_REQUESTS, PORTAL_FEATURE_UNITS


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    restrict_portal_chatter_to_own_messages = fields.Boolean(
        config_parameter='isky_20_broker_portal.restrict_chatter',
        default=True,
        help="A portal salesperson/broker sharing a lead with colleagues only sees their own "
             "chatter messages (plus system messages), not their colleagues'. They can still "
             "post a new message. Internal users are never affected.")
    portal_feature_crm_enabled = fields.Boolean(
        string="Portal: Leads & Opportunities", compute='_compute_portal_feature_flags',
        inverse='_inverse_portal_feature_crm')
    portal_feature_units_enabled = fields.Boolean(
        string="Portal: Units", compute='_compute_portal_feature_flags', inverse='_inverse_portal_feature_units')
    portal_feature_permission_requests_enabled = fields.Boolean(
        string="Portal: Permission Requests", compute='_compute_portal_feature_flags',
        inverse='_inverse_portal_feature_permission_requests')

    @api.depends_context('company')
    def _compute_portal_feature_flags(self):
        FeatureFlag = self.env['broker.feature.flag']
        for settings in self:
            settings.portal_feature_crm_enabled = FeatureFlag.is_portal_feature_enabled(PORTAL_FEATURE_CRM)
            settings.portal_feature_units_enabled = FeatureFlag.is_portal_feature_enabled(PORTAL_FEATURE_UNITS)
            settings.portal_feature_permission_requests_enabled = FeatureFlag.is_portal_feature_enabled(
                PORTAL_FEATURE_PERMISSION_REQUESTS)

    def _inverse_portal_feature_crm(self):
        self._set_portal_feature_flag(PORTAL_FEATURE_CRM, "Leads & Opportunities", self.portal_feature_crm_enabled)

    def _inverse_portal_feature_units(self):
        self._set_portal_feature_flag(PORTAL_FEATURE_UNITS, "Units", self.portal_feature_units_enabled)

    def _inverse_portal_feature_permission_requests(self):
        self._set_portal_feature_flag(
            PORTAL_FEATURE_PERMISSION_REQUESTS, "Permission Requests", self.portal_feature_permission_requests_enabled)

    def _set_portal_feature_flag(self, code, name, enabled):
        # Settings access itself (base.group_system) is the real gate here; sudo() so the
        # setting doesn't additionally require the separate group_broker_admin on
        # broker.feature.flag just to flip a checkbox on this page.
        FeatureFlag = self.env['broker.feature.flag'].sudo()
        flag = FeatureFlag.search([
            ('code', '=', code), ('company_id', '=', self.env.company.id),
        ], limit=1)
        if flag:
            flag.enabled = enabled
        else:
            FeatureFlag.create({
                'code': code, 'name': name, 'enabled': enabled, 'company_id': self.env.company.id,
            })
