from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Phase 3 step 5: the company-wide installments default (Sales Setup).

    Company-level rather than ir.config_parameter so a multi-company database can run one
    company on installments and another without."""
    _inherit = 'res.company'

    installments_enabled = fields.Boolean(
        string='Use Installments',
        default=True,
        help="Default for new projects. When off, deals in projects that inherit this default "
             "generate no installment or maintenance installment lines; the deal still "
             "completes. A project can override this.")

    def write(self, vals):
        """Lock rule (NEEDS REVIEW, see decisions log): the company default cannot be changed
        while a project that inherits it already has installment lines - flipping it would
        leave those lines against a schedule the company no longer generates.

        In write() rather than @api.constrains for the same reason as the project override:
        constrains would reject saving the company form at all once any such project existed.
        """
        if 'installments_enabled' in vals:
            for company in self:
                if company.installments_enabled == vals['installments_enabled']:
                    continue
                projects = self.env['realestate.project'].search([
                    ('installments_mode', '=', 'inherit'),
                    ('company_id', 'in', (company.id, False)),
                ])
                blocking = projects.filtered(lambda p: p._has_installment_lines())
                if blocking:
                    raise ValidationError(_(
                        "'Use Installments' cannot be changed for company '%(company)s': "
                        "%(count)d project(s) inheriting this default already have "
                        "installment lines (%(names)s).\n\n"
                        "Set those projects to an explicit On/Off override first, or change "
                        "the default before any installments are generated.",
                        company=company.name,
                        count=len(blocking),
                        names=', '.join(blocking.mapped('name')[:5]),
                    ))
        return super().write(vals)
