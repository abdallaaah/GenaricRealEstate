from odoo import api, models
from odoo.fields import Domain


class MailMessage(models.Model):
    """Restrict portal users to their own authored messages (plus authorless
    system/tracking messages) on crm.lead, on top of stock mail.message's own
    record-level access check. Stock Odoo already hides internal-only
    subtypes from portal users; this additionally hides *other salespeople's*
    regular comments on a lead/opportunity the customer happens to share,
    while still letting the customer post their own messages (the composer is
    unaffected -- this only narrows what _search returns).
    """
    _inherit = 'mail.message'

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        restrict = self.env['ir.config_parameter'].sudo().get_bool(
            'isky_20_broker_portal.restrict_chatter', True)
        if restrict and self.env.user.share and not self.env.su:
            own_or_system = Domain('author_id', '=', self.env.user.partner_id.id) | Domain('author_id', '=', False)
            domain = Domain(domain) & (Domain('model', '!=', 'crm.lead') | own_or_system)
        return super()._search(domain, offset, limit, order, **kwargs)
