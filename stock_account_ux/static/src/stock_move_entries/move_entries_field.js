import { Component, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { computeM2OProps, Many2One } from "@web/views/fields/many2one/many2one";
import {
    buildM2OFieldDescription,
    many2OneFieldProps,
} from "@web/views/fields/many2one/many2one_field";

/**
 * The move's journal entry as a regular many2one, or a button listing all of them
 * when the move has more than one.
 */
export class StockMoveEntriesField extends Component {
    static template = "stock_account_ux.StockMoveEntriesField";
    static components = { Many2One };
    props = useProps({ ...many2OneFieldProps });

    setup() {
        this.action = useService("action");
    }

    get m2oProps() {
        return computeM2OProps(this.props);
    }

    get entriesCount() {
        return this.props.record.data.account_move_count || 0;
    }

    get buttonLabel() {
        return _t("%s Journal Entries", this.entriesCount);
    }

    async openEntries(ev) {
        ev.stopPropagation();
        return this.action.doActionButton({
            type: "object",
            name: "action_view_account_moves",
            resModel: this.props.record.resModel,
            resId: this.props.record.resId,
        });
    }
}

registry.category("fields").add("stock_move_entries", {
    ...buildM2OFieldDescription(StockMoveEntriesField),
    fieldDependencies: [{ name: "account_move_count", type: "integer" }],
});
