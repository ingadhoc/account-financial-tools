# Account Analytic UX

This module enhances analytic accounting UX by adding automatic cost segmentation for projects, allowing service companies to compare analytic budgets against actual costs strictly classified by type.

## Features

- Automatic segmentation of analytic costs by type (labor hours vs. material movements)
- Project-level activation field for segmented analytics
- Auto-creation of analytic plans and accounts per project
- Cost routing based on transaction nature, without manual intervention

## Configuration

1. Install the module
2. Go to **Project > Configuration > Projects**
3. Open or create a project
4. In the **Settings** tab, enable **Segmented Cost Analytics**
5. The system automatically creates the required analytic plans and accounts

## Usage

Once enabled on a project, costs are automatically routed:

- **Labor costs** (timesheets with `employee_id` and product category `other`) → posted to the Hours plan
- **Material costs** (inventory movements with category `picking_entry`) → posted to the Materials plan

## Technical Details

### Dependencies

- `account`: Accounting
- `analytic`: Analytic Accounting
- `project`: Project Management
- `hr_timesheet`: Timesheets

### Models

- `project.project`: Added `use_segmented_analytics` field and account auto-creation logic
- `account.analytic.line`: Extended `create()` for automatic cost routing

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
