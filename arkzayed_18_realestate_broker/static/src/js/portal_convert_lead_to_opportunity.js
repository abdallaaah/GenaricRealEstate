/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import publicWidget from "@web/legacy/js/public/public_widget";
import { parseDate, formatDate, serializeDate } from "@web/core/l10n/dates";
const { DateTime } = luxon;

publicWidget.registry.crmPartnerAssign.include({

    start: function() {
        this._super.apply(this, arguments);
        this._bindEvents();
        this.notification = this.bindService("notification");
    },
    _bindEvents: function() {
        const self = this;
        // Bind event to the customer select dropdown
        this.$el.find('.customer').on('change', function(ev) {
            self._onCustomerTypeChange(ev);
        });
    },
    _onCustomerTypeChange: async function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        const customerType = ev.target.value;
        const newCustomerFields = document.querySelector('.new-customer-fields');
        const existingCustomerFields = document.querySelector('.existing-customer-fields');
        const customerSelect = document.querySelector(".interested_partner_assign_form .customer");
        // Hide both fields initially
        if (newCustomerFields) {
            newCustomerFields.style.display = 'none';
        }
        if (existingCustomerFields) {
            existingCustomerFields.style.display = 'none';
        }
        // Insert new customer fields if selected and they are not already present
        if (customerType === 'new_customer' && !newCustomerFields) {
            const newCustomerFieldsHTML = `
                <div class="mb-3 new-customer-fields" style="display: block;">
                    <div class="mb-3">
                        <label class="col-form-label" for="customer_name">Customer Name</label>
                        <input type="text" name="customer_name" id="customer_name" class="form-control"/>
                    </div>
                    <div class="mb-3">
                        <label class="col-form-label" for="customer_email">Email</label>
                        <input type="email" name="customer_email" id="customer_email" class="form-control"/>
                    </div>
                    <div class="mb-3">
                        <label class="col-form-label" for="customer_phone">Phone</label>
                        <input type="tel" name="customer_phone" id="customer_phone" class="form-control" required="1"/>
                    </div>
                </div>
            `;
            customerSelect.insertAdjacentHTML('afterend', newCustomerFieldsHTML);
        }
        // Insert existing customer fields if selected and they are not already present
        if (customerType === 'existing_customer' && !existingCustomerFields) {
            const existingCustomerFieldHTML = `
                <div class="mb-3 existing-customer-fields" style="display: block;">
                    <label class="col-form-label" for="existing_customer_id">Select Customer</label>
                    <select name="existing_customer_id" id="existing_customer_id" class="form-select" required="1">
                        <option value="">Loading customers...</option>
                    </select>
                </div>
            `;
            customerSelect.insertAdjacentHTML('afterend', existingCustomerFieldHTML);
            // Fetch existing customers asynchronously and populate the dropdown
            const customers = await this.orm.call('res.partner', 'search_read', [[], ['id', 'name']], { context: this.context });
            const select = document.querySelector('#existing_customer_id');
            select.innerHTML = customers.map(customer =>
                `<option value="${customer.id}">${customer.name}</option>`
            ).join('');
        }
    },

    _confirmInterestedPartner: async function () {
        self = this;
        const leadId = parseInt(document.querySelector(".interested_partner_assign_form .assign_lead_id").value);
        const stageId = parseInt(document.querySelector(".interested_partner_assign_form .convert_stage").value);
        const buyingType = document.querySelector(".interested_partner_assign_form .buying_type").value;
        const customerType = document.querySelector(".interested_partner_assign_form .customer").value;
        const attachmentInput = document.querySelector(".interested_partner_assign_form .attachment");

        // Get EOI amount
        const eoiAmount = parseInt(document.querySelector(".eoi_amount").value) || 0;

        const reservationPrice = parseInt(document.querySelector(".reservation_price").value) || 0;
        const reservedDate = document.querySelector(".reserved_date").value;
        const contractPrice = parseInt(document.querySelector(".contract_price").value) || 0;
        const contractedDate = document.querySelector(".contracted_date").value;
        const unitnumber = document.querySelector(".unit_number").value;

        const buttons = document.querySelectorAll(".interested_partner_assign_confirm")
        buttons.forEach(button => {
            button.disabled = false;
        });

        if (!customerType) {
             self.notification.add(_t("Please select a customer."), { type: 'danger' });
             return
        }
        if (!attachmentInput.files.length) {
             self.notification.add(_t("Please upload an attachment."), { type: 'danger' });
             return
        }

        // Prepare customer data based on selection
        let customerData = {};
        if (customerType === 'new_customer') {
            customerData = {
                type: 'new',
                name: document.querySelector("#customer_name").value,
                email: document.querySelector("#customer_email").value,
                phone: document.querySelector("#customer_phone").value
            };
        } else {
            customerData = {
                type: 'existing',
                id: parseInt(document.querySelector("#existing_customer_id").value)
            };
        }

        const files = attachmentInput.files;
        var reader = new FileReader();
        const widget = this;
        reader.onload = function(e) {
            var fileContentBase64 = e.target.result.split(',')[1];
            const file = {"name": files[0].name, "content": fileContentBase64}

            // get errors if found
            widget.orm.call("crm.lead", "validate_all_constraints_for_portal", [[leadId]]).then(function (data) {
                console.log('validate : ', data)
                if (data && data.errors) {
                    self.notification.add(_t(data.errors), { type: 'danger' });
                    return
                }
            });

            widget.orm.call("crm.lead", "portal_lead_converted_to_opportunity", [
                [leadId], {
                    stageId,
                    buyingType,
                    file,
                    customerData,
                    eoiAmount,  // Added EOI amount
                    reservationPrice,
                    reservedDate,
                    contractPrice,
                    unitnumber,
                    contractedDate
                }
            ]).then(function () {
                window.location.href = '/my/leads';
            });
        }
        reader.readAsDataURL(files[0] || '');
        return Promise.resolve()
    },
});