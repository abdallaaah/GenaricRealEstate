from odoo import api, fields, models
from odoo.exceptions import AccessError


class BrokerFeatureFlag(models.Model):
    """Centralized on/off switch for an optional feature.

    Menus, QWeb templates, portal controllers, and the commission engine all
    call :meth:`is_feature_enabled` / :meth:`_check_feature` instead of each
    re-implementing the same lookup, so disabling a feature here reliably
    restricts every surface at once instead of only hiding a menu entry.

    Originally portal-only; generalized because the commission engine needs the
    same per-client toggling (segmentation, retroactive effect, team rollup).
    The ``is_portal_feature_enabled``/``_check_portal_feature`` names are kept
    as the portal's entry points so existing callers are untouched.
    """
    _name = 'broker.feature.flag'
    _description = "Broker Feature Flag"

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    category = fields.Selection([
        ('portal', "Portal"),
        ('commission', "Commission"),
    ], default='portal', required=True,
        help="Which area of the platform this flag belongs to. Used only to group the list.")
    enabled = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    _unique_code_per_company = models.UniqueIndex('(code, company_id)')

    @api.model
    def is_feature_enabled(self, code, company=None, default=True):
        """Is `code` enabled for `company` (the current company by default)?

        `default` is the answer when no flag record exists at all. Portal
        features fail open (a newly installed page should not be invisible
        until someone configures a flag). Features that move money -- the
        commission ones -- pass ``default=False`` and ship an explicit seed
        record instead, so an upgrade can never switch one on by itself.
        """
        company = company or self.env.company
        FeatureFlag = self.sudo()
        # Deliberately two searches rather than one ordered by company_id desc: in
        # Postgres, DESC sorts NULLs first, so a global row would have outranked a
        # company-specific override -- the opposite of the intent. Company first, then
        # the global fallback.
        flag = FeatureFlag.search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
        if not flag:
            flag = FeatureFlag.search([('code', '=', code), ('company_id', '=', False)], limit=1)
        return flag.enabled if flag else default

    @api.model
    def _check_feature(self, code, company=None, default=True):
        if not self.is_feature_enabled(code, company=company, default=default):
            raise AccessError(self.env._("This feature is not available."))

    @api.model
    def _set_flag(self, code, name, enabled, category='portal', company=None):
        """Upsert the flag record for `code`, creating it on first use.

        sudo() because the callers are Settings pages, where access is already
        gated by base.group_system; without it, flipping a checkbox there would
        additionally require group_broker_admin on this model.
        """
        company = company or self.env.company
        FeatureFlag = self.sudo()
        flag = FeatureFlag.search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
        if flag:
            flag.enabled = enabled
        else:
            FeatureFlag.create({
                'code': code, 'name': name, 'category': category,
                'enabled': enabled, 'company_id': company.id,
            })

    @api.model
    def is_portal_feature_enabled(self, code, company=None):
        return self.is_feature_enabled(code, company=company)

    @api.model
    def _check_portal_feature(self, code, company=None):
        self._check_feature(code, company=company)
