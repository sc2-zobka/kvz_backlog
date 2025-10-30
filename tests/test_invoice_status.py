# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
import logging
import os
from datetime import datetime

_logger = logging.getLogger(__name__)


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
            "kvz_backlog.block_stage_006", raise_if_not_found=False
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

        # Determine report file path
        module_path = os.path.dirname(os.path.dirname(__file__))
        reports_dir = os.path.join(module_path, "tests", "reports")

        try:
            # Create reports directory if it doesn't exist
            os.makedirs(reports_dir, exist_ok=True)

            # Generate filename with timestamp
            filename = (
                f"test_invoice_status_{test_end_time.strftime('%Y%m%d_%H%M%S')}.txt"
            )
            report_path = os.path.join(reports_dir, filename)

            # Also create a "latest" version
            latest_path = os.path.join(reports_dir, "test_invoice_status_latest.txt")

            # Write the timestamped report
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)

            # Write latest version
            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(report_content)

            # Log success
            _logger.info("=" * 80)
            _logger.info(f"Test report saved to: {report_path}")
            _logger.info(f"Latest report: {latest_path}")
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
