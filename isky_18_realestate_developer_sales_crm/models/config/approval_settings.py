from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)

# S7: the approval stages whose approver groups are configurable.
#
#   key -> (res.company field, default group xmlid, human label)
#
# Section 11 fixes the shape: the groups are configurable, the gates stay in code, and one
# company switch turns the approval step on or off. Nothing here can disable a gate - only
# change who satisfies it.
#
# Two stages in the S7 spec have no Python gate in this module and are included so the
# configuration is complete and the form is not misleading:
#   - operation_manager: referenced only from legacy views (groups= attributes)
#   - show_discount:     likewise, view-only
# Both are marked has_python_gate=False below. See the decisions log for why they were kept.
APPROVAL_STAGES = {
    # --- Setting B: the contract chain -------------------------------------------------
    'finance': {
        'field': 'finance_approver_group_ids',
        'default': 'isky_18_realestate_developer_sales_crm.group_finance_approval',
        'label': 'Finance Approval',
        'has_python_gate': True,
    },
    'finance_two': {
        'field': 'finance_two_approver_group_ids',
        'default': 'isky_18_realestate_developer_sales_crm.group_finance_two_approval',
        'label': 'Second Finance Approval',
        'has_python_gate': True,
    },
    'manager': {
        'field': 'manager_approver_group_ids',
        'default': 'isky_18_realestate_developer_sales_crm.group_manager_approval',
        'label': 'Manager Approval',
        'has_python_gate': True,
    },
    'operation_manager': {
        'field': 'operation_manager_approver_group_ids',
        # The S7 spec names sales_crm.group_operation_manager_approval, which does not exist:
        # the group is defined in arkzayed_18_realestate_development and referenced only from
        # legacy views. No default is set rather than pointing at a group this module cannot
        # see. Configure it explicitly, or leave it unused.
        'default': None,
        'label': 'Sales Sector Manager Approval',
        'has_python_gate': False,
    },
    # --- Setting C: reservation and discount -------------------------------------------
    'confirm_reservation': {
        'field': 'confirm_reservation_group_ids',
        'default': 'isky_18_realestate_developer_sales_crm.group_confirm_reservation',
        'label': 'Confirm Reservation',
        'has_python_gate': True,
    },
    'show_discount': {
        'field': 'show_discount_group_ids',
        'default': 'isky_18_realestate_developer_sales_crm.group_show_discount_percentage',
        'label': 'Show Discount Percentage',
        'has_python_gate': False,
    },
    'edit_discount': {
        'field': 'edit_discount_group_ids',
        'default': 'isky_18_realestate_developer_sales_crm.group_edit_discount_percentage',
        'label': 'Edit Discount Percentage',
        'has_python_gate': True,
    },
    'manual_paid': {
        'field': 'manual_paid_group_ids',
        'default': 'isky_18_realestate_developer_sales_crm.group_manual_paid_installment',
        'label': 'Can Tick Installments as Paid',
        'has_python_gate': True,
    },
}

# Gates that are never configurable and are never skipped by the on/off switch
# (section 11, decision 4). Listed here so the rule is visible in one place.
#
# SG-D1/SG-D2 (2026-11-10, owner): the two signing gates joined this list, moving OUT of the
# configurable stage registry above. One group - the Director - signs everything, and
# `approval_enabled = False` does not skip signing. This is the recorded exception to S7
# decision 2: signing is the first gate that began life as a configurable stage (`sign_client`,
# 2026-11-08) and was then made exempt from the switch. The group is changed by editing its
# members, never through Sales Setup (SG-D3).
#
# `sale.proposal.write()` enforces these with the labels below; keep key, group and label
# together so the gate and its refusal message cannot drift apart.
NON_CONFIGURABLE_GATES = {
    'block_unit': 'isky_18_realestate_developer_unit_inventory.group_block_unit',
    'exception_reservation': 'isky_18_realestate_developer_sales_crm.group_exception_reservation',
    'sign_client': 'isky_18_realestate_developer_sales_crm.director_manager_group',
    'sign_ceo': 'isky_18_realestate_developer_sales_crm.director_manager_group',
}

# Labels for the signing gates' refusal messages and audit rows. Not in APPROVAL_STAGES on
# purpose: these are not stages, and putting them back there would re-grow a settings field.
NON_CONFIGURABLE_GATE_LABELS = {
    'sign_client': 'Sign by Client',
    'sign_ceo': 'Sign by CEO',
}


def _default_groups(xmlid):
    """Default factory for one stage. Resolves at install time; tolerates absence so a
    partial module set cannot break the install."""
    def _default(self):
        if not xmlid:
            return [(5, 0, 0)]
        group = self.env.ref(xmlid, raise_if_not_found=False)
        return [(6, 0, group.ids)] if group else [(5, 0, 0)]
    return _default


class ResCompany(models.Model):
    """S7: the approval settings. Company-level, so a multi-company database configures its
    approvers independently."""
    _inherit = 'res.company'

    approval_enabled = fields.Boolean(
        string='Require Approvals', default=True,
        help="When off, the approval stages are not required and the action is allowed to any "
             "user with the base access rights. It does NOT affect unit blocking or the "
             "reservation exception check, which are always enforced.")

    finance_approver_group_ids = fields.Many2many(
        'res.groups', 'company_finance_approver_rel', 'company_id', 'group_id',
        string='Finance Approvers',
        default=_default_groups(APPROVAL_STAGES['finance']['default']))
    finance_two_approver_group_ids = fields.Many2many(
        'res.groups', 'company_finance_two_approver_rel', 'company_id', 'group_id',
        string='Second Finance Approvers',
        default=_default_groups(APPROVAL_STAGES['finance_two']['default']))
    manager_approver_group_ids = fields.Many2many(
        'res.groups', 'company_manager_approver_rel', 'company_id', 'group_id',
        string='Manager Approvers',
        default=_default_groups(APPROVAL_STAGES['manager']['default']))
    operation_manager_approver_group_ids = fields.Many2many(
        'res.groups', 'company_op_manager_approver_rel', 'company_id', 'group_id',
        string='Sales Sector Manager Approvers',
        default=_default_groups(APPROVAL_STAGES['operation_manager']['default']))

    confirm_reservation_group_ids = fields.Many2many(
        'res.groups', 'company_confirm_reservation_rel', 'company_id', 'group_id',
        string='Can Confirm Reservations',
        default=_default_groups(APPROVAL_STAGES['confirm_reservation']['default']))
    show_discount_group_ids = fields.Many2many(
        'res.groups', 'company_show_discount_rel', 'company_id', 'group_id',
        string='Can See Discount Percentage',
        default=_default_groups(APPROVAL_STAGES['show_discount']['default']))
    edit_discount_group_ids = fields.Many2many(
        'res.groups', 'company_edit_discount_rel', 'company_id', 'group_id',
        string='Can Edit Discount Percentage',
        default=_default_groups(APPROVAL_STAGES['edit_discount']['default']))
    manual_paid_group_ids = fields.Many2many(
        'res.groups', 'company_manual_paid_rel', 'company_id', 'group_id',
        string='Can Tick Installments as Paid',
        default=_default_groups(APPROVAL_STAGES['manual_paid']['default']))

    # -- defaults for records that predate the fields --------------------------------------

    @api.model
    def _s7_apply_default_approver_groups(self):
        """Populate the approver groups on companies that already existed when this module was
        installed.

        A field `default=` only applies to records created afterwards. For a Many2many there is
        no column to backfill either, so Odoo populates nothing - and `res.company` is created
        during the `base` install, long before this module. Without this, every database (fresh
        ones included) installs with all eight stages empty, which is both a behaviour change
        and, with approvals on, an unsatisfiable gate.

        Idempotent and conservative: fills only stages that are currently empty, so a module
        update never overwrites what an administrator configured.
        """
        for company in self.sudo().search([]):
            vals = {}
            for spec in APPROVAL_STAGES.values():
                if company[spec['field']] or not spec['default']:
                    continue
                group = self.env.ref(spec['default'], raise_if_not_found=False)
                if group:
                    vals[spec['field']] = [(6, 0, group.ids)]
            if vals:
                # skip the audit trail for the install-time seed: it is the default, not a
                # change somebody made
                company.with_context(s7_skip_audit=True).write(vals)
        return True

    # -- reading the configuration ---------------------------------------------------------

    def _approver_groups(self, stage):
        """The configured approver groups for one stage. Read at the moment of the action, never
        snapshotted - decision 1: group changes apply retroactively, so a pending contract is
        approved by whoever is in the configured group when the approval happens."""
        self.ensure_one()
        spec = APPROVAL_STAGES.get(stage)
        if not spec:
            raise ValidationError(_("Unknown approval stage '%s'.", stage))
        return self[spec['field']]

    # -- validation and audit --------------------------------------------------------------

    @api.constrains('approval_enabled', *[s['field'] for s in APPROVAL_STAGES.values()])
    def _check_approver_groups_configured(self):
        """An approval stage with no group while approvals are on would be unsatisfiable, so
        the save is rejected rather than leaving a gate nobody can pass."""
        for company in self:
            if not company.approval_enabled:
                continue
            empty = [
                spec['label'] for spec in APPROVAL_STAGES.values()
                if spec['has_python_gate'] and not company[spec['field']]
            ]
            if empty:
                raise ValidationError(_(
                    "These approval stages have no approver group configured for company "
                    "'%(company)s': %(stages)s.\n\n"
                    "Either configure a group for each, or turn off 'Require Approvals'.",
                    company=company.name, stages=', '.join(empty)))

    def _warn_memberless_groups(self):
        """Decision in section 4 of the spec: a group with no members may be saved, but the save
        warns. A truly non-blocking save warning is only available client-side, so this logs
        server-side and res.config.settings raises it as an onchange warning in the form."""
        messages = []
        for company in self:
            for stage, spec in APPROVAL_STAGES.items():
                for group in company[spec['field']]:
                    if not group.users:
                        messages.append(_(
                            "Approver group '%(group)s' for stage '%(stage)s' has no members.",
                            group=group.display_name, stage=spec['label']))
        for m in messages:
            _logger.warning("S7 approval settings: %s", m)
        return messages

    def write(self, vals):
        """Audit every configuration change: who, when, old value, new value (decision 3)."""
        watched = {'approval_enabled'} | {s['field'] for s in APPROVAL_STAGES.values()}
        touched = watched.intersection(vals.keys())
        before = {}
        if touched:
            for company in self:
                before[company.id] = {
                    f: (company[f].ids if f != 'approval_enabled' else company[f])
                    for f in touched
                }
        res = super().write(vals)
        if touched and not self.env.context.get('s7_skip_audit'):
            Audit = self.env['realestate.approval.audit'].sudo()
            for company in self:
                for f in touched:
                    old = before.get(company.id, {}).get(f)
                    new = company[f].ids if f != 'approval_enabled' else company[f]
                    if old == new:
                        continue
                    Audit.create({
                        'entry_type': 'config',
                        'company_id': company.id,
                        'field_name': f,
                        'stage': next((k for k, s in APPROVAL_STAGES.items()
                                       if s['field'] == f), False),
                        'old_value': str(old),
                        'new_value': str(new),
                    })
            self._warn_memberless_groups()
        return res
