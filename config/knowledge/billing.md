# Billing, Invoicing, and Subscription Issues

## Summary

This article covers billing and account issues in Modelyo Confidential Cloud, including unexpected charges, invoice discrepancies, subscription management, quota alerts, and payment failures.

## Affected Components

- `billing-service`

## Common Symptoms

- Invoice amount does not match expected usage
- Payment declined or subscription suspended
- Usage quota alert despite workloads appearing normal
- Missing or delayed invoice
- Incorrect billing period or date on invoice
- Subscription plan features unavailable despite active plan

## Diagnostic Steps

Collect the following information before contacting support:

1. **Account and subscription details**
   - Your Modelyo account ID (shown in the portal under Account Settings)
   - Subscription plan name and billing period (monthly/annual)
   - Invoice ID or billing period in dispute (e.g., "2026-04")

2. **Usage report**
   ```
   modelyo billing usage --period <YYYY-MM>
   modelyo billing usage --period <YYYY-MM> --breakdown resource
   ```

3. **Invoice download**
   ```
   modelyo billing invoice get <invoice-id>
   ```

4. **Quota status**
   ```
   modelyo billing quota list
   ```

5. **Payment method status**
   Check in the Modelyo portal under Billing → Payment Methods for any declined card or expired payment method notifications.

## Common Causes and Resolutions

### Unexpected charges
- Review the usage breakdown report for the billing period — look for any resources that were not intentionally provisioned
- Check for orphaned resources (stopped instances, unattached volumes, idle load balancers) that still incur charges
- Verify autoscaling did not create additional instances during a traffic spike

### Invoice discrepancy
- Compare the line items in the downloaded invoice against `modelyo billing usage --breakdown resource`
- If a line item cannot be reconciled, note the resource ID and timestamp and raise a dispute through the portal

### Payment failure / subscription suspended
- Update the payment method in the portal under Billing → Payment Methods
- After updating, manually trigger a retry under Billing → Invoices → Retry Payment
- Contact your bank if the card is being declined despite sufficient balance

### Missing or delayed invoice
- Invoices are generated on the 1st of each month for the previous period
- Allow 24 hours after the period end before raising a missing-invoice ticket

### Quota alert
- Review `modelyo billing quota list` to identify which quota is being approached
- Increase limits through the portal under Billing → Quotas if your plan permits self-service adjustment
- For hard limits, submit a quota increase request — include your use case and requested new limit

## Escalation

When escalating, include: account ID, invoice ID or billing period, resource IDs in dispute, and the output of the usage breakdown command for the affected period.
