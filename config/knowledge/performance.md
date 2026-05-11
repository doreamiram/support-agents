# Performance Degradation and High Latency

## Summary

This article covers performance degradation in Modelyo Confidential Cloud, including high CPU/memory utilization, elevated API latency, throughput bottlenecks, and slow query response times.

## Affected Components

- `compute-engine`
- `api-gateway`

## Common Symptoms

- API response times exceeding expected SLA thresholds
- CPU utilization above 80% sustained
- Memory utilization above 85% with OOM errors
- Reduced throughput (requests per second below baseline)
- Job queues backing up or stalling
- Intermittent timeouts on previously stable operations

## Diagnostic Steps

Run the following checks and share the output with the support team:

1. **CPU and memory snapshot**
   ```
   top -bn1 | head -20
   free -h
   vmstat 1 5
   ```

2. **Process inventory**
   ```
   ps aux --sort=-%cpu | head -15
   ps aux --sort=-%mem | head -15
   ```

3. **Disk I/O**
   ```
   iostat -x 1 5
   df -h
   ```

4. **API latency measurement**
   ```
   curl -w "@curl-format.txt" -o /dev/null -s https://<endpoint>/health
   ```
   (curl-format.txt should contain: `time_total: %{time_total}\n`)

5. **Network throughput**
   ```
   iftop -t -s 5
   ```

## Common Causes and Resolutions

### High CPU utilization
- Identify the CPU-intensive process using `ps` or `top`
- Check for runaway jobs or infinite loops in scheduled tasks
- If caused by Modelyo workloads, review job concurrency settings and reduce parallelism
- Enable CPU throttling for non-critical background workloads

### High memory utilization
- Check for memory leaks using `valgrind` or heap profiling tools specific to your runtime
- Review caching configuration — reduce in-memory cache size if exceeding available RAM
- Increase memory limits if the workload genuinely requires more resources
- Enable swap carefully — excessive swap use causes significant latency

### Elevated API latency
- Compare latency with and without local network hops to isolate client-side delays
- Check the API gateway access logs for upstream timeout patterns
- Verify no rate limiting is active on your tenant (`X-RateLimit-Remaining` response header)
- Review query patterns — N+1 query problems cause disproportionate latency

### Throughput bottlenecks
- Check connection pool settings — insufficient pool size causes queuing
- Verify the load balancer health checks are not consuming excessive capacity
- Review autoscaling policy — scale-out threshold may need adjustment for your workload

## Escalation

When escalating, include: CPU/memory snapshots, API latency samples (p50, p95, p99), and the time window when degradation began.
