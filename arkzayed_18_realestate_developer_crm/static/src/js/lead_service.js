/** @odoo-module */

import { Component, reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

const leadCounterService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        const state = reactive({ counts: 0 });
        async function updateRecordsCount(type){
            let recordsCounts;
            if (type == 'opportunity'){
                recordsCounts = await orm.searchCount("crm.lead", [['type', '=', type], ['is_cancel', '=', false]]);
            }else{
                recordsCounts = await orm.searchCount("crm.lead", [['type', '=', type]]);
            }
            state.counts = recordsCounts;
        }
        return {
            state,
            updateRecordsCount
        };
    },
};

registry.category("services").add("arkzayed_18_realestate_developer_crm.lead_counter_service", leadCounterService);
