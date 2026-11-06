from odoo import _, models
from odoo.exceptions import UserError

from ..config.approval_settings import APPROVAL_STAGES


class ApprovalGate(models.AbstractModel):
    """S7: the one helper every approval gate calls.

    Before S7, each gate called `has_group()` on a hardcoded xmlid, so who could approve was
    frozen in the source. Now the gate names its *stage* and the helper reads the configured
    groups from the company. The gate itself still lives in code and cannot be disabled -
    section 11 allows configuring *who* approves, never *whether* the check runs.
    """
    _name = 'realestate.approval.gate'
    _description = 'Approval Gate Helper'

    def _approval_company(self):
        """The company whose configuration governs this record."""
        company = self.company_id if 'company_id' in self._fields else False
        return company or self.env.company

    def _user_can_approve(self, stage, user=None):
        """True when `user` (default: the current user) may pass `stage`.

        Rules, in order:
          * approvals turned off -> True (the stage is not required)
          * no group configured  -> refuse loudly, never silently allow
          * otherwise            -> membership of any configured group

        Reads the configuration at call time, so a group change applies to records that are
        already pending (decision 1).
        """
        self.ensure_one() if self else None
        user = user or self.env.user
        company = self._approval_company()

        if not company.approval_enabled:
            return True

        groups = company._approver_groups(stage)
        if not groups:
            raise UserError(_(
                "No approver group is configured for the '%(stage)s' stage on company "
                "'%(company)s', so this action cannot be approved.\n\n"
                "Configure it in Settings > Real Estate Sales > Sales Setup.",
                stage=APPROVAL_STAGES.get(stage, {}).get('label', stage),
                company=company.name))

        return bool(set(groups.ids) & set(user.groups_id.ids))

    def _matched_approver_group(self, stage, user=None):
        """Which configured group the user matched on, for the audit row."""
        user = user or self.env.user
        groups = self._approval_company()._approver_groups(stage)
        return next((g for g in groups if g in user.groups_id), self.env['res.groups'])

    def _require_approval(self, stage, message=None):
        """Gate + raise. The single call site shape for an approval check."""
        if self._user_can_approve(stage):
            return True
        raise UserError(message or _(
            "You are not allowed to perform the '%(stage)s' step.",
            stage=APPROVAL_STAGES.get(stage, {}).get('label', stage)))

    def _log_approval(self, stage):
        """Record who approved, when, and the group they matched on (decision 3)."""
        self.ensure_one()
        return self.env['realestate.approval.audit'].sudo().create({
            'entry_type': 'approval',
            'company_id': self._approval_company().id,
            'stage': stage,
            'approver_id': self.env.user.id,
            'matched_group_id': self._matched_approver_group(stage).id,
            'res_model': self._name,
            'res_id': self.id,
        })
