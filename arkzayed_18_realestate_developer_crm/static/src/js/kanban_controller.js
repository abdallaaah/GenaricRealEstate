/** @odoo-module **/
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { LeadCounter } from "./lead_counter";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";

export class LeadKanbanController extends KanbanController {

    static template = "arkzayed_18_realestate_developer_crm.CrmKanbanController";
    static components = {
        ...KanbanController.components,
        LeadCounter: LeadCounter,
    };
}


export const LeadCounterKanbanView = {
    ...kanbanView,
    Controller: LeadKanbanController,
};

registry.category("views").add('lead_counter_widget_kanban', LeadCounterKanbanView);
