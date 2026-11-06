from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# job.level was defined twice (arkzayed_18_realestate_development and
# arkzayed_18_realestate_developer_crm) with slightly different flag sets and two
# same-named, non-super()-calling _flag_constrains methods - only the later-loaded one
# actually ran. Merged into one definition with every flag from both copies.
#
# Phase 4 added company scoping and `sequence`:
#   - the plan requires job levels defined per company, so the flag-uniqueness rule below
#     is now per company rather than global;
#   - `sequence` replaces the hardcoded position list the hierarchy engine used to carry
#     (['Sales Person', 'Sales Manager', ...]). Role identity and ordering are configuration
#     now, not literals in four copies of an algorithm. Lower sequence wins when one user
#     holds more than one role, which preserves the old behaviour of the lowest list index
#     taking precedence.

ROLE_FLAGS = [
    ('is_sales_person', 'Sales Person'),
    ('is_team_leader', 'Team Leader'),
    ('is_sales_manager', 'Sales Manager'),
    ('is_sales_sector_manager', 'Sales Sector Manager'),
    ('is_operations', 'Operations'),
    ('is_directory', 'Directory'),
]


class JobLevel(models.Model):
    _name = 'job.level'
    _description = 'Job Level'
    _order = 'sequence, id'

    name = fields.Char()
    sequence = fields.Integer(
        string='Sequence', default=10,
        help="Order in the commission hierarchy. When one person holds several roles on the "
             "same deal, the lowest sequence is the one recorded.")
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
        help="Job levels are defined per company; each role may be held by one job level "
             "per company.")

    is_sales_person = fields.Boolean(string='Is Sales Person')
    is_team_leader = fields.Boolean(string='Is Team Leader')
    is_directory = fields.Boolean(string='Is Directory')
    is_sales_manager = fields.Boolean(string='Is Sales Manager')
    is_operations = fields.Boolean(string='Is Operations')
    is_sales_sector_manager = fields.Boolean(string='Is Sales Sector Manager')

    @api.constrains('is_sales_person', 'is_team_leader', 'is_directory', 'is_sales_manager',
                    'is_operations', 'is_sales_sector_manager', 'company_id')
    def _flag_constrains(self):
        """At least one role per job level, and each role held by at most one job level
        **per company** (it used to be global, which a multi-company database cannot satisfy)."""
        for rec in self:
            if not any(rec[flag] for flag, _label in ROLE_FLAGS):
                raise ValidationError(_("At least one role must be selected."))

            for flag, label in ROLE_FLAGS:
                if not rec[flag]:
                    continue
                if self.search_count([
                    (flag, '=', True),
                    ('id', '!=', rec.id),
                    ('company_id', '=', rec.company_id.id),
                ]):
                    raise ValidationError(_(
                        "Only one job level per company can be marked as %(label)s.",
                        label=label))

    def _role_key(self):
        """A stable identity for the role this job level represents, used by the hierarchy
        engine to group people and to split a role's percentage between them. Falls back to
        the record id so an unflagged level still groups with itself rather than with every
        other unflagged level."""
        self.ensure_one()
        for flag, _label in ROLE_FLAGS:
            if self[flag]:
                return flag
        return 'job_level_%s' % self.id
