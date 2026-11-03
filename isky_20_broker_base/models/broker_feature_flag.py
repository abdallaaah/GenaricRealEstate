from odoo import api, fields, models
from odoo.exceptions import AccessError


class BrokerFeatureFlag(models.Model):
    """Centralized on/off switch for a portal-facing feature.

    Menus, QWeb templates, and portal controllers all call
    :meth:`is_portal_feature_enabled` / :meth:`_check_portal_feature` instead of
    each re-implementing the same lookup, so disabling a feature here reliably
    restricts every surface at once instead of only hiding a menu entry.
    """
    _name = 'broker.feature.flag'
    _description = "Broker Portal Feature Flag"

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    enabled = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    _unique_code_per_company = models.UniqueIndex('(code, company_id)')

    @api.model
    def is_portal_feature_enabled(self, code, company=None):
        company = company or self.env.company
        flag = self.sudo().search([
            ('code', '=', code),
            ('company_id', 'in', [company.id, False]),
        ], order='company_id desc', limit=1)
        # Fail open: a feature with no configured flag record is enabled by
        # default, so installing a new portal feature does not silently hide it.
        return flag.enabled if flag else True

    @api.model
    def _check_portal_feature(self, code, company=None):
        if not self.is_portal_feature_enabled(code, company=company):
            raise AccessError(self.env._("This feature is not available."))
