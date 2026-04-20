## Workflow Status Model
The system uses a shared status model to track the lifecycle of Service Requests and Jobs.

### Service Request Statuses
- `REQUEST_SUBMITTED`: Initial entry after client submission.
- `REQUEST_UNDER_REVIEW`: Ryan has seen the request and is evaluating.
- `REQUEST_APPROVED`: Ryan has approved the dates and service.
- `REQUEST_DECLINED`: Request was rejected.

### Job Statuses
- `JOB_CREATED`: Initial state of a job record.
- `JOB_ASSIGNED`: Worker (Ryan, Wife, Nephew) has been assigned to the job.
    - *Note: The staff list is currently a hardcoded frontend configuration (Ryan, Wife, Nephew1, Nephew2) and requires manual sync until the Staff Directory module is implemented.*
- `JOB_IN_PROGRESS`: Service has started.
- `JOB_COMPLETED`: Service is finished.
- `JOB_CANCELLED`: Job was aborted after creation.
- `CANCELLATION_REQUESTED`: Customer has requested to void the booking.
- `CANCELLED`: Final administrative cancellation (Request-level).
- `CANCELLATION_DENIED`: Ryan/Admin has rejected the cancellation request.

## Records
### Client Record
- **PK**: `CLIENT#<uuid>`
- **SK**: `METADATA`
- **Attributes**: `name`, `email`, `phone`, `address`, `status`, `created_at`, `root_folder_id` (Google/OneDrive link)

### Pet Record (Care Card)
- **PK**: `PET#<uuid>`
- **SK**: `CLIENT#<client_uuid>`
- **Attributes**:
    - `name`, `breed`, `age`
    - `photo_url`: S3 URL for fast UI display
    - `care_instructions`: feeding instructions, medication/dosage/timing
    - `behavior`: temperament, triggers, social notes
    - `logistics`: access codes, key locations, entry notes
    - `health`: vet details (name/phone), emergency contact (name/phone)
    - `document_links`:
        - `intake_form_url`
        - `vaccination_records_url`
        - `care_instructions_doc_url`
        - `photos_folder_url`
        - `misc_files_url`
    - `meet_and_greet_completed`: boolean
    - *Note: This is an administrative gate for first-time approvals. It can be manually toggled via the 'Mark M&G Complete' action in the Admin Dashboard.*

### Service Request Record
- **PK**: `REQ#<uuid>`
- **SK**: `CLIENT#<client_uuid>`
- **Attributes**: 
    - `start_date`, `end_date`, `service_type`, `status`
    - `window_type`: `WALK_30MIN`, `DROPIN_1HR`, `DROPIN_3HR`, `OVERNIGHT`, `EXACT_TIME`
    - `preferred_start`, `preferred_end`
    - `arrival_window_start`, `arrival_window_end`
    - `created_at`
    - `cancellation_reason`, `cancellation_requested_at`, `cancellation_requested_by`
    - `cancellation_decision_at`, `cancellation_decision_by`, `cancellation_decision_note`
    - `notification_delivery_status`: Map of worker/customer notification results

### Job Record (Tasks)
- **PK**: `JOB#<uuid>`
- **SK**: `REQ#<req_uuid>`
- **Attributes**: 
    - `worker_id`, `status`
    - `scheduled_start`, `scheduled_end`
    - `assigned_at`, `status_audit_log`

### Staff/Worker Record
- **PK**: `WORKER#<uuid>`
- **SK**: `METADATA`
- **Attributes**: 
    - `name`, `role`, `contact_info`
    - `color_code`: (e.g., Deep Blue for Ryan, Teal for Wife)

## Global Secondary Indexes (GSI)
- **GSI1 (StatusIndex)**:
    - **PK**: `status`
    - **SK**: `created_at`
    - Used to find all `PENDING` requests for Ryan's dashboard.
- **GSI2 (WorkerIndex)**:
    - **PK**: `worker_id`
    - **SK**: `assigned_at`
    - Used to find all jobs assigned to a specific worker.
