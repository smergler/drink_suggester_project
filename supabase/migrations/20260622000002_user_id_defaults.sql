-- Set user_id defaults to auth.uid() so application code doesn't need to
-- pass user_id explicitly; the RLS INSERT check (auth.uid() = user_id) then passes.

ALTER TABLE bottles    ALTER COLUMN user_id SET DEFAULT auth.uid();
ALTER TABLE companions ALTER COLUMN user_id SET DEFAULT auth.uid();
ALTER TABLE sessions   ALTER COLUMN user_id SET DEFAULT auth.uid();
