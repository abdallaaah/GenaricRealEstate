odoo.define('arkzayed_18_realestate_broker.lead_actions', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');
    var core = require('web.core');
    var _t = core._t;

    publicWidget.registry.LeadActions = publicWidget.Widget.extend({
        selector: '.o_portal_my_lead',
        events: {
            'click .action-unqualified': '_onClickUnqualified',
            'click .action-call-later': '_onClickCallLater',
            'click .action-no-answer': '_onClickNoAnswer',
            'click .action-qualified': '_onClickQualified',
            'click .confirm-unqualified': '_onConfirmUnqualified',
            'click .stage-button': '_onClickStage'
        },

        init: function () {
            this._super.apply(this, arguments);
            this.currentLeadId = null;
        },

        _onClickUnqualified: function (ev) {
            ev.preventDefault();
            this.currentLeadId = $(ev.currentTarget).data('lead-id');
            $('#unqualifiedReasonModal').modal('show');
        },

        _onConfirmUnqualified: function () {
            var self = this;
            var reason = $('#reason_to_cancel').val();

            this._rpc({
                route: '/my/lead/state_to_unqualified',
                params: {
                    lead_id: this.currentLeadId,
                    reason_to_cancel: reason
                },
            }).then(function (result) {
                if (result.success) {
                    window.location.reload();
                } else {
                    alert(result.error || _t('An error occurred'));
                }
            });
        },

        _onClickCallLater: function (ev) {
            ev.preventDefault();
            var leadId = $(ev.currentTarget).data('lead-id');

            this._rpc({
                route: '/my/lead/call_later',
                params: { lead_id: leadId },
            }).then(function (result) {
                if (result.success) {
                    window.location.reload();
                } else {
                    alert(result.error || _t('An error occurred'));
                }
            });
        },

        _onClickNoAnswer: function (ev) {
            ev.preventDefault();
            var leadId = $(ev.currentTarget).data('lead-id');

            this._rpc({
                route: '/my/lead/no_answer',
                params: { lead_id: leadId },
            }).then(function (result) {
                if (result.success) {
                    window.location.reload();
                } else {
                    alert(result.error || _t('An error occurred'));
                }
            });
        },

        _onClickQualified: function (ev) {
            ev.preventDefault();
            var leadId = $(ev.currentTarget).data('lead-id');

            this._rpc({
                route: '/my/lead/qualified',
                params: { lead_id: leadId },
            }).then(function (result) {
                if (result.success) {
                    window.location.reload();
                } else {
                    alert(result.error || _t('An error occurred'));
                }
            });
        },

        _onClickStage: function (ev) {
            ev.preventDefault();
            var $btn = $(ev.currentTarget);

            this._rpc({
                route: '/my/lead/update_stage',
                params: {
                    lead_id: $btn.data('lead-id'),
                    stage_id: $btn.data('stage-id')
                },
            }).then(function (result) {
                if (result.success) {
                    window.location.reload();
                } else {
                    alert(result.error || _t('An error occurred'));
                }
            });
        }
    });
});
