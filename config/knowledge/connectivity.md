# Network Connectivity Troubleshooting

## Summary

This article covers common network connectivity issues in Modelyo Confidential Cloud, including DNS resolution failures, VPN connection drops, timeout errors, and unreachable endpoints.

## Affected Components

- `network-service`
- `api-gateway`

## Common Symptoms

- Connection refused or connection timeout when reaching an API endpoint
- DNS resolution failures (NXDOMAIN or SERVFAIL)
- High packet loss or elevated latency (>500 ms) to Modelyo endpoints
- VPN tunnel drops or fails to establish

## Diagnostic Steps

Run the following checks and share the output with the support team:

1. **DNS resolution check**
   ```
   dig <your-modelyo-endpoint>
   nslookup <your-modelyo-endpoint>
   ```

2. **Connectivity test**
   ```
   ping -c 4 <your-modelyo-endpoint>
   curl -v --max-time 10 https://<your-modelyo-endpoint>/health
   ```

3. **Routing and firewall check**
   ```
   traceroute <your-modelyo-endpoint>
   ```

4. **VPN status** (if using VPN)
   Check your VPN client status and review VPN logs for tunnel state.

## Common Causes and Resolutions

### DNS failure
- Verify your DNS resolver is reachable: `dig @8.8.8.8 <endpoint>`
- Check that your network's firewall allows UDP/TCP port 53
- If using a private DNS zone, confirm the resolver is correctly configured

### Connection refused
- Confirm the target port is open in your firewall/security group
- Verify no local proxy or corporate firewall is blocking egress on the required port
- Check that the API gateway is not under maintenance (consult Modelyo status page)

### High latency or packet loss
- Identify the hop with latency using `traceroute`
- Check for network congestion on your local network
- Verify your ISP or cloud provider does not have an active incident

### VPN tunnel failure
- Re-authenticate your VPN client
- Check that your VPN endpoint IP has not changed
- Review firewall rules for IKE/IPSec ports (UDP 500, UDP 4500)

## Escalation

If the above steps do not resolve the issue within 30 minutes, escalate to Modelyo Tier 2 with the diagnostic output from each step above attached to the ticket.
