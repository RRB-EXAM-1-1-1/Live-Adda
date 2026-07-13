# Live Adda - API Contracts & Integration Plan

## Overview
This document outlines the API contracts between frontend and backend, mock data locations, and integration steps for building the full-stack Live Adda application.

## Mock Data Location
- **File**: `/app/frontend/src/mock.js`
- **Data**: Plans, features, user data, stream status, videos, activity

## Authentication System

### JWT + Google OAuth Integration

#### Auth Endpoints
1. **POST /api/auth/register**
   - Input: `{ email, password, name }`
   - Output: `{ user_id, email, name, created_at }` + cookies (access_token, refresh_token)

2. **POST /api/auth/login**
   - Input: `{ email, password }`
   - Output: `{ user_id, email, name }` + cookies (access_token, refresh_token)

3. **POST /api/auth/logout**
   - Input: None (uses cookies)
   - Output: `{ message: "Logged out successfully" }`

4. **GET /api/auth/me**
   - Input: None (uses cookies or Authorization header)
   - Output: `{ user_id, email, name, plan, balance }`

5. **POST /api/auth/google-session** (Emergent OAuth)
   - Input: `{ session_id }` from URL fragment
   - Output: `{ user_id, email, name, picture }` + session_token cookie

## Video Management

### Video Endpoints
1. **POST /api/videos/upload**
   - Input: FormData with video file (chunked upload)
   - Output: `{ video_id, title, duration, size, thumbnail_url }`

2. **GET /api/videos**
   - Input: None (authenticated)
   - Output: `[{ video_id, title, duration, size, thumbnail_url, uploaded_at }]`

3. **DELETE /api/videos/:video_id**
   - Input: video_id in URL
   - Output: `{ message: "Video deleted successfully" }`

### Storage System
- Videos stored in `/app/backend/uploads/videos/`
- Thumbnails stored in `/app/backend/uploads/thumbnails/`
- Implement chunked upload to bypass proxy limits

## Live Streaming

### Live Slot Endpoints
1. **GET /api/live-slot**
   - Input: None (authenticated)
   - Output: `{ is_live, current_video, viewers, uptime, next_video }`

2. **POST /api/live-slot/start**
   - Input: `{ video_playlist: [video_ids] }`
   - Output: `{ status: "live", stream_url }`

3. **POST /api/live-slot/stop**
   - Input: None
   - Output: `{ status: "stopped" }`

4. **PUT /api/live-slot/settings**
   - Input: `{ auto_rotate: boolean, loop_videos: boolean }`
   - Output: `{ message: "Settings updated" }`

## Payment Integration (Stripe)

### Payment Endpoints
1. **POST /api/payments/checkout-session**
   - Input: `{ plan_id: 'daily' | 'weekly' | 'monthly', origin_url }`
   - Output: `{ session_id, checkout_url }`
   - Note: Backend defines fixed prices (Daily: $4.99, Weekly: $24.99, Monthly: $79.99)

2. **GET /api/payments/checkout-status/:session_id**
   - Input: session_id in URL
   - Output: `{ status, payment_status, amount, plan_id }`

3. **POST /api/webhook/stripe**
   - Input: Stripe webhook payload
   - Output: `{ received: true }`
   - Action: Update user plan and credits in database

### Payment Flow
1. Frontend sends plan_id + window.location.origin to backend
2. Backend creates checkout session with fixed prices
3. User completes payment on Stripe
4. User redirected back with session_id in URL
5. Frontend polls payment status
6. Backend updates user plan after successful payment

## Billings & Subscription

### Billing Endpoints
1. **GET /api/billings/current-plan**
   - Input: None (authenticated)
   - Output: `{ plan_name, price, next_billing_date, payment_method }`

2. **GET /api/billings/transactions**
   - Input: None (authenticated)
   - Output: `[{ id, date, description, amount, status }]`

## Support

### Support Endpoints
1. **POST /api/support/ticket**
   - Input: `{ subject, message }`
   - Output: `{ ticket_id, created_at }`

## Database Schema

### Collections

#### users
```
{
  user_id: string (custom UUID),
  email: string (unique),
  password_hash: string (for JWT auth),
  name: string,
  picture: string (from Google OAuth),
  plan: string (daily/weekly/monthly),
  balance: number,
  active_live_slots: number,
  total_videos: number,
  created_at: datetime
}
```

#### user_sessions (for Google OAuth)
```
{
  user_id: string,
  session_token: string,
  expires_at: datetime,
  created_at: datetime
}
```

#### videos
```
{
  video_id: string,
  user_id: string,
  title: string,
  duration: string,
  size: number,
  file_path: string,
  thumbnail_url: string,
  uploaded_at: datetime
}
```

#### live_streams
```
{
  stream_id: string,
  user_id: string,
  is_live: boolean,
  current_video_id: string,
  playlist: [video_ids],
  viewers: number,
  started_at: datetime,
  settings: {
    auto_rotate: boolean,
    loop_videos: boolean
  }
}
```

#### payment_transactions
```
{
  transaction_id: string,
  user_id: string,
  session_id: string (Stripe),
  plan_id: string,
  amount: number,
  currency: string,
  payment_status: string,
  status: string,
  created_at: datetime
}
```

#### support_tickets
```
{
  ticket_id: string,
  user_id: string,
  subject: string,
  message: string,
  status: string,
  created_at: datetime
}
```

## Frontend Integration Steps

1. **Remove mock data imports** from components
2. **Add API service layer** (`/app/frontend/src/services/api.js`)
3. **Update components** to use real API calls
4. **Add AuthContext** for global auth state
5. **Add ProtectedRoute** wrapper for dashboard routes
6. **Add polling mechanism** for payment status checks
7. **Add loading states** and error handling

## Backend Implementation Steps

1. **Setup authentication** (JWT + Emergent OAuth)
2. **Create video upload endpoint** with chunking
3. **Implement Stripe payment** integration
4. **Add live stream management** logic
5. **Create database models** and seed admin user
6. **Add proper error handling** and validation
7. **Test all endpoints** with curl/Postman

## Key Notes
- All prices are defined in backend (security)
- Video uploads use chunking (handle large files)
- Payment polling required (no webhook in dev)
- Session_token in httpOnly cookies (security)
- User_id is custom UUID (not MongoDB _id)
