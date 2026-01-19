# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Module Overview

The `kvz_backlog` module is an Odoo 17 custom addon that manages confirmed sales order lines through a backlog workflow. It tracks invoiceable lines from sales orders through stages: forecast → planning → provisioned → invoiced, with currency conversion support (CLP/USD) and Chilean DTE integration.

## Docker Environment

- **Odoo container**: `odoo-17`
- **PostgreSQL container**: `postgres-14`
- **Current database**: `NEW_BACKLOG`

### Common Commands

**Run Odoo tests for this module:**
```bash
docker exec -it odoo-17 odoo-bin -d NEW_BACKLOG -u kvz_backlog --test-enable --test-tags=kvz_backlog --stop-after-init
```

**Run specific test file:**
```bash
docker exec -it odoo-17 odoo-bin -d NEW_BACKLOG -u kvz_backlog --test-enable --test-tags=/backlog/tests/test_invoice_status.py --stop-after-init
```

**Update module after code changes:**
```bash
docker exec -it odoo-17 odoo-bin -d NEW_BACKLOG -u kvz_backlog --stop-after-init
```

**Start Odoo shell for debugging:**
```bash
docker exec -it odoo-17 odoo-bin shell -d NEW_BACKLOG
```

**Restart Odoo container:**
```bash
docker restart odoo-17
```

**View Odoo logs:**
```bash
docker logs -f odoo-17
```

**Access PostgreSQL:**
```bash
docker exec -it postgres-14 psql -U odoo -d NEW_BACKLOG
```

## Architecture

### Core Models

**`backlog.stages` (models/backlog.py:11-44)**
- Defines workflow stages with types: forecast, planning, provisioned, invoiced
- Each stage type can only exist once (constraint enforced)

**`sale.order.line` extension (models/backlog.py:57-524)**
- Main model that tracks backlog items
- Inherits: `mail.activity.mixin`, `mail.thread`, `utm.mixin`
- Key fields:
  - `backlog_state_id`: Many2one to backlog.stages (visual stage)
  - `bklg_state`: Selection field (internal state: forecast, planning, high_risk, pending_risk, sent_to_provision, sent_to_invoicing, provisioned, invoiced, frozen)
  - `forecast_date`: Due date for the backlog item
  - `date_deadline`: Deadline date used for replanning
  - `clp_price_total/clp_price_subtotal`: Computed CLP amounts
  - `amount_us`: Computed USD amount
  - `replanning_count`: Tracks number of times item was replanned

**`sale.order.line` invoice tracking (models/sale_order_line.py:9-337)**
- Extends sale.order.line with real invoice amount tracking
- Key computed fields:
  - `real_invoiced_amount`: Actual amount from posted invoices (line-specific)
  - `real_invoice_total`: Total of all related invoices
  - `invoice_number`: Invoice number from posted invoice
  - `credit_note_number`: Credit note number if exists
  - `has_credit_note`: Boolean flag for credit notes
  - `credit_note_amount`: Total credit note amount
  - `initial_provisioned_amount`: Snapshot when moved to provisioned stage
  - `initial_provisioned_amount_datetime`: Timestamp of provisioning

### Key Business Logic

**Currency Conversion (models/backlog.py:342-429)**
- `compute_clp_currency()`: Converts prices to CLP using forecast_date or create_date for exchange rate
- `_compute_amount_us()`: Converts to USD with special handling for CLP→USD inverse rates
- Both skip computation when `invoice_status='invoiced'` or `bklg_state='provisioned'` to freeze amounts

**Invoice Status Automation (models/sale_order_line.py:215-337)**
- `_compute_invoice_status()`: Overrides Odoo's standard compute
- Automatically updates `bklg_state` to 'invoiced' when invoice is posted with valid DTE status
- Dynamically reverts state when credit notes reduce net amount to zero:
  - If previously provisioned → reverts to 'provisioned'
  - Otherwise → reverts to 'planning'
- Uses Chilean DTE validation: `l10n_cl_dte_status in ['objected', 'accepted']`
- Follows Odoo 17 idiomatic pattern: state computed from net amounts, no stored "previous state"

**Provisioning Workflow (models/backlog.py:444-500)**
- `action_provision()`: Marks lines as provisioned, captures initial_provisioned_amount
- `action_provision()` freezes currency amounts at provision time
- `action_reverse_provision()`: Reverts to planning stage, forces currency recalculation

**State Change Validation (models/backlog.py:186-230)**
- `onchage_on_bklg_state()`: Validates user permissions before allowing state changes
- Only Project Manager or users in project_line_ids.user_id can change state
- Increments `replanning_count` on manual state changes
- Creates mail activities for backlog manager when moved to 'sent_to_invoicing'

### Security Model

**Groups (defined in security/security.xml):**
- `group_backlog_manager`: Full access to backlog stages and management
- `group_backlog_users`: Read-only access to backlog stages
- `group_project_manager`: Can edit sale order lines in backlog
- `group_head_of_sales`: Can modify backlog for draft/sent orders
- `group_business_owner`: Can modify backlog for draft/sent orders

**Permission constraints (models/backlog.py:288-306):**
- Draft/sent orders: Only Business Owner or Head of Sales can set backlog state
- Confirmed orders: Project Manager or Salesperson can modify
- State selection (`bklg_state`) visibility depends on user group

### Wizards

**`forecast.wizard` (wizard/forecast.py:4-91)**
- Sets `date_deadline` on sale order lines
- Creates mail activities for backlog manager
- Handles: forecast, Unforecast, send_invoicing, send_provisioning actions
- Increments `replanning_count`

**`replan.wizard` and `forecast.status.update`**
- Support replanning and status updates for backlog items

## Testing

Test suite in `tests/test_invoice_status.py` validates:
1. Invoice status updates with accepted/objected DTE
2. Draft invoices don't trigger state changes
3. Credit notes dynamically revert backlog state (Odoo 17 idiomatic approach)
4. Partial credit notes keep invoiced state
5. Provisioned lines revert to provisioned (not planning) after full credit

Tests generate reports in `tests/reports/` directory.

## Key Design Patterns

**Chilean Localization Integration:**
- All invoice/credit note validations check `l10n_cl_dte_status in ['objected', 'accepted']`
- Only posted documents with valid DTE status trigger state changes

**Dynamic State Computation (Odoo 17 Pattern):**
- States computed from net invoice amounts (invoice - credit_note)
- No stored "previous state" needed
- Credit notes automatically revert state by reducing net amount
- Idempotent computation follows Odoo standard (like qty_invoiced)

**Currency Freezing:**
- When line reaches 'provisioned' or 'invoiced', currency amounts freeze
- `compute_clp_currency()` and `_compute_amount_us()` skip frozen lines
- Prevents exchange rate fluctuations from affecting provisioned/invoiced amounts

**Activity Tracking:**
- Uses `mail.activity.mixin` for task management
- Creates activities for backlog manager group on specific state transitions
- Activity type filtered by `is_todo=True` field

## File Structure

```
backlog/
├── models/
│   ├── backlog.py          # BacklogStages, backlog_lines (sale.order.line extension)
│   ├── sale_order_line.py  # Invoice tracking fields and automation
│   └── sale.py             # Sale order extensions
├── wizard/
│   ├── forecast.py         # Forecast wizard for date/state changes
│   ├── replan.py           # Replanning wizard
│   └── forecast_status_update.py  # Status update wizard
├── views/
│   ├── backlog_view.xml    # Main backlog kanban/tree/form views
│   ├── backlog_stages.xml  # Stage configuration views
│   └── backlog_menus.xml   # Menu structure
├── security/
│   ├── security.xml        # Security groups definition
│   └── ir.model.access.csv # Model access rights
└── tests/
    └── test_invoice_status.py  # Invoice status automation tests
```

## Important Notes

- Always use `docker exec -it odoo-17` to run Odoo commands
- Test report generation requires writable `tests/reports/` directory
- Exchange rates are pulled from `res.currency` using the forecast_date or create_date
- The module depends on Chilean localization (`l10n_cl`) for DTE integration
- When modifying computed fields, remember frozen lines (provisioned/invoiced) skip recomputation
