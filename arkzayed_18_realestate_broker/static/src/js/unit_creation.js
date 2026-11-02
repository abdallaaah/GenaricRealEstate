/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import publicWidget from "@web/legacy/js/public/public_widget";
import { parseDate, formatDate, serializeDate } from "@web/core/l10n/dates";
import { rpc } from "@web/core/network/rpc";
const { DateTime } = luxon;

publicWidget.registry.UnitCreation = publicWidget.Widget.extend({
    selector: '.create_unit',

    init: function() {
        this._super.apply(this, arguments);
    },

    start: function() {
        return this._super.apply(this, arguments).then(() => {
            return this._callBrokerUnitFunction();
        });
    },

    events: {
        'change #project_id': '_onProjectChange',
        'change #seller_client_id': '_onSellerClientChange',
    },

    _onProjectChange: function(ev) {
        const selectedProject = ev.target.options[ev.target.selectedIndex];
        if (selectedProject){
            const developerId = selectedProject.dataset.developerId;
            if (developerId) {
                document.getElementById('developer_id').value = developerId;
            }
        }
    },

    _onSellerClientChange: function(ev) {
        const selectedClient = ev.target.options[ev.target.selectedIndex];
        if (selectedClient){
            const selectedClientPhone = selectedClient.dataset.clientPhone;
            if (selectedClientPhone) {
                document.getElementById('seller_client_phone').value = selectedClientPhone;
            }
        }
    },
     _callBrokerUnitFunction: async function(ev) {
        const user = parseInt(document.getElementById('seller_sales_person_id').value);
        console.log(user)
        if (user) {
            const result = await rpc('/web/dataset/call_kw/', {
                    model: "broker.unit",
                    method: "compute_seller_tap_details",
                    args: [user],
                    kwargs: {user: user}
                })
                document.getElementById('seller_team_leader_id').value = result[0];
                document.getElementById('seller_sales_manager_id').value = result[1];
                document.getElementById('seller_sales_director_id').value = result[2];
                document.getElementById('seller_sales_person_mobile').value = result[3];
        }
    },

});
