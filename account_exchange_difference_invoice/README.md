# Account Exchange Difference Invoice

This module extends Odoo's accounting functionality to handle exchange rate differences through invoices. It provides a mechanism to generate invoices for currency exchange differences that arise from fluctuations in exchange rates between the time of invoice creation and payment.

## Features

- Generate exchange difference invoices automatically
- Configure specific product for exchange difference operations
- Wizard interface for processing exchange differences
- Automatic reconciliation of exchange difference entries
- Support for both positive and negative exchange differences
- Integration with existing accounting workflows

## Configuration

1. Install the module
2. Go to Accounting > Configuration > Settings
3. Configure the exchange difference product in company settings
   - This product will be used when generating exchange difference invoices

## Usage

### Generate Exchange Difference Invoice

1. Navigate to Accounting > Exchange Difference List
2. Use the filters to find entries to process:
   - "To Process" filter shows entries not yet processed
   - "Previous Month" and "Current Month" filters help narrow down the date range
3. Select the entries you want to process
4. Click the "Convert to Debit/Credit Note" button at the top of the list
5. The wizard will show the calculated differences grouped by partner
6. Select the journal for the exchange difference invoice
7. Confirm to create the exchange difference invoice

### Important Notes

- The module will only process entries that haven't been previously processed for exchange differences
- Exchange difference entries are automatically reconciled with their corresponding original entries
- The system validates that all necessary configuration is in place before allowing the generation of exchange difference invoices

## Technical Details

### Dependencies

- `account_debit_note`: For handling debit notes related to exchange differences

### Models

- `account.exchange.difference.wizard`: Main wizard for generating exchange difference invoices
- `account.move`: Extended to handle exchange difference reconciliation
- `res.company`: Extended to configure exchange difference product

## Bug Tracker

Bugs are tracked on [GitHub Issues](https://github.com/ingadhoc/account-financial-tools/issues). In case of trouble, please check there if your issue has already been reported.

## Credits

### Authors

* ADHOC SA

### Contributors

* ADHOC SA <info@adhoc.com.ar>

### Maintainers

This module is maintained by ADHOC SA.

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
