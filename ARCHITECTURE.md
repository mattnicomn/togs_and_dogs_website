# Architecture - Togs and Dogs

## Logical Architecture
The system follows a serverless, event-driven architecture using AWS native services.

### 1. Frontend Layer
- **Operations Portal**: Hosted on `toganddogs.usmissionhero.com`. This is the core application for client intake and admin management.
- **Branded Portal Gateway**: Entry point at `/` that serves as a professional operations hub.
- **Public Marketing**: Ryan's main marketing site remains at `toganddogs.com`, linking to the operations portal for booking.
- **Admin Dashboard**: Protected by **AWS Cognito**. Provides interface for Ryan to approve/decline and assign workers.

### 2. API & Logic Layer
- **API Gateway**: Handles HTTP requests.
    - `/intake` (POST): Public ingestion.
    - `/admin/*`: Private management (Authenticated via Cognito).
- **Python Lambdas**: Handle business logic, validation, and database interactions.
- **Workflow (Step Functions)**: Orchestrates the multi-step process from Service Request -> Ryan Approval -> Job Conversion -> Calendar Sync.

### 3. Data Layer
- **DynamoDB**: Single table `TogAndDogsData`. Focuses on core workflow access patterns (Intake, Request, Job, Staff).
- **Secrets Manager**: Centralized secret storage for GCal OAuth and future app integrations.
- **Observability**: CloudWatch Log Groups with standardized naming and retention for audit trails.

### 4. Integration Layer
- **Google Calendar API**: External sync for approved bookings.
- **Amazon SES/SNS**: Email and SMS alerts for Ryan and staff.

## Data Model (First-Pass)

| Entity | Attributes |
|---|---|
| **Client** | ID, Name, Phone, Address, Email, Status |
| **Pet** | ID, OwnerID, Name, Breed, Age, CareInstructions |
| **ServiceRequest** | ID, ClientID, Dates, ServiceType, Status (Pending/Approved/Declined) |
| **Job** | ID, RequestID, WorkerID, Status (Assigned/Completed) |
| **Staff** | ID, Name, Role (Ryan/Wife/Nephew), ContactInfo |
| **AuditLog** | ID, Action, User, Timestamp, EntityRef |

## Coordination Logic
1. **Intake**: Client fills form -> Lambda writes to `ServiceRequests`.
2. **Review**: Ryan logs in -> Sees pending requests -> Updates status.
3. **Execution**: On Approval -> Lambda triggers GCal Sync and creates a `Job` record.
4. **Assignment**: Ryan manually assigns `Job` to a `Staff` member in the dashboard.
