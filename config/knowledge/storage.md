# Storage Access Errors and Data Availability

## Summary

This article covers storage access issues in Modelyo Confidential Cloud, including bucket access errors, upload/download failures, disk unavailability, and object-not-found errors.

## Affected Components

- `storage-service`

## Common Symptoms

- HTTP 404 when accessing a known object or bucket
- HTTP 403 when uploading or downloading files
- Upload operations timing out or returning 503
- Object data appears corrupted or incomplete after download
- Storage bucket quota exceeded
- Disk unavailable or I/O errors on mounted volumes

## Diagnostic Steps

Run the following checks and share the results with the support team:

1. **Bucket existence and permissions**
   ```
   modelyo storage ls <bucket-name>
   modelyo storage stat <bucket-name>/<object-key>
   ```

2. **Upload test with a small file**
   ```
   echo "test" > /tmp/test.txt
   modelyo storage put /tmp/test.txt <bucket-name>/test-probe-$(date +%s).txt
   ```

3. **Download test**
   ```
   modelyo storage get <bucket-name>/<known-object-key> /tmp/download-test.bin
   md5sum /tmp/download-test.bin
   ```

4. **Quota check**
   ```
   modelyo storage quota <bucket-name>
   ```

5. **Volume mount status** (for block storage)
   ```
   df -h
   lsblk
   dmesg | tail -50 | grep -i "error\|fail\|disk\|I/O"
   ```

## Common Causes and Resolutions

### HTTP 403 on upload/download
- Verify the IAM role or access key attached to your workload has the required storage permissions
- Check bucket policy — object-level ACLs may override bucket-level permissions
- Confirm you are accessing the bucket in the correct region/zone

### HTTP 404 on object access
- Confirm the object key is correct (paths are case-sensitive)
- Check whether the object was deleted recently — enable versioning to recover previous versions
- If the bucket itself returns 404, it may have been deleted or renamed

### Upload timeout / 503
- Check storage service health (use `modelyo storage health`)
- Retry with exponential backoff — brief 503 responses indicate capacity pressure
- Split large uploads into multipart chunks (recommended for objects > 100 MB)

### Data corruption
- Verify the MD5/SHA-256 checksum of the downloaded object against the `ETag` header
- Re-upload the original file and re-attempt the download
- If corruption persists, escalate immediately — do not overwrite the affected object

### Quota exceeded
- Review current usage: `modelyo storage quota <bucket-name>`
- Delete or archive objects no longer required
- Request a quota increase through the Modelyo billing portal

## Escalation

When escalating, include: bucket name (redact credentials), operation attempted, HTTP status code received, and the output of `modelyo storage stat` for the affected object.
