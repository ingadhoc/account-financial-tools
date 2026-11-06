import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { StockValuationReport } from "@account/components/stock_valuation/stock_valuation_report";

// Open the loss moves with the valuation list, which shows the journal entry.
patch(StockValuationReport.prototype, {
    openInventoryLoss() {
        const domain = [
            "|",
            ["location_id.usage", "=", "inventory"],
            ["location_dest_id.usage", "=", "inventory"],
        ];
        if (this.controller.dateAsString) {
            domain.unshift("&");
            domain.push(["date", "<=", this.controller.dateAsString]);
        }
        return this.actionService.doAction({
            name: _t("Inventory Loss"),
            type: "ir.actions.act_window",
            res_model: "stock.move",
            domain,
            views: [[false, "list"], [false, "form"]],
            context: { list_view_ref: "stock_account.stock_move_view_list_valuation" },
            target: "current",
        });
    },
});
