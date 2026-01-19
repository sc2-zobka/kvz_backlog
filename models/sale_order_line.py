# -*- coding: utf-8 -*-
from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    real_invoiced_amount = fields.Float(
        string="Monto Linea Facturado",
        compute="_compute_real_invoiced_amounts",
        store=True,
        readonly=True,
        help="Monto real para esta línea específico desde las facturas en contabilidad. "
        "Impuestos excluidos. "
        "Incluye reembolsos (montos negativos).",
    )

    real_invoice_total = fields.Float(
        string="Total Factura Real",
        compute="_compute_real_invoiced_amounts",
        store=True,
        readonly=True,
        help="Monto total de todas las facturas relacionadas (monto completo). "
        "Incluye impuestos. "
        "Suma de todas las facturas asociadas a esta línea.",
    )

    invoice_number = fields.Char(
        string="Factura",
        compute="_compute_invoice_number",
        help="Número de factura asociado al hito.",
        readonly=True,
        store=True,
    )

    credit_note_number = fields.Char(
        string="Nota de Crédito",
        compute="_compute_credit_note_info",
        help="Número de la nota de crédito asociada (si existe).",
        readonly=True,
        store=True,
    )

    has_credit_note = fields.Boolean(
        string="Tiene Nota de Crédito",
        compute="_compute_credit_note_info",
        help="Indica si esta línea tiene una nota de crédito asociada.",
        readonly=True,
        store=True,
    )

    credit_note_amount = fields.Float(
        string="Monto Nota de Crédito",
        compute="_compute_credit_note_info",
        help="Monto total de las notas de crédito asociadas.",
        readonly=True,
        store=True,
    )

    initial_provisioned_amount = fields.Float(
        string="Monto Inicial Provisionado",
        compute="_compute_initial_provisioned_amount",
        default=0.0,
        readonly=True,
        store=True,
        help="Captura el monto de la línea de pedido cuando se mueve a la etapa 'Provisionado'. Sin IVA.",
    )

    initial_provisioned_amount_datetime = fields.Datetime(
        help="Fecha y hora en que se registró el monto provisionado.",
        readonly=True,
        store=True,
    )

    income_recognition_date = fields.Date(
        string="Recognition Date",
        compute="_compute_income_recognition_date",
        store=True,
        readonly=True,
        help="Fecha de reconocimiento de ingresos. Se establece inicialmente en date_deadline, "
        "luego se actualiza con la fecha más temprana entre invoice_date y initial_provisioned_amount_datetime.",
    )

    invoice_line_date = fields.Date(
        string="Invoice Date",
        compute="_compute_invoice_line_date",
        store=True,
        readonly=True,
        help="Fecha de la factura relacionada. Solo se muestra para facturas aceptadas u objetadas.",
    )

    @api.depends("backlog_state_id", "price_subtotal")
    def _compute_initial_provisioned_amount(self):
        """Compute initial provisioned amount and datetime (one-time snapshot)"""

        provisioned_stage = self.env.ref(
            "kvz_backlog.block_stage_005", raise_if_not_found=False
        )

        if not provisioned_stage:
            _logger.warning("Etapa 'Provisionado' (block_stage_005) no encontrada.")
            return

        for record in self:
            if record.initial_provisioned_amount_datetime:
                continue

            if record.backlog_state_id.id == provisioned_stage.id:
                record.initial_provisioned_amount = record.price_subtotal or 0.0
                record.initial_provisioned_amount_datetime = fields.Datetime.now()

    @api.depends(
        "date_deadline",
        "invoice_lines.move_id.invoice_date",
        "initial_provisioned_amount_datetime",
    )
    def _compute_income_recognition_date(self):
        """
        Compute income recognition date with the following logic:
        1. Initially set to date_deadline
        2. After initialization, use the earliest date between:
           - invoice_date from related invoice
           - date part of initial_provisioned_amount_datetime
        3. If only one exists, use that one
        4. If neither exists, keep date_deadline
        """
        for record in self:
            # Start with date_deadline as the default
            recognition_date = record.date_deadline

            # Get invoice date if available (from posted invoices)
            invoice_date = None
            if record.invoice_lines:
                posted_invoices = record.invoice_lines.filtered(
                    lambda ml: ml.move_id
                    and ml.move_id.state == "posted"
                    and ml.move_id.move_type == "out_invoice"
                    and ml.move_id.l10n_cl_dte_status in ["objected", "accepted"]
                )
                if posted_invoices:
                    # Get the earliest invoice date
                    invoice_dates = posted_invoices.mapped("move_id.invoice_date")
                    invoice_date = min(invoice_dates) if invoice_dates else None

            # Get provision date if available (extract date from datetime)
            provision_date = None
            if record.initial_provisioned_amount_datetime:
                provision_date = record.initial_provisioned_amount_datetime.date()

            # Determine the income recognition date
            available_dates = []
            if invoice_date:
                available_dates.append(invoice_date)
            if provision_date:
                available_dates.append(provision_date)

            if available_dates:
                # Use the earliest of the available dates
                recognition_date = min(available_dates)

            record.income_recognition_date = recognition_date

    @api.depends(
        "invoice_lines.move_id.invoice_date",
        "invoice_lines.move_id.state",
        "invoice_lines.move_id.l10n_cl_dte_status",
    )
    def _compute_invoice_line_date(self):
        """
        Compute invoice date from posted invoice with valid DTE status.
        Only shows date when an actual invoice exists (posted + accepted/objected).
        """
        for line in self:
            # Filter for posted invoices with valid DTE status
            posted_invoices = line.invoice_lines.filtered(
                lambda ml: ml.move_id
                and ml.move_id.move_type == "out_invoice"
                and ml.move_id.state == "posted"
                and ml.move_id.l10n_cl_dte_status in ["objected", "accepted"]
            )
            if posted_invoices:
                # Get the earliest invoice date (if multiple invoices)
                invoice_dates = posted_invoices.mapped("move_id.invoice_date")
                line.invoice_line_date = min(invoice_dates) if invoice_dates else False
            else:
                line.invoice_line_date = False

    @api.depends("invoice_lines.move_id.name")
    def _compute_invoice_number(self):
        """
        Compute the invoice number based on the related account.move.
        This field will be set when the sale order line is invoiced.
        """
        for line in self:
            # Get the invoice number from the related account.move
            invoice_line = line.invoice_lines.filtered(
                lambda ml: ml.move_id
                and ml.move_id.move_type == "out_invoice"
                and ml.move_id.state == "posted"
                and ml.move_id.l10n_cl_dte_status in ["objected", "accepted"]
            )
            if invoice_line:
                line.invoice_number = invoice_line[0].move_id.name
            else:
                line.invoice_number = False

    @api.depends(
        "invoice_lines.move_id.name",
        "invoice_lines.move_id.state",
        "invoice_lines.move_id.move_type",
        "invoice_lines.price_subtotal",
    )
    def _compute_credit_note_info(self):
        """
        Compute credit note information.
        - credit_note_number: Number of the credit note
        - has_credit_note: Boolean indicating if credit note exists
        - credit_note_amount: Total amount of credit notes
        """
        for line in self:
            # Filter for posted credit notes (refunds)
            credit_note_lines = line.invoice_lines.filtered(
                lambda ml: ml.move_id
                and ml.move_id.move_type == "out_refund"
                and ml.move_id.state == "posted"
                and ml.move_id.l10n_cl_dte_status in ["objected", "accepted"]
            )

            if credit_note_lines:
                line.has_credit_note = True
                # Get all credit note numbers (comma separated if multiple)
                credit_notes = credit_note_lines.mapped("move_id")
                line.credit_note_number = ", ".join(credit_notes.mapped("name"))
                # Sum the absolute values of credit note amounts
                line.credit_note_amount = abs(
                    sum(credit_note_lines.mapped("price_subtotal"))
                )
            else:
                line.has_credit_note = False
                line.credit_note_number = False
                line.credit_note_amount = 0.0

    @api.depends(
        "invoice_lines.move_id.state",
        "invoice_lines.price_subtotal",
        "invoice_status",
    )
    def _compute_real_invoiced_amounts(self):
        """
        Compute real amounts from actual posted invoices.
        - real_invoiced_amount: Amount specific to this sale line
        - real_invoice_total: Total of all related invoices
        """
        for record in self:
            # Reset to zero by default
            record.real_invoiced_amount = 0.0
            record.real_invoice_total = 0.0

            # Only process if there are invoice lines
            if not record.invoice_lines:
                continue

            # Filter only posted customer invoices and refunds
            posted_invoice_lines = record.invoice_lines.filtered(
                lambda ml: ml.move_id
                and ml.move_id.state == "posted"
                and ml.move_id.move_type in ["out_invoice", "out_refund"]
                and ml.move_id.l10n_cl_dte_status in ["objected", "accepted"]
            )

            if not posted_invoice_lines:
                continue

            # 1. Line-specific amount (price_subtotal is already signed)
            # Positive for invoices, negative for refunds
            record.real_invoiced_amount = sum(
                posted_invoice_lines.mapped("price_subtotal")
            )

            # 2. Total invoice amounts (avoid counting same invoice multiple times)
            unique_invoices = posted_invoice_lines.mapped("move_id")
            record.real_invoice_total = sum(
                unique_invoices.mapped("amount_total_signed")
            )

            # Optional: Log for debugging
            if record.real_invoiced_amount:
                _logger.info(
                    f"Sale line {record.id}: "
                    f"Line amount={record.real_invoiced_amount}, "
                    f"Invoice total={record.real_invoice_total}, "
                    f"Has credit note={record.has_credit_note}, "
                    f"Status={record.invoice_status}"
                )

    @api.depends(
        "invoice_lines.move_id.state",
        "invoice_lines.move_id.move_type",
        "invoice_lines.move_id.l10n_cl_dte_status",
        "invoice_lines.price_subtotal",
        "qty_to_invoice",
        "qty_invoiced",
    )
    def _compute_invoice_status(self):
        """
        Override to automatically update backlog state based on invoice analysis.

        Follows Odoo 17 standard pattern (like qty_invoiced):
        - Computes state dynamically from net invoice amounts
        - Credit notes automatically "revert" state by reducing net amount
        - No stored "previous state" needed (idempotent computation)

        State logic:
        - net_amount > 0 + invoice_status='invoiced' → bklg_state='invoiced'
        - net_amount == 0 (fully credited) → revert to 'provisioned' or 'planning'
        - net_amount < 0 (over-credited) → handle edge case
        """
        super(SaleOrderLine, self)._compute_invoice_status()

        invoiced_stage = self.env.ref(
            "kvz_backlog.block_stage_006", raise_if_not_found=False
        )
        provisioned_stage = self.env.ref(
            "kvz_backlog.block_stage_005", raise_if_not_found=False
        )
        planning_stage = self.env.ref(
            "kvz_backlog.block_stage_002", raise_if_not_found=False
        )

        if not invoiced_stage:
            _logger.warning("Etapa 'Facturado' (block_stage_006) no encontrada.")
            return

        for line in self:
            # Skip if no backlog state field or no invoice lines
            if not hasattr(line, "bklg_state") or not line.invoice_lines:
                continue

            # Get all posted invoice/refund lines with valid DTE status
            # Following Chilean localization requirements
            valid_invoice_lines = line.invoice_lines.filtered(
                lambda ml: ml.move_id
                and ml.move_id.state == "posted"
                and ml.move_id.move_type in ["out_invoice", "out_refund"]
                and ml.move_id.l10n_cl_dte_status in ["objected", "accepted"]
            )

            if not valid_invoice_lines:
                continue

            # Calculate NET invoiced amount using sign multiplier pattern
            # This is the standard Odoo 17 approach (see sale_subscription module)
            amount_sign = {"out_invoice": 1, "out_refund": -1}
            net_invoiced_amount = sum(
                amount_sign.get(ml.move_id.move_type, 1) * ml.price_subtotal
                for ml in valid_invoice_lines
            )

            _logger.debug(
                f"Sale line {line.id}: net_invoiced_amount={net_invoiced_amount}, "
                f"invoice_status={line.invoice_status}, "
                f"current_bklg_state={line.bklg_state}"
            )

            # State computation based on net amount
            currency = line.currency_id or line.order_id.currency_id

            if line.invoice_status == "invoiced" and not currency.is_zero(
                net_invoiced_amount
            ):
                # Fully invoiced with positive net amount → mark as invoiced
                if line.bklg_state != "invoiced":
                    line.bklg_state = "invoiced"
                    _logger.info(
                        f"Sale line {line.id} marked as invoiced (net amount: {net_invoiced_amount})"
                    )

                if (
                    hasattr(line, "backlog_state_id")
                    and line.backlog_state_id.id != invoiced_stage.id
                ):
                    line.backlog_state_id = invoiced_stage

            elif currency.is_zero(net_invoiced_amount):
                # Net amount is zero (fully credited) → revert state
                # Determine revert target based on business logic

                # If was previously provisioned, go back to provisioned
                if line.initial_provisioned_amount_datetime and provisioned_stage:
                    if line.bklg_state != "provisioned":
                        line.bklg_state = "provisioned"
                        line.backlog_state_id = provisioned_stage
                        _logger.info(
                            f"Sale line {line.id} reverted to provisioned (fully credited)"
                        )

                        # Log in chatter if available
                        if hasattr(line, "message_post") and line.has_credit_note:
                            line.message_post(
                                body=f"<b>Backlog state automatically reverted to 'Provisioned' due to credit note.<br/>"
                                f"Credit Note(s): {line.credit_note_number}</b>"
                            )

                # Otherwise, revert to planning
                elif planning_stage and line.bklg_state == "invoiced":
                    line.bklg_state = "planning"
                    line.backlog_state_id = planning_stage
                    _logger.info(
                        f"Sale line {line.id} reverted to planning (fully credited)"
                    )

                    # Log in chatter
                    if hasattr(line, "message_post") and line.has_credit_note:
                        line.message_post(
                            body=f"<b>Backlog state automatically reverted to 'Planning' due to credit note.<br/>"
                            f"Credit Note(s): {line.credit_note_number}</b>"
                        )

            elif net_invoiced_amount < 0:
                # Over-credited edge case (refund > invoice)
                _logger.warning(
                    f"Sale line {line.id} has negative net amount: {net_invoiced_amount}. "
                    f"This indicates over-crediting."
                )
