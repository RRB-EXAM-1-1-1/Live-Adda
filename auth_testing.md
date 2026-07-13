# Auth Testing Playbook for Live Adda

## Emergent Google OAuth Testing

### Step 1: Create Test User & Session
```bash
mongosh --eval "
use('live_adda_db');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

### Step 2: Test Backend API
```bash
# Test auth endpoint
curl -X GET "YOUR_APP_URL/api/auth/me" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"

# Test protected endpoints
curl -X GET "YOUR_APP_URL/api/videos" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

### Step 3: Checklist
- [ ] User document has user_id field (custom UUID)
- [ ] Session user_id matches user's user_id exactly
- [ ] All queries use `{"_id": 0}` projection
- [ ] Backend queries use user_id (not _id or id)
- [ ] API returns user data with user_id field
- [ ] Browser loads dashboard (not login page)

## JWT Authentication Testing

### Step 1: MongoDB Verification
```bash
mongosh
use live_adda_db
db.users.find({role: "admin"}).pretty()
db.users.findOne({role: "admin"}, {password_hash: 1})
```

Verify bcrypt hash starts with `$2b$`

### Step 2: API Testing
```bash
# Login
curl -c cookies.txt -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}'

# Check cookies
cat cookies.txt

# Test /me endpoint
curl -b cookies.txt http://localhost:8001/api/auth/me
```

### Success Indicators
✅ /api/auth/me returns user data
✅ Dashboard loads without redirect
✅ Login/Register works correctly

### Failure Indicators
❌ "User not found" errors
❌ 401 Unauthorized responses
❌ Redirect loop to login page
