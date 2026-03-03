# Skill: users-profile

**Status:** Active
**Risk Level:** Medium
**Owner:** Platform Team
**Last Updated:** 2026-02-27

---

## Purpose

User profile management including personal information, settings, preferences, profile pictures, and user-specific configuration. Handles everything related to user identity beyond authentication.

## Business Value

- **Personalization:** Users can customize their experience (currency, theme, language)
- **User Identity:** Clear profile information improves trust and engagement
- **Configuration Foundation:** Settings affect all other features
- **Impact if Failed:** Users cannot customize experience or update profile info

## Boundaries

### In Scope
- User profile data (name, email, profile picture)
- User settings (currency, theme, language)
- Profile update operations
- User preferences management
- Data export/import for user data

### Out of Scope
- Authentication flows → `authentication` skill
- Password management → `authentication` skill
- Admin user management → `admin-governance` skill
- Billing/subscription → Future feature

## Core Responsibilities

1. **Store user profile data** (name, profile picture, preferences)
2. **Manage user settings** (currency, theme, language)
3. **Provide profile API** for reading/updating user info
4. **Support data export** for user data portability
5. **Handle profile picture uploads** (future)

## User Journeys

### Journey 1: View Profile
1. User clicks profile icon
2. Frontend sends GET /api/auth/me
3. Backend retrieves user record
4. User sees profile information

### Journey 2: Update Settings
1. User navigates to Settings page
2. User changes currency from BRL to USD
3. Frontend sends PUT /api/auth/settings
4. Backend updates settings in users table
5. Frontend refreshes; all amounts now in USD

### Journey 3: Update Profile Picture
1. User uploads profile image
2. Frontend uploads to storage service
3. Backend updates profile_picture URL
4. User sees new profile picture

### Journey 4: Export User Data
1. User requests data export
2. Backend collects all user data (transactions, accounts, categories)
3. Backend generates JSON export
4. User downloads file

## Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Invalid currency code | Medium: Display errors | Validate against ISO 4217 codes |
| Settings JSONB corrupt | Medium: Settings lost | Schema validation; default fallback |
| Profile picture 404 | Low: Missing avatar | Fallback to default avatar |
| Name too long | Low: Display overflow | Enforce max length (255 chars) |

## Dependencies

### Upstream
- `authentication` — User context, authentication required

### Downstream
- All skills — Read user settings for currency, locale

## Code Map

### Backend
- **Routes:** `backend/routes/auth.py` (settings endpoints)
- **Services:** `backend/services/user_service.py`
- **Repositories:** `backend/repositories/user_repository_supabase.py`

### Frontend
- **Components:** `frontend/src/components/settings/*`, `frontend/src/components/Profile.tsx`
- **Contexts:** `frontend/src/contexts/AuthContext.tsx`

### Database
- **Tables:** `users`
- **Migrations:** `backend/database/schema.sql`

## Security Considerations

- Users can only access/modify own profile
- Email changes require re-authentication (future)
- Profile picture URLs validated (prevent XSS)
- Settings validated before save

## Observability Plan

### Logs
- Profile updated (user_id, fields_changed)
- Settings changed (user_id, old_settings, new_settings)

### Metrics
- `profile.updates.count` — Profile update frequency
- `settings.changes.count` — Settings change frequency
- `settings.currency.distribution` — Currency usage distribution

## Future Evolution

### v1.0 (Current)
- Basic profile management
- Settings (currency, theme, language)

### v2.0 (Planned)
- Profile picture upload
- Email change with verification
- Phone number support
- Timezone settings
- Notification preferences

### v3.0 (Vision)
- Social profile links
- Bio/description
- Privacy settings
- Account deletion flow

---

## Related Documentation

- [API Contracts](./contracts/api.md)
- [Database Contracts](./contracts/db.md)
