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

    # R4: the precision the sum-to-100 split rule compares against, rather than a literal 2
    # in the engine. Phase 6 puts rounding rules in Financials; this is the first of them, and
    # it defaults to 2 so the rule behaves exactly as it did before the setting existed.
    # A scalar default IS backfilled onto existing rows by Odoo, unlike the Many2many defaults
    # S7 had to seed explicitly.
    split_percentage_precision = fields.Integer(
        string='Split Percentage Decimals', default=2,
        help="Decimal places used when checking that a split adds up to 100%. Raise it if you "
             "allocate ownership to more than two decimals.")

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
