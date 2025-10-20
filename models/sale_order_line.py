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
        help="Fecha y hora en que se registró el monto inicial provisionado.",
        readonly=True,
        store=True,
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
                _logger.debug(
                    f"Sale line {record.id}: "
                    f"Line amount={record.real_invoiced_amount}, "
                    f"Invoice total={record.real_invoice_total}, "
                    f"Has credit note={record.has_credit_note}, "
                    f"Status={record.invoice_status}"
                )

    @api.depends("invoice_lines.move_id.state", "qty_to_invoice", "qty_invoiced")
    def _compute_invoice_status(self):
        """
        Override to automatically update backlog state when invoice_status changes.
        Uses direct assignment instead of write() to avoid recursion.
        """
        super(SaleOrderLine, self)._compute_invoice_status()

        invoiced_stage = self.env.ref(
            "kvz_backlog.block_stage_006", raise_if_not_found=False
        )

        if not invoiced_stage:
            _logger.warning("Etapa 'Facturado' (block_stage_006) no encontrada.")
            return

        for line in self:
            if line.invoice_status == "invoiced":
                if hasattr(line, "bklg_state") and line.bklg_state != "invoiced":
                    line.bklg_state = "invoiced"

                if (
                    hasattr(line, "backlog_state_id")
                    and line.backlog_state_id.id != invoiced_stage.id
                ):
                    line.backlog_state_id = invoiced_stage

                _logger.debug(
                    f"Sale line {line.id} backlog state updated to 'invoiced'"
                )
