# Evaluation Workflow Monitoring Updates

## Overview
Updated the evaluation workflow to include comprehensive job monitoring that continues until the job is finished, replacing the previous placeholder implementation.

## Changes Made

### 1. New Monitoring Activity (`budeval/evals/workflows.py`)
- Added `monitor_eval_job_progress` activity that checks job status using the Ansible orchestrator
- Returns structured job status information including success/failure states
- Handles errors gracefully and returns appropriate error responses

### 2. Enhanced Workflow Monitoring Loop
- Implemented continuous monitoring with configurable intervals (5 seconds between checks)
- Maximum monitoring duration of 30 minutes (360 attempts × 5 seconds)
- Monitors both high-level job status and detailed Kubernetes job conditions
- Checks for job completion states: `succeeded`, `failed`, `completed`, `error`
- Also monitors Kubernetes-specific job counters: `active`, `succeeded`, `failed`

### 3. Improved Notifications
- Progress notifications every 50 seconds (every 10 monitoring attempts)
- Success/failure notifications when job completes
- Timeout notifications if monitoring exceeds maximum duration
- Updated ETA estimates to be more realistic (30 minutes for evaluation jobs)

### 4. Enhanced Ansible Orchestrator (`budeval/registry/orchestrator/ansible_orchestrator.py`)
- Added `_run_ansible_playbook_with_output` method to capture Ansible execution results
- Added `_parse_job_status_from_ansible_output` method to extract job status from Ansible events
- Enhanced `get_job_status` method to return detailed status information
- Improved error handling with structured error responses

### 5. Fixed Ansible Playbook (`budeval/ansible/playbooks/get_job_status_k8s.yml`)
- Fixed syntax error in the debug task
- Playbook now properly sets job status facts for parsing

### 6. Enhanced Service Layer (`budeval/evals/services.py`)
- `get_job_status` method now returns comprehensive job information
- Includes job status, namespace, and detailed Kubernetes information
- Proper error handling for failed status checks

## Monitoring Flow

1. **Job Deployment**: After successful job deployment, extract job ID from results
2. **Monitoring Loop**: 
   - Check job status every 5 seconds
   - Parse Kubernetes job conditions (`active`, `succeeded`, `failed`)
   - Determine overall status based on conditions
   - Continue until job completes or timeout (30 minutes)
3. **Progress Notifications**: Send status updates every 50 seconds
4. **Completion Handling**: 
   - Success: Include job results in final notification
   - Failure: Send failure notification and exit workflow
   - Timeout: Send timeout notification and exit workflow

## Status Determination Logic

```python
if succeeded > 0:
    status = "succeeded"
elif failed > 0:
    status = "failed"
elif active > 0:
    status = "running"
else:
    status = "pending"
```

## Configuration

- **Monitoring Interval**: 5 seconds
- **Maximum Monitoring Time**: 30 minutes (1800 seconds)
- **Progress Notification Frequency**: Every 50 seconds
- **Job Namespace**: `budeval`

## Error Handling

- Network/cluster connection failures are handled gracefully
- Ansible playbook failures return structured error responses
- Monitoring timeouts are detected and reported
- All errors include detailed error messages for debugging

## Benefits

1. **Real-time Monitoring**: Continuous job status tracking
2. **Reliable Completion Detection**: Multiple methods to detect job completion
3. **User Feedback**: Regular progress updates and clear completion notifications
4. **Robust Error Handling**: Graceful handling of various failure scenarios
5. **Configurable Timeouts**: Prevents infinite monitoring loops
6. **Detailed Logging**: Comprehensive logging for debugging and monitoring

## Testing

The implementation has been tested with:
- Syntax validation of all modified files
- Error handling verification with mock Kubernetes clusters
- Status determination logic validation
- Monitoring loop logic verification

## Future Enhancements

1. **Dynamic Timeout Configuration**: Allow timeout configuration per job type
2. **Enhanced Status Parsing**: Parse more detailed job information from Kubernetes
3. **Metrics Collection**: Add monitoring metrics for job execution times
4. **Retry Logic**: Add retry mechanisms for transient failures
5. **Job Logs Retrieval**: Fetch and include job logs in completion notifications 