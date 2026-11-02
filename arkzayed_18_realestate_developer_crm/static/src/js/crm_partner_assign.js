/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

import publicWidget from "@web/legacy/js/public/public_widget";
import { parseDate, formatDate, serializeDate } from "@web/core/l10n/dates";
const { DateTime } = luxon;

publicWidget.registry.crmPartnerAssignLead = publicWidget.Widget.extend({
    selector: '#wrapwrap',
    selectorHas: '.opp-lead-stage-button, .reassign_leads_form, #dest_country_id,.edit_area_opp_form, .attachment-input, .lead_creation_form .mark-as-done .needs-validation .create_unit .change_project_select',
    events: {
        'click .opp-lead-stage-button': '_onOppLeadStageButtonClick',
        'click .edit_lead_details_confirm': '_onEditLeadConfirm',
        'click .edit_lead_contact_confirm': '_onEditLeadContactConfirm',
        'click .edit_qualified_required_fields_confirm': '_onEditQualifiedRequiredFieldsConfirm',
        'click .edit_call_later_confirm': '_onEditLeadCallLaterConfirm',
        'click .confirm-unqualified': '_editLeadUnqualified',
        'click .edit_lead_confirm': '_onEditLeadActivityConfirm',
        'click .edit_marketing_confirm': '_onEditLeadMarketingConfirm',
        'click .edit_marketing_confirm_opp': '_onEditOppMarketingConfirm',
        'click .edit_payment_info_confirm': '_onEditPaymentInfoConfirm',
        'click .edit_extra_info_confirm': '_onEditExtraInfoConfirm',
        'click .edit_preferences_confirm': '_onEditLeadPreference',
        'click .edit_opp_preferences_confirm': '_onEditOppPreference',
        'click #dest_country_id': '_onCountryChange',
        'click #project_id': '_onProjectChange',
        'click #project_id_edit': '_onProjectChangeEditLead',
        'click .reassign_leads_confirm': '_onReAssignLeadsConfirm',
        'click .edit_lead_unit_confirm': '_onEditUnitLeadsConfirm',
        'click .edit_unit_confirm': '_onEditSalesLeadsConfirm',
        'click .edit_unit_confirm': '_onEditSalesOppConfirm',
        'click .edit_area_confirm': '_onEditAreaConfirm',
        'click .edit_phones_confirm': '_onEditPhoneNumbers',
        'click .edit_analysis_confirm': '_onEditAnalysisConfirm',
        'click .edit_cancel_reason_confirm': '_onEditCancelReason',
        'click .edit_cancel_reason': '_onEditCancelReasonOpp',
        'click .edit_qualified_comment_confirm': '_onEditQualifiedComment',
        'click .edit_area_confirm_opp': '_onEditOppAreaConfirm',
        'click .developer_id': '_preventDeveloperId',
        'change .attachment-input': '_onChangeAttachments',
        'click .edit_split_deal_confirm': '_onEditSplitDeal',
        'click .edit_extra_info_confirm': '_onEditExtraInfoConfirm',
        'click .edit_contact_info_confirm': '_onEditContactInfoConfirm',
        'click .edit_sales_confirm': '_onEditSalesConfirm',
        'click .edit_phones_confirm_opp': '_onEditPhoneNumbersOpp',
        'click .edit_tracking_confirm': '_onEditTrackingConfirm',
        'click .edit_address_confirm_opp': '_onEditAddressConfirmOpp',
        'click .edit_address_confirm_lead': '_onEditAddressConfirmLead',
        'click .edit_opp_confirm': '_onEditOppConfirmFixStandard',
        'change .convert_stage': '_onChangeStage',
        'change .user_id': '_onChangeSalesperson',
        'change .change_project_select': '_onChangeProjectCreateUnit',
        'click .mark-as-cancel': '_onMarkAsCancel',
        'click .mark-as-cancel': '_onMarkAsCancel',
        'submit .lead_creation_form': '_createLead'
    },

    init() {
        this._super(...arguments);
        this.orm = this.bindService("orm");
        this.notification = this.bindService("notification");

    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Element} btnEl
     * @param {function} callback
     * @returns {Promise}
     */
    _buttonExec: function (btnEl, callback) {
        // TODO remove once the automatic system which does this lands in master
        btnEl.setAttribute("disabled", true);
        return callback.call(this).catch(function (e) {
            btnEl.removeAttribute("disabled");
            if (e instanceof Error) {
                return Promise.reject(e);
            }
        });
    },

    /**
     * @private
     * @param {}
     * @returns {Promise}
     */
    _changeLeadStage: function (leadID, stageID, New, callLater, noAnswer, qualified, unqualified, locked, qualified_limited_budget, follow_up) {
        const buttons = document.querySelectorAll(".opp-lead-stage-button")
        buttons.forEach(button => {
            button.disabled = false;
        });
        // over all
        return this.orm.call("crm.lead", "validate_locked_and_treated_security", [[leadID], locked])
            .then(result => {
                if (result && result.error) {
                    this.notification.add(result.error, { type: 'danger' });
                } else {
                    return this._validateAllLeadStages(leadID, stageID, New, callLater, noAnswer, qualified, unqualified, locked, qualified_limited_budget, follow_up);
                }
        });
    },
    _validateAllLeadStages: function (leadID, stageID, New, callLater, noAnswer, qualified, unqualified, locked, qualified_limited_budget, follow_up) {
        if (qualified || qualified_limited_budget) {
            return this.orm.call("crm.lead", "validate_qualified_stage", [leadID])
                .then(result => {
                    if (result.error) {
                        const modal = $('.modal_qualified_required_fields');
                        if (!modal.find('input[name="stage_id"]').length) {
                            modal.find('form').append(`<input type="hidden" class="new_lead_stage" name="stage_id" value="${stageID}">`);
                        } else {
                            modal.find('input[name="stage_id"]').val(stageID);
                        }
                        modal.modal('show');
                        return false;
                    } else {
                        return this._editLeadStage(leadID, stageID);
                    }
                });
        }
        else if (unqualified) {
            return this.orm.call("crm.lead", "validate_unqualified_stage", [leadID])
                .then(result => {
                    if (result.error) {
//                        this.notification.add(result.error, { type: 'danger' });
                        $('.modal_un_qualified_reason').modal('show');
                    } else {
                        return this._editLeadStage(leadID, stageID);
                    }
                });
        }
//        else if (locked && New == null && callLater == null && noAnswer == null && qualified== null && unqualified == null && qualified_limited_budget == null && follow_up == null) {
//            console.log('ssssss', locked, stageID, follow_up)
//            console.log(locked && New == null && callLater == null && noAnswer == null && qualified== null && unqualified == null && qualified_limited_budget == null && follow_up == null)
//            console.log('from js hereeeee');
//            this.notification.add(_t('You cann\'t move to locked state'), { type: 'danger' });
//            return
//        }
        else {
            return this._editLeadStage(leadID, stageID);
        }
    },
    _validateEditLead: function (leadID) {
        const buttons = document.querySelectorAll(".edit_lead_details_confirm")
        buttons.forEach(button => {
            button.disabled = false;
        });
        return this.orm.call("crm.lead", "validate_locked_and_treated_security", [leadID])
            .then(result => {
                if (result && result.error) {
                    this.notification.add(result.error, { type: 'danger' });
                    return
                }
        });
    },
    _editLeadStage: function (leadID, stageID) {
        return this.orm.write("crm.lead", [leadID], {
                lead_stage_id: stageID
            }, {
                context: { website_partner_assign: 1 }
            }).then(() => {
                window.location.reload();
                return true;
            });
    },
    _onMarkAsDone: function (ev) {
        ev.preventDefault();
        const button = ev.currentTarget;
        const activityId = button.dataset.activityId;

        if (activityId) {
            // Show a confirmation dialog
            if (confirm(_t("Are you sure you want to mark this activity as done?"))) {
                // Call the server to mark the activity as done
                this.orm.call("mail.activity", "action_done", [[parseInt(activityId)]], {
                    context: { website_partner_assign: 1 },
                }).then(() => {
                    // Reload the page to reflect the changes
                    window.location.reload();
                }).catch((error) => {
                    this.notification.add(_t("Failed to mark the activity as done."), { type: 'danger' });
                    console.error(error);
                });
            }
        }
    },
    _onMarkAsCancel: function (ev) {
        ev.preventDefault();
        const button = ev.currentTarget;
        const activityId = button.dataset.activityId;

        if (activityId) {
            // Show a confirmation dialog
            if (confirm(_t("Are you sure you want to mark this activity as cancel?"))) {
                // Call the server to mark the activity as done
                this.orm.call("mail.activity", "action_cancel", [[parseInt(activityId)]], {
                    context: { website_partner_assign: 1 },
                }).then(() => {
                    // Reload the page to reflect the changes
                    window.location.reload();
                }).catch((error) => {
                    this.notification.add(_t("Failed to mark the activity as done."), { type: 'danger' });
                    console.error(error);
                });
            }
        }
    },

    _createLead: function (ev) {
        ev.preventDefault();
        console.log('leaaaad creation validation');
        var form = ev.target.closest('form');
        return this.orm.call("crm.lead", "validate_is_duplicate_lead_or_not_on_creation", [[], {
            phone: document.querySelector(".lead_creation_form .phone").value,
            mobile: document.querySelector(".lead_creation_form .mobile").value,
            phone1: document.querySelector(".lead_creation_form .phone1").value,
            phone2: document.querySelector(".lead_creation_form .phone2").value,
            phone3: document.querySelector(".lead_creation_form .phone3").value,
            phone4: document.querySelector(".lead_creation_form .phone4").value,
        }])
            .then(result => {
                if (result && result.error) {
                var hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = 'duplicate_portal';
                hiddenInput.value = 'true';
                form.appendChild(hiddenInput);
                this.notification.add(result.error, { type: 'danger' });
                form.submit();
                } else {
                    form.submit();
                }
        });
    },

    _editLead: function () {
        var selectedTags = Array.from(document.querySelectorAll(".edit_lead_details .tag_ids option:checked"))
            .map(function (option) {
                return parseInt(option.value);  // Get the value (tag ID) of the selected option
        });

        const leadID = parseInt(document.querySelector(".edit_lead_details .lead_id").value)
        // validate backend errors
        this._validateEditLead(leadID)

        return this.orm.call("crm.lead", "update_lead_info_portal", [[leadID],
            {
                interested_in: document.querySelector(".edit_lead_details .interested_in").value,
                buying_type: document.querySelector(".edit_lead_details .buying_type").value,
//                project_id: parseInt(document.querySelector(".edit_lead_details .project_id_edit").selectedOptions[0].getAttribute("data")),
//                developer_id: parseInt(document.querySelector(".edit_lead_details .developer_id").selectedOptions[0].getAttribute("data")),
//                dest_country_id: parseInt(document.querySelector(".edit_lead_details .dest_country_id").selectedOptions[0].getAttribute("data")),
//                governorate_id: parseInt(document.querySelector(".edit_lead_details .governorate_id").selectedOptions[0].getAttribute("data")),
//                dest_city_id: parseInt(document.querySelector(".edit_lead_details .dest_city_id").selectedOptions[0].getAttribute("data")),
                user_id: parseInt(document.querySelector(".edit_lead_details .user_id").selectedOptions[0].getAttribute("data")),
                follow_up_date: this._parse_date(document.querySelector(".edit_lead_details .follow_up_date").data),
                sales_volume: parseInt(document.querySelector(".edit_lead_details .sales_volume").value),
                priority: document.querySelector(".edit_lead_details .priority").value,
                tag_ids: selectedTags,
            },
        ]).then(function () {
            window.location.reload();
        })
    },
    _editOpportunity: function () {
        return this.orm.call("crm.lead", "update_lead_portal", [
            [parseInt(document.querySelector(".edit_opp_form .opportunity_id").value)],
            {
                date_deadline: this._parse_date(document.querySelector(".edit_opp_form .date_deadline").value),
                expected_revenue: parseFloat(document.querySelector(".edit_opp_form .expected_revenue").value),
                probability: parseFloat(document.querySelector(".edit_opp_form .probability").value),
                activity_type_id: parseInt(document.querySelector(".edit_opp_form .next_activity").selectedOptions[0].getAttribute("data")),
                activity_summary: document.querySelector(".edit_opp_form .activity_summary").value,
                activity_date_deadline: this._parse_date(document.querySelector(".edit_opp_form .activity_date_deadline").value),
                priority: document.querySelector("input[name='PriorityRadioOptions']:checked").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },

    _editLeadContact: function () {
        const leadID = parseInt(document.querySelector(".edit_contact_form .lead_id").value)
        // validate backend errors
        this._validateEditLead(leadID)

        return this.orm.call("crm.lead", "update_lead_contact_portal", [[leadID],{
//                contact_name: document.querySelector(".edit_contact_form .contact_name").value,
//                phone: document.querySelector(".edit_contact_form .phone").value,
                mobile: document.querySelector(".edit_contact_form .mobile").value,
                email_from: document.querySelector(".edit_contact_form .email_from").value,
                email_cc: document.querySelector(".edit_contact_form .email_cc").value,
                job_position: document.querySelector(".edit_contact_form .function").value,
                },
        ]).then(function () {
            window.location.reload();
        });
    },

    /**
     * @private
     * @param {}
     * @returns {Promise}
     */
    _editLeadCallLater: function () {
        return this.orm.call("crm.lead", "update_lead_call_later_portal", [
            [parseInt(document.querySelector(".edit_call_later_form .lead_id").value)],
            {
                activity_type_id: parseInt(document.querySelector(".edit_call_later_form .next_activity").selectedOptions[0].getAttribute("data")),
                activity_date_deadline: this._parse_date(document.querySelector(".edit_call_later_form .activity_date_deadline").value),
                activity_time_deadline: document.querySelector(".edit_call_later_form .activity_time_deadline").value,
                time_type: document.querySelector(".edit_call_later_form .time_type").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editQualifiedRequiredFields: function () {
        const min_area = document.querySelector(".modal_qualified_required_fields .min_area").value
        const max_area = document.querySelector(".modal_qualified_required_fields .max_area").value
        const min_price = document.querySelector(".modal_qualified_required_fields .min_price").value
        const max_price = document.querySelector(".modal_qualified_required_fields .max_price").value
        const qualified_comment = document.querySelector(".modal_qualified_required_fields .qualified_comment").value
        const priority = document.querySelector(".modal_qualified_required_fields .priority").value
        const unit_type = document.querySelector(".modal_qualified_required_fields .unit_type").value
        const finish_type = document.querySelector(".modal_qualified_required_fields .finish_type").value
        const requiredFields = {
            min_area: true,
            max_area: true,
            min_price: true,
            max_price: true,
            qualified_comment: true,
            priority: true,
            unit_type: true,
            finish_type: true,
        };
        const emptyFields = Object.keys(requiredFields).filter(key => !document.querySelector(`.modal_qualified_required_fields .${key}`).value);
        if (emptyFields.length) {
            this.notification.add(`${_t("Failed to update lead stage. Please fill in the following required fields:")} ${emptyFields.map(f => _t(f)).join(", ")}`, {
                type: 'danger'
            });
        }
        return this.orm.call("crm.lead", "update_qualified_fields", [
            [parseInt(document.querySelector(".modal_qualified_required_fields .lead_id").value)],
            {
                min_area: document.querySelector(".modal_qualified_required_fields .min_area").value,
                max_area: document.querySelector(".modal_qualified_required_fields .max_area").value,
                min_price: document.querySelector(".modal_qualified_required_fields .min_price").value,
                max_price: document.querySelector(".modal_qualified_required_fields .max_price").value,
                qualified_comment: document.querySelector(".modal_qualified_required_fields .qualified_comment").value,
                priority: document.querySelector(".modal_qualified_required_fields .priority").value,
                unit_type: document.querySelector(".modal_qualified_required_fields .unit_type").value,
                finish_type: document.querySelector(".modal_qualified_required_fields .finish_type").value,
                lead_stage_id: parseInt(document.querySelector(".modal_qualified_required_fields .new_lead_stage").value),
            },
        ]).then(function () {
            window.location.reload();
        });
    },

    _editLeadActivity: function () {
        return this.orm.call("crm.lead", "update_lead_activity_portal", [
            [parseInt(document.querySelector(".edit_lead_form .lead_id").value)],
            {
                activity_type_id: parseInt(document.querySelector(".edit_lead_form .next_activity").selectedOptions[0].getAttribute("data")),
                activity_date_deadline: this._parse_date(document.querySelector(".edit_lead_form .activity_date_deadline").value),
                activity_summary: document.querySelector(".edit_lead_form .activity_summary").value,
                activity_time_deadline: document.querySelector(".edit_lead_form .activity_time_deadline").value,
                time_type: document.querySelector(".edit_lead_form .time_type").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },

    _editLeadMarketing: function () {
        return this.orm.call("crm.lead", "update_lead_marketing_portal", [
            [parseInt(document.querySelector(".edit_marketing_form .lead_id").value)],
            {
                company_id: parseInt(document.querySelector(".edit_marketing_form .company_id").selectedOptions[0].getAttribute("data")),
                channel: document.querySelector(".edit_marketing_form .channel").value,
                referred: document.querySelector(".edit_marketing_form .referred").value,
                campaign_id: parseInt(document.querySelector(".edit_marketing_form .campaign_id").selectedOptions[0].getAttribute("data")),
//                source_id: parseInt(document.querySelector(".edit_marketing_form .source_id").selectedOptions[0].getAttribute("data")),
//                medium_id: parseInt(document.querySelector(".edit_marketing_form .medium_id").selectedOptions[0].getAttribute("data")),
                campaign_form_name: document.querySelector(".edit_marketing_form .campaign_form_name").value,
                media_buyer: document.querySelector(".edit_marketing_form .media_buyer").value,

            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editOppMarketingConfirm: function () {
        return this.orm.call("crm.lead", "update_opp_marketing_portal", [
            [parseInt(document.getElementById("opp_marketing_opportunity_id").value)],
            {
                campaign_id: parseInt(document.getElementById("opp_campaign_id").value),
//                source_id: parseInt(document.getElementById("opp_source_id").value),
//                medium_id: parseInt(document.getElementById("opp_medium_id").value),
                channel: document.getElementById("opp_channel").value,
                referred: document.getElementById("opp_referred").value,
                campaign_form_name: document.getElementById("campaign_form_name").value,
                media_buyer: document.getElementById("media_buyer").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },

    /**
     * @private
     * Handle payment information updates
     */
    _editPaymentInfo: function () {
        return this.orm.call("crm.lead", "update_payment_info_portal", [
            [parseInt(document.querySelector(".edit_payment_info_form .opportunity_id").value)],
            {
                // payment_plan: parseFloat(document.querySelector(".edit_payment_info_form .payment_plan").value),
                // delivery_date: this._parse_date(document.querySelector(".edit_payment_info_form .delivery_date").value),
                reserved_date: this._parse_date(document.querySelector(".edit_payment_info_form .reserved_date").value),
                contracted_date: this._parse_date(document.querySelector(".edit_payment_info_form .contracted_date").value),
                down_payment: parseFloat(document.querySelector(".edit_payment_info_form .down_payment").value),
                eoi_amount: parseFloat(document.querySelector(".edit_payment_info_form .eoi_amount").value),
                reservation_price: parseFloat(document.querySelector(".edit_payment_info_form .reservation_price").value),
                contract_price: parseFloat(document.querySelector(".edit_payment_info_form .contract_price").value),
                sales_volume: parseFloat(document.querySelector(".edit_payment_info_form .contract_price").value) ||
                          parseFloat(document.querySelector(".edit_payment_info_form .reservation_price").value),
                },
        ]).then(function () {
            window.location.reload();
        });
    },

    _editLeadPreference: function () {
        const leadID = parseInt(document.querySelector(".modal_edit_preferences .lead_id").value)
        // validate backend errors
        this._validateEditLead(leadID)
        return this.orm.call("crm.lead", "update_lead_preference_portal", [[leadID],{
                place_preferences: document.querySelector(".modal_edit_preferences .place_preferences").value,
                furniture_type: document.querySelector(".modal_edit_preferences .furniture_type").value,
                ready_to_move: document.querySelector(".modal_edit_preferences .ready_to_move").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editOppPreference: function () {
        return this.orm.call("crm.lead", "update_lead_preference_portal", [
            [parseInt(document.querySelector(".modal_edit_opp_preferences .opportunity_id").value)],
            {
                place_preferences: document.querySelector(".modal_edit_opp_preferences .place_preferences").value,
                furniture_type: document.querySelector(".modal_edit_opp_preferences .furniture_type").value,
                ready_to_move: document.querySelector(".modal_edit_opp_preferences .ready_to_move").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editUnitLead: function () {
        const leadID = parseInt(document.querySelector(".edit_lead_unit_form .lead_id").value)
        // validate backend errors
        this._validateEditLead(leadID)
        return this.orm.call("crm.lead", "update_unit_details", [[leadID],
            {
                unit_type: document.querySelector(".edit_lead_unit_form .unit_type").value,
                finish_type: document.querySelector(".edit_lead_unit_form .finish_type").value,
                number_of_bedrooms: document.querySelector(".edit_lead_unit_form .number_of_bedrooms").value,
                number_of_bathrooms: document.querySelector(".edit_lead_unit_form .number_of_bathrooms").value,
                building_area: document.querySelector(".edit_lead_unit_form .building_area").value,
                garden_area: document.querySelector(".edit_lead_unit_form .garden_area").value,
                land_area: document.querySelector(".edit_lead_unit_form .land_area").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },

    _editSalesLead: function () {
        return this.orm.call("crm.lead", "update_unit_details", [
            [parseInt(document.querySelector(".edit_unit_form .opportunity_id").value)],
            {
                unit_type: document.querySelector(".edit_unit_form .unit_type").value,
                finish_type: document.querySelector(".edit_unit_form .finish_type").value,
                number_of_bedrooms: document.querySelector(".edit_unit_form .number_of_bedrooms").value,
                number_of_bathrooms: document.querySelector(".edit_unit_form .number_of_bathrooms").value,
                building_area: document.querySelector(".edit_unit_form .building_area").value,
                garden_area: document.querySelector(".edit_unit_form .garden_area").value,
                land_area: document.querySelector(".edit_unit_form .land_area").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editOppConfirmFixStandard: function () {
        return this.orm.call("crm.lead", "update_lead_portal", [
            [parseInt(document.querySelector(".edit_opp_form .opportunity_id").value)],
            {
                date_deadline: this._parse_date(document.querySelector(".edit_opp_form .date_deadline").value),
                expected_revenue: parseFloat(document.querySelector(".edit_opp_form .expected_revenue").value),
                probability: parseFloat(document.querySelector(".edit_opp_form .probability").value),
                activity_type_id: parseInt(document.querySelector(".edit_opp_form .next_activity").selectedOptions[0].getAttribute("data")),
                activity_type_id: parseInt(document.querySelector(".edit_opp_form .next_activity").selectedOptions[0].getAttribute("data")),
                activity_summary: document.querySelector(".edit_opp_form .activity_summary").value,
                activity_date_deadline: this._parse_date(document.querySelector(".edit_opp_form .activity_date_deadline").value),
                priority: document.querySelector("input[name='PriorityRadioOptions']:checked").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editSalesOpp: function () {
        return this.orm.call("crm.lead", "update_unit_details", [
            [parseInt(document.querySelector(".edit_unit_form_opp .opportunity_id").value)],
            {
                unit_type: document.querySelector(".edit_unit_form_opp .unit_type").value,
                finish_type: document.querySelector(".edit_unit_form_opp .finish_type").value,
                number_of_bedrooms: parseInt(document.querySelector(".edit_unit_form_opp .number_of_bedrooms").value),
                number_of_bathrooms: parseInt(document.querySelector(".edit_unit_form_opp .number_of_bathrooms").value),
                building_area: parseInt(document.querySelector(".edit_unit_form_opp .building_area").value),
                garden_area: parseInt(document.querySelector(".edit_unit_form_opp .garden_area").value),
                land_area: parseInt(document.querySelector(".edit_unit_form_opp .land_area").value),
            },
        ]).then(function () {
            window.location.reload();
        });
    },

    /**
     * @private
     * Handle extra information updates
     */
    _editExtraInfo: function () {
        return this.orm.call("crm.lead", "update_extra_info_portal", [
            [parseInt(document.querySelector(".edit_extra_info_form .opportunity_id").value)],
            {
                date_open: this._parse_date(document.querySelector(".edit_extra_info_form .date_open").value),
                unit_number: document.querySelector(".edit_extra_info_form .unit_number").value,
                },
        ]).then(function () {
            window.location.reload();
        });
    },

    _editAreaLead: function () {
        const leadID = parseInt(document.querySelector(".edit_area_form .lead_id").value)
        // validate backend errors
        this._validateEditLead(leadID)
        return this.orm.call("crm.lead", "update_area_pricing", [[leadID],{
                min_area: document.querySelector(".edit_area_form .min_area").value,
                max_area: document.querySelector(".edit_area_form .max_area").value,
                min_price: document.querySelector(".edit_area_form .min_price").value,
                max_price: document.querySelector(".edit_area_form .max_price").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editPhoneNumbers: function () {
        const leadID = parseInt(document.querySelector(".edit_phones_form .lead_id").value)
        // validate backend errors
        this._validateEditLead(leadID)
        return this.orm.call("crm.lead", "update_phone_numbers", [[leadID],{
                phone1: document.querySelector(".edit_phones_form .phone1").value,
                phone2: document.querySelector(".edit_phones_form .phone2").value,
                phone3: document.querySelector(".edit_phones_form .phone3").value,
                phone4: document.querySelector(".edit_phones_form .phone4").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editPhoneNumbersOpp: function () {
        return this.orm.call("crm.lead", "update_phone_numbers", [
            [parseInt(document.querySelector(".edit_phones_form .opportunity_id").value)],
            {
                phone1: document.querySelector(".edit_phones_form .phone1").value,
                phone2: document.querySelector(".edit_phones_form .phone2").value,
                phone3: document.querySelector(".edit_phones_form .phone3").value,
                phone4: document.querySelector(".edit_phones_form .phone4").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },

    _editAnalysis: function () {
        return this.orm.call("crm.lead", "update_analysis", [
            [parseInt(document.querySelector(".edit_analysis_form .lead_id").value)],
            {
                date_closed: this._parse_date(document.querySelector(".edit_analysis_form .date_closed").value),
            },
        ]).then(function () {
            window.location.reload();
        });
    },

    _editSplitDeal: function() {
        let opportunity_id = parseInt(document.querySelector(".edit_split_deal_form .opportunity_id").value);
        function getMultiValues(selector) {
            return $(selector).val() ? $(selector).val().map(v => parseInt(v)) : [];
        }
        return this.orm.call("crm.lead", "update_split_deal", [opportunity_id],
         {
            split_deal: document.querySelector(".edit_split_deal_form .split_deal").checked,
            partner_ids: getMultiValues(".edit_split_deal_form .partner_id"),
            employee_ids: getMultiValues(".edit_split_deal_form .employee_id"),
            broker_ids: getMultiValues(".edit_split_deal_form .broker_id"),
            ambassador_ids: getMultiValues(".edit_split_deal_form .ambassador_id"),
            non_sales_ids: getMultiValues(".edit_split_deal_form .non_sales_id"),
            sales_ids: getMultiValues(".edit_split_deal_form .sales_id"),
            other: document.querySelector(".edit_split_deal_form .other").value,
         },
         ).then(function () {
            window.location.reload();
        });
    },

    _onEditCancelReason: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const leadID = parseInt(document.querySelector(".edit_cancel_reason_form .lead_id").value)
        // validate backend errors
        this._validateEditLead(leadID)
        return this.orm.call("crm.lead", "update_unqualified_reason", [[leadID],
            {
                lost_reason_id: document.querySelector(".edit_cancel_reason_form .reason_to_cancel").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editLeadUnqualified : function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        let is_opportunity = false;
        let leadID = document.querySelector(".edit_unqualified_form .lead_id")
        if (leadID) {
            leadID = parseInt(leadID.value)
        }else{
            leadID = document.querySelector(".edit_unqualified_form .opportunity_id")
            if (leadID) {
                is_opportunity = true
                leadID = parseInt(leadID.value)
            }
        }
        if (!leadID) {
            return
        }
        // validate backend errors
        this._validateEditLead(leadID)
        const method_name = is_opportunity ? 'update_unqualified_reason_opp' : 'update_unqualified_reason'
        return this.orm.call("crm.lead", method_name, [[leadID],
            {
                lost_reason_id: document.querySelector(".edit_unqualified_form .reason_to_cancel").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _onEditCancelReasonOpp: function () {
        return this.orm.call("crm.lead", "update_unqualified_reason_opp", [
            [parseInt(document.querySelector(".edit_cancel_reason_line .opportunity_id").value)],
            {
                lost_reason_id: document.querySelector(".edit_cancel_reason_line .lost_reason_id").value,
                },
        ]).then(function () {
            window.location.reload();
        });
    },

    _onEditQualifiedComment: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const leadID = parseInt(document.querySelector(".edit_qualified_comment_form .lead_id").value)
        // validate backend errors
        this._validateEditLead(leadID)
        return this.orm.call("crm.lead", "update_qualified_comment", [[leadID],
            {
                qualified_comment: document.querySelector(".edit_qualified_comment_form .qualified_comment").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },

    _onChangeProjectCreateUnit: function () {
        console.log('zzzzzzzzzzzzz');
    },

    _editAreaOpp: function () {
        return this.orm.call("crm.lead", "update_area_pricing", [
            [parseInt(document.querySelector(".edit_area_opp_form .opportunity_id").value)],
            {
                min_area: document.querySelector(".edit_area_opp_form .min_area").value,
                max_area: document.querySelector(".edit_area_opp_form .max_area").value,
                min_price: document.querySelector(".edit_area_opp_form .min_price").value,
                max_price: document.querySelector(".edit_area_opp_form .max_price").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editAddressConfirmOpp: function () {
        return this.orm.call("crm.lead", "update_address_info", [
            [parseInt(document.querySelector(".edit_address_form_opp .opportunity_id").value)],
            {
                street: document.querySelector(".edit_address_form_opp .street").value,
                street2: document.querySelector(".edit_address_form_opp .street2").value,
                city: document.querySelector(".edit_address_form_opp .city").value,
                zip: document.querySelector(".edit_address_form_opp .zip").value,
                state_id: parseInt(document.querySelector(".edit_address_form_opp .state_id").value),
                country_id: parseInt(document.querySelector(".edit_address_form_opp .country_id").value),
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editAddressConfirmLead: function () {
        const leadID = parseInt(document.querySelector(".edit_address_form_lead .lead_id").value)
        // validate backend errors
        this._validateEditLead(leadID)
        return this.orm.call("crm.lead", "update_address_info", [[leadID],{
                street: document.querySelector(".edit_address_form_lead .street").value,
                street2: document.querySelector(".edit_address_form_lead .street2").value,
                city: document.querySelector(".edit_address_form_lead .city").value,
                zip: document.querySelector(".edit_address_form_lead .zip").value,
                state_id: parseInt(document.querySelector(".edit_address_form_lead .state_id").value),
                country_id: parseInt(document.querySelector(".edit_address_form_lead .country_id").value),
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editContactInfoConfirm: function () {
        return this.orm.call("crm.lead", "update_contact_info", [
            [parseInt(document.querySelector(".edit_contact_info_form .opportunity_id").value)],
            {
                partner_name: document.querySelector(".edit_contact_info_form .partner_name").value,
                website: document.querySelector(".edit_contact_info_form .website").value,
//                contact_name: document.querySelector(".edit_contact_info_form .contact_name").value,
                mobile: document.querySelector(".edit_contact_info_form .mobile").value,
                mobile: document.querySelector(".edit_contact_info_form .mobile").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editTrackingConfirm: function () {
        return this.orm.call("crm.lead", "update_tracking_info", [
            [parseInt(document.querySelector(".edit_tracking_form .opportunity_id").value)],
            {
                company_id: document.querySelector(".edit_tracking_form .company_id").value,
                day_open: document.querySelector(".edit_tracking_form .day_open").value,
                day_close: document.querySelector(".edit_tracking_form .day_close").value,
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    _editSalesConfirm: function () {
         let priority = document.getElementById("test_priority").checked;
         let priority2 = document.getElementById("test_priority2").checked;
         let priority3 = document.getElementById("test_priority3").checked;
         let priority4 = document.getElementById("test_priority4").checked;
         let priority_number = 0;
         if (priority) {
            priority_number = 0;
         } else if (priority2) {
            priority_number = 1;
         } else if (priority3) {
            priority_number = 2;
         } else {
            priority_number = 3;
         }

         function getMultiValues(selector) {
            return $(selector).val() ? $(selector).val().map(v => parseInt(v)) : [];
        }
        return this.orm.call("crm.lead", "update_sales_info", [
            [parseInt(document.querySelector(".edit_sales_form .opportunity_id").value)],
            {
                user_id: parseInt(document.querySelector(".edit_sales_form .user_id").value),
                priority: priority_number,
                tag_ids: getMultiValues(".edit_sales_form .tag_ids"),
            },
        ]).then(function () {
            window.location.reload();
        });
    },
    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    _onOppLeadStageButtonClick: function (ev) {
        const btnEl = ev.currentTarget;
        this._buttonExec(
            btnEl,
            this._changeLeadStage.bind(
                this,
                parseInt(btnEl.getAttribute("opp")),
                parseInt(btnEl.getAttribute("data")),
                btnEl.getAttribute("new"),
                btnEl.getAttribute("call_later"),
                btnEl.getAttribute("no_answer"),
                btnEl.getAttribute("qualified"),
                btnEl.getAttribute("unqualified"),
                btnEl.getAttribute("locked"),
                btnEl.getAttribute("qualified_limited_budget"),
                btnEl.getAttribute("follow_up"),
            )
        );
    },
    _onEditLeadConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editLead);
    },
    _onEditLeadContactConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editLeadContact);
    },
    _onEditQualifiedRequiredFieldsConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editQualifiedRequiredFields);
    },
    _onEditLeadCallLaterConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editLeadCallLater);
    },
    _onEditLeadActivityConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editLeadActivity);
    },
    _onEditLeadMarketingConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editLeadMarketing);
    },
    _onEditOppMarketingConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editOppMarketingConfirm);
    },
    _onEditPaymentInfoConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editPaymentInfo);
    },
    _onEditExtraInfoConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editExtraInfo);
    },
    _onEditLeadPreference: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editLeadPreference);
    },
    _onEditOppPreference: function (ev) {
    ev.preventDefault();
    ev.stopPropagation();
    this._buttonExec(ev.currentTarget, this._editOppPreference);
    },
    _onEditUnitLeadsConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editUnitLead);
    },
    _onEditSalesLeadsConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editSalesLead);
    },
    _onEditSalesOppConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editSalesOpp);
    },
    _onEditAreaConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editAreaLead);
    },
    _onEditOppAreaConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editAreaOpp);
    },
    _onEditPhoneNumbers: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editPhoneNumbers);
    },
    _onEditPhoneNumbersOpp: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editPhoneNumbersOpp);
    },
    _onEditAnalysisConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editAnalysis);
    },
    _onEditSalesConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editSalesConfirm);
    },
    _onEditTrackingConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editTrackingConfirm);
    },
    _parse_date: function (value) {
        var date = parseDate(value);
        if (!date.isValid || date.year < 1900) {
            return false;
        }
        return serializeDate(date);
    },

    _onEditSplitDeal: function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editSplitDeal)

    },
    _onEditExtraInfoConfirm: function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editExtraInfo)

    },
    _onEditPaymentInfo: function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editPaymentInfo)

    },
    _onEditContactInfoConfirm: function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editContactInfoConfirm)

    },
    _onEditAddressConfirmOpp: function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editAddressConfirmOpp)

    },
    _onEditAddressConfirmLead: function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editAddressConfirmLead)

    },
    _onEditOppConfirmFixStandard: function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._editOppConfirmFixStandard)

    },
    _onChangeStage: function(ev) {
        let stage_id = document.getElementById("stage_id")?.value;
        let eoi_amount_div = document.querySelector(".eoi_amount_div");
        let reservation_price_div = document.querySelector(".reservation_price_div");
        let reserved_date_div = document.querySelector(".reserved_date_div");
        let contract_price_div = document.querySelector(".contract_price_div");
        let contract_date_div = document.querySelector(".contract_date_div");
        let unit_number_div = document.querySelector(".unit_number_div");

        // Hide all divs first
        if (eoi_amount_div) eoi_amount_div.style.display = 'none';
        if (reservation_price_div) reservation_price_div.style.display = 'none';
        if (reserved_date_div) reserved_date_div.style.display = 'none';
        if (contract_price_div) contract_price_div.style.display = 'none';
        if (contract_date_div) contract_date_div.style.display = 'none';
        if (unit_number_div) unit_number_div.style.display = 'none';

        if (stage_id) {
            // Assuming stage IDs: 1 = EOI, 2 = Reservation, 3 = Contract
            // You may need to adjust these IDs based on your actual stage IDs
            if (parseInt(stage_id) === 1) { // EOI stage
                if (eoi_amount_div) {
                    eoi_amount_div.style.display = 'block';
                }
            }
            else if (parseInt(stage_id) === 2) { // Reservation stage
                if (reservation_price_div && reserved_date_div) {
                    reservation_price_div.style.display = 'block';
                    reserved_date_div.style.display = 'block';
                }
            }
            else if (parseInt(stage_id) === 3) { // Contract stage
                if (contract_price_div && contract_date_div && unit_number_div) {
                    contract_price_div.style.display = 'block';
                    contract_date_div.style.display = 'block';
                    unit_number_div.style.display = 'block';
                }
            }
        }
    },

    _onCountryChange: function (ev) {
        let countryId = ev.currentTarget.value;
        console.log(countryId);
        let governmentSelect = document.getElementById("government_id");

        if (!governmentSelect) return;

        const allOptions = governmentSelect.querySelectorAll("option");

        allOptions.forEach(option => {
            const isDefaultOption = option.value === "";
            const matchesCountry = option.getAttribute("data-country-id") === countryId;

            option.hidden = !isDefaultOption && !matchesCountry;
            if (matchesCountry) {
                option.selected = true; // Auto-select first available option
            } else {
                option.selected = false;
            }
        });

        governmentSelect.value = ""; // Reset the selection
    },

    _onProjectChange: function(ev) {
        let projectSelect = document.querySelector("#project_id");
        let developerSelect = document.querySelector("#developer_id");
        let countrySelect = document.querySelector("#dest_country_id");
        let governmentSelect = document.querySelector("#government_id");
        let DistrictSelect = document.querySelector("#governorate_id");
        let neighborhoodSelect = document.querySelector("#neighborhood_id");
        let selectedProject = projectSelect.options[projectSelect.selectedIndex];
        let developerId = selectedProject.getAttribute("data-developer-id");
        let countryId = selectedProject.getAttribute("data-country-id");
        let governorateId = selectedProject.getAttribute("data-governorate-id");
        let districtId = selectedProject.getAttribute("data-district-id");
        let neighborhoodId = selectedProject.getAttribute("data-neighborhood-id");

            if (developerId) {
                developerSelect.value = developerId;
            } else {
                developerSelect.value = "";
            }
            if (countryId) {
                countrySelect.value = countryId;
            } else {
                countrySelect.value = "";
            }
            if(governorateId) {
                governmentSelect.value = governorateId;
            } else {
                governmentSelect.value = "";
            }
            if(districtId) {
                DistrictSelect.value = districtId;
            } else {
                DistrictSelect.value = '';
            }
            if(neighborhoodId) {
                neighborhoodSelect.value = neighborhoodId;
            } else {
                neighborhoodSelect.value = '';
            }

    },
    _onProjectChangeEditLead: function(ev) {
        let projectSelect = document.querySelector("#project_id_edit");
        let developerSelect = document.querySelector("#developer_id_edit");
        let countrySelect = document.querySelector("#dest_country_id_edit");
        let governmentSelect = document.querySelector("#governorate_id_edit");
        let DistrictSelect = document.querySelector("#dest_city_id");
        let selectedProject = projectSelect.options[projectSelect.selectedIndex];
        let developerId = selectedProject.getAttribute("data-developer-id");
        let countryId = selectedProject.getAttribute("data-country-id");
        let governorateId = selectedProject.getAttribute("data-governorate-id");
        let districtId = selectedProject.getAttribute("data-district-id");

            if (developerId) {
                developerSelect.value = developerId;
            } else {
                developerSelect.value = "";
            }
            if (countryId) {
                countrySelect.value = countryId;
            } else {
                countrySelect.value = "";
            }
            if(governorateId) {
                governmentSelect.value = governorateId;
            } else {
                governmentSelect.value = "";
            }
            if(districtId) {
                DistrictSelect.value = districtId;
            } else {
                DistrictSelect.value = '';
            }


    },

    _onReAssignLeadsConfirm: function (ev) {
        ev.preventDefault();

        let checkboxes = document.querySelectorAll('#oppTable input[type="checkbox"]');
        if (checkboxes.length === 0) {
            checkboxes = document.querySelectorAll('#leadTable input[type="checkbox"]');
        }
        let selectedRows = Array.from(checkboxes).filter(cb => cb.checked);
        let selectedLeads = selectedRows.map(row => parseInt(row.getAttribute("data")));
        let selectedUser = parseInt(document.querySelector(".reassign_leads_form .new_user").selectedOptions[0].getAttribute("data"))

//        let portalUser = parseInt(ev.currentTarget.getAttribute("user"))
        self = this;
        return this.orm.call("crm.lead", "reassign_leads", [selectedLeads, selectedUser] , {
            context: Object.assign({website_partner_assign: 1}),
        }).then(function () {
            window.location.reload();
            self.notification.add(_t("Reassignment Done Successfully"), { type: 'success' });
        });
    },

    _onChangeAttachments: function(ev){
        let field_name = ev.currentTarget.name
        let leadID = parseInt(ev.currentTarget.getAttribute("opp"))
        let files = ev.currentTarget.files
        var reader = new FileReader();
        const widget = this;
        reader.onload = function(e) {
            let fileContentBase64 = e.target.result.split(',')[1];
            let fileName = files[0].name
            let fileNameField = field_name + "_filename"
            widget.orm.write("crm.lead", [leadID], {[field_name]: fileContentBase64, [fileNameField]: fileName}).then(function () {
                window.location.reload();
            });
        }
        reader.readAsDataURL(files[0]);
        return Promise.resolve()
    },

    _onChangeSalesperson: async function(ev){
        let user_id = document.querySelector(".user_id")?.value;
        return this.orm.call("crm.team.member", "search_read", [], {
            fields: ["id", "crm_team_id"],
            domain: [['user_id', '=', Number(user_id)]],
            limit:1,
        }).then(function (data) {
            if (data.length === 0){
                document.querySelector(".team_selection").removeAttribute("disabled");
                document.querySelector(".team_selection").value = "";
                document.querySelector(".team_selection").setAttribute("disabled", true);
            }
            else{
                document.querySelector(".team_selection").removeAttribute("disabled");
                document.querySelector(".team_selection").value = data[0]['crm_team_id'][0];
                document.querySelector(".team_selection").setAttribute("disabled", true);
            }
        });
    }

});

publicWidget.registry.crmPartnerAssign.include({
    init() {
        this._super(...arguments);
        this.notification = this.bindService("notification");
    },
    //  opportunity validations
    _onOppStageButtonClick: function (ev) {
        const btnEl = ev.currentTarget;
        this._buttonExec(
            btnEl,
            this._changeOppStage.bind(
                this,
                parseInt(btnEl.getAttribute("opp")),
                parseInt(btnEl.getAttribute("data")),
                btnEl.getAttribute("eoi"),
                btnEl.getAttribute("reservation"),
                btnEl.getAttribute("contract"),
                btnEl.getAttribute("collected"),
                btnEl.getAttribute("confirmed_contract"),
                btnEl.getAttribute("request_to_cancel"),
                btnEl.getAttribute("cancel"),
            )
        );
    },
    _changeOppStage: function (leadID, stageID, eoi, reservation, contract, collected, confirmed_contract, request_to_cancel, cancel) {
        const buttons = document.querySelectorAll(".opp-stage-button")
        buttons.forEach(button => {
            button.disabled = false;
        });

        return this.orm.call("crm.lead", "validate_stage_return_back", [leadID], { stage_id: stageID })
            .then(result => {
                if (result && result.error) {
                    this.notification.add(result.error, { type: 'danger' });
                } else {
                    return this._validateAllStages(leadID, stageID, eoi, reservation, contract, collected, confirmed_contract, request_to_cancel, cancel);
                }
        });
    },
    _validateAllStages: function (leadID, stageID, eoi, reservation, contract, collected, confirmed_contract, request_to_cancel, cancel) {
        if (eoi) {
        }
        else if (request_to_cancel || cancel) {
            return this.orm.call("crm.lead", "validate_stage_cancel_reason", [leadID], { stage_id: stageID })
                .then(result => {
                    if (result && result.error) {
                        console.log('result', result)
                        $('.modal_un_qualified_reason').modal('show');
//                        this.notification.add(result.error, { type: 'danger' });
                    } else {
                        return this._editCrmStage(leadID, stageID);
                    }
            });
        }
        else if (reservation || contract){
            return this.orm.call("crm.lead", "validate_required_fields_portal", [leadID], { stage_id: stageID })
                .then(result => {
                    if (result && result.error) {
                        this.notification.add(result.error, { type: 'danger' });
                    } else {
                        return this._editCrmStage(leadID, stageID);
                    }
            });
        }
//        else if (collected || confirmed_contract) {
//            console.log('collected', collected)
//            console.log('confirmed_contract', confirmed_contract)
//        }
        else{
            return this._editCrmStage(leadID, stageID);
        }
    },
    _editCrmStage: function (leadID, stageID) {
        return this.orm.write("crm.lead", [leadID], { stage_id: stageID }, {
            context: Object.assign({website_partner_assign: 1}),
        }).then(function () {
            window.location.reload();
        });
    },
    _onInterestedPartnerAssignConfirm: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._buttonExec(ev.currentTarget, this._confirmInterestedPartner);
    },
});