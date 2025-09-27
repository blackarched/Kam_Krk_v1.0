# NeonHack Enhanced Features Documentation v6.0

## Overview

This document describes the comprehensive enhancements made to the NeonHack application, including enhanced logging, progress tracking, retry mechanisms, modular attack framework, and unified API endpoints.

## 🚀 Enhanced Features

### 1. Enhanced Logging System

#### ContextualLogger Class
- **User-friendly messages**: All logs include contextual information without exposing sensitive backend details
- **Operation tracking**: Start, success, and failure states are logged with context
- **Security event logging**: Authentication failures and suspicious activities are tracked
- **Performance metrics**: Duration tracking for operations
- **Job status changes**: All job state transitions are logged with details

#### Example Log Outputs
```
🚀 STARTING: Hydra Attack Job | User: a1b2c3d4 | Target: 192.168.1.10 | Protocol: ssh
✅ SUCCESS: API Call: POST /api/hydra_attack | Duration: 0.15s | User: a1b2c3d4
🔄 JOB STATUS: queued → running | Job: abc123def456 | User: a1b2c3d4
❌ FAILED: Hydra Attack | User: a1b2c3d4 | Error: Hydra binary not found
🔒 SECURITY: Authentication Failure | Invalid API key attempt from IP: 192.168.1.100
```

### 2. Progress Indicators & Job Management

#### Enhanced Database Schema
```sql
-- New columns added to jobs table
progress INTEGER DEFAULT 0,           -- Progress percentage (0-100)
progress_message TEXT,               -- User-friendly progress message
error_count INTEGER DEFAULT 0,       -- Number of retry attempts
max_retries INTEGER DEFAULT 3,       -- Maximum retry attempts allowed
expires_at TEXT,                     -- When the job should be cleaned up
priority INTEGER DEFAULT 5          -- Job priority (1-10, 1 being highest)
```

#### JobManager Class Features
- **Progress tracking**: Real-time progress updates with user-friendly messages
- **Automatic expiration**: Jobs automatically expire after 24 hours
- **Statistics**: Job statistics by status and user
- **Cleanup mechanism**: Automatic cleanup of expired jobs

#### New API Endpoints

##### Get Job Status with Progress
```http
GET /api/job_status/{job_id}
```
**Response:**
```json
{
  "id": "abc123def456",
  "status": "running",
  "progress": 75,
  "progress_message": "Hydra attack in progress...",
  "type": "hydra_attack",
  "created_at": "2025-09-27T10:30:00Z",
  "result": null
}
```

##### List Jobs with Filtering
```http
GET /api/jobs?status=running&type=hydra_attack&limit=20&offset=0
```
**Response:**
```json
{
  "jobs": [...],
  "total": 15,
  "limit": 20,
  "offset": 0
}
```

##### Job Statistics
```http
GET /api/jobs/statistics
```
**Response:**
```json
{
  "statistics": {
    "running": 3,
    "queued": 2,
    "done": 45,
    "error": 1
  },
  "user": "a1b2c3d4"
}
```

##### Manual Job Cleanup
```http
POST /api/jobs/cleanup
```
**Response:**
```json
{
  "message": "Cleanup completed successfully",
  "deleted_jobs": 12
}
```

### 3. Retry Mechanisms

#### Retry Configuration
- **Exponential backoff**: Delays increase exponentially with jitter
- **Retryable exceptions**: Network errors, timeouts, and connection issues
- **Maximum retries**: Configurable per operation (default: 3)
- **Jitter**: 10% random variation to prevent thundering herd

#### Retry Decorator Usage
```python
@with_retry(max_retries=3, retryable_exceptions=(NetworkRetryableError, TimeoutRetryableError))
def network_operation():
    # Your network operation here
    pass
```

#### Enhanced Functions with Retry
- **Hydra attacks**: Retries on network/timeout errors
- **Metasploit exploits**: Retries on connection issues
- **Camera scans**: Retries on network discovery failures
- **Network scans**: Retries on socket communication errors

### 4. Modular Attack Framework

#### AttackModule Base Class
All attack modules inherit from `AttackModule` and implement:
- Parameter validation
- Execution logic
- Progress tracking integration
- Error handling

#### Available Attack Modules

##### HydraAttackModule
```json
{
  "name": "hydra_attack",
  "description": "Brute force authentication using Hydra",
  "required_params": ["target_ip", "protocol", "username_wordlist", "password_wordlist"],
  "optional_params": {"timeout": 300, "threads": 16}
}
```

##### MetasploitAttackModule
```json
{
  "name": "metasploit_exploit",
  "description": "Execute Metasploit exploits",
  "required_params": ["target_ip", "module"],
  "optional_params": {"timeout": 60, "payload": null}
}
```

##### CameraScanModule
```json
{
  "name": "camera_scan",
  "description": "Scan network for cameras",
  "required_params": ["network_cidr"],
  "optional_params": {"timeout": 300}
}
```

##### NetworkScanModule
```json
{
  "name": "network_scan",
  "description": "ARP scan for network discovery",
  "required_params": ["target_cidr", "interface"],
  "optional_params": {"timeout": 30}
}
```

#### Custom Module Registration
```python
class CustomAttackModule(AttackModule):
    def __init__(self):
        super().__init__(
            name="custom_attack",
            description="Custom attack implementation",
            required_params=["target"],
            optional_params={"option1": "default_value"}
        )
    
    def execute(self, job_id, params):
        # Implementation here
        pass

# Register the module
attack_framework.register_module(CustomAttackModule())
```

### 5. Unified Attack API

#### Single Endpoint for All Attacks
```http
POST /api/attack
```

#### Request Format
```json
{
  "attack_type": "hydra_attack",
  "priority": 3,
  "parameters": {
    "target_ip": "192.168.1.10",
    "protocol": "ssh",
    "username_wordlist": "admin\nroot\nuser",
    "password_wordlist": "password\n123456\nadmin",
    "timeout": 300
  }
}
```

#### Response
```json
{
  "job_id": "abc123def456",
  "attack_type": "hydra_attack",
  "status": "queued",
  "message": "hydra_attack attack job created successfully",
  "priority": 3
}
```

#### List Available Modules
```http
GET /api/attack/modules
```
**Response:**
```json
{
  "available_modules": {
    "hydra_attack": {
      "description": "Brute force authentication using Hydra",
      "required_params": ["target_ip", "protocol", "username_wordlist", "password_wordlist"],
      "optional_params": {"timeout": 300, "threads": 16}
    },
    "metasploit_exploit": {...},
    "camera_scan": {...},
    "network_scan": {...}
  },
  "total_modules": 4
}
```

### 6. Automatic Job Cleanup

#### Scheduled Cleanup
- **Frequency**: Every hour
- **Criteria**: Jobs older than 24 hours OR completed jobs older than 24 hours
- **Logging**: All cleanup operations are logged

#### Manual Cleanup
- Available via API endpoint: `POST /api/jobs/cleanup`
- Returns count of deleted jobs
- Accessible to authenticated users

### 7. Enhanced Error Handling

#### User-Friendly Error Messages
- Technical details are logged but not exposed to users
- Contextual error information helps with debugging
- Retry attempts are logged with explanations

#### Error Categories
- **Retryable errors**: Network issues, timeouts, connection problems
- **Non-retryable errors**: Configuration issues, invalid parameters
- **Security errors**: Authentication failures, unauthorized access

## 🔧 Configuration

### Environment Variables
```bash
# Existing
NEONHACK_API_KEY=your-secure-api-key
MSF_PASSWORD=metasploit-rpc-password

# New (optional)
NEONHACK_LOG_LEVEL=INFO
NEONHACK_JOB_RETENTION_HOURS=24
NEONHACK_MAX_RETRIES=3
```

### Database Migration
The application automatically migrates existing databases to the new schema on startup. No manual intervention required.

## 📊 Monitoring & Observability

### Log Files
- **Console output**: Real-time operations
- **File logging**: `neonhack.log` (if writable)
- **Structured format**: Timestamps, levels, operation context

### Performance Metrics
- API call durations
- Job execution times
- Retry attempt tracking
- Success/failure rates

### Health Indicators
- Job queue status
- Database performance
- Cleanup effectiveness
- Error rates by type

## 🚨 Security Enhancements

### Enhanced Authentication Logging
- Failed login attempts with IP tracking
- API key usage monitoring
- Suspicious activity detection

### Resource Management
- Job priority system
- Automatic cleanup prevents resource exhaustion
- Process limits and timeouts

### Data Protection
- Secure deletion of temporary files
- Sanitized error messages
- No sensitive data in logs

## 📈 Usage Examples

### Basic Hydra Attack with Progress Tracking
```bash
# Start attack
curl -X POST http://localhost:5000/api/attack \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "attack_type": "hydra_attack",
    "priority": 2,
    "parameters": {
      "target_ip": "192.168.1.10",
      "protocol": "ssh",
      "username_wordlist": "admin\nroot",
      "password_wordlist": "password\n123456"
    }
  }'

# Check progress
curl -X GET http://localhost:5000/api/job_status/abc123def456 \
  -H "X-API-Key: your-api-key"
```

### Monitor All Jobs
```bash
# List running jobs
curl -X GET "http://localhost:5000/api/jobs?status=running" \
  -H "X-API-Key: your-api-key"

# Get statistics
curl -X GET http://localhost:5000/api/jobs/statistics \
  -H "X-API-Key: your-api-key"
```

## 🔄 Migration Guide

### From v5.2 to v6.0
1. **Database**: Automatic migration on first startup
2. **API**: All existing endpoints remain compatible
3. **New features**: Available immediately after upgrade
4. **Logging**: Enhanced logging starts automatically

### Backward Compatibility
- All existing API endpoints work unchanged
- Legacy job creation methods supported
- Existing job data preserved during migration

## 🎯 Benefits

1. **Better Observability**: Comprehensive logging and monitoring
2. **Improved Reliability**: Retry mechanisms reduce transient failures
3. **Enhanced UX**: Progress tracking provides real-time feedback
4. **Easier Management**: Unified API and automatic cleanup
5. **Extensibility**: Modular framework for custom attacks
6. **Performance**: Optimized database queries and resource management

## 📚 API Reference Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/attack` | POST | Unified attack execution |
| `/api/attack/modules` | GET | List available attack modules |
| `/api/jobs` | GET | List jobs with filtering |
| `/api/jobs/statistics` | GET | Job statistics |
| `/api/jobs/cleanup` | POST | Manual job cleanup |
| `/api/job_status/{id}` | GET | Enhanced job status with progress |

All endpoints require the `X-API-Key` header for authentication.