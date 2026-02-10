# Database Migrations

## Overview

This directory contains SQL migration files for the Supabase PostgreSQL database.

## Migration Strategy

Alça Finanças uses **Supabase** as the database, which provides multiple ways to manage migrations:

### Method 1: Supabase Dashboard (Recommended for Quick Changes)

1. Go to your project: https://app.supabase.com/project/YOUR_PROJECT/editor/sql
2. Use the SQL Editor to write and run migrations
3. Supabase tracks executed migrations automatically

### Method 2: Supabase CLI (Recommended for Production)

```bash
# Install Supabase CLI
npm install -g supabase

# Login
supabase login

# Link to your project
supabase link --project-ref YOUR_PROJECT_REF

# Create a new migration
supabase migration new add_user_preferences

# Edit the generated file in supabase/migrations/

# Apply migrations
supabase db push

# Pull current schema
supabase db pull
```

### Method 3: SQL Files in this Directory

Place your migration files here with numeric prefixes:

```
scripts/db/
├── 001_initial_schema.sql
├── 002_add_categories.sql
├── 003_add_indexes.sql
└── README.md
```

Run migrations:

```bash
./scripts/prod/migrate.sh
```

## Migration File Format

Each migration should be idempotent (safe to run multiple times):

```sql
-- 001_initial_schema.sql

-- Create users table (if not exists)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can view their own data"
    ON users FOR SELECT
    USING (auth.uid() = id);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
```

## Current Schema

The application expects these tables (managed by Supabase repositories):

### Core Tables
- `users` - User accounts and authentication
- `categories` - Transaction categories (income/expense)
- `accounts` - Bank accounts and wallets
- `transactions` - Financial transactions
- `oauth_states` - OAuth state management

### Support Tables
- `profiles` (optional) - Extended user information
- `user_preferences` (optional) - User settings

## Row Level Security (RLS)

**IMPORTANT:** All tables should have RLS enabled for security.

Example RLS policies:

```sql
-- Users can only see their own transactions
CREATE POLICY "users_transactions_select"
    ON transactions FOR SELECT
    USING (user_id = auth.uid());

-- Users can only insert their own transactions
CREATE POLICY "users_transactions_insert"
    ON transactions FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users can only update their own transactions
CREATE POLICY "users_transactions_update"
    ON transactions FOR UPDATE
    USING (user_id = auth.uid());

-- Users can only delete their own transactions
CREATE POLICY "users_transactions_delete"
    ON transactions FOR DELETE
    USING (user_id = auth.uid());
```

## Best Practices

### ✅ DO:
- Use descriptive migration names with numeric prefixes
- Always use `IF NOT EXISTS` for CREATE statements
- Always use `IF EXISTS` for DROP statements
- Include rollback statements in comments
- Test migrations on a staging environment first
- Add indexes for frequently queried columns
- Enable RLS on all tables
- Document complex migrations

### ❌ DON'T:
- Never drop tables without backup
- Don't modify previous migrations (create new ones)
- Don't store sensitive data without encryption
- Don't bypass RLS policies in production
- Don't run untested migrations on production

## Rolling Back Migrations

If you need to rollback a migration:

1. Create a new migration that reverses the changes
2. Name it appropriately (e.g., `004_rollback_user_preferences.sql`)
3. Apply it using the same process

Example rollback:

```sql
-- 004_rollback_user_preferences.sql

DROP TABLE IF EXISTS user_preferences CASCADE;
```

## Checking Applied Migrations

Using Supabase CLI:

```bash
supabase migration list
```

Using SQL:

```sql
SELECT * FROM supabase_migrations.schema_migrations
ORDER BY version;
```

## Seed Data

For development seed data, see:
- `/scripts/seed/` - Seed scripts for development
- Root `alca_seed_*.sh` scripts - Demo data scripts

## Troubleshooting

### Migration fails with "permission denied"

Make sure you're using the `SUPABASE_SERVICE_ROLE_KEY`, not the anon key.

### Migration fails with "relation already exists"

Use `IF NOT EXISTS` in your CREATE statements or check if the migration was already applied.

### RLS prevents access to data

Check your RLS policies. During development, you can temporarily disable RLS:

```sql
ALTER TABLE your_table DISABLE ROW LEVEL SECURITY;
```

**Remember to re-enable it before production!**

### Can't connect to Supabase

Verify your connection string and credentials:

```bash
# Test connection
curl -H "apikey: YOUR_SERVICE_ROLE_KEY" \
     -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
     https://your-project.supabase.co/rest/v1/
```

## Resources

- [Supabase Database Guide](https://supabase.com/docs/guides/database)
- [Supabase CLI Reference](https://supabase.com/docs/reference/cli)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Row Level Security](https://supabase.com/docs/guides/auth/row-level-security)
