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
        help="Real amount for this specific line from the actual invoices in accounting. "
        "Includes refunds (negative amounts).",
    )

    real_invoice_total = fields.Float(
        string="Total Factura Real",
        compute="_compute_real_invoiced_amounts",
        store=True,
        readonly=True,
        help="Total amount of all related invoices (entire invoice amount). "
        "Sum of all invoices related to this line.",
    )
    
    invoice_number = fields.Char(
        string="Factura",
        compute="_compute_invoice_number",
        help="Número de factura asociado al hito.",
        readonly=True,
        store=True,
    )
    
    @api.depends("invoice_lines.move_id.name")
    def _compute_invoice_number(self):
        """
        Compute the invoice number based on the related account.move.
        This field will be set when the sale order line is invoiced.
        """
        for line in self:
            # Get the invoice number from the related account.move
            move_line = line.invoice_lines.filtered(
                lambda ml: ml.move_id
                and ml.move_id.move_type in ["out_invoice", "out_refund"]
            )
            if move_line:
                line.invoice_number = move_line[0].move_id.name
            else:
                line.invoice_number = False

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
                    f"Status={record.invoice_status}"
                )

    def write(self, vals):
        """
        Override write to automatically set backlog state fields
        when invoice_status becomes 'invoiced'.
        """
        if "invoice_status" in vals and vals["invoice_status"] == "invoiced":
            vals["bklg_state"] = "invoiced"
            vals["backlog_state_id"] = 4

        return super(SaleOrderLine, self).write(vals)
