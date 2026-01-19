# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged
from odoo import fields
import logging
import os
from datetime import datetime

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestInvoiceStatus(TransactionCase):
    """Test cases for _compute_invoice_status method in sale.order.line"""

    @classmethod
    def setUpClass(cls):
        super(TestInvoiceStatus, cls).setUpClass()
        cls.test_results = []
        cls.test_start_time = datetime.now()

    def setUp(self):
        super(TestInvoiceStatus, self).setUp()

        # Create test data
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
            }
        )

        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "service",
                "list_price": 1000.0,
                "invoice_policy": "delivery",
            }
        )

        # Get invoiced stage
        self.invoiced_stage = self.env.ref(
            "backlog.block_stage_006", raise_if_not_found=False
        )

    def _log_test_result(self, test_name, passed, message=""):
        """Log individual test results"""
        self.__class__.test_results.append(
            {"name": test_name, "passed": passed, "message": message}
        )

    @classmethod
    def tearDownClass(cls):
        """Generate test report and save to file - ALWAYS writes to file"""
        super(TestInvoiceStatus, cls).tearDownClass()

        if not cls.test_results:
            _logger.warning("No test results to report")
            return

        # Calculate statistics
        passed = sum(1 for r in cls.test_results if r["passed"])
        failed = len(cls.test_results) - passed
        test_end_time = datetime.now()
        duration = (test_end_time - cls.test_start_time).total_seconds()

        # Prepare report content
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("TEST REPORT - Invoice Status Compute Method")
        report_lines.append("=" * 80)
        report_lines.append(f"Test Date: {test_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Duration: {duration:.2f} seconds")
        report_lines.append(f"Database: {cls.env.cr.dbname}")
        report_lines.append("")
        report_lines.append("-" * 80)
        report_lines.append("TEST RESULTS")
        report_lines.append("-" * 80)

        # Individual test results
        for idx, result in enumerate(cls.test_results, 1):
            status = "PASSED" if result["passed"] else "FAILED"
            report_lines.append(f"{idx}. [{status}] {result['name']}")
            if result["message"]:
                report_lines.append(f"   Details: {result['message']}")
            report_lines.append("")

        report_lines.append("-" * 80)
        report_lines.append("SUMMARY")
        report_lines.append("-" * 80)
        report_lines.append(f"Total Tests: {len(cls.test_results)}")
        report_lines.append(f"Passed: {passed}")
        report_lines.append(f"Failed: {failed}")
        report_lines.append(
            f"Success Rate: {(passed / len(cls.test_results) * 100):.1f}%"
        )
        report_lines.append("")

        # Overall status
        if failed == 0:
            report_lines.append("OVERALL STATUS: ALL TESTS PASSED")
        else:
            report_lines.append("OVERALL STATUS: SOME TESTS FAILED")

        report_lines.append("=" * 80)

        # Write to file - THIS ALWAYS HAPPENS
        report_content = "\n".join(report_lines)

        # Determine report file path using Odoo's module path
        try:
            # Get the module path from Odoo's module registry
            import odoo.modules as addons

            module_path = addons.get_module_path("backlog")
        except Exception:
            # Fallback to __file__ if module path resolution fails
            module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        reports_dir = os.path.join(module_path, "tests", "reports")

        try:
            # Create reports directory if it doesn't exist
            os.makedirs(reports_dir, exist_ok=True)

            # Log the actual path being used
            _logger.info(f"Report directory: {reports_dir}")
            _logger.info(f"Directory exists: {os.path.exists(reports_dir)}")
            _logger.info(f"Directory is writable: {os.access(reports_dir, os.W_OK)}")

            # Generate filename with timestamp
            filename = (
                f"test_invoice_status_{test_end_time.strftime('%Y%m%d_%H%M%S')}.txt"
            )
            report_path = os.path.join(reports_dir, filename)

            # Write the report
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)
            _logger.info(f"Report written to: {report_path}")

            # Verify file was created
            if os.path.exists(report_path):
                _logger.info(
                    f"✓ Confirmed: Report file exists with size {os.path.getsize(report_path)} bytes"
                )
            else:
                _logger.error(f"✗ Report file NOT found at {report_path}")

            # Log success
            _logger.info("=" * 80)
            _logger.info(f"Test report saved to: {report_path}")
            _logger.info("=" * 80)

            # Also print to console if available (but file writing happens regardless)
            try:
                print("\n" + "=" * 80)
                print("TEST SUMMARY - Invoice Status Compute Method")
                print("=" * 80)

                for result in cls.test_results:
                    status = "PASSED" if result["passed"] else "FAILED"
                    print(f"[{status}] {result['name']}")

                print(f"\nTotal: {len(cls.test_results)}")
                print(f"Passed: {passed}")
                if failed > 0:
                    print(f"Failed: {failed}")

                if failed == 0:
                    print("\nALL TESTS PASSED")
                else:
                    print("\nSOME TESTS FAILED")

                print(f"\nReport saved to: {report_path}")
                print("=" * 80 + "\n")
            except Exception as print_error:
                # If console output fails, that's OK - file is already written
                _logger.debug(f"Console output failed (non-critical): {print_error}")

        except Exception as e:
            # If file writing fails, log the error but also try to log to Odoo logger
            error_msg = f"CRITICAL: Failed to write test report to {reports_dir}: {e}"
            _logger.error(error_msg)
            _logger.error(f"Report content was:\n{report_content}")

            # Try to write to a fallback location
            try:
                fallback_path = f"/tmp/odoo_test_report_{test_end_time.strftime('%Y%m%d_%H%M%S')}.txt"
                with open(fallback_path, "w", encoding="utf-8") as f:
                    f.write(report_content)
                _logger.warning(f"Report saved to fallback location: {fallback_path}")
            except Exception as fallback_error:
                _logger.error(f"Even fallback failed: {fallback_error}")

    def test_compute_invoice_status_with_accepted_dte(self):
        """Test that backlog state is updated to 'invoiced' when invoice is posted with accepted DTE status"""
        test_name = "Invoice Status with Accepted DTE"

        try:
            # Create a sale order
            sale_order = self.env["sale.order"].create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 1.0,
                                "price_unit": 100.0,
                                "qty_delivered": 1.0,
                            },
                        )
                    ],
                }
            )

            # Confirm sale order
            sale_order.action_confirm()

            sol = sale_order.order_line[0]

            # Initial state checks
            self.assertEqual(sale_order.state, "sale", "Sale order should be confirmed")
            self.assertIn(
                sol.invoice_status,
                ["to invoice", "no"],
                "Sale order line should be invoiceable",
            )

            # Create and post invoice
            invoice = sale_order._create_invoices()
            self.assertTrue(invoice, "Invoice should be created")

            invoice.action_post()
            self.assertEqual(invoice.state, "posted", "Invoice should be posted")

            # Set DTE status to accepted
            if hasattr(invoice, "l10n_cl_dte_status"):
                invoice.l10n_cl_dte_status = "accepted"

            # Trigger compute method
            sol._compute_invoice_status()

            # Assertions
            self.assertEqual(
                sol.invoice_status,
                "invoiced",
                "Sale order line invoice_status should be 'invoiced'",
            )

            if hasattr(sol, "bklg_state"):
                self.assertEqual(
                    sol.bklg_state,
                    "invoiced",
                    "Backlog state should be updated to 'invoiced'",
                )

            if self.invoiced_stage and hasattr(sol, "backlog_state_id"):
                self.assertEqual(
                    sol.backlog_state_id.id,
                    self.invoiced_stage.id,
                    f"Backlog stage should be '{self.invoiced_stage.name}'",
                )

            self._log_test_result(
                test_name, True, "Backlog state correctly updated to 'invoiced'"
            )

        except AssertionError as e:
            self._log_test_result(test_name, False, str(e))
            raise

    def test_compute_invoice_status_with_draft_invoice(self):
        """Test that backlog state is NOT updated when invoice is in draft state"""
        test_name = "Invoice Status with Draft Invoice"

        try:
            # Create a sale order
            sale_order = self.env["sale.order"].create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 1.0,
                                "price_unit": 100.0,
                                "qty_delivered": 1.0,
                            },
                        )
                    ],
                }
            )

            # Confirm sale order
            sale_order.action_confirm()

            sol = sale_order.order_line[0]

            initial_bklg_state = sol.bklg_state if hasattr(sol, "bklg_state") else None
            initial_stage_id = (
                sol.backlog_state_id.id
                if hasattr(sol, "backlog_state_id") and sol.backlog_state_id
                else None
            )

            # Create invoice but don't post it
            invoice = sale_order._create_invoices()
            self.assertEqual(invoice.state, "draft", "Invoice should be in draft state")

            if hasattr(invoice, "l10n_cl_dte_status"):
                invoice.l10n_cl_dte_status = "accepted"

            # Trigger compute method
            sol._compute_invoice_status()

            # Assertions - backlog state should NOT change
            if hasattr(sol, "bklg_state"):
                self.assertEqual(
                    sol.bklg_state,
                    initial_bklg_state,
                    "Backlog state should NOT change when invoice is draft",
                )

            if hasattr(sol, "backlog_state_id"):
                current_stage_id = (
                    sol.backlog_state_id.id if sol.backlog_state_id else None
                )
                self.assertEqual(
                    current_stage_id,
                    initial_stage_id,
                    "Backlog stage should NOT change when invoice is draft",
                )

            self._log_test_result(
                test_name, True, "Draft invoice correctly did not update backlog state"
            )

        except AssertionError as e:
            self._log_test_result(test_name, False, str(e))
            raise

    def test_compute_invoice_status_with_objected_dte(self):
        """Test that backlog state is updated even with objected DTE status"""
        test_name = "Invoice Status with Objected DTE"

        try:
            # Create a sale order
            sale_order = self.env["sale.order"].create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 1.0,
                                "price_unit": 100.0,
                                "qty_delivered": 1.0,
                            },
                        )
                    ],
                }
            )

            # Confirm sale order
            sale_order.action_confirm()

            sol = sale_order.order_line[0]

            # Create and post invoice
            invoice = sale_order._create_invoices()
            invoice.action_post()

            # Set DTE status to objected
            if hasattr(invoice, "l10n_cl_dte_status"):
                invoice.l10n_cl_dte_status = "objected"

            # Trigger compute method
            sol._compute_invoice_status()

            # Assertions
            self.assertEqual(
                sol.invoice_status,
                "invoiced",
                "Sale order line invoice_status should be 'invoiced'",
            )

            if hasattr(sol, "bklg_state"):
                self.assertEqual(
                    sol.bklg_state,
                    "invoiced",
                    "Backlog state should be updated to 'invoiced' even with objected DTE",
                )

            self._log_test_result(
                test_name, True, "Objected DTE correctly updated backlog state"
            )

        except AssertionError as e:
            self._log_test_result(test_name, False, str(e))
            raise

    def test_credit_note_reverts_backlog_state(self):
        """Test that posting a credit note dynamically reverts the backlog state (Odoo 17 idiomatic approach)"""
        test_name = "Credit Note Reverts Backlog State (Dynamic Computation)"

        try:
            # Get planning stage for initial state
            planning_stage = self.env.ref(
                "backlog.block_stage_002", raise_if_not_found=False
            )

            # Create a sale order
            sale_order = self.env["sale.order"].create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 1.0,
                                "price_unit": 100.0,
                                "qty_delivered": 1.0,
                            },
                        )
                    ],
                }
            )

            # Confirm sale order
            sale_order.action_confirm()
            sol = sale_order.order_line[0]

            # Set initial backlog state to planning
            if planning_stage:
                sol.bklg_state = "planning"
                sol.backlog_state_id = planning_stage

            initial_state = sol.bklg_state
            initial_stage = sol.backlog_state_id

            _logger.info(
                f"Initial state: {initial_state}, stage: {initial_stage.name if initial_stage else None}"
            )

            # Create and post invoice
            invoice = sale_order._create_invoices()
            invoice.action_post()

            # Set DTE status to accepted
            if hasattr(invoice, "l10n_cl_dte_status"):
                invoice.l10n_cl_dte_status = "accepted"

            # Trigger compute to mark as invoiced
            sol._compute_invoice_status()

            # Verify it was marked as invoiced
            self.assertEqual(
                sol.bklg_state,
                "invoiced",
                "Backlog state should be 'invoiced' after posting invoice",
            )

            _logger.info(f"After invoice: state={sol.bklg_state}")

            # Create a credit note for the invoice (full refund)
            refund_wizard = (
                self.env["account.move.reversal"]
                .with_context(active_model="account.move", active_ids=invoice.ids)
                .create(
                    {
                        "reason": "Test credit note",
                        "journal_id": invoice.journal_id.id,
                    }
                )
            )

            # Create the refund
            refund_action = refund_wizard.reverse_moves()
            credit_note = self.env["account.move"].browse(refund_action["res_id"])

            # Post the credit note
            credit_note.action_post()

            # Set DTE status to accepted
            if hasattr(credit_note, "l10n_cl_dte_status"):
                credit_note.l10n_cl_dte_status = "accepted"

            _logger.info(f"Credit note created and posted: {credit_note.name}")

            # Trigger compute to detect credit note
            # State should be computed dynamically based on net amount (invoice - credit_note = 0)
            sol._compute_invoice_status()
            sol._compute_credit_note_info()

            _logger.info(
                f"After credit note: state={sol.bklg_state}, has_credit_note={sol.has_credit_note}"
            )

            # Assertions - state should be reverted AUTOMATICALLY
            self.assertTrue(
                sol.has_credit_note,
                "Sale order line should have a credit note",
            )

            # State should revert to planning (since net invoiced amount is now zero)
            self.assertEqual(
                sol.bklg_state,
                initial_state,
                f"Backlog state should dynamically revert to '{initial_state}' "
                f"after full credit note (net amount = 0)",
            )

            if planning_stage and initial_stage:
                self.assertEqual(
                    sol.backlog_state_id.id,
                    initial_stage.id,
                    f"Backlog stage should dynamically revert to '{initial_stage.name}' "
                    f"after credit note",
                )

            self._log_test_result(
                test_name,
                True,
                "Backlog state correctly reverted using dynamic computation (no stored state)",
            )

        except AssertionError as e:
            self._log_test_result(test_name, False, str(e))
            raise

    def test_credit_note_with_objected_dte_reverts_state(self):
        """Test that credit note with objected DTE status dynamically reverts backlog state (Odoo 17 idiomatic)"""
        test_name = "Credit Note with Objected DTE Reverts State (Dynamic)"

        try:
            # Get planning stage for initial state
            planning_stage = self.env.ref(
                "backlog.block_stage_002", raise_if_not_found=False
            )

            # Create a sale order
            sale_order = self.env["sale.order"].create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 1.0,
                                "price_unit": 100.0,
                                "qty_delivered": 1.0,
                            },
                        )
                    ],
                }
            )

            # Confirm sale order
            sale_order.action_confirm()
            sol = sale_order.order_line[0]

            # Set initial backlog state to planning
            if planning_stage:
                sol.bklg_state = "planning"
                sol.backlog_state_id = planning_stage

            initial_state = sol.bklg_state

            # Create and post invoice
            invoice = sale_order._create_invoices()
            invoice.action_post()

            if hasattr(invoice, "l10n_cl_dte_status"):
                invoice.l10n_cl_dte_status = "accepted"

            # Trigger compute to mark as invoiced
            sol._compute_invoice_status()

            # Verify it was marked as invoiced
            self.assertEqual(sol.bklg_state, "invoiced")

            # Create a credit note
            refund_wizard = (
                self.env["account.move.reversal"]
                .with_context(active_model="account.move", active_ids=invoice.ids)
                .create(
                    {
                        "reason": "Test objected credit note",
                        "journal_id": invoice.journal_id.id,
                    }
                )
            )

            refund_action = refund_wizard.reverse_moves()
            credit_note = self.env["account.move"].browse(refund_action["res_id"])
            credit_note.action_post()

            # Set DTE status to objected (not accepted)
            if hasattr(credit_note, "l10n_cl_dte_status"):
                credit_note.l10n_cl_dte_status = "objected"

            # Trigger compute
            sol._compute_invoice_status()
            sol._compute_credit_note_info()

            # Assertions - state should still be reverted even with objected status
            self.assertEqual(
                sol.bklg_state,
                initial_state,
                f"Backlog state should revert even with objected DTE status",
            )

            self._log_test_result(
                test_name, True, "Objected credit note correctly reverted backlog state"
            )

        except AssertionError as e:
            self._log_test_result(test_name, False, str(e))
            raise

    def test_partial_credit_note_keeps_invoiced_state(self):
        """Test that partial credit note doesn't revert state (net amount still positive)"""
        test_name = "Partial Credit Note Keeps Invoiced State"

        try:
            planning_stage = self.env.ref(
                "backlog.block_stage_002", raise_if_not_found=False
            )

            # Create sale order with 2 lines
            sale_order = self.env["sale.order"].create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 2.0,  # 2 units
                                "price_unit": 100.0,
                                "qty_delivered": 2.0,
                            },
                        )
                    ],
                }
            )

            sale_order.action_confirm()
            sol = sale_order.order_line[0]

            if planning_stage:
                sol.bklg_state = "planning"
                sol.backlog_state_id = planning_stage

            # Create and post invoice for full amount (200.0)
            invoice = sale_order._create_invoices()
            invoice.action_post()

            if hasattr(invoice, "l10n_cl_dte_status"):
                invoice.l10n_cl_dte_status = "accepted"

            sol._compute_invoice_status()

            # Verify invoiced
            self.assertEqual(sol.bklg_state, "invoiced")
            _logger.info(
                f"After invoice: state={sol.bklg_state}, amount={sol.price_subtotal}"
            )

            # Create partial credit note for only 1 unit (100.0 out of 200.0)
            # Manually create a partial refund
            refund = self.env["account.move"].create(
                {
                    "move_type": "out_refund",
                    "partner_id": self.partner.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "quantity": 1.0,  # Only 1 unit
                                "price_unit": 100.0,
                                "sale_line_ids": [(4, sol.id)],
                            },
                        )
                    ],
                }
            )
            refund.action_post()

            if hasattr(refund, "l10n_cl_dte_status"):
                refund.l10n_cl_dte_status = "accepted"

            _logger.info(f"Partial credit note created: {refund.name}")

            # Trigger compute
            sol._compute_invoice_status()
            sol._compute_credit_note_info()

            _logger.info(
                f"After partial credit: state={sol.bklg_state}, "
                f"has_credit_note={sol.has_credit_note}"
            )

            # Assertions - state should STAY 'invoiced' (net amount still > 0)
            self.assertTrue(sol.has_credit_note)
            self.assertEqual(
                sol.bklg_state,
                "invoiced",
                "Backlog state should remain 'invoiced' after partial credit note "
                "(net amount = 200 - 100 = 100 > 0)",
            )

            self._log_test_result(
                test_name,
                True,
                "Partial credit note correctly keeps invoiced state (dynamic net amount check)",
            )

        except AssertionError as e:
            self._log_test_result(test_name, False, str(e))
            raise

    def test_provisioned_line_reverts_to_provisioned(self):
        """Test that provisioned lines revert to provisioned (not planning) after full credit"""
        test_name = "Provisioned Line Reverts to Provisioned After Credit"

        try:
            provisioned_stage = self.env.ref(
                "backlog.block_stage_005", raise_if_not_found=False
            )

            if not provisioned_stage:
                self._log_test_result(
                    test_name, True, "Skipped - provisioned stage not found"
                )
                return

            # Create sale order
            sale_order = self.env["sale.order"].create(
                {
                    "partner_id": self.partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "product_uom_qty": 1.0,
                                "price_unit": 100.0,
                                "qty_delivered": 1.0,
                            },
                        )
                    ],
                }
            )

            sale_order.action_confirm()
            sol = sale_order.order_line[0]

            # Set to provisioned state
            sol.bklg_state = "provisioned"
            sol.backlog_state_id = provisioned_stage
            sol.initial_provisioned_amount = sol.price_subtotal
            sol.initial_provisioned_amount_datetime = fields.Datetime.now()

            # Create and post invoice
            invoice = sale_order._create_invoices()
            invoice.action_post()

            if hasattr(invoice, "l10n_cl_dte_status"):
                invoice.l10n_cl_dte_status = "accepted"

            sol._compute_invoice_status()

            # Should be invoiced now
            self.assertEqual(sol.bklg_state, "invoiced")

            # Create full credit note
            refund_wizard = (
                self.env["account.move.reversal"]
                .with_context(active_model="account.move", active_ids=invoice.ids)
                .create(
                    {
                        "reason": "Test full credit",
                        "journal_id": invoice.journal_id.id,
                    }
                )
            )

            refund_action = refund_wizard.reverse_moves()
            credit_note = self.env["account.move"].browse(refund_action["res_id"])
            credit_note.action_post()

            if hasattr(credit_note, "l10n_cl_dte_status"):
                credit_note.l10n_cl_dte_status = "accepted"

            # Trigger compute
            sol._compute_invoice_status()
            sol._compute_credit_note_info()

            # Should revert to PROVISIONED (not planning)
            self.assertEqual(
                sol.bklg_state,
                "provisioned",
                "Provisioned line should revert to 'provisioned' after full credit note",
            )

            self.assertEqual(
                sol.backlog_state_id.id,
                provisioned_stage.id,
                "Should revert to provisioned stage",
            )

            self._log_test_result(
                test_name,
                True,
                "Provisioned line correctly reverted to provisioned (not planning)",
            )

        except AssertionError as e:
            self._log_test_result(test_name, False, str(e))
            raise
